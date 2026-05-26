from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from worker.tasks.email_tasks import fetch_and_summarize_emails, fetch_and_process_mess_menu
from app.core.config import settings
import redis
import json
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from app.tools.retrieval import embeddings

router = APIRouter()
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

@router.post("/trigger-email-worker")
def trigger_email_worker():
    """Manually trigger the Celery worker to fetch and summarize emails and mess menu."""
    task1 = fetch_and_summarize_emails.delay()
    task2 = fetch_and_process_mess_menu.delay()
    return {"status": "Tasks dispatched", "task_id_emails": task1.id, "task_id_mess_menu": task2.id}

class WorkerConfig(BaseModel):
    polling_rate_hours: float
    max_capacity: int

@router.get("/worker/config")
def get_worker_config():
    try:
        polling_rate = redis_client.get("email_worker_interval_hours") or "24.0"
        max_capacity = redis_client.get("email_worker_max_capacity") or "1000"
        return {
            "polling_rate_hours": float(polling_rate),
            "max_capacity": int(max_capacity)
        }
    except Exception as e:
        return {"polling_rate_hours": 24.0, "max_capacity": 1000}

@router.post("/worker/config")
def set_worker_config(config: WorkerConfig):
    try:
        redis_client.set("email_worker_interval_hours", str(config.polling_rate_hours))
        redis_client.set("email_worker_max_capacity", str(config.max_capacity))
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to save config to Redis.")

@router.get("/worker/logs")
def get_worker_logs():
    try:
        logs = redis_client.lrange("email_worker_logs", 0, -1)
        return {"logs": logs}
    except Exception as e:
        return {"logs": [f"Error fetching logs: {str(e)}"]}

@router.post("/upload-json")
async def upload_json(file: UploadFile = File(...)):
    """Upload a JSON file containing schemes/rules and ingest into longterm_db."""
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Only JSON files are supported.")
    
    try:
        content = await file.read()
        data = json.loads(content)
        
        docs = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if "page_content" in item:
                        docs.append(Document(
                            page_content=item["page_content"],
                            metadata=item.get("metadata", {})
                        ))
                    else:
                        # Serialize arbitrary JSON objects beautifully for embedding
                        docs.append(Document(
                            page_content=json.dumps(item, indent=2),
                            metadata={"source": file.filename}
                        ))
                else:
                    docs.append(Document(
                        page_content=str(item),
                        metadata={"source": file.filename}
                    ))
        elif isinstance(data, dict):
            docs.append(Document(
                page_content=json.dumps(data),
                metadata={"source": file.filename}
            ))
            
        if not docs:
            raise HTTPException(status_code=400, detail="No valid documents found in JSON.")

        QdrantVectorStore.from_documents(
            docs,
            embeddings,
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            collection_name=settings.QDRANT_LONGTERM_COLLECTION,
            force_recreate=False
        )
        
        return {"status": "success", "message": f"Successfully ingested {len(docs)} documents."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/worker/start")
def start_worker():
    try:
        redis_client.set("email_worker_active", "True")
        redis_client.set("email_worker_last_run", "0") # Reset timer to allow immediate run
        
        # Push initial log so UI updates instantly
        from worker.tasks.email_tasks import push_log, fetch_and_summarize_emails
        push_log(redis_client, "Worker started. Forcing immediate email extraction...")
        
        # Trigger Celery task immediately
        fetch_and_summarize_emails.delay()
        
        return {"status": "success", "worker_state": "Active"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start worker: {e}")

@router.post("/worker/stop")
def stop_worker():
    try:
        redis_client.set("email_worker_active", "False")
        return {"status": "success", "worker_state": "Inactive"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Redis is not running. Start Redis to manage the worker.")

@router.get("/worker/status")
def worker_status():
    try:
        status = redis_client.get("email_worker_active")
        return {"worker_state": "Active" if status == "True" else "Inactive"}
    except Exception as e:
        return {"worker_state": "Offline (No Redis)"}
