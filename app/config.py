import os, dotenv
from typing import Dict, Any

def create_config() -> Dict[str, Any]:
    config = {
        **os.environ,
        **dotenv.dotenv_values("../.env"),
        **dotenv.dotenv_values("../.env.local"),
        **dotenv.dotenv_values("../.env.development.local"),
        **dotenv.dotenv_values(".env"),
        **dotenv.dotenv_values(".env.local"),
        **dotenv.dotenv_values(".env.development.local"),
    }
    
    # Add Stripe price IDs configuration
    config["PRICE_IDS"] = {
        "individual": {
            "monthly": {
                "base": "price_1RYQV6IqfRSqLdqDCfQgwH6M",  # Base plan price
                "seat": "price_1RYbafIqfRSqLdqDJJt1Mtvz"   # $7 per additional seat
            },
            "annual": {
                "base": "price_1RYUbeIqfRSqLdqDHRsoKANR",  # Base plan price
                "seat": "price_1RYbbDIqfRSqLdqDsCr9GYkK"   # Annual seat price
            }
        },
        "standard": {
            "monthly": {
                "base": "price_1RYQiZIqfRSqLdqDetDS4LyJ",
                "seat": "price_1RYbbgIqfRSqLdqDpqIUHXdY"
            },
            "annual": {
                "base": "price_1RYUcJIqfRSqLdqDuSTUw4be",
                "seat": "price_1RYbc8IqfRSqLdqDmTYuLuDG"
            }
        },
        "smb": {
            "monthly": {
                "base": "price_1RYQjGIqfRSqLdqDD7xwlV0w",
                "seat": "price_1RYbcUIqfRSqLdqDvWcUSvv2"
            },
            "annual": {
                "base": "price_1RYUceIqfRSqLdqD9jNpbllm",
                "seat": "price_1RYbcvIqfRSqLdqDmV5KWCev"
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
    
    return config

config = create_config()
