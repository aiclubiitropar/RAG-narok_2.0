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

def create_llm_instance(model_name: str, temperature: float, use_sum_key: bool):
    if model_name.startswith("gemini") or model_name.startswith("gemma"):
        api_key = gemini_key_manager.get_random_key()
        if use_sum_key:
            sum_key = os.getenv("GEM_SUM")
            if sum_key and sum_key.strip():
                api_key = sum_key.strip()
                
        return ChatGoogleGenerativeAI(
            api_key=api_key,
            model=model_name,
            temperature=temperature,
            max_retries=1
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
            temperature=temperature,
            max_retries=1
        )

def get_llm(model_name: str = "rotate", temperature: float = 0.0, use_sum_key: bool = False, estimated_tokens: int = 0):
    """Returns an LLM instance with robust cross-provider fallbacks to bypass rate limits seamlessly."""
    
    primary_model_name = model_name
    if use_sum_key:
        primary_model_name = random.choice(["gemma-4-26b-a4b-it", "gemma-4-31b-it", "llama-3.3-70b-versatile", "qwen/qwen3-32b"])
    elif primary_model_name == "rotate":
        gemini_models = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.0-flash"]
        
        if estimated_tokens > 12000:
            # Groq's max limit is 12K. Exceeding this routes purely to Gemini (1M TPM)
            primary_model_name = random.choice(gemini_models)
        elif estimated_tokens > 8000:
            models = ["llama-3.3-70b-versatile", "gemma-4-31b-it"] + gemini_models
            weights = [3, 3] + [1] * len(gemini_models)
            primary_model_name = random.choices(models, weights=weights, k=1)[0]
        elif estimated_tokens > 3000:
            models = ["llama-3.3-70b-versatile", "gemma-4-26b-a4b-it", "gemma-4-31b-it", "openai/gpt-oss-120b", "openai/gpt-oss-20b"] + gemini_models
            weights = [3, 3, 3, 1, 1] + [1] * len(gemini_models)
            primary_model_name = random.choices(models, weights=weights, k=1)[0]
        else:
            models = ["llama-3.3-70b-versatile", "gemma-4-26b-a4b-it", "gemma-4-31b-it", "qwen/qwen3-32b", "llama-3.1-8b-instant", "openai/gpt-oss-120b", "openai/gpt-oss-20b"] + gemini_models
            weights = [3, 3, 3, 3, 1, 1, 1] + [1] * len(gemini_models)
            primary_model_name = random.choices(models, weights=weights, k=1)[0]
            
    primary_llm = create_llm_instance(primary_model_name, temperature, use_sum_key)
    
    # Define cross-provider fallbacks: If Gemini is rate limited, try Groq. If Groq is limited, try Gemini.
    if primary_model_name.startswith("gemini") or primary_model_name.startswith("gemma"):
        fallback_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    else:
        fallback_models = ["gemini-1.5-flash", "llama-3.1-8b-instant"]
        
    fallbacks = [create_llm_instance(m, temperature, use_sum_key) for m in fallback_models if m != primary_model_name]
    
    # Langchain natively wraps the LLM to automatically retry with fallbacks upon failure (e.g. 429 Rate Limits)
    return primary_llm.with_fallbacks(fallbacks)
