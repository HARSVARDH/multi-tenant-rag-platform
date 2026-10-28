import uuid
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.core.config import settings
from app.ingestion.embeddings import OpenAIEmbeddings


class VectorSearch:

    def __init__(self, qdrant_host: str = None, qdrant_port: int = None):
        host = qdrant_host or settings.QDRANT_HOST
        port = qdrant_port or settings.QDRANT_PORT

        try:
            self.qdrant = QdrantClient(host=host, port=port)
            self.qdrant.get_collections()
        except Exception:
            if host == "qdrant":
                self.qdrant = QdrantClient(host="localhost", port=port)
            else:
                raise

        self.embeddings = OpenAIEmbeddings()
        self.collection_name = "documents"

    def search(
        self, query: str, owner_id: uuid.UUID, limit: int = 5
    ) -> List[Dict[str, Any]]:
        query_vector = self.embeddings.get_embeddings([query])[0]

        tenant_filter = Filter(
            must=[
                FieldCondition(
                    key="owner_id", match=MatchValue(value=str(owner_id))
                )
            ]
        )

        results = self.qdrant.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=tenant_filter,
            limit=limit,
        )

        hits = []
        for hit in results.points:
            hits.append(
                {
                    "id": hit.id,
                    "score": hit.score,
                    "document_id": hit.payload.get("document_id"),
                    "filename": hit.payload.get("filename"),
                    "chunk_index": hit.payload.get("chunk_index"),
                    "text": hit.payload.get("text"),
                }
            )

        return hits
