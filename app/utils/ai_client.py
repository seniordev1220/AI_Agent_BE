from typing import Dict
import openai
import anthropic
from google.generativeai import GenerativeModel
import os
from openai import OpenAI

async def get_ai_response(conversation: Dict) -> str:
    """
    Get response from AI model based on provider
    """
    provider = conversation["provider"]
    api_key = conversation["api_key"]
    messages = conversation["messages"]
    model = conversation["model"]
    
    if provider == "openai":
        client = OpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=model,
            messages=messages
        )
        return response.choices[0].message.content

    elif provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        response = await client.messages.create(
            model=model,
            messages=messages
        )
        return response.content[0].text

    elif provider == "google":
        model = GenerativeModel(model)
        response = model.generate_content(messages[-1]["content"])
        return response.text

    elif provider == "deepseek":
        # DeepSeek uses OpenAI-compatible API
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"  # DeepSeek's API endpoint
        )
        response = await client.chat.completions.create(
            model=model,  # e.g., "deepseek-chat", "deepseek-coder"
            messages=messages
        )
        return response.choices[0].message.content

    else:
        raise ValueError(f"Unsupported provider: {provider}") 