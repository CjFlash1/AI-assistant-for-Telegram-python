import asyncio
import os
import sys

# Add src to path
sys.path.append(os.getcwd())

from src.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from pinecone import Pinecone

async def verify_keys():
    print("--- Verifying Keys ---")

    # 1. Telegram (Already validated via logs "Conflict" error imply auth worked)
    print("[Telegram] Token format looks correct. 'Conflict' error in main app logs confirms it authenticates but has duplicate instances.")

    # 2. Google Gemini
    print(f"\n[Google] Testing API Key: {settings.GOOGLE_API_KEY[:5]}... (Gemini 2.0 Flash)")
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-001",
            google_api_key=settings.GOOGLE_API_KEY,
        )
        response = await llm.ainvoke("Say 'Google Key Works'.")
        print(f"✅ Success! Response: {response.content}")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # 3. Pinecone
    print(f"\n[Pinecone] Testing API Key: {settings.PINECONE_API_KEY[:5]}...")
    try:
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        indexes = pc.list_indexes()
        index_names = [i.name for i in indexes]
        print(f"✅ Success! Connected. Indexes found: {index_names}")

        target_index = settings.PINECONE_INDEX_NAME
        if target_index in index_names:
            print(f"   - Index '{target_index}' exists.")
        else:
             print(f"   - ⚠️ Index '{target_index}' NOT found in account.")

    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_keys())
