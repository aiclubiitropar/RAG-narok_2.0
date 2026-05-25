import asyncio
import json
from langchain_core.messages import HumanMessage
from app.agents.graph import app_graph

async def test_stream():
    initial_state = {
        "messages": [HumanMessage(content="hi")],
        "next_node": ""
    }
    
    async for event in app_graph.astream_events(initial_state, version="v2"):
        kind = event["event"]
        node = event.get("metadata", {}).get("langgraph_node", "")
        
        if kind == "on_chat_model_stream" and node != "supervisor":
            chunk = event["data"]["chunk"].content
            if chunk:
                print(f"CHUNK: {chunk}", end="", flush=True)

if __name__ == "__main__":
    asyncio.run(test_stream())
