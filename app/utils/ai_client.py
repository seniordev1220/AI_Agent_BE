from typing import Dict
import openai
import anthropic
from google.generativeai import GenerativeModel
import os
from openai import OpenAI
from huggingface_hub import InferenceClient
from transformers import GPT2LMHeadModel, GPT2Tokenizer
import torch


def convert_model_name(model_display_name: str) -> str:
    """
    Convert display model names to their correct API identifiers
    """
    model_mapping = {
        "GPT 3.5 Turbo": "gpt-3.5-turbo",
        "GPT-4": "gpt-4",
        "GPT-4o Mini": "gpt-4o-mini",
        "Claude-3.5": "claude-3-5-sonnet-20240620",
        "Claude-3.7": "claude-3-7-sonnet-20240620",
        "Gemini": "gemini-1.5-pro",
        "Mistral": "mistral-large-latest",
        "Hugging Face": "meta-llama/Llama-2-7b-chat-hf",
        "DeepSeek": "deepseek-chat",
        "Perplexity": "perplexity-2-mini",
        "Meta: llama. 3.2 1B": "meta-llama/Meta-Llama-3.2-1B-Instruct",
    }
    return model_mapping.get(model_display_name, model_display_name)

async def get_ai_response(conversation: Dict) -> str:
    """
    Get response from AI model based on provider
    """
    provider = conversation["provider"]
    api_key = conversation["api_key"]
    messages = conversation["messages"]
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    
    model = convert_model_name(conversation["model"])
    
    if provider == "openai":
        client = OpenAI(api_key=api_key)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API Error: {str(e)}")
            raise

    elif provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        response = await client.messages.create(
            model=model,
            messages=messages
        )
        return response.content[0].text

    elif provider == "gemini":
    
        model = GenerativeModel(model)
        response = model.generate_content(messages[-1]["content"])
        return response.text

    elif provider == "deepseek":
        # DeepSeek uses OpenAI-compatible API
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"  # DeepSeek's API endpoint
        )
        response = client.chat.completions.create(
            model=model,  # e.g., "deepseek-chat", "deepseek-coder"
            messages=messages
        )
        return response.choices[0].message.content

    elif provider == "huggingface":
        try:
            model_name = "gpt2"  # You can choose a different model on hugging face or fine-tune a model
            tokenizer = GPT2Tokenizer.from_pretrained(model_name)
            model = GPT2LMHeadModel.from_pretrained(model_name)
            inputs = tokenizer.encode(messages[-1]["content"], return_tensors="pt")
            outputs = model.generate(inputs, max_length=100, num_return_sequences=1)
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            return response
        except Exception as e:
            error_msg = str(e) if str(e) else "Unknown error occurred"
            print(f"Hugging Face API Error: {error_msg}")
            raise Exception(f"Hugging Face API Error: {error_msg}")

    else:
        raise ValueError(f"Unsupported provider: {provider}") 