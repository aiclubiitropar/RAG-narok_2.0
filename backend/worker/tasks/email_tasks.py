from worker.celery_app import celery_app
from app.core.llm import get_llm
import logging
from langchain_core.messages import HumanMessage
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from app.tools.retrieval import embeddings
from app.core.config import settings
import os
import imaplib
import email
from email.header import decode_header
import redis
import time
import socket

# Force IPv4 globally for this worker to prevent "Network is unreachable" IPv6 timeouts on Hugging Face
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

import PyPDF2
from io import BytesIO
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

import re

logger = logging.getLogger(__name__)

def _extract_and_clean_response(content):
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
            elif isinstance(block, str):
                text_parts.append(block)
        text = "".join(text_parts)
    else:
        text = str(content)
    
    # Remove <think> blocks
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return text.strip()

def push_log(redis_client, msg: str):
    timestamp = time.strftime("%H:%M:%S")
    log_line = f"[{timestamp}] {msg}"
    logger.info(msg)
    try:
        redis_client.lpush("email_worker_logs", log_line)
        redis_client.ltrim("email_worker_logs", 0, 99)
    except:
        pass

class EmailScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.mail = None

    def connect(self):
        self.mail = imaplib.IMAP4_SSL("imap.gmail.com")
        self.mail.login(self.username, self.password)

    def scrape_latest_emails(self, count=5):
        try:
            self.connect()
            self.mail.select("inbox")
            status, messages = self.mail.search(None, "UNSEEN")
            if status != "OK":
                return []
                
            email_ids = messages[0].split()
            emails = []
            
            for e_id in email_ids[-count:]:
                status, msg_data = self.mail.fetch(e_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                        
                        from_ = str(msg.get("From", ""))
                        date = msg.get("Date")
                        
                        # Apply blocklist filter
                        blocklist = ["no-reply@accounts.google.com", "security alert", "unstop", "linkedin", "kaggle", "team unstop", "canva", "noreply@github.com", "noreply", "feed","huggingface","instagram","udacity","udemy","supabase","vercel"]
                        if any(b in from_.lower() or b in subject.lower() for b in blocklist):
                            continue
                            
                        body = ""
                        attachments_text = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))
                                
                                if content_type == "text/plain" and "attachment" not in content_disposition:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body = payload.decode(errors='ignore')
                                
                                if "attachment" in content_disposition:
                                    filename = part.get_filename()
                                    if filename:
                                        payload = part.get_payload(decode=True)
                                        if filename.lower().endswith('.pdf'):
                                            try:
                                                pdf_reader = PyPDF2.PdfReader(BytesIO(payload))
                                                for page in pdf_reader.pages:
                                                    attachments_text += page.extract_text() + "\n"
                                            except Exception as e:
                                                logger.error(f"Failed to read PDF attachment {filename}: {e}")
                                        elif filename.lower().endswith('.txt'):
                                            attachments_text += payload.decode(errors='ignore') + "\n"
                                            
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body = payload.decode(errors='ignore')
                        
                        full_content = body
                        if attachments_text:
                            full_content += "\n\n--- Attachments ---\n" + attachments_text
                            
                        emails.append({
                            "id": str(e_id),
                            "subject": subject,
                            "from": from_,
                            "body": full_content,
                            "date": date
                        })
            return emails
        except Exception as e:
            logger.error(f"Failed to scrape emails: {e}")
            return []

    def scrape_latest_mess_menu(self, redis_client=None):
        try:
            self.connect()
            self.mail.select("inbox")
            status, messages = self.mail.search(None, '(SUBJECT "mess" SUBJECT "menu")')
            if status != "OK" or not messages[0]:
                return None
                
            email_ids = messages[0].split()
            
            # Iterate backwards (newest to oldest) to find the latest one WITH a PDF
            for e_id in reversed(email_ids):
                status, msg_data = self.mail.fetch(e_id, "(RFC822)")
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject, encoding = decode_header(msg.get("Subject", ""))[0]
                        if isinstance(subject, bytes):
                            try:
                                subject = subject.decode(encoding if encoding else "utf-8")
                            except:
                                subject = str(subject)
                        
                        date = msg.get("Date")
                        attachments_text = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_disposition = str(part.get("Content-Disposition"))
                                if "attachment" in content_disposition:
                                    filename = part.get_filename()
                                    if filename and filename.lower().endswith('.pdf'):
                                        payload = part.get_payload(decode=True)
                                        try:
                                            pdf_reader = PyPDF2.PdfReader(BytesIO(payload))
                                            for page in pdf_reader.pages:
                                                extracted = page.extract_text()
                                                if extracted:
                                                    attachments_text += extracted + "\n"
                                        except Exception as e:
                                            logger.error(f"Failed to read Mess Menu PDF attachment: {e}")
                                            if redis_client:
                                                push_log(redis_client, f"PyPDF2 error on {filename}: {e}")
                        
                        if attachments_text.strip():
                            if redis_client:
                                push_log(redis_client, f"Successfully extracted {len(attachments_text)} chars from {filename}")
                            return {
                                "id": str(e_id.decode()),
                                "subject": subject,
                                "date": date,
                                "attachments_text": attachments_text
                            }
            return None
        except Exception as e:
            import traceback
            logger.error(f"Failed to scrape mess menu: {e}")
            traceback.print_exc()
            return None

@celery_app.task
def fetch_and_process_mess_menu():
    """
    Fetches the latest email with 'mess menu' in the subject, extracts the PDF,
    formats it into a markdown table using the LLM, and replaces the existing mess menu in Qdrant.
    """
    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    
    username = os.getenv("GMAIL_USERNAME")
    password = os.getenv("GMAIL_PASSWORD")
    if not username or not password:
        return
        
    scraper = EmailScraper(username, password)
    push_log(redis_client, "Searching for latest Mess Menu email...")
    menu_data = scraper.scrape_latest_mess_menu(redis_client=redis_client)
    
    if not menu_data:
        push_log(redis_client, "No Mess Menu email found.")
        return
        
    last_processed_id = redis_client.get("last_processed_mess_menu_id")
    if last_processed_id == menu_data["id"]:
        return # Already processed this specific email
        
    push_log(redis_client, f"Found new Mess Menu: {menu_data['subject']}. Parsing with LLM...")
    
    import datetime
    readable_time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    
    llm = get_llm(use_sum_key=True)
    prompt = f"The following is raw text extracted from a Mess Menu PDF sent on {menu_data['date']}. Convert this exact information into a clean, well-formatted Markdown Table. Above the table, add a clear H3 heading stating the Month and Year. Do not include any other conversational text.\n\nRaw Text:\n{menu_data['attachments_text']}"
    
    response = llm.invoke([HumanMessage(content=prompt)])
    markdown_table = _extract_and_clean_response(response.content)
    
    page_content = f"Source: Mess Menu\nDate Received: {menu_data['date']}\nIngestion Timestamp: {readable_time}\nSubject: {menu_data['subject']}\n\n{markdown_table}"
        
    doc = Document(
        page_content=page_content,
        metadata={"source": "mess_menu", "id": menu_data["id"], "timestamp": time.time()}
    )
    
    QdrantVectorStore.from_documents(
        [doc],
        embeddings,
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        collection_name="shortterm_db",
        force_recreate=False
    )
    
    redis_client.set("last_processed_mess_menu_id", menu_data["id"])
    push_log(redis_client, "Successfully updated the Mess Menu in shortterm_db.")

@celery_app.task
def fetch_and_summarize_emails():
    """
    Fetches the latest unread emails, summarizes them using Groq LLM, and embeds them into the Qdrant shortterm DB.
    """
    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    if redis_client.get("email_worker_active") != "True":
        logger.info("Email worker is inactive. Skipping execution.")
        return

    # Check Polling Rate
    polling_rate_hours = float(redis_client.get("email_worker_interval_hours") or "24.0")
    last_run = float(redis_client.get("email_worker_last_run") or "0.0")
    current_time = time.time()
    
    if current_time - last_run < (polling_rate_hours * 3600):
        logger.info(f"Skipping email task. Polling interval ({polling_rate_hours}h) has not elapsed.")
        return
        
    redis_client.set("email_worker_last_run", str(current_time))

    try:
        username = os.getenv("GMAIL_USERNAME")
        password = os.getenv("GMAIL_PASSWORD")
        if not username or not password:
            logger.error("Gmail credentials missing.")
            return

        scraper = EmailScraper(username, password)
        push_log(redis_client, "Scraping unread emails from Gmail...")
        emails = scraper.scrape_latest_emails(count=5)
        
        if not emails:
            push_log(redis_client, "No new emails found.")
            return

        push_log(redis_client, f"Found {len(emails)} new email(s). Summarizing...")
        docs = []
        
        for em in emails:
            llm = get_llm(use_sum_key=True)
            prompt = f"Summarize the following email body into a concise, informative paragraph for an AI assistant's memory. CRITICAL: If the email contains any tabular data, schedules, or structured lists, you MUST preserve and format them accurately as Markdown tables or lists below your summary paragraph.\n\nEmail Body:\n{em['body']}"
            response = llm.invoke([HumanMessage(content=prompt)])
            summary = _extract_and_clean_response(response.content)

            page_content = f"Date: {em['date']}\nFrom: {em['from']}\nSubject: {em['subject']}\nSummary: {summary}"
            docs.append(Document(
                page_content=page_content,
                metadata={"source": "email", "id": em["id"], "timestamp": time.time()}
            ))
            push_log(redis_client, f"Ingested email: {em['subject']}")
            
        if docs:
            QdrantVectorStore.from_documents(
                docs,
                embeddings,
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
                collection_name="shortterm_db",
                force_recreate=False
            )
            push_log(redis_client, f"Successfully embedded {len(docs)} new emails to shortterm_db.")
            
            # FIFO Cleanup Logic
            try:
                max_capacity = int(redis_client.get("email_worker_max_capacity") or 1000)
                q_client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
                count_result = q_client.count(collection_name="shortterm_db")
                
                if count_result.count > max_capacity:
                    excess = count_result.count - max_capacity
                    logger.info(f"Capacity exceeded ({count_result.count} > {max_capacity}). Deleting {excess} oldest records.")
                    
                    # Fetch all points and sort by timestamp in memory since we lack an index
                    records, _ = q_client.scroll(collection_name="shortterm_db", limit=10000, with_payload=True)
                    sorted_records = sorted(records, key=lambda x: x.payload.get("metadata", {}).get("timestamp", 0))
                    to_delete = [r.id for r in sorted_records[:excess]]
                    
                    if to_delete:
                        q_client.delete(collection_name="shortterm_db", points_selector=to_delete)
                        push_log(redis_client, f"Capacity exceeded ({count_result.count}/{max_capacity}). Deleted {len(to_delete)} oldest emails.")
            except Exception as qc_err:
                push_log(redis_client, f"Failed to enforce capacity: {qc_err}")
            
    except Exception as e:
        push_log(redis_client, f"Error in worker task: {e}")

@celery_app.task
def maintenance_cleanup_task():
    """
    Runs in the background to detect and remove duplicate entries in the shortterm_db.
    Groups by `metadata.id` or `metadata.source` and keeps the latest one.
    """
    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    if redis_client.get("maintenance_worker_active") != "True":
        return
        
    try:
        q_client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        collection_name = settings.QDRANT_SHORTTERM_COLLECTION
        
        # Check if collection exists
        try:
            q_client.get_collection(collection_name)
        except Exception:
            return

        records, _ = q_client.scroll(collection_name=collection_name, limit=10000, with_payload=True)
        
        if not records:
            return

        # Group by ID (emails) or Source (mess menu)
        groups = {}
        for r in records:
            meta = r.payload.get("metadata", {})
            dedup_key = meta.get("id") or meta.get("source")
            if dedup_key:
                if dedup_key not in groups:
                    groups[dedup_key] = []
                groups[dedup_key].append(r)
                
        to_delete = []
        for key, items in groups.items():
            if len(items) > 1:
                # Sort by timestamp, highest first
                items.sort(key=lambda x: float(x.payload.get("metadata", {}).get("timestamp", 0)), reverse=True)
                # Keep the first (latest), delete the rest
                for duplicate in items[1:]:
                    to_delete.append(duplicate.id)
                    
        if to_delete:
            q_client.delete(collection_name=collection_name, points_selector=to_delete)
            push_log(redis_client, f"Maintenance: Deleted {len(to_delete)} duplicate records from shortterm_db.")
            
    except Exception as e:
        push_log(redis_client, f"Maintenance task error: {e}")
