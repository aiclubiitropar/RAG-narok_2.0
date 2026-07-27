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

from sentence_transformers import SentenceTransformer

class LocalEmbeddings(Embeddings):
    def __init__(self, model_name='multi-qa-mpnet-base-cos-v1'):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # SentenceTransformer handles batching naturally
        return self.model.encode(texts, convert_to_numpy=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode(text, convert_to_numpy=True).tolist()

# Initialize embeddings
embeddings = LocalEmbeddings()

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
