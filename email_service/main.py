from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import smtplib
from email.message import EmailMessage
import os

app = FastAPI(title="RAGnarok Email Microservice")

class EmailRequest(BaseModel):
    to_email: str
    otp: str

def send_otp_email(to_email: str, otp: str):
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_user or not smtp_password:
        raise Exception("SMTP_USER or SMTP_PASSWORD not configured on Render.")

    msg = EmailMessage()
    msg['Subject'] = 'Your RAGnarok Verification Code'
    msg['From'] = f"Iota Cluster <{smtp_user}>"
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

    if smtp_port == 465:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
    else:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        
    server.login(smtp_user, smtp_password)
    server.send_message(msg)
    server.quit()

@app.post("/send-email")
def send_email_endpoint(req: EmailRequest, x_api_key: str = Header(None)):
    expected_key = os.getenv("EMAIL_SERVICE_API_KEY")
    
    if not expected_key:
        raise HTTPException(status_code=500, detail="EMAIL_SERVICE_API_KEY not configured on server.")
        
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        send_otp_email(req.to_email, req.otp)
        return {"status": "success", "message": "Email sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # When deployed on Render, PORT is provided as an environment variable
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
