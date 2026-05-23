import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

async def main():
    load_dotenv('.env')
    client = AsyncOpenAI(
        api_key=os.getenv('LLM_API_KEY'),
        base_url=os.getenv('LLM_BASE_URL'),
    )
    try:
        response = await client.chat.completions.create(
            model=os.getenv('LLM_MODEL'),
            messages=[{'role': 'user', 'content': 'respond with json format'}],
            response_format={'type': 'json_object'},
            timeout=10
        )
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
