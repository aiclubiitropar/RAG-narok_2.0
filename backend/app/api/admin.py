from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from worker.tasks.email_tasks import fetch_and_summarize_emails, fetch_and_process_mess_menu
from app.core.config import settings
import redis
import json
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from app.tools.retrieval import embeddings
from fastapi import Depends, Header
import base64
from io import BytesIO
import PyPDF2
from datetime import datetime
from app.core.llm import get_llm
from langchain_core.messages import HumanMessage
from qdrant_client import QdrantClient
from typing import List
import httpx
import time
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

@router.post("/trigger-email-worker")
def trigger_email_worker():
    """Manually trigger the Google Apps Script Webhook to push emails to the backend."""
    redis_client.delete("last_processed_mess_menu_id")
    
    webhook_url = settings.APPS_SCRIPT_WEBHOOK_URL if hasattr(settings, 'APPS_SCRIPT_WEBHOOK_URL') else os.getenv("APPS_SCRIPT_WEBHOOK_URL")
    if not webhook_url:
        return {"status": "error", "message": "APPS_SCRIPT_WEBHOOK_URL is not configured in .env"}
        
    try:
        # Send an HTTP GET to the Google Apps Script Web App to trigger it
        httpx.get(webhook_url, timeout=10.0)
        return {"status": "Success", "message": "Triggered Google Apps Script Webhook. Check logs in a few moments."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger Webhook: {str(e)}")

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
        from worker.tasks.email_tasks import push_log
        push_log(redis_client, "Webhook started. Command Center enabled.")
        
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

class Base64UploadRequest(BaseModel):
    filename: str
    base64_data: str

@router.post("/worker/upload-base64-pdf")
async def upload_base64_pdf(req: Base64UploadRequest, authorization: str = Header(None)):
    if redis_client.get("email_worker_active") != "True":
        raise HTTPException(status_code=403, detail="Worker is stopped in Command Center.")
        
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = authorization.split(" ")[1]
    if token != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")

    if not req.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        # Decode base64 to bytes
        pdf_bytes = base64.b64decode(req.base64_data)
        
        # Extract text using PyPDF2
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
        extracted_text = ""
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
                
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract any text from the PDF. It may be image-based.")

        # Structure the messy PDF text using Groq
        llm = get_llm(use_sum_key=True)
        prompt = f"The following text was extracted from a PDF of a hostel mess menu (food schedule for the week/month). The text is very messy because of the PDF extraction. Please reconstruct this into a clean, easy-to-read Markdown table. Do not include any extra conversation, ONLY output the Markdown table.\n\nRaw Text:\n{extracted_text}"
        
        response = llm.invoke([HumanMessage(content=prompt)])
        structured_menu = response.content.strip()

        # Log it to Redis so it appears in the UI
        log_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Apps Script pushed {req.filename}. Structured and saved successfully!"
        try:
            redis_client.lpush("email_worker_logs", log_msg)
            redis_client.ltrim("email_worker_logs", 0, 99)
        except:
            pass

        # Ingest into Qdrant shortterm collection
        doc = Document(
            page_content=f"MESS MENU ({req.filename}):\n\n{structured_menu}",
            metadata={"source": req.filename, "type": "mess_menu", "date_processed": datetime.now().isoformat()}
        )
        
        QdrantVectorStore.from_documents(
            [doc],
            embeddings,
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            collection_name=settings.QDRANT_SHORTTERM_COLLECTION,
            force_recreate=False
        )
        
        return {"status": "success", "message": f"Successfully ingested {req.filename}"}
        
    except Exception as e:
        error_msg = f"Failed to process PDF: {str(e)}"
        try:
            redis_client.lpush("email_worker_logs", f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {error_msg}")
        except:
            pass
        raise HTTPException(status_code=500, detail=error_msg)

class EmailItem(BaseModel):
    id: str
    subject: str
    sender: str
    date: str
    body: str

class EmailUploadRequest(BaseModel):
    emails: List[EmailItem]

@router.post("/worker/upload-emails")
async def upload_emails(req: EmailUploadRequest, authorization: str = Header(None)):
    if redis_client.get("email_worker_active") != "True":
        raise HTTPException(status_code=403, detail="Worker is stopped in Command Center.")
        
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = authorization.split(" ")[1]
    if token != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")

    if not req.emails:
        return {"status": "success", "message": "No new emails provided."}

    try:
        from worker.tasks.email_tasks import push_log
        push_log(redis_client, f"Apps Script pushed {len(req.emails)} unread email(s). Summarizing...")
        
        docs = []
        for em in req.emails:
            llm = get_llm(use_sum_key=True)
            prompt = f"Summarize the following email body into a concise, informative paragraph for an AI assistant's memory. CRITICAL: If the email contains any tabular data, schedules, or structured lists, you MUST preserve and format them accurately as Markdown tables or lists below your summary paragraph.\n\nEmail Body:\n{em.body}"
            
            response = llm.invoke([HumanMessage(content=prompt)])
            summary = response.content.strip()

            page_content = f"Date: {em.date}\nFrom: {em.sender}\nSubject: {em.subject}\nSummary: {summary}"
            docs.append(Document(
                page_content=page_content,
                metadata={"source": "email", "id": em.id, "timestamp": time.time()}
            ))
            
            # Show summary directly in the frontend logs!
            push_log(redis_client, f"Ingested email: {em.subject} - Summary: {summary[:150]}...")

        if docs:
            QdrantVectorStore.from_documents(
                docs,
                embeddings,
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
                collection_name=settings.QDRANT_SHORTTERM_COLLECTION,
                force_recreate=False
            )
            push_log(redis_client, f"Successfully embedded {len(docs)} new emails to shortterm_db.")
            
            # FIFO Cleanup Logic
            try:
                max_capacity = int(redis_client.get("email_worker_max_capacity") or 1000)
                q_client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
                count_result = q_client.count(collection_name=settings.QDRANT_SHORTTERM_COLLECTION)
                
                if count_result.count > max_capacity:
                    excess = count_result.count - max_capacity
                    logger.info(f"Capacity exceeded ({count_result.count} > {max_capacity}). Deleting {excess} oldest records.")
                    
                    records, _ = q_client.scroll(collection_name=settings.QDRANT_SHORTTERM_COLLECTION, limit=10000, with_payload=True)
                    sorted_records = sorted(records, key=lambda x: x.payload.get("metadata", {}).get("timestamp", 0))
                    to_delete = [r.id for r in sorted_records[:excess]]
                    
                    if to_delete:
                        q_client.delete(collection_name=settings.QDRANT_SHORTTERM_COLLECTION, points_selector=to_delete)
                        push_log(redis_client, f"Capacity exceeded. Deleted {len(to_delete)} oldest emails.")
            except Exception as qc_err:
                push_log(redis_client, f"Failed to enforce capacity: {qc_err}")

        return {"status": "success", "message": f"Processed {len(docs)} emails."}
        
    except Exception as e:
        error_msg = f"Failed to process emails: {str(e)}"
        try:
            from worker.tasks.email_tasks import push_log
            push_log(redis_client, f"ERROR: {error_msg}")
        except:
            pass
        raise HTTPException(status_code=500, detail=error_msg)
