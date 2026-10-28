import uuid
import re
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from rank_bm25 import BM25Okapi

from app.core.config import settings


class BM25Search:

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

        self.collection_name = "documents"

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def search(
        self, query: str, owner_id: uuid.UUID, limit: int = 5
    ) -> List[Dict[str, Any]]:
        scroll_filter = Filter(
            must=[
                FieldCondition(
                    key="owner_id", match=MatchValue(value=str(owner_id))
                )
            ]
        )

        points = []
        next_page = None

        while True:
            results, next_page = self.qdrant.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=100,
                offset=next_page,
                with_payload=True,
                with_vectors=False,
            )
            points.extend(results)
            if not next_page:
                break

        if not points:
            return []

        corpus_texts = []
        corpus_points = []
        for p in points:
            text = p.payload.get("text", "")
            corpus_texts.append(text)
            corpus_points.append(p)

        tokenized_corpus = [self._tokenize(t) for t in corpus_texts]
        bm25 = BM25Okapi(tokenized_corpus)

        tokenized_query = self._tokenize(query)
        doc_scores = bm25.get_scores(tokenized_query)

        scored_points = []
        for p, score in zip(corpus_points, doc_scores):
            if score > 0:
                scored_points.append((p, score))

        scored_points.sort(key=lambda x: x[1], reverse=True)

        hits = []
        for p, score in scored_points[:limit]:
            hits.append(
                {
                    "id": p.id,
                    "score": float(score),
                    "document_id": p.payload.get("document_id"),
                    "filename": p.payload.get("filename"),
                    "chunk_index": p.payload.get("chunk_index"),
                    "text": p.payload.get("text"),
                }
            )

        return hits
