from typing import List, Dict, Any
import openai
# from google.generativeai import generate_embeddings
from anthropic import Anthropic
from langchain_openai import OpenAIEmbeddings
import os

class EmbeddingManager:
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.api_key = api_key
        
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding based on model"""
        if "openai" in self.model_name:
            return await self._get_openai_embedding(text)
        elif "gemini" in self.model_name:
            return await self._get_gemini_embedding(text)
        elif "claude" in self.model_name:
            return await self._get_claude_embedding(text)
        elif "deepseek" in self.model_name:
            return await self._get_deepseek_embedding(text)
        else:
            raise ValueError(f"Unsupported embedding model: {self.model_name}")
            
    async def _get_openai_embedding(self, text: str) -> List[float]:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=self.api_key)
        response = embeddings.embed_query(text)
        return response
        
    # async def _get_gemini_embedding(self, text: str) -> List[float]:
    #     response = await generate_embeddings(
    #         model="models/embedding-001",
    #         text=text
    #     )
        return response.embedding
        
    # Implement other embedding methods similarly
