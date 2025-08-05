from sqlalchemy.orm import Session
from ..models.user import User
from ..models.price_plan import PricePlan
from .password import get_password_hash
from decimal import Decimal
from ..config import config
from .api_key_validator import generate_finiite_api_key
from ..services.subscription_service import SubscriptionService

def create_default_admin(db: Session) -> None:
    """
    Create default admin user if it doesn't exist
    """
    admin_email = "contact@finiite.com"
    
    # Check if admin already exists
    admin = db.query(User).filter(User.email == admin_email).first()
    if admin:
        return
    
    # Create admin user
    admin_user = User(
        email=admin_email,
        first_name="Fatima",
        last_name="Awan",
        hashed_password=get_password_hash("admin$1M"),
        role="admin",
        is_active=True,
        finiite_api_key=generate_finiite_api_key()
    )
    
    db.add(admin_user)
    db.commit()

def create_test_user(db: Session) -> None:
    """
    Create test user if it doesn't exist
    """
    test_email = "test@finiite.com"
    
    # Check if test user already exists
    test_user = db.query(User).filter(User.email == test_email).first()
    if test_user:
        return
    
    # Create test user with standard plan limits
    test_user = User(
        email=test_email,
        first_name="Test",
        last_name="User",
        hashed_password=get_password_hash("123456"),
        role="user",
        is_active=True,
        is_test_account=True,  # Set test account flag
        finiite_api_key=generate_finiite_api_key(),
        trial_status="active",  # Set as active to bypass trial
        max_users=2,  # Standard plan default seats
        storage_limit_bytes=1024 * 1024 * 1024  # 1 GB (Standard plan storage limit)
    )
    
    db.add(test_user)
    db.flush()  # Flush to get the user ID
    
    # Create Stripe customer
    try:
        # Skip Stripe customer creation for test user
        customer_id = None
        test_user.stripe_customer_id = customer_id
        
        # Create subscription for standard plan
        standard_plan = db.query(PricePlan).filter(PricePlan.name == "standard").first()
        if standard_plan:
            from ..models.subscription import Subscription
            subscription = Subscription(
                user_id=test_user.id,
                price_plan_id=standard_plan.id,
                plan_type="standard",
                billing_interval="monthly",
                seats=2,
                status="active"
            )
            db.add(subscription)
    except Exception as e:
        print(f"Warning: Could not create Stripe customer for test user: {str(e)}")
    
    db.commit()

def create_default_price_plans(db: Session) -> None:
    """
    Create default price plans if they don't exist
    """
    # Check if any price plans exist
    if db.query(PricePlan).first():
        return
    
    # Define default plans
    plans = [
        PricePlan(
            name="individual",
            monthly_price=Decimal("39"),
            annual_price=Decimal("348"),  # $29 * 12 months
            included_seats=1,
            additional_seat_price=Decimal("7"),
            features=[
                {"description": "Connect to AI models including OpenAI, Google Gemini, Anthropic", "included": True},
                {"description": "1 AI Agent", "included": True},
                {"description": "Connect your knowledge base with 50 MB of files", "included": True},
                {"description": "Dashboard analytics", "included": True}
            ],
            is_best_value=False,
            is_active=True,
            stripe_price_id_monthly=config["PRICE_IDS"]["individual"]["monthly"]["base"],
            stripe_price_id_annual=config["PRICE_IDS"]["individual"]["annual"]["base"]
        ),
        PricePlan(
            name="standard",
            monthly_price=Decimal("99"),
            annual_price=Decimal("888"),  # $74 * 12 months
            included_seats=2,
            additional_seat_price=Decimal("7"),
            features=[
                {"description": "Connect to AI models including OpenAI, Google Gemini, Anthropic", "included": True},
                {"description": "Create 10 AI agents and assistants", "included": True},
                {"description": "Connect your knowledge base with 1 GB of files", "included": True},
                {"description": "Dashboard analytics", "included": True},
                {"description": "Workflow automations included", "included": True}
            ],
            is_best_value=True,
            is_active=True,
            stripe_price_id_monthly=config["PRICE_IDS"]["standard"]["monthly"]["base"],
            stripe_price_id_annual=config["PRICE_IDS"]["standard"]["annual"]["base"]
        ),
        PricePlan(
            name="SMB",
            monthly_price=Decimal("157"),
            annual_price=Decimal("1416"),  # $118 * 12 months
            included_seats=3,
            additional_seat_price=Decimal("5"),
            features=[
                {"description": "Connect to AI models including OpenAI, Google Gemini, Anthropic, OpenSource", "included": True},
                {"description": "Create unlimited AI agents and assistants", "included": True},
                {"description": "Connect your knowledge base with 10 GB of files", "included": True},
                {"description": "Dashboard analytics", "included": True},
                {"description": "Workflow automations included", "included": True},
                {"description": "Deploy& integrate agents into your workflows or websites", "included": True}
            ],
            is_best_value=False,
            is_active=True,
            stripe_price_id_monthly=config["PRICE_IDS"]["smb"]["monthly"]["base"],
            stripe_price_id_annual=config["PRICE_IDS"]["smb"]["annual"]["base"]
        )
    ]
    
    # Add plans to database
    for plan in plans:
        db.add(plan)
    db.commit() 
