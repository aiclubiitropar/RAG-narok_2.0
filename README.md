---
title: RAG-narok Backend
emoji: 🚀
colorFrom: blue
colorTo: purple
sdk: docker
app_file: Dockerfile
pinned: false
---

# RAGnarok 2.0 🚀

RAGnarok is an intelligent, multi-agent AI Assistant customized specifically for the Iota Cluster / IIT Ropar campus. Built with a modern Agentic Retrieval-Augmented Generation (RAG) architecture, it acts as a centralized knowledge hub for everything from academic calendars and mess menus to administrative announcements.

## Architecture & Tech Stack

RAGnarok uses a decoupled full-stack architecture:

- **Frontend**: Next.js 16, React 19, TailwindCSS, Progressive Web App (PWA) ready.
- **Backend API**: FastAPI (Python), providing asynchronous HTTP and Server-Sent Events (SSE) streaming.
- **Agent Orchestration**: LangGraph, orchestrating a multi-tool agentic loop using Groq (Llama 3 70B).
- **Vector Database**: Qdrant, powering hybrid (dense + sparse keyword) semantic search over campus documents.
- **Background Tasks**: Celery + Redis, managing heavy data ingestion and asynchronous email (SMTP) dispatch.
- **Authentication**: Supabase Auth combined with a custom OTP verification flow via Redis & SMTP to enforce domain-restricted signups.
- **Long-term Memory**: Mem0, providing persistent cross-session user memory.

## Features

- ðŸ§  **Multi-Agent RAG**: Instead of just injecting context, the agent autonomously decides when to query the "Short-term" database (announcements), the "Long-term" database (static campus info), or fall back to live Web Search via DuckDuckGo.
- âš¡ **Real-time Streaming**: LLM tokens are streamed directly to the UI using SSE for immediate responsiveness.
- ðŸ›¡ï¸ **Custom OTP Auth**: Students sign up using their `@iitrpr.ac.in` emails. A 6-digit OTP is generated via Redis and emailed via standard SMTP to verify the account before it is registered in Supabase.
- ðŸ“± **Progressive Web App**: Fully installable on iOS and Android with a native app-like experience.
- ðŸ› ï¸ **Admin Dashboard**: Dedicated portal (`/admin`) to upload JSON context, trigger background Celery ingestion tasks, and manage system configuration.

## Setup Instructions

### 1. Prerequisites
- Node.js (v18+)
- Python (v3.10+)
- Redis Server (running on `localhost:6379`)
- Qdrant Vector Database (Cloud or Docker)
- Supabase Project

### 2. Environment Variables
You will need two `.env` files. 

**`backend/.env`**:
```env
# Groq & Mem0 API Keys
GROQ_API_KEYS=your_groq_api_key
MEM0_API_KEY=your_mem0_key

# Database
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_key
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0

# SMTP for Auth
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_iotacluster_email@gmail.com
SMTP_PASSWORD=your_app_password
```

**`frontend/.env.local`**:
```env
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Start the Backend

Open a terminal and start the Redis server.

In a new terminal, run the FastAPI backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or .\.venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In a new terminal, run the Celery worker (required for ingestion and emails):
```bash
cd backend
source .venv/bin/activate
celery -A worker.celery_app worker --loglevel=info -P threads
```

### 4. Start the Frontend
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` in your browser.

## Deployment Notes

- **Frontend**: Can be deployed seamlessly on Vercel.
- **Backend & Worker**: Can be deployed on Render, Heroku, or an AWS EC2 instance. Ensure Redis is accessible to the Celery worker.
- **HF Spaces**: If deploying to Hugging Face Spaces, you must use a Custom Docker Space that installs Node.js, Python, and Redis, and uses a `supervisord` configuration to run all services concurrently on port `7860`, or separate the frontend to Vercel and run only the backend on HF Spaces.
