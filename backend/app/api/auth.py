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

from supabase import create_client

# Initialize Supabase Admin Client
# We use the service_role key to allow administrative actions like resetting passwords
supabase_admin = None
if settings.SUPABASE_URL and settings.SUPABASE_KEY:
    supabase_admin = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

class OTPVerify(BaseModel):
    email: str
    otp: str

class PasswordReset(BaseModel):
    email: str
    otp: str
    new_password: str

import httpx

def send_otp_email(to_email: str, otp: str):
    email_service_url = settings.EMAIL_SERVICE_URL
    api_key = settings.EMAIL_SERVICE_API_KEY
    
    if not email_service_url or not api_key:
        print(f"WARNING: Email microservice not configured. OTP for {to_email} is {otp}")
        return
        
    try:
        response = httpx.post(
            email_service_url,
            json={"to_email": to_email, "otp": otp, "apiKey": api_key},
            timeout=60.0,
            follow_redirects=True
        )
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to trigger email microservice: {e}")

@router.post("/send-otp")
def send_otp(req: OTPRequest, background_tasks: BackgroundTasks):
    email = req.email.strip().lower()
    if not email.endswith("@iitrpr.ac.in"):
        raise HTTPException(status_code=400, detail="Only @iitrpr.ac.in accounts are permitted.")

    # Generate 6 digit OTP
    otp = str(random.randint(100000, 999999))
    
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

@router.post("/reset-password")
def reset_password(req: PasswordReset):
    email = req.email.strip().lower()
    
    # 1. Verify OTP
    stored_otp = redis_client.get(f"otp:{email}")
    if not stored_otp:
        raise HTTPException(status_code=400, detail="OTP expired or not found. Please request a new one.")
        
    if stored_otp != req.otp.strip():
        raise HTTPException(status_code=400, detail="Invalid OTP.")
        
    # 2. Check Supabase Admin config
    if not supabase_admin:
        raise HTTPException(status_code=500, detail="Supabase Admin not configured on backend.")
        
    # 3. Find the user's UUID in Supabase
    target_uid = None
    try:
        # Note: In a massive app, list_users() needs pagination. 
        # For a campus app, this is fine to find the user.
        users_resp = supabase_admin.auth.admin.list_users()
        for u in users_resp:
            if u.email.lower() == email:
                target_uid = u.id
                break
    except Exception as e:
        print(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail="Error communicating with authentication server.")
        
    if not target_uid:
        raise HTTPException(status_code=404, detail="No account found with this email address.")
        
    # 4. Update the password
    try:
        supabase_admin.auth.admin.update_user_by_id(target_uid, {"password": req.new_password})
    except Exception as e:
        print(f"Error updating password: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset password.")
        
    # 5. Clean up OTP on success
    redis_client.delete(f"otp:{email}")
    return {"message": "Password updated successfully"}
