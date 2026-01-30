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
            logger.warning(f"Index {self.index_name} does not exist! Creating...")
            self.pc.create_index(
                name=self.index_name,
                dimension=768, # all-mpnet-base-v2
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )

        # Check dimension compatibility
        index_info = self.pc.describe_index(self.index_name)
        if index_info.dimension != 768:
            logger.error(f"Dimension Mismatch: Index has {index_info.dimension}, Model has 768. Recreating index...")
            self.pc.delete_index(self.index_name)
            self.pc.create_index(
                name=self.index_name,
                dimension=768,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )

        self.index = self.pc.Index(self.index_name)

    async def upsert(self, id: str, vector: list[float], metadata: dict):
        """Upserts a vector with metadata into Pinecone."""
        try:
            # Clean metadata: Remove keys with None values
            metadata = {k: v for k, v in metadata.items() if v is not None}

            logger.info(f"Upserting vector {id} (len: {len(vector)}) to namespace {self.namespace}")
            self.index.upsert(
                vectors=[(id, vector, metadata)],
                namespace=self.namespace
            )
            logger.info(f"Upsert successful for {id}")
            return True
        except Exception as e:
            logger.error(f"Error upserting to Pinecone: {e}")
            return False

    async def search(self, vector: list[float], top_k: int = 5, filter: dict = None):
        """Searches for similar vectors with optional metadata filtering."""
        try:
            # Clean filter: Remove keys with None values
            if filter:
                filter = {k: v for k, v in filter.items() if v is not None}
                if not filter: filter = None

            logger.info(f"Searching Pinecone (len: {len(vector)}) with filter: {filter}")
            results = self.index.query(
                vector=vector,
                top_k=top_k,
                include_metadata=True,
                namespace=self.namespace,
                filter=filter
            )
            logger.info(f"Search Results: Found {len(results.matches)} matches")
            for m in results.matches:
                logger.debug(f" - Match: {m.id} (Score: {m.score})")
            return results
        except Exception as e:
            logger.error(f"Error searching Pinecone: {e}")
            return None
