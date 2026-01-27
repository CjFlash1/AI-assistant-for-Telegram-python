
import os
import sys
from dotenv import load_dotenv

# Force flush
sys.stdout.reconfigure(encoding='utf-8')

print("Starting verification...", flush=True)

load_dotenv()
PINECONE_KEY = os.getenv("PINECONE_API_KEY")
print(f"Key loaded: {PINECONE_KEY[:5]}...", flush=True)

try:
    from pinecone import Pinecone
    print("Pinecone imported.", flush=True)
    pc = Pinecone(api_key=PINECONE_KEY)
    print("Pinecone client initialized.", flush=True)
    indexes = pc.list_indexes()
    print(f"Indexes: {indexes}", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
