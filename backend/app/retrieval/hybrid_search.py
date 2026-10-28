import uuid
from typing import List, Dict, Any
from app.retrieval.vector_search import VectorSearch
from app.retrieval.bm25 import BM25Search


class HybridSearch:

    def __init__(self, qdrant_host: str = None, qdrant_port: int = None):
        self.vector_search = VectorSearch(qdrant_host, qdrant_port)
        self.bm25_search = BM25Search(qdrant_host, qdrant_port)

    def search(
        self, query: str, owner_id: uuid.UUID, limit: int = 5, k: int = 60
    ) -> List[Dict[str, Any]]:
        # Fetch a larger pool of items from both systems to fuse ranks effectively
        fetch_limit = max(limit * 2, 20)

        dense_results = self.vector_search.search(
            query, owner_id, limit=fetch_limit
        )
        sparse_results = self.bm25_search.search(
            query, owner_id, limit=fetch_limit
        )

        rrf_scores = {}
        doc_details = {}

        # Dense rank fusion
        for rank, doc in enumerate(dense_results):
            doc_id = doc["id"]
            doc_details[doc_id] = doc
            rrf_scores[doc_id] = (
                rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            )

        # Sparse rank fusion
        for rank, doc in enumerate(sparse_results):
            doc_id = doc["id"]
            doc_details[doc_id] = doc
            rrf_scores[doc_id] = (
                rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            )

        sorted_doc_ids = sorted(
            rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True
        )

        fused_results = []
        for doc_id in sorted_doc_ids[:limit]:
            doc = doc_details[doc_id].copy()
            doc["score"] = float(rrf_scores[doc_id])
            fused_results.append(doc)

        return fused_results
