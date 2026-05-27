import os
import random
# pyrefly: ignore [missing-import]
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.globals import set_llm_cache
from langchain_core.caches import InMemoryCache
from app.core.config import settings

# Enable in-memory caching for all LLM calls to reduce redundant requests
set_llm_cache(InMemoryCache())

class GroqKeyManager:
    def __init__(self):
        self.keys = []
        for key, value in os.environ.items():
            if key.startswith("GROQ_API_KEY") and value.strip():
                self.keys.append(value.strip())
                
        if not self.keys:
            self.keys = ["dummy-key"]

    def get_random_key(self) -> str:
        return random.choice(self.keys)

class GeminiKeyManager:
    def __init__(self):
        self.keys = []
        for key, value in os.environ.items():
            if key.startswith("GEMINI_API_KEY") and value.strip():
                self.keys.append(value.strip())
                
        if not self.keys:
            self.keys = ["dummy-key"]

    def get_random_key(self) -> str:
        return random.choice(self.keys)

groq_key_manager = GroqKeyManager()
gemini_key_manager = GeminiKeyManager()

def get_llm(model_name: str = "rotate", temperature: float = 0.0, use_sum_key: bool = False, estimated_tokens: int = 0):
    """Returns an LLM instance using a randomly selected API key and model to handle high traffic."""
    
    if model_name == "rotate":
        if estimated_tokens > 12000:
            # Groq's max limit is 12K. Exceeding this routes purely to Gemini (1M TPM)
            model_name = random.choice(["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash-lite", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"])
        elif estimated_tokens > 8000:
            model_name = random.choice(["llama-3.3-70b-versatile", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash-lite", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"])
        elif estimated_tokens > 3000:
            model_name = random.choice(["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash-lite", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"])
        else:
            model_name = random.choice(["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash-lite", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"])
            
    if model_name.startswith("gemini"):
        api_key = gemini_key_manager.get_random_key()
        return ChatGoogleGenerativeAI(
            api_key=api_key,
            model=model_name,
            temperature=temperature
        )
    else:
        api_key = groq_key_manager.get_random_key()
        if use_sum_key:
            sum_key = os.getenv("GROQ_SUM")
            if sum_key and sum_key.strip():
                api_key = sum_key.strip()
                
        return ChatGroq(
            api_key=api_key,
            model_name=model_name,
            temperature=temperature
        )
