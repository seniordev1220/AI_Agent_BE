from sqlalchemy.orm import Session
from typing import Optional, Dict
import hashlib
from ..models.activation_code import ActivationCode
from ..schemas.activation_code import ActivationCodeCreate
from ..utils.password import get_password_hash, verify_password

class ActivationCodeService:
    @staticmethod
    def generate_deterministic_code(
        first_name: str,
        last_name: str,
        email: str,
        password: str
    ) -> str:
        """
        Generate a deterministic 9-character activation code based on user information.
        Uses the same algorithm as the frontend to ensure consistency.
        """
        # Create input string with same format as frontend
        input_string = f"{first_name.lower()}|{last_name.lower()}|{email.lower()}|{password}"
        
        # Create SHA-256 hash
        hash_object = hashlib.sha256(input_string.encode())
        hash_hex = hash_object.hexdigest()
        
        # Define character set (same as frontend)
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        code = ""
        
        # Generate 9-character code using same method as frontend
        for i in range(9):
            # Take 2 characters from hash at a time and convert to integer
            byte = int(hash_hex[i * 2:(i * 2) + 2], 16)
            # Use modulo to get index within valid character range
            code += chars[byte % len(chars)]
        
        return code

    @staticmethod
    def create_activation_code(
        db: Session,
        activation_code_data: ActivationCodeCreate
    ) -> Dict:
        """
        Create or retrieve an activation code, with additional validation logic.
        Returns a dictionary with success status, message, and code (if successful).
        """
        try:
            # Generate the deterministic activation code
            activation_code = ActivationCodeService.generate_deterministic_code(
                activation_code_data.first_name,
                activation_code_data.last_name,
                activation_code_data.email,
                activation_code_data.password
            )

            # Check if this exact combination already exists
            existing_entry = db.query(ActivationCode).filter(
                ActivationCode.email.ilike(activation_code_data.email),
                ActivationCode.first_name.ilike(activation_code_data.first_name),
                ActivationCode.last_name.ilike(activation_code_data.last_name)
            ).first()

            if existing_entry and verify_password(activation_code_data.password, existing_entry.hashed_password):
                return {
                    "success": True,
                    "message": "Activation code retrieved successfully",
                    "activation_code": existing_entry,
                    "is_existing": True
                }

            # Check if the activation code already exists (regardless of credentials)
            code_exists = db.query(ActivationCode).filter(
                ActivationCode.activation_code == activation_code
            ).first()

            if code_exists:
                # If it exists with different credentials, return error
                if (code_exists.email.lower() != activation_code_data.email.lower() or
                    code_exists.first_name.lower() != activation_code_data.first_name.lower() or
                    code_exists.last_name.lower() != activation_code_data.last_name.lower()):
                    return {
                        "success": False,
                        "message": "Unable to generate activation code. Please try with different credentials.",
                        "activation_code": None,
                        "is_existing": False
                    }
                # If it exists with same credentials but different password, return error
                elif not verify_password(activation_code_data.password, code_exists.hashed_password):
                    return {
                        "success": False,
                        "message": "An activation code already exists for these credentials but with a different password.",
                        "activation_code": None,
                        "is_existing": False
                    }
                # If it exists with exact same credentials and password, return the existing code
                else:
                    return {
                        "success": True,
                        "message": "Activation code retrieved successfully",
                        "activation_code": code_exists,
                        "is_existing": True
                    }

            # Create new activation code entry
            db_activation_code = ActivationCode(
                first_name=activation_code_data.first_name,
                last_name=activation_code_data.last_name,
                email=activation_code_data.email,
                hashed_password=get_password_hash(activation_code_data.password),
                activation_code=activation_code,
                is_used=False
            )

            db.add(db_activation_code)
            db.commit()
            db.refresh(db_activation_code)

            return {
                "success": True,
                "message": "Activation code generated successfully",
                "activation_code": db_activation_code,
                "is_existing": False
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to generate activation code: {str(e)}",
                "activation_code": None,
                "is_existing": False
            }

    @staticmethod
    def get_activation_code(db: Session, code: str) -> Optional[ActivationCode]:
        """
        Get activation code entry by code.
        """
        return db.query(ActivationCode).filter(ActivationCode.activation_code == code).first()

    @staticmethod
    def mark_code_as_used(db: Session, code: str) -> Optional[ActivationCode]:
        """
        Mark an activation code as used.
        """
        activation_code = ActivationCodeService.get_activation_code(db, code)
        if activation_code and not activation_code.is_used:
            activation_code.is_used = True
            db.commit()
            db.refresh(activation_code)
            return activation_code
        return None