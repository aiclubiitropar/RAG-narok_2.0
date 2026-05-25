import asyncio
import traceback
from fastapi import Request
from app.api.chat import chat_endpoint, ChatRequest

async def test():
    try:
        req = ChatRequest(message='hi')
        res = await chat_endpoint(req, "admin_user")
        print("Success:", res)
    except Exception as e:
        print("TRACEBACK:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
