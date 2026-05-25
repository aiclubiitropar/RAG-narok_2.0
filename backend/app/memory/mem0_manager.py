import os
import logging
from mem0 import Memory # pyrefly: ignore [missing-import]
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Mem0
# If you don't provide an api_key, Mem0 will run locally by default using Qdrant/SQLite depending on the default config.
# To enforce Mem0 to use our Qdrant instance, we can configure it.
config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "url": settings.QDRANT_URL,
            "api_key": settings.QDRANT_API_KEY,
            "collection_name": "mem0_episodic_memory_v4",
            "embedding_model_dims": 384
        }
    },
    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": "sentence-transformers/all-MiniLM-L6-v2"
        }
    },
    "llm": {
        "provider": "groq",
        "config": {
            "model": "llama-3.1-8b-instant",
            "api_key": getattr(settings, "GROQ_API_KEY", os.getenv("GROQ_API_KEY", "none"))
        }
    }
}

memory = Memory.from_config(config)

def add_user_memory(user_id: str, content: str, metadata: dict = None):
    """Add episodic memory for a specific user."""
    memory.add(content, user_id=user_id, metadata=metadata)

def get_user_memory(user_id: str, query: str):
    """Retrieve episodic memory for a specific user based on a query."""
    return memory.search(query, filters={'user_id': user_id})
