from typing import Dict, List
import openai
import anthropic
from google.generativeai import GenerativeModel
import os
from openai import OpenAI
from huggingface_hub import InferenceClient
from transformers import GPT2LMHeadModel, GPT2Tokenizer
import torch
import base64
import google.generativeai as genai

# Define supported models
ANTHROPIC_MODELS = [
    "claude-3-5-sonnet-20240620"
]

GOOGLE_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

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
        "Gemini": "gemini-2.5-flash",
        "Mistral": "mistral-large-latest",
        "Hugging Face": "meta-llama/Llama-2-7b-chat-hf",
        "DeepSeek": "deepseek-chat",
        "Perplexity": "perplexity-2-mini",
        "Meta: llama. 3.2 1B": "meta-llama/Meta-Llama-3.2-1B-Instruct",
    }
    return model_mapping.get(model_display_name, model_display_name)

def base64_to_image(base64_string: str):
    """Convert base64 string to image for Gemini"""
    if "base64," in base64_string:
        base64_string = base64_string.split("base64,")[1]
    image_data = base64.b64decode(base64_string)
    return genai.types.Image(image_data)

def messages_to_gemini(messages: List[Dict]) -> List[Dict]:
    """Convert messages to Gemini format"""
    gemini_messages = []
    prev_role = None
    
    for message in messages:
        if prev_role and (prev_role == message["role"]):
            gemini_message = gemini_messages[-1]
        else:
            gemini_message = {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [],
            }

        for content in message["content"]:
            if isinstance(content, str):
                gemini_message["parts"].append(content)
            elif isinstance(content, dict):
                if content["type"] == "text":
                    gemini_message["parts"].append(content["text"])
                elif content["type"] == "image_url":
                    gemini_message["parts"].append(
                        base64_to_image(content["image_url"]["url"])
                    )
                elif content["type"] in ["video_file", "audio_file"]:
                    gemini_message["parts"].append(
                        genai.upload_file(content[content["type"]])
                    )

        if prev_role != message["role"]:
            gemini_messages.append(gemini_message)

        prev_role = message["role"]
        
    return gemini_messages

def messages_to_anthropic(messages: List[Dict]) -> List[Dict]:
    """Convert messages to Anthropic format"""
    anthropic_messages = []
    prev_role = None
    
    for message in messages:
        if prev_role and (prev_role == message["role"]):
            anthropic_message = anthropic_messages[-1]
        else:
            anthropic_message = {
                "role": message["role"],
                "content": [],
            }

        for content in message["content"]:
            if isinstance(content, str):
                anthropic_message["content"].append({"type": "text", "text": content})
            elif isinstance(content, dict):
                if content["type"] == "image_url":
                    # Extract media type and base64 data from the URL
                    media_type = content["image_url"]["url"].split(";")[0].split(":")[1]
                    base64_data = content["image_url"]["url"].split(",")[1]
                    
                    anthropic_message["content"].append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data
                        }
                    })
                else:
                    anthropic_message["content"].append(content)

        if prev_role != message["role"]:
            anthropic_messages.append(anthropic_message)

        prev_role = message["role"]
        
    return anthropic_messages

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
        if model not in ANTHROPIC_MODELS:
            raise ValueError(f"Unsupported Anthropic model: {model}")
            
        client = anthropic.Anthropic(api_key=api_key)
        anthropic_messages = messages_to_anthropic(messages)
        
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=anthropic_messages,
            temperature=0.7
        )
        return response.content[0].text

    elif provider == "gemini":
        if model not in GOOGLE_MODELS:
            raise ValueError(f"Unsupported Gemini model: {model}")
            
        genai.configure(api_key=api_key)
        model_instance = genai.GenerativeModel(convert_model_name(model))
        gemini_messages = messages_to_gemini(messages)
        
        chat = model_instance.start_chat(history=gemini_messages[:-1])
        response = chat.send_message(gemini_messages[-1]["parts"])
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