from worker.celery_app import celery_app
from app.core.llm import get_groq_llm
import logging
from langchain_core.messages import HumanMessage
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from app.tools.retrieval import embeddings
import os
import imaplib
import email
from email.header import decode_header
import redis
import time
import PyPDF2
from io import BytesIO
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

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
                        blocklist = ["no-reply@accounts.google.com", "security alert", "unstop", "linkedin", "kaggle", "team unstop", "canva", "noreply@github.com", "noreply", "feed","huggingface","instagram","udacity","udemy","supabase"]
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
            llm = get_groq_llm()
            prompt = f"Summarize the following email body into a concise, informative paragraph for an AI assistant's memory: {em['body']}"
            response = llm.invoke([HumanMessage(content=prompt)])
            summary = response.content.strip()

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
                url=os.getenv("QDRANT_URL"),
                api_key=os.getenv("QDRANT_API_KEY"),
                collection_name="shortterm_db",
                force_recreate=False
            )
            push_log(redis_client, f"Successfully embedded {len(docs)} new emails to shortterm_db.")
            
            # FIFO Cleanup Logic
            try:
                max_capacity = int(redis_client.get("email_worker_max_capacity") or 1000)
                q_client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
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
