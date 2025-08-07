from passlib.context import CryptContext
import hashlib
import base64
import string
import re
from typing import Optional
from sqlalchemy.orm import Session

from app.models.activation_code import ActivationCode
from app.schemas.activation_code import ActivationCodeCreate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_activation_code(user_data: ActivationCodeCreate) -> str:
    """
    Generate a deterministic 9-character activation code based on user data.
    The code will be the same for the same input data.
    """
    # Normalize input data
    normalized_data = (
        user_data.first_name.lower() +
        user_data.last_name.lower() +
        user_data.email.lower() +
        user_data.password
    )
    
    # Create a deterministic hash
    hash_object = hashlib.sha256(normalized_data.encode())
    hash_bytes = hash_object.digest()
    
    # Convert to base64 and keep only alphanumeric characters
    base64_str = base64.b64encode(hash_bytes).decode()
    alphanumeric = re.sub(r'[^A-Z0-9]', '', base64_str.upper())
    
    # Return first 9 characters
    return alphanumeric[:9]

def create_activation_code(db: Session, user_data: ActivationCodeCreate) -> Optional[ActivationCode]:
    """
    Create a new activation code entry in the database.
    Returns None if an unused activation code already exists for the email.
    """
    # Check if an unused activation code already exists for this email
    existing_code = db.query(ActivationCode).filter(
        ActivationCode.email == user_data.email,
        ActivationCode.is_used == False
    ).first()
    
    if existing_code:
        return None
    
    # Generate activation code
    activation_code = generate_activation_code(user_data)
    
    # Create new activation code entry
    db_activation_code = ActivationCode(
        activation_code=activation_code,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        email=user_data.email,
        password_hash=pwd_context.hash(user_data.password),
        is_used=False
    )
    
    db.add(db_activation_code)
    db.commit()
    db.refresh(db_activation_code)
    
    return db_activation_code

def get_activation_code(db: Session, code: str) -> Optional[ActivationCode]:
    """
    Retrieve an activation code from the database.
    """
    return db.query(ActivationCode).filter(ActivationCode.activation_code == code).first()

def mark_activation_code_as_used(db: Session, code: str) -> bool:
    """
    Mark an activation code as used.
    Returns True if successful, False if code not found or already used.
    """
    activation_code = get_activation_code(db, code)
    if not activation_code or activation_code.is_used:
        return False
        
    activation_code.is_used = True
    db.commit()
    return True