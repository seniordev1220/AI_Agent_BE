from typing import Dict, List, Any, Union, AsyncGenerator
import anthropic
from google.generativeai import GenerativeModel
from openai import OpenAI
from huggingface_hub import InferenceClient
from transformers import GPT2LMHeadModel, GPT2Tokenizer
import base64
import google.generativeai as genai
from PyPDF2 import PdfReader
from io import BytesIO
import tempfile
from langchain.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatOpenAI
from langchain.callbacks import StreamingStdOutCallbackHandler
from langchain.callbacks.base import BaseCallbackHandler

# Define supported models
ANTHROPIC_MODELS = [
    "claude-3-5-sonnet-20240620",
    "claude-3-7-sonnet-20240620"
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
            if attachment["type"] == "jpg":
                mime_type = "jpeg"
            else:
                mime_type = attachment["type"]
            base64_image = base64.b64encode(image_data).decode("utf-8")
            return {
                "type": "image",
                "image": {
                    "type": "base64",
                    "media_type": f"image/{mime_type}",
                    "data": base64_image
                }
            }
    else:
        return {"type": "text", "text": f"Unsupported file: {attachment['name']}"}

def messages_to_openai(messages: List[Dict], attachments: List[Dict]) -> List[Dict]:
    """Format messages for OpenAI (including vision)"""
    formatted_messages = []
    for msg in messages:
        content = []
        if isinstance(msg["content"], str):
            content.append({"type": "text", "text": msg["content"]})
        elif isinstance(msg["content"], list):
            content.extend(msg["content"])
        
        # Add processed attachments for user messages
        if msg["role"] == "user" and attachments:
            content.extend([process_attachment(a) for a in attachments])
        
        formatted_messages.append({
            "role": msg["role"],
            "content": content
        })
    return formatted_messages

def base64_to_image(image_data: Dict) -> Any:
    """Convert base64 image data for Gemini"""
    if isinstance(image_data, dict) and "data" in image_data:
        image_bytes = base64.b64decode(image_data["data"])
        return genai.types.Image(image_bytes)
    return None

def messages_to_gemini(messages: List[Dict], attachments: List[Dict] = None) -> List[Dict]:
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

        # Handle string content
        if isinstance(message["content"], str):
            gemini_message["parts"].append(message["content"])
        # Handle list content
        elif isinstance(message["content"], list):
            for content in message["content"]:
                if isinstance(content, str):
                    gemini_message["parts"].append(content)
                elif isinstance(content, dict):
                    if content["type"] == "text":
                        gemini_message["parts"].append(content["text"])
                    elif content["type"] == "image":
                        image = base64_to_image(content["image"])
                        if image:
                            gemini_message["parts"].append(image)

        # Add attachments for user messages
        if message["role"] == "user" and attachments:
            for attachment in attachments:
                processed = process_attachment(attachment)
                if processed["type"] == "text":
                    gemini_message["parts"].append(processed["text"])
                elif processed["type"] == "image":
                    image = base64_to_image(processed["image"])
                    if image:
                        gemini_message["parts"].append(image)

        if prev_role != message["role"]:
            gemini_messages.append(gemini_message)

        prev_role = message["role"]
        
    return gemini_messages

def messages_to_anthropic(messages: List[Dict], attachments: List[Dict] = None) -> Dict:
    """Convert messages to Anthropic format and extract system message"""
    anthropic_messages = []
    system_message = None
    prev_role = None
    
    for message in messages:
        # Extract system message
        if message["role"] == "system":
            system_message = message["content"]
            continue
            
        if prev_role and (prev_role == message["role"]):
            anthropic_message = anthropic_messages[-1]
        else:
            anthropic_message = {
                "role": message["role"],
                "content": [],
            }

        # Handle string content
        if isinstance(message["content"], str):
            anthropic_message["content"].append({"type": "text", "text": message["content"]})
        # Handle list content
        elif isinstance(message["content"], list):
            for content in message["content"]:
                if isinstance(content, str):
                    anthropic_message["content"].append({"type": "text", "text": content})
                elif isinstance(content, dict):
                    if content["type"] == "text":
                        anthropic_message["content"].append({"type": "text", "text": content["text"]})
                    elif content["type"] == "image":
                        anthropic_message["content"].append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": content["image"]["media_type"],
                                "data": content["image"]["data"]
                            }
                        })

        # Add attachments for user messages
        if message["role"] == "user" and attachments:
            for attachment in attachments:
                processed = process_attachment(attachment)
                if processed["type"] == "text":
                    anthropic_message["content"].append({"type": "text", "text": processed["text"]})
                elif processed["type"] == "image":
                    anthropic_message["content"].append({
                        "type": "image",
                        "source": processed["image"]
                    })

        if prev_role != message["role"]:
            anthropic_messages.append(anthropic_message)

        prev_role = message["role"]
        
    return {
        "messages": anthropic_messages,
        "system": system_message
    }

def generate_system_prompt(agent_instructions: str, agent_category: str) -> str:
    """
    Generate a system prompt based on agent's instructions and category
    """
    base_prompt = "You are an AI assistant"
    
    if agent_category:
        base_prompt += f" specialized in {agent_category}"
    
    if agent_instructions:
        base_prompt += f". {agent_instructions}"
    else:
        base_prompt += ". Your goal is to help users by providing accurate and helpful responses."
    
    return base_prompt

class ChunkCollectorCallbackHandler(BaseCallbackHandler):
    def __init__(self):
        self.chunks = []
        
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.chunks.append(token)
        
    def get_collected_tokens(self) -> str:
        return "".join(self.chunks)

async def get_ai_response_from_vectorstore(conversation: Dict) -> str:
    """Get AI response with context from vector store"""
    messages = conversation["messages"]
    agent_instructions = conversation.get("agent_instructions", "")
    references = conversation.get("references", [])
    reference_enabled = conversation.get("reference_enabled", True)  # Default to True for backward compatibility
    
    # Create a system message that includes instructions for handling references
    system_prompt = f"""
    {agent_instructions}
    
    {
    '''When using information from referenced sources, please:
    1. Cite the source in your response using [Source Name] format
    2. Only use information that is directly relevant to the query
    3. Maintain accuracy and context of the referenced information
    4. Synthesize information from multiple sources when appropriate
    ''' if reference_enabled else 
    '''Please provide responses based on the available context without citing or referencing specific sources.'''
    }
    """
    
    # Format the conversation with references
    formatted_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Query: {conversation['query']}\n\nRelevant Context:\n{messages}"}
    ]
    
    # Get response using the appropriate model
    response = await get_ai_response_from_model({
        "messages": formatted_messages,
        "model": conversation["model"],
        "provider": conversation["provider"],
        "api_key": conversation["api_key"],
        "attachments": conversation.get("attachments", [])
    })
    
    return response

async def get_ai_response_from_model(conversation: Dict) -> str:
    """
    Get response from AI model based on provider
    """
    provider = conversation["provider"]
    api_key = conversation["api_key"]
    messages = conversation["messages"]
    attachments = conversation.get("attachments", [])
    agent_instructions = conversation.get("agent_instructions", "")
    
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    
    # Generate system prompt
    system_prompt = generate_system_prompt(
        agent_instructions=agent_instructions,
        agent_category=conversation.get("agent_category", "")
    )
    
    # Add system message at the beginning if not present
    if not messages or messages[0]["role"] != "system":
        messages.insert(0, {"role": "system", "content": system_prompt})
    
    model = convert_model_name(conversation["model"])
    
    if provider == "openai":
        client = OpenAI(api_key=api_key)
        formatted_messages = messages_to_openai(messages, attachments)
        
        if model in OPENAI_MODELS:
            response = client.chat.completions.create(
                model=model,
                messages=formatted_messages,
                max_tokens=2000
            )
            return response.choices[0].message.content
        else:
            text_only_messages = []
            for msg in formatted_messages:
                text_content = [c for c in msg["content"] if c["type"] == "text"]
                text_only_messages.append({**msg, "content": text_content})
            
            response = client.chat.completions.create(
                model=model,
                messages=text_only_messages,
                max_tokens=2000
            )
            return response.choices[0].message.content
    
    elif provider == "anthropic":
        if model not in ANTHROPIC_MODELS:
            raise ValueError(f"Unsupported Anthropic model: {model}")
            
        client = anthropic.Client(api_key=api_key)
        formatted_data = messages_to_anthropic(messages, attachments)
        
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=formatted_data["messages"],
            system=formatted_data["system"],
            temperature=0.7
        )
        return response.content[0].text

    elif provider == "gemini":
        if model not in GOOGLE_MODELS:
            raise ValueError(f"Unsupported Gemini model: {model}")
            
        genai.configure(api_key=api_key)
        model_instance = genai.GenerativeModel(convert_model_name(model))
        gemini_messages = messages_to_gemini(messages, attachments)
        
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
