import httpx
import asyncio


async def test_streaming():
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", "http://127.0.0.1:8000/chat") as response:
            async for chunk in response.aiter_text():
                print(chunk.strip())  # Print received data


asyncio.run(test_streaming())
