import asyncio
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
# pyrefly: ignore [missing-import]
from langchain_core.messages import HumanMessage
from app.agents.graph import app_graph
from app.memory.mem0_manager import add_user_memory, get_user_memory
from app.api.deps import get_current_user

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    chat_history: Optional[List[dict]] = None

class ChatResponse(BaseModel):
    reply: str
    route_taken: Optional[str] = None

from fastapi.responses import StreamingResponse
import json

@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest, current_user_id: str = Depends(get_current_user)):
    # Retrieve recent episodic memory for context in a separate thread to prevent blocking
    past_memories = await asyncio.to_thread(get_user_memory, current_user_id, request.message)
    context_str = ""
    if past_memories:
        memories_list = past_memories.get("results", past_memories.get("memories", [])) if isinstance(past_memories, dict) else past_memories
        if isinstance(memories_list, list):
            texts = [m.get("memory", m.get("text", str(m))) if isinstance(m, dict) else str(m) for m in memories_list]
            context_str = "\n".join(texts)
    
    # Construct input with memory context if any
    input_text = request.message
    if context_str:
        input_text = f"Context from previous conversations:\n{context_str}\n\nUser: {request.message}"
    
    # Build messages list from history
    msgs = []
    if request.chat_history:
        for m in request.chat_history:
            if m.get("role") == "user":
                msgs.append(HumanMessage(content=m.get("content", "")))
            else:
                from langchain_core.messages import AIMessage
                msgs.append(AIMessage(content=m.get("content", "")))
                
    msgs.append(HumanMessage(content=input_text))
    
    initial_state = {
        "messages": msgs,
        "next_node": ""
    }

    async def event_generator():
        try:
            final_reply = ""
            route_taken = "general_agent" # default fallback
            
            async for event in app_graph.astream_events(initial_state, version="v2"):
                kind = event["event"]
                name = event.get("name", "")
                
                # Identify which tool was called to determine the route
                if kind == "on_tool_start":
                    if name == "query_academic_guidelines":
                        route_taken = "academic_agent"
                    elif name == "query_campus_info":
                        route_taken = "campus_agent"
                
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"].content
                    if chunk:
                        final_reply += chunk
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            
            # Save to memory asynchronously without blocking the event loop
            await asyncio.to_thread(add_user_memory, current_user_id, f"User: {request.message}\nAssistant: {final_reply}")
            
            # Yield the final route metadata
            yield f"data: {json.dumps({'route_taken': route_taken})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, current_user_id: str = Depends(get_current_user)):
    # Fallback non-streaming endpoint
    # Retrieve recent episodic memory for context in a separate thread
    past_memories = await asyncio.to_thread(get_user_memory, current_user_id, request.message)
    context_str = ""
    if past_memories:
        memories_list = past_memories.get("results", past_memories.get("memories", [])) if isinstance(past_memories, dict) else past_memories
        if isinstance(memories_list, list):
            texts = [m.get("memory", m.get("text", str(m))) if isinstance(m, dict) else str(m) for m in memories_list]
            context_str = "\n".join(texts)
    
    # Construct input with memory context if any
    input_text = request.message
    if context_str:
        input_text = f"Context from previous conversations:\n{context_str}\n\nUser: {request.message}"
    
    # Build messages list from history
    msgs = []
    if request.chat_history:
        for m in request.chat_history:
            if m.get("role") == "user":
                msgs.append(HumanMessage(content=m.get("content", "")))
            else:
                from langchain_core.messages import AIMessage
                msgs.append(AIMessage(content=m.get("content", "")))
                
    msgs.append(HumanMessage(content=input_text))
    
    
    initial_state = {
        "messages": msgs,
        "next_node": ""
    }
    
    # Run the graph asynchronously
    try:
        final_state = await app_graph.ainvoke(initial_state)
        # The reply is the last message in the list
        reply = final_state["messages"][-1].content
        
        # Save to memory asynchronously
        await asyncio.to_thread(add_user_memory, current_user_id, f"User: {request.message}\nAssistant: {reply}")
        
        return ChatResponse(
            reply=reply,
            route_taken=final_state.get("next_node")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
