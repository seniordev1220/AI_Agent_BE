import openai
from google.cloud import aiplatform
import anthropic
import requests
from fastapi import HTTPException
from ..models.api_key import APIKey
from ..schemas.api_key import Provider

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
        client.messages.create(
            model="claude-3-haiku",
            max_tokens=1,
            messages=[{"role": "user", "content": "Hi"}]
        )
        return True
    except:
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
        Provider.GOOGLE: validate_google_key,
        Provider.DEEPSEEK: validate_deepseek_key,
        Provider.ANTHROPIC: validate_anthropic_key,
        Provider.HUGGINGFACE: validate_huggingface_key,
        Provider.PERPLEXITY: validate_perplexity_key,
    }
    
    validator = validation_functions.get(provider)
    if not validator:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    
    return await validator(api_key) 