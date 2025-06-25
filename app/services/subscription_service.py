from sqlalchemy.orm import Session
from typing import Dict, Optional, Tuple
from ..models.user import User
from ..models.subscription import Subscription
from ..models.price_plan import PricePlan
from fastapi import HTTPException
from sqlalchemy import func
import stripe
from decimal import Decimal
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class SubscriptionService:
    PLAN_LIMITS = {
        "individual": {
            "storage_mb": 50,  # 50 MB
            "agents": 1,
            "workflow_automation": False
        },
        "standard": {
            "storage_mb": 1024,  # 1 GB
            "agents": 10,
            "workflow_automation": True
        },
        "smb": {
            "storage_mb": 10240,  # 10 GB
            "agents": float('inf'),  # Unlimited
            "workflow_automation": True
        }
    }

    @staticmethod
    def get_user_limits(db: Session, user: User) -> Dict:
        """Get the limits for a user based on their subscription"""
        if not user.subscription:
            return None

        subscription = db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.status == "active"
        ).first()

        if not subscription:
            return None

        return SubscriptionService.PLAN_LIMITS.get(subscription.plan_type.lower())

    @staticmethod
    def check_storage_limit(db: Session, user: User, additional_size_bytes: int = 0) -> bool:
        """Check if user is within storage limits"""
        limits = SubscriptionService.get_user_limits(db, user)
        if not limits:
            return False

        # Get current storage usage from data sources
        from ..models.data_source import DataSource
        current_usage = db.query(DataSource).filter(
            DataSource.user_id == user.id
        ).with_entities(
            func.sum(DataSource.raw_size_bytes + DataSource.processed_size_bytes)
        ).scalar() or 0

        # Convert limit to bytes
        limit_bytes = limits["storage_mb"] * 1024 * 1024

        # Check if adding new data would exceed limit
        if current_usage + additional_size_bytes > limit_bytes:
            raise HTTPException(
                status_code=403,
                detail=f"Storage limit exceeded. Your plan allows {limits['storage_mb']}MB of storage."
            )
        return True

    @staticmethod
    def check_agent_limit(db: Session, user: User, current_count: Optional[int] = None) -> bool:
        """Check if user is within agent limits"""
        limits = SubscriptionService.get_user_limits(db, user)
        if not limits:
            return False

        if current_count is None:
            from ..models.agent import Agent
            current_count = db.query(Agent).filter(Agent.user_id == user.id).count()

        if current_count >= limits["agents"]:
            raise HTTPException(
                status_code=403,
                detail=f"Agent limit reached. Your plan allows {limits['agents']} AI agents."
            )
        return True

    @staticmethod
    def can_use_workflow_automation(db: Session, user: User) -> bool:
        """Check if user can use workflow automation"""
        limits = SubscriptionService.get_user_limits(db, user)
        if not limits:
            return False
        return limits["workflow_automation"]

    @staticmethod
    async def create_stripe_customer(user: User) -> str:
        """Create a Stripe customer for a user."""
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip(),
                metadata={
                    "user_id": str(user.id)
                }
            )
            return customer.id
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def create_stripe_price(
        amount: int,
        interval: str,
        product_name: str,
        metadata: Dict = None
    ) -> Tuple[str, str]:
        """
        Create a Stripe product and price.
        Returns a tuple of (product_id, price_id)
        """
        try:
            # Create product
            product = stripe.Product.create(
                name=product_name,
                metadata=metadata or {}
            )

            # Create price
            price = stripe.Price.create(
                product=product.id,
                unit_amount=amount,  # amount in cents
                currency="usd",
                recurring={"interval": interval},  # "month" or "year"
                metadata=metadata or {}
            )

            return product.id, price.id
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def create_or_update_admin_subscription(
        db: Session,
        user: User,
        monthly_amount: Optional[int] = None,
        annual_amount: Optional[int] = None,
        plan_name: str = None
    ) -> Subscription:
        """Create or update a subscription for a user added by admin."""
        
        # Create Stripe customer if not exists
        if not user.stripe_customer_id:
            customer_id = await SubscriptionService.create_stripe_customer(user)
            user.stripe_customer_id = customer_id
            db.flush()

        # Create or get custom price plan
        custom_plan = db.query(PricePlan).filter(
            PricePlan.is_custom == True,
            PricePlan.id == user.subscription.price_plan_id if user.subscription else None
        ).first()

        if not custom_plan:
            custom_plan = PricePlan(
                name=plan_name or f"Custom Plan - {user.email}",
                monthly_price=Decimal(monthly_amount or 0) / 100,  # Convert cents to dollars
                annual_price=Decimal(annual_amount or 0) / 100,  # Convert cents to dollars
                included_seats=user.max_users,
                storage_limit_bytes=user.storage_limit_bytes,
                features={
                    "custom": True,
                    "storage_limit_bytes": user.storage_limit_bytes,
                    "max_users": user.max_users,
                    "workflow_automation": True
                },
                is_custom=True
            )
            db.add(custom_plan)
            db.flush()

        # Create Stripe products and prices if needed
        metadata = {"user_id": str(user.id), "plan_id": str(custom_plan.id)}
        
        if monthly_amount and not custom_plan.stripe_price_id_monthly:
            product_id, price_id = await SubscriptionService.create_stripe_price(
                amount=monthly_amount,
                interval="month",
                product_name=f"{plan_name or 'Custom Plan'} (Monthly)",
                metadata=metadata
            )
            custom_plan.stripe_product_id = product_id
            custom_plan.stripe_price_id_monthly = price_id

        if annual_amount and not custom_plan.stripe_price_id_annual:
            product_id, price_id = await SubscriptionService.create_stripe_price(
                amount=annual_amount,
                interval="year",
                product_name=f"{plan_name or 'Custom Plan'} (Annual)",
                metadata=metadata
            )
            custom_plan.stripe_product_id = product_id
            custom_plan.stripe_price_id_annual = price_id

        # Create or update subscription
        if not user.subscription:
            subscription = Subscription(
                user_id=user.id,
                price_plan_id=custom_plan.id,
                plan_type="custom",
                billing_interval="monthly" if monthly_amount else "annual",
                seats=user.max_users,
                status="active"
            )
            db.add(subscription)
        else:
            user.subscription.price_plan_id = custom_plan.id
            user.subscription.plan_type = "custom"
            user.subscription.billing_interval = "monthly" if monthly_amount else "annual"
            user.subscription.seats = user.max_users
            subscription = user.subscription

        db.commit()
        return subscription

async def create_or_update_custom_subscription(
    db: Session,
    user: User,
    monthly_price: Decimal = None,
    annual_price: Decimal = None
) -> Subscription:
    """Create or update a custom subscription plan for a user."""
    
    # Check if user already has a custom price plan
    custom_plan = db.query(PricePlan).filter(
        PricePlan.is_custom == True,
        PricePlan.id == user.subscription.price_plan_id if user.subscription else None
    ).first()
    
    if not custom_plan:
        # Create new custom price plan
        custom_plan = PricePlan(
            name=f"Custom Plan - {user.email}",
            monthly_price=monthly_price or Decimal('0'),
            annual_price=annual_price or Decimal('0'),
            included_seats=user.max_users,
            storage_limit_bytes=user.storage_limit_bytes,
            features={"custom": True},
            is_custom=True
        )
        db.add(custom_plan)
        db.flush()  # Get the ID
        
        # Create Stripe products and prices
        if monthly_price:
            product = stripe.Product.create(
                name=f"Custom Plan - {user.email} (Monthly)",
                description="Custom subscription plan"
            )
            monthly_stripe_price = stripe.Price.create(
                product=product.id,
                unit_amount=int(monthly_price * 100),  # Convert to cents
                currency="usd",
                recurring={"interval": "month"}
            )
            custom_plan.stripe_price_id_monthly = monthly_stripe_price.id
        
        if annual_price:
            product = stripe.Product.create(
                name=f"Custom Plan - {user.email} (Annual)",
                description="Custom subscription plan"
            )
            annual_stripe_price = stripe.Price.create(
                product=product.id,
                unit_amount=int(annual_price * 100),  # Convert to cents
                currency="usd",
                recurring={"interval": "year"}
            )
            custom_plan.stripe_price_id_annual = annual_stripe_price.id
    else:
        # Update existing custom plan
        if monthly_price is not None:
            custom_plan.monthly_price = monthly_price
            if custom_plan.stripe_price_id_monthly:
                # Create new price and update product
                product = stripe.Product.create(
                    name=f"Custom Plan - {user.email} (Monthly)",
                    description="Custom subscription plan"
                )
                monthly_stripe_price = stripe.Price.create(
                    product=product.id,
                    unit_amount=int(monthly_price * 100),
                    currency="usd",
                    recurring={"interval": "month"}
                )
                custom_plan.stripe_price_id_monthly = monthly_stripe_price.id
        
        if annual_price is not None:
            custom_plan.annual_price = annual_price
            if custom_plan.stripe_price_id_annual:
                # Create new price and update product
                product = stripe.Product.create(
                    name=f"Custom Plan - {user.email} (Annual)",
                    description="Custom subscription plan"
                )
                annual_stripe_price = stripe.Price.create(
                    product=product.id,
                    unit_amount=int(annual_price * 100),
                    currency="usd",
                    recurring={"interval": "year"}
                )
                custom_plan.stripe_price_id_annual = annual_stripe_price.id
    
    # Create or update subscription
    if not user.subscription:
        subscription = Subscription(
            user_id=user.id,
            price_plan_id=custom_plan.id,
            plan_type="custom",
            billing_interval="monthly" if monthly_price else "annual",
            seats=user.max_users,
            status="active"
        )
        db.add(subscription)
    else:
        user.subscription.price_plan_id = custom_plan.id
        user.subscription.plan_type = "custom"
        user.subscription.billing_interval = "monthly" if monthly_price else "annual"
        user.subscription.seats = user.max_users
        subscription = user.subscription
    
    db.commit()
    return subscription

async def cancel_subscription(stripe_subscription_id: str) -> None:
    """Cancel a Stripe subscription."""
    if stripe_subscription_id:
        try:
            stripe.Subscription.delete(stripe_subscription_id)
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

async def get_subscription_url(price_id: str, user_email: str) -> str:
    """Get Stripe Checkout URL for subscription."""
    try:
        checkout_session = stripe.checkout.Session.create(
            success_url="https://your-domain.com/success",
            cancel_url="https://your-domain.com/cancel",
            mode="subscription",
            customer_email=user_email,
            line_items=[{
                "price": price_id,
                "quantity": 1
            }]
        )
        return checkout_session.url
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e)) 
