from langchain_core.tools import tool
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from gradio_client import Client
from app.core.config import settings
import logging
import ast

logger = logging.getLogger(__name__)

import json

class GradioEmbeddings(Embeddings):
    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = Client("IotaCluster/embedding-model", token=settings.HF_TOKEN)
        return self._client

    def _extract_embedding(self, result) -> list[float]:
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except:
                try:
                    result = ast.literal_eval(result)
                except:
                    pass
        
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            if "dense_embedding" in result:
                return result["dense_embedding"]
            elif "" in result and isinstance(result[""], dict) and "dense_embedding" in result[""]:
                return result[""]["dense_embedding"]
            for v in result.values():
                if isinstance(v, list):
                    return v
                if isinstance(v, dict) and "dense_embedding" in v:
                    return v["dense_embedding"]
        return result

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for t in texts:
            embeddings.append(self.embed_query(t))
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        import time
        max_retries = 5
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                result = self.client.predict(text=text, api_name="/embed_dense")
                return self._extract_embedding(result)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to get embeddings after {max_retries} attempts: {e}")
                    raise
                
                # If rate limited, sleep and retry
                error_str = str(e).lower()
                if "too many requests" in error_str or "rate limit" in error_str or "500" in error_str or "503" in error_str:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Embedding API rate limited. Retrying in {delay} seconds (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(delay)
                else:
                    raise

# Initialize embeddings
embeddings = GradioEmbeddings()

# Initialize Qdrant client using Cloud URL and API Key
client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

def get_academic_store():
    return QdrantVectorStore(
        client=client,
        collection_name=settings.QDRANT_LONGTERM_COLLECTION,
        embedding=embeddings,
    )

def get_campus_store():
    return QdrantVectorStore(
        client=client,
        collection_name=settings.QDRANT_SHORTTERM_COLLECTION,
        embedding=embeddings,
    )

import re

def smart_query(collection_name: str, query_text: str, topk: int = 20, top_l: int = 7, doc_search: bool = True):
    """
    Hybrid query: first prefetch with dense (topk), then filter.
    If doc_search is True, also filter by fuzzy/substring/keyword in the document (case-insensitive) 
    and concatenate all matches in the collection.
    """
    dense_vec = embeddings.embed_query(query_text)
    
    results = client.query_points(
        collection_name=collection_name,
        query=dense_vec,
        limit=topk,
        with_payload=True,
        with_vectors=False
    )
    
    points_list = getattr(results, 'points', results)
    
    hits = []
    for hit in points_list:
        payload = getattr(hit, 'payload', {}) or {}
        # Langchain Qdrant uses page_content
        content = payload.get('page_content', '')
        hits.append({"id": hit.id, "document": content})
        
    hits = hits[:top_l]
    
    if doc_search:
        query_words = set(re.findall(r"\w+", query_text.lower()))
        def fuzzy_match(doc):
            doc_text = doc.lower()
            if query_text.lower() in doc_text: return True
            for word in query_words:
                if len(word) > 3 and word in doc_text: return True
                for token in re.findall(r"\w+", doc_text):
                    if len(word) > 3 and token and abs(len(word) - len(token)) <= 1 and sum(a != b for a, b in zip(word, token)) <= 1:
                        return True
            return False

        filtered_hits = [hit for hit in hits if fuzzy_match(hit['document'])]
        
        doc_hits = []
        next_offset = None
        while True:
            scroll_result = client.scroll(collection_name=collection_name, with_payload=True, offset=next_offset, limit=100)
            points = scroll_result[0]
            next_offset = scroll_result[1]
            for point in points:
                payload = point.payload or {}
                content = payload.get('page_content', '')
                if content and fuzzy_match(content):
                    doc_hits.append({"id": point.id, "document": content})
            if not next_offset:
                break
                
        seen_ids = set()
        merged = []
        for hit in filtered_hits:
            if hit['id'] not in seen_ids:
                merged.append(hit)
                seen_ids.add(hit['id'])
        for hit in doc_hits:
            if hit['id'] not in seen_ids:
                merged.append(hit)
                seen_ids.add(hit['id'])
                
        # Limit to top 3 and truncate each document to prevent Groq TPM (token) rate limits
        merged = merged[:3]
        return "\n\n---\n\n".join([hit['document'][:1500] + ("..." if len(hit['document']) > 1500 else "") for hit in merged]) if merged else "No relevant information found."
    else:
        hits = hits[:3]
        return "\n\n---\n\n".join([hit['document'][:1500] + ("..." if len(hit['document']) > 1500 else "") for hit in hits]) if hits else "No relevant information found."

@tool
def campus_data(query: str) -> str:
    """
    Query the academic database for rules regarding course registration, 
    graduation requirements, exams, and grading.
    """
    logger.info(f"Querying longterm academic database for: {query}")
    try:
        return smart_query(settings.QDRANT_LONGTERM_COLLECTION, query)
    except Exception as e:
        logger.error(f"Error querying longterm database: {e}")
        return "Longterm database is currently unavailable or empty."

@tool
def latest_announcements(query: str) -> str:
    """
    Query the campus database for recent information about hostels, mess menus, 
    sports facilities, and campus events/emails.
    """
    logger.info(f"Querying shortterm campus database for: {query}")
    try:
        return smart_query(settings.QDRANT_SHORTTERM_COLLECTION, query)
    except Exception as e:
        logger.error(f"Error querying shortterm database: {e}")
        return "Shortterm database is currently unavailable or empty."
