# pyrefly: ignore [missing-import]
from qdrant_client import QdrantClient
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class QdrantManager:
    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        self._ensure_collections()

    def _ensure_collections(self):
        """Ensure that both longterm and shortterm collections exist."""
        try:
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]

            for col_name in [settings.QDRANT_LONGTERM_COLLECTION, settings.QDRANT_SHORTTERM_COLLECTION]:
                if col_name not in collection_names:
                    # Creating with a default vector size for Groq/OpenAI embeddings (e.g., 1536 or 1024 depending on model)
                    # Adjust vector size based on the actual embedding model used.
                    self.client.create_collection(
                        collection_name=col_name,
                        vectors_config={"size": 768, "distance": "Cosine"}
                    )
                    logger.info(f"Created collection {col_name}")
        except Exception as e:
            logger.error(f"Error ensuring Qdrant collections: {e}")

qdrant_manager = QdrantManager()
