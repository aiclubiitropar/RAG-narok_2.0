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
            if (key.startswith("GROQ_API_KEY") or key == "GROQ_API_KEYS") and value.strip():
                for k in value.split(","):
                    k = k.strip()
                    if k and k not in self.keys:
                        self.keys.append(k)
                
        if not self.keys:
            self.keys = ["dummy-key"]

    def get_random_key(self) -> str:
        return random.choice(self.keys)

    def has_valid_key(self) -> bool:
        return bool(self.keys and self.keys != ["dummy-key"])

class GeminiKeyManager:
    def __init__(self):
        self.keys = []
        for key, value in os.environ.items():
            if (key.startswith("GEMINI_API_KEY") or key.startswith("GOOGLE_API_KEY") or key in ("GEMINI_API_KEYS", "GOOGLE_API_KEYS")) and value.strip():
                for k in value.split(","):
                    k = k.strip()
                    if k and k not in self.keys:
                        self.keys.append(k)
                
        if not self.keys:
            self.keys = ["dummy-key"]

    def get_random_key(self) -> str:
        return random.choice(self.keys)

    def has_valid_key(self) -> bool:
        return bool(self.keys and self.keys != ["dummy-key"])

groq_key_manager = GroqKeyManager()
gemini_key_manager = GeminiKeyManager()

def create_llm_instance(model_name: str, temperature: float = 0.0, use_sum_key: bool = False):
    if model_name.startswith("gemini"):
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
    
    has_gemini = gemini_key_manager.has_valid_key()
    has_groq = groq_key_manager.has_valid_key()
    
    gemini_models = ["gemini-2.0-flash", "gemini-2.0-flash-lite"]
    groq_models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "qwen/qwen3.6-27b"]

    primary_model_name = model_name
    if use_sum_key:
        candidate_models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "qwen/qwen3.6-27b"]
        if has_gemini:
            candidate_models.append("gemini-2.0-flash")
        primary_model_name = random.choice(candidate_models)
    elif primary_model_name == "rotate":
        if estimated_tokens > 12000:
            if has_gemini:
                models = ["gemini-2.0-flash", "openai/gpt-oss-120b"]
                primary_model_name = random.choice(models)
            else:
                primary_model_name = "openai/gpt-oss-120b"
        elif estimated_tokens > 8000:
            models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
            weights = [4, 2]
            if has_gemini:
                models.extend(gemini_models)
                weights.extend([3, 1])
            primary_model_name = random.choices(models, weights=weights, k=1)[0]
        elif estimated_tokens > 3000:
            models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "qwen/qwen3.6-27b"]
            weights = [3, 2, 2]
            if has_gemini:
                models.extend(gemini_models)
                weights.extend([3, 1])
            primary_model_name = random.choices(models, weights=weights, k=1)[0]
        else:
            models = ["qwen/qwen3.8-27b", "qwen/qwen3.6-27b", "openai/gpt-oss-120b"]
            weights = [3, 3, 1]
            if has_gemini:
                models.extend(gemini_models)
                weights.extend([3, 1])
            primary_model_name = random.choices(models, weights=weights, k=1)[0]
            
    primary_llm = create_llm_instance(primary_model_name, temperature, use_sum_key)
    
    # Define cross-provider fallbacks: If Gemini is rate limited, try Groq. If Groq is limited, try other models / Gemini.
    if primary_model_name.startswith("gemini"):
        fallback_models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "gemini-2.0-flash-lite"]
    elif primary_model_name == "openai/gpt-oss-120b":
        fallback_models = ["qwen/qwen3.8-27b", "qwen/qwen3.6-27b"]
        if has_gemini:
            fallback_models.append("gemini-2.0-flash")
    elif primary_model_name == "qwen/qwen3.8-27b":
        fallback_models = ["qwen/qwen3.6-27b", "openai/gpt-oss-120b"]
        if has_gemini:
            fallback_models.append("gemini-2.0-flash")
    elif primary_model_name == "qwen/qwen3.6-27b":
        fallback_models = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"]
        if has_gemini:
            fallback_models.append("gemini-2.0-flash")
    else:
        fallback_models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "qwen/qwen3.6-27b"]
        if has_gemini:
            fallback_models.append("gemini-2.0-flash")
        
    fallback_instances = [
        create_llm_instance(m, temperature, use_sum_key) 
        for m in fallback_models 
        if m != primary_model_name
    ]
    
    if fallback_instances:
        return primary_llm.with_fallbacks(fallback_instances)
    return primary_llm

