import sys
import os

# Add the backend directory to sys.path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from app.tools.retrieval import embeddings, client
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_database():
    logger.info("Seeding Academic Database...")
    academic_docs = [
        Document(
            page_content="Course Registration Rule 1: All B.Tech students must register for courses within the first 5 days of the semester starting. Late registration incurs a fine of Rs. 1000 per day.",
            metadata={"source": "academic_guidelines_2024.pdf"}
        ),
        Document(
            page_content="Grading System: IIT Ropar follows a 10-point grading system. A grade 'A' corresponds to 10 points, 'A-' to 9 points, 'B' to 8 points, and so on.",
            metadata={"source": "academic_guidelines_2024.pdf"}
        ),
        Document(
            page_content="Attendance Policy: A minimum of 75% attendance is required in all registered courses to be eligible to appear for the end-semester examinations.",
            metadata={"source": "academic_guidelines_2024.pdf"}
        )
    ]
    QdrantVectorStore.from_documents(
        academic_docs,
        embeddings,
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        collection_name=settings.QDRANT_LONGTERM_COLLECTION,
        force_recreate=True
    )
    logger.info(f"Added {len(academic_docs)} documents to academic_store.")

    logger.info("Seeding Campus Database...")
    campus_docs = [
        Document(
            page_content="Mess Menu Today (Monday): Breakfast - Poha, Jalebi, Milk/Tea. Lunch - Rajma Chawal, Roti, Salad. Dinner - Paneer Butter Masala, Naan, Gulab Jamun.",
            metadata={"source": "mess_menu_current.txt"}
        ),
        Document(
            page_content="Hostel Timings: First-year students must return to their respective hostels by 11:00 PM. Senior students have unrestricted in-out timings but must carry their ID cards.",
            metadata={"source": "hostel_rules.txt"}
        ),
        Document(
            page_content="Sports Complex: The main sports complex includes a badminton court, gym, and swimming pool. The swimming pool is open from 6:00 AM to 9:00 AM and 4:00 PM to 8:00 PM.",
            metadata={"source": "campus_facilities.txt"}
        )
    ]
    QdrantVectorStore.from_documents(
        campus_docs,
        embeddings,
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        collection_name=settings.QDRANT_SHORTTERM_COLLECTION,
        force_recreate=True
    )
    logger.info(f"Added {len(campus_docs)} documents to campus_store.")

if __name__ == "__main__":
    seed_database()
    logger.info("Database seeding complete!")
