import openai
import anthropic
import requests
import secrets
import string
from fastapi import HTTPException
from ..models.api_key import APIKey
from ..schemas.api_key import Provider

def generate_finiite_api_key() -> str:
    # Define character set for API key generation
    chars = string.ascii_letters + string.digits
    # Generate a random string of 32 characters (excluding the prefix)
    random_part = ''.join(secrets.choice(chars) for _ in range(32))
    # Return the API key with 'fk_' prefix
    return f"fk_{random_part}"

async def validate_finiite_api_key(api_key: str) -> bool:
    # Validate Finiite API key format
    if not api_key.startswith('fk_') or len(api_key) != 35:  # 'fk_' + 32 chars
        return False
    return True

async def validate_openai_key(api_key: str) -> bool:    
    try:
        client = openai.OpenAI(api_key=api_key)
        client.models.list()
        return True
    except:
        return False

async def validate_google_key(api_key: str) -> bool:
    try:
        # Google validation logic
        # This is a placeholder - implement according to Google's API
        return True
    except:
        return False

async def validate_deepseek_key(api_key: str) -> bool:
    try:
        # DeepSeek validation logic
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get("https://api.deepseek.com/v1/models", headers=headers)
        return response.status_code == 200
    except:
        return False

async def validate_anthropic_key(api_key: str) -> bool:
    try:
        client = anthropic.Anthropic(api_key=api_key)
        # Use a simpler validation method
        models = client.models.list()
        return True
    except Exception as e:
        print(f"Anthropic validation error: {str(e)}")  # For debugging
        return False

async def validate_huggingface_key(api_key: str) -> bool:
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get("https://huggingface.co/api/models", headers=headers)
        return response.status_code == 200
    except:
        return False

async def validate_perplexity_key(api_key: str) -> bool:
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get("https://api.perplexity.ai/models", headers=headers)
        return response.status_code == 200
    except:
        return False

async def validate_api_key(provider: Provider, api_key: str) -> bool:
    validation_functions = {
        Provider.OPENAI: validate_openai_key,
        Provider.GEMINI: validate_google_key,
        Provider.DEEPSEEK: validate_deepseek_key,
        Provider.ANTHROPIC: validate_anthropic_key,
        Provider.HUGGINGFACE: validate_huggingface_key,
        Provider.PERPLEXITY: validate_perplexity_key,
        Provider.FINIITE: validate_finiite_api_key,
    }
    
    validator = validation_functions.get(provider)
    if not validator:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    
    return await validator(api_key) 
