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

def get_dynamic_chunks(candidates, max_chars=8000, min_chunks=3):
    """Dynamically select chunks until a character limit is reached, ensuring a minimum number of chunks."""
    selected = []
    current_len = 0
    for hit in candidates:
        if len(selected) < min_chunks or current_len < max_chars:
            selected.append(hit)
            current_len += len(hit['document'])
        else:
            break
    return selected

def smart_query(collection_name: str, query_text: str, topk: int = 100, top_l: int = 7, doc_search: bool = True):
    """
    Hybrid query: first prefetch with dense (topk), then filter.
    If doc_search is True, also filter by fuzzy/substring/keyword in the document (case-insensitive) 
    and prioritize those matches.
    """
    try:
        dense_vec = embeddings.embed_query(query_text)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return "Search unavailable due to embedding model error."
    
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
        content = payload.get('page_content', '')
        if content:
            hits.append({"id": hit.id, "document": content})
            
    if not hits:
        return "No relevant information found."
        
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

        # Prioritize hits that have fuzzy matches
        exact_matches = []
        other_matches = []
        for hit in hits:
            if fuzzy_match(hit['document']):
                exact_matches.append(hit)
            else:
                other_matches.append(hit)
                
        # Combine prioritizing exact matches, then fallback to dense
        merged = exact_matches + other_matches
        
        # Take the top_l
        final_hits = get_dynamic_chunks(merged[:max(top_l, len(exact_matches))])
        return "\n\n---\n\n".join([hit['document'] for hit in final_hits]) if final_hits else "No relevant information found."
    else:
        final_hits = get_dynamic_chunks(hits[:top_l])
        return "\n\n---\n\n".join([hit['document'] for hit in final_hits]) if final_hits else "No relevant information found."

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
