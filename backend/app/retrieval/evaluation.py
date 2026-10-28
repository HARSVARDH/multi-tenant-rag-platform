import uuid
import json
from typing import List, Dict, Any
from openai import OpenAI

from app.core.config import settings
from app.retrieval.hybrid_search import HybridSearch


class RAGEvaluator:

    def __init__(self, qdrant_host: str = None, qdrant_port: int = None):
        self.hybrid_search = HybridSearch(qdrant_host, qdrant_port)
        self.client = (
            OpenAI(api_key=settings.OPENAI_API_KEY)
            if settings.OPENAI_API_KEY
            else None
        )

    def evaluate_retrieval(
        self, dataset: List[Dict[str, Any]], owner_id: uuid.UUID, limit: int = 5
    ) -> Dict[str, float]:
        if not dataset:
            return {"hit_rate": 0.0, "mrr": 0.0}

        hits = 0
        rr_sum = 0.0
        total = len(dataset)

        for item in dataset:
            query = item.get("query")
            expected_ids = {
                str(eid) for eid in item.get("expected_document_ids", [])
            }

            search_results = self.hybrid_search.search(
                query, owner_id, limit=limit
            )
            retrieved_ids = [
                str(doc.get("document_id")) for doc in search_results
            ]

            has_hit = False
            for idx, rid in enumerate(retrieved_ids):
                if rid in expected_ids:
                    if not has_hit:
                        hits += 1
                        has_hit = True

            for idx, rid in enumerate(retrieved_ids):
                if rid in expected_ids:
                    rr_sum += 1.0 / (idx + 1)
                    break

        return {
            "hit_rate": float(hits / total),
            "mrr": float(rr_sum / total),
        }

    def evaluate_generation(
        self, query: str, contexts: List[str], answer: str
    ) -> Dict[str, float]:
        default_scores = {"faithfulness": 0.0, "relevance": 0.0}
        if not self.client:
            return default_scores

        contexts_text = "\n\n".join(
            [f"Context {idx}:\n{text}" for idx, text in enumerate(contexts)]
        )

        prompt = (
            "You are an expert AI evaluator assessing a Retrieval-Augmented Generation (RAG) system.\n"
            "Evaluate the system's generated answer based on the query and retrieved contexts.\n\n"
            f"Query: {query}\n\n"
            f"Retrieved Contexts:\n{contexts_text}\n\n"
            f"Generated Answer: {answer}\n\n"
            "Provide two scores between 0.0 and 1.0:\n"
            "1. 'faithfulness': How well does the answer ground itself strictly in the contexts? (1.0 = completely faithful, no hallucinations; 0.0 = completely hallucinated or contains facts not present in contexts).\n"
            "2. 'relevance': How directly and accurately does the answer address the query? (1.0 = highly relevant and helpful; 0.0 = completely off-topic or fails to answer the question).\n\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            "  \"faithfulness\": 0.95,\n"
            "  \"relevance\": 0.90\n"
            "}\n"
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise evaluator. Output ONLY a valid JSON object with the keys 'faithfulness' and 'relevance'.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )
            content = response.choices[0].message.content.strip()
            data = json.loads(content)
            return {
                "faithfulness": float(data.get("faithfulness", 0.0)),
                "relevance": float(data.get("relevance", 0.0)),
            }
        except Exception as e:
            print(f"Warning: Generation evaluation failed: {e}")
            return default_scores
