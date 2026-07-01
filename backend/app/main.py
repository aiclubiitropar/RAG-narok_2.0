from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.api import chat, admin, auth

app = FastAPI(
    title="RAGnarok 2.0 API",
    description="Backend for the Multi-Agent RAGnarok 2.0 AI Assistant",
    version="2.0.0"
)

from app.core.config import settings

# CORS configuration
origins = [
    "https://rag-narok.vercel.app"
]

if settings.EXTERNAL_URL:
    origins.append(settings.EXTERNAL_URL.rstrip("/"))
if settings.EXTERNAL_URL1:
    origins.append(settings.EXTERNAL_URL1.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HealthResponse(BaseModel):
    status: str

@app.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok"}

app.include_router(chat.router, prefix="/api")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(auth.router, prefix="/api/auth")

