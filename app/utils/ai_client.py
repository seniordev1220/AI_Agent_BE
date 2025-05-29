from typing import Dict, List, Any
import openai
import anthropic
from google.generativeai import GenerativeModel
import os
from openai import OpenAI
from huggingface_hub import InferenceClient
from transformers import GPT2LMHeadModel, GPT2Tokenizer
import base64
import google.generativeai as genai
from PyPDF2 import PdfReader
from io import BytesIO
import tempfile
import time
from tenacity import retry, stop_after_attempt, wait_exponential

# Define supported models
ANTHROPIC_MODELS = [
    "claude-3-5-sonnet-20240620"
]

GOOGLE_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

OPENAI_MODELS = [
    "gpt-4-turbo",
    "gpt-4o",
]

def convert_model_name(model_display_name: str) -> str:
    """
    Convert display model names to their correct API identifiers
    """
    model_mapping = {
        "GPT 3.5 Turbo": "gpt-3.5-turbo",
        "GPT-4": "gpt-4",
        "GPT-4o": "gpt-4o",
        "GPT-4o Mini": "gpt-4o-mini",
        "Claude-3.5": "claude-3-5-sonnet-20240620",
        "Claude-3.7": "claude-3-7-sonnet-20240620",
        "Gemini": "gemini-1.5-flash",
        "Mistral": "mistral-large-latest",
        "Hugging Face": "meta-llama/Llama-2-7b-chat-hf",
        "DeepSeek": "deepseek-chat",
        "Perplexity": "perplexity-2-mini",
        "Meta: llama. 3.2 1B": "meta-llama/Meta-Llama-3.2-1B-Instruct",
    }
    return model_mapping.get(model_display_name, model_display_name)

def extract_text_from_pdf(pdf_path: str) -> str:
    with open(pdf_path, "rb") as file:
        reader = PdfReader(file)
        text = "\n".join([page.extract_text() for page in reader.pages])
    return text

def process_attachment(attachment: Dict) -> Dict:
    """Convert attachments to AI-consumable format"""
    if attachment["type"] in ["pdf", "docx", "txt", "csv"]:
        if attachment["type"] == "pdf":
            text = extract_text_from_pdf(attachment["url"])
        else:
            with open(attachment["url"], "r") as f:
                text = f.read()
        return {"type": "text", "text": f"File: {attachment['name']}\n{text}"}
    
    elif attachment["type"] in ["png", "jpg", "jpeg"]:
        with open(attachment["url"], "rb") as f:
            image_data = f.read()
            base64_image = base64.b64encode(image_data).decode("utf-8")
            mime_type = "jpeg" if attachment["type"] == "jpg" else attachment["type"]
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/{mime_type};base64,{base64_image}"
                }
            }
    else:
        return {"type": "text", "text": f"Unsupported file: {attachment['name']}"}

def messages_to_openai(messages: List[Dict], attachments: List[Dict]) -> List[Dict]:
    """Format messages for OpenAI (including vision)"""
    formatted_messages = []
    
    for msg in messages:
        if msg["role"] == "user" and attachments:
            # For user messages with attachments, format as multimodal content
            content = []
            content.append({"type": "text", "text": msg["content"]})
            
            for attachment in attachments:
                content.append(attachment)  # Add attachment as is
            
            formatted_messages.append({
                "role": msg["role"],
                "content": content
            })
        else:
            # For messages without attachments or non-user messages
            formatted_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    
    return formatted_messages

def base64_to_image(image_data: Dict) -> Any:
    """Convert base64 image data for Gemini"""
    if isinstance(image_data, dict) and "data" in image_data:
        image_bytes = base64.b64decode(image_data["data"])
        return genai.types.Image(image_bytes)
    return None

def messages_to_gemini(messages: List[Dict], attachments: List[Dict]) -> List[Dict]:
    """Convert messages to Gemini format"""
    gemini_messages = []
    
    for msg in messages:
        parts = []
        parts.append(msg["content"])
        
        if msg["role"] == "user" and attachments:
            for attachment in attachments:
                if attachment["type"] == "image":
                    # Convert data URL to bytes for Gemini
                    image_data = attachment["image_url"].split(",")[1]
                    image_bytes = base64.b64decode(image_data)
                    parts.append(genai.types.Image(image_bytes))
                elif attachment["type"] == "text":
                    parts.append(attachment["text"])
        
        gemini_messages.append({
            "role": "model" if msg["role"] == "assistant" else "user",
            "parts": parts
        })
    
    return gemini_messages

def messages_to_anthropic(messages: List[Dict], attachments: List[Dict]) -> List[Dict]:
    """Convert messages to Anthropic format"""
    anthropic_messages = []
    
    for msg in messages:
        if isinstance(msg["content"], str):
            # If content is a string, create a single text content
            content = [{"type": "text", "text": msg["content"]}]
        else:
            # If content is already a list, use it as is
            content = msg["content"]
        
        if msg["role"] == "user" and attachments:
            for attachment in attachments:
                if attachment["type"] == "image_url":
                    # Convert OpenAI format to Anthropic format
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": attachment["image_url"]["url"].split(";")[0].split("/")[1],
                            "data": attachment["image_url"]["url"].split(",")[1]
                        }
                    })
                elif attachment["type"] == "text":
                    content.append({"type": "text", "text": attachment["text"]})
        
        anthropic_messages.append({
            "role": msg["role"],
            "content": content
        })
    
    return anthropic_messages

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry_error_callback=lambda e: isinstance(e, (
        anthropic.APIStatusError,
        anthropic.APITimeoutError,
        anthropic.APIConnectionError,
        anthropic.APIResponseValidationError
    ))
)
async def get_ai_response(conversation: Dict) -> str:
    """Get response from AI model based on provider"""
    provider = conversation["provider"]
    api_key = conversation["api_key"]
    messages = conversation["messages"]
    attachments = conversation.get("attachments", [])
    
    # Process attachments first
    processed_attachments = [process_attachment(a) for a in attachments]
    
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    
    model = convert_model_name(conversation["model"])
    
    if provider == "openai":
        client = OpenAI(api_key=api_key)
        formatted_messages = messages_to_openai(messages, processed_attachments)
        
        response = client.chat.completions.create(
            model=model,
            messages=formatted_messages,
            max_tokens=2000
        )
        return response.choices[0].message.content
    
    elif provider == "anthropic":
        if model not in ANTHROPIC_MODELS:
            raise ValueError(f"Unsupported Anthropic model: {model}")
            
        client = anthropic.Anthropic(api_key=api_key)
        anthropic_messages = messages_to_anthropic(messages, processed_attachments)
        
        try:
            # Add system message if agent instructions exist
            if "agent_instructions" in conversation and conversation["agent_instructions"]:
                system_message = {
                    "role": "assistant",
                    "content": [{"type": "text", "text": conversation["agent_instructions"]}]
                }
                anthropic_messages.insert(0, system_message)

            response = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=anthropic_messages,
                temperature=0.7,
                system=conversation.get("agent_instructions", "You are a helpful AI assistant.")
            )
            return response.content[0].text
        except (anthropic.APIStatusError, anthropic.APITimeoutError) as e:
            if "overloaded" in str(e).lower():
                time.sleep(2)
            raise e
        except Exception as e:
            raise Exception(f"Anthropic API Error: {str(e)}")

    elif provider == "gemini":
        if model not in GOOGLE_MODELS:
            raise ValueError(f"Unsupported Gemini model: {model}")
            
        genai.configure(api_key=api_key)
        model_instance = genai.GenerativeModel(model)
        gemini_messages = messages_to_gemini(messages, processed_attachments)
        
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