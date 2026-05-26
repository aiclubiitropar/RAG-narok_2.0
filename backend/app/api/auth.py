from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
import random
import string
import smtplib
from email.message import EmailMessage
import redis
from app.core.config import settings

router = APIRouter()
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

class OTPRequest(BaseModel):
    email: str

class OTPVerify(BaseModel):
    email: str
    otp: str

import httpx

def send_otp_email(to_email: str, otp: str):
    email_service_url = settings.EMAIL_SERVICE_URL
    api_key = settings.EMAIL_SERVICE_API_KEY
    
    if not email_service_url or not api_key:
        print(f"WARNING: Email microservice not configured. OTP for {to_email} is {otp}")
        return
        
    try:
        response = httpx.post(
            f"{email_service_url.rstrip('/')}/send-email",
            json={"to_email": to_email, "otp": otp},
            headers={"x-api-key": api_key},
            timeout=60.0
        )
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to trigger email microservice: {e}")

@router.post("/send-otp")
def send_otp(req: OTPRequest, background_tasks: BackgroundTasks):
    email = req.email.strip().lower()
    if not email.endswith("@iitrpr.ac.in"):
        raise HTTPException(status_code=400, detail="Only @iitrpr.ac.in accounts are permitted.")

    otp = ''.join(random.choices(string.digits, k=6))
    
    # Store in Redis with 5 minutes (300 seconds) expiration
    redis_client.setex(f"otp:{email}", 300, otp)
    
    # Send email in background to avoid blocking the HTTP response
    background_tasks.add_task(send_otp_email, email, otp)
    
    return {"message": "OTP sent successfully"}

@router.post("/verify-otp")
def verify_otp(req: OTPVerify):
    email = req.email.strip().lower()
    stored_otp = redis_client.get(f"otp:{email}")
    
    if not stored_otp:
        raise HTTPException(status_code=400, detail="OTP expired or not found. Please request a new one.")
        
    if stored_otp != req.otp.strip():
        raise HTTPException(status_code=400, detail="Invalid OTP.")
        
    # Delete OTP to prevent reuse
    redis_client.delete(f"otp:{email}")
    return {"message": "OTP verified successfully"}
