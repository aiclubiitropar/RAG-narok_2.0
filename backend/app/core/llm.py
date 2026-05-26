import os
import random
# pyrefly: ignore [missing-import]
from langchain_groq import ChatGroq
from app.core.config import settings

class GroqKeyManager:
    def __init__(self):
        # Auto-detect any environment variable starting with GROQ_API_KEY
        self.keys = []
        for key, value in os.environ.items():
            if key.startswith("GROQ_API_KEY") and value.strip():
                self.keys.append(value.strip())
                
        if not self.keys:
            # Fallback for development without keys configured
            self.keys = ["dummy-key"]

    def get_random_key(self) -> str:
        return random.choice(self.keys)

key_manager = GroqKeyManager()

def get_groq_llm(model_name: str = "llama-3.3-70b-versatile", temperature: float = 0.0, use_sum_key: bool = False) -> ChatGroq:
    """Returns a ChatGroq instance using a randomly selected API key to handle high traffic."""
    api_key = key_manager.get_random_key()
    
    if use_sum_key:
        sum_key = os.getenv("GROQ_SUM")
        if sum_key and sum_key.strip():
            api_key = sum_key.strip()
            
    return ChatGroq(
        api_key=api_key,
        model_name=model_name,
        temperature=temperature
    )
