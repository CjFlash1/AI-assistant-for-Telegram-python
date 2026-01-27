from pinecone import Pinecone, ServerlessSpec
from src.config import settings
import logging

logger = logging.getLogger(__name__)

class VectorDBService:
    def __init__(self):
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index_name = settings.PINECONE_INDEX_NAME
        self.namespace = settings.PINECONE_NAMESPACE

        # Check if index exists, if not create (optional, maybe unsafe for existing prod data)
        # For now, we assume index exists as per n8n workflow
        if self.index_name not in [i.name for i in self.pc.list_indexes()]:
            logger.warning(f"Index {self.index_name} does not exist!")

        self.index = self.pc.Index(self.index_name)

    async def upsert(self, id: str, vector: list[float], metadata: dict):
        """Upserts a vector with metadata into Pinecone."""
        try:
            self.index.upsert(
                vectors=[(id, vector, metadata)],
                namespace=self.namespace
            )
            logger.info(f"Upserted vector {id} to namespace {self.namespace}")
            return True
        except Exception as e:
            logger.error(f"Error upserting to Pinecone: {e}")
            return False

    async def search(self, vector: list[float], top_k: int = 5):
        """Searches for similar vectors."""
        try:
            results = self.index.query(
                vector=vector,
                top_k=top_k,
                include_metadata=True,
                namespace=self.namespace
            )
            return results
        except Exception as e:
            logger.error(f"Error searching Pinecone: {e}")
            return None
