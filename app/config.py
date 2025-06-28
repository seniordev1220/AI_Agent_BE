import os, dotenv
from typing import Dict, Any
from pathlib import Path

# Get the project root directory (parent of app directory)
PROJECT_ROOT = Path(__file__).parent.parent

def create_config() -> Dict[str, Any]:
    config = {
        **os.environ,
        **dotenv.dotenv_values(PROJECT_ROOT / ".env"),
        **dotenv.dotenv_values(PROJECT_ROOT / ".env.local"),
        **dotenv.dotenv_values(PROJECT_ROOT / ".env.development.local"),
        **dotenv.dotenv_values(".env"),
        **dotenv.dotenv_values(".env.local"),
        **dotenv.dotenv_values(".env.development.local"),
    }
    
    # Add Stripe price IDs configuration
    config["PRICE_IDS"] = {
        "individual": {
            "monthly": {
                "base": "price_1ReJCrIqfRSqLdqDo5NuVCT4",  # Base plan price
                "seat": "price_1ReJDUIqfRSqLdqDYM3qJLq7"   # $7 per additional seat
            },
            "annual": {
                "base": "price_1ReJDKIqfRSqLdqDt755nFEY",  # Base plan price
                "seat": "price_1ReJDjIqfRSqLdqDfULeVSzQ"   # Annual seat price
            }
        },
        "standard": {
            "monthly": {
                "base": "price_1ReJFxIqfRSqLdqDhkn7ffZc",
                "seat": "price_1ReJGVIqfRSqLdqDHWzNHtHx"
            },
            "annual": {
                "base": "price_1ReJGOIqfRSqLdqDvp7rF63J",
                "seat": "price_1ReJGeIqfRSqLdqDfxhd6GlX"
            }
        },
        "smb": {
            "monthly": {
                "base": "price_1ReJI3IqfRSqLdqD6ue6NWe8",
                "seat": "price_1ReJIVIqfRSqLdqDYfj18wR3"
            },
            "annual": {
                "base": "price_1ReJINIqfRSqLdqDcuvwt4q2",
                "seat": "price_1ReJIdIqfRSqLdqDl85d6BWZ"
            }
        }
    }

    # Add file upload configuration
    config["FILE_UPLOAD"] = {
        "MAX_SIZE_BYTES": 10 * 1024 * 1024,  # 10MB in bytes
        "ALLOWED_TYPES": ["application/pdf", "text/plain", "text/csv", "application/json", 
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]
    }

    # Add Google Drive configuration
    service_account_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "service-account.json")
    if not os.path.isabs(service_account_path):
        # If it's a relative path, make it relative to the project root
        service_account_path = str(PROJECT_ROOT / service_account_path)
    
    # Ensure the service account file exists
    if not os.path.exists(service_account_path):
        # Try looking in the current directory
        current_dir_path = os.path.join(os.getcwd(), "service-account.json")
        if os.path.exists(current_dir_path):
            service_account_path = current_dir_path
        else:
            print(f"Warning: Service account file not found at {service_account_path} or {current_dir_path}")

    config["GOOGLE_DRIVE"] = {
        "SERVICE_ACCOUNT_PATH": service_account_path
    }

    # Set Google Application Credentials environment variable
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path
    
    return config

config = create_config()
