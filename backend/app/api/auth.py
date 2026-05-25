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

def send_otp_email(to_email: str, otp: str):
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"WARNING: SMTP not configured. OTP for {to_email} is {otp}")
        return

    msg = EmailMessage()
    msg['Subject'] = 'Your RAGnarok Verification Code'
    msg['From'] = f"Iota Cluster <{settings.SMTP_USER}>"
    msg['To'] = to_email

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #0D131F; color: #ffffff; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #141C2B; padding: 30px; border-radius: 12px; border: 1px solid #22304A;">
          <h2 style="color: #FBBF24; text-align: center;">Welcome to RAGnarok</h2>
          <p style="color: #cbd5e1; font-size: 16px; text-align: center;">Please use the following OTP to complete your registration. This code will expire in 5 minutes.</p>
          <div style="text-align: center; margin: 30px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #10b981; background-color: #0D131F; padding: 15px 30px; border-radius: 8px; border: 1px solid #304163;">
              {otp}
            </span>
          </div>
          <p style="color: #94a3b8; font-size: 12px; text-align: center;">If you did not request this, please ignore this email.</p>
          <hr style="border-color: #22304A; margin-top: 30px;" />
          <p style="color: #64748b; font-size: 10px; text-align: center; text-transform: uppercase; letter-spacing: 1px;">Iota Cluster • IIT Ropar</p>
        </div>
      </body>
    </html>
    """
    msg.set_content("Your OTP is: " + otp)
    msg.add_alternative(html_content, subtype='html')

    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT)
        else:
            server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
            server.starttls()
            
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")
        # Not re-raising here so it doesn't crash the background task, just logs it

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
