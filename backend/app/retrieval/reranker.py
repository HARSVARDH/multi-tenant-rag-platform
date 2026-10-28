import json
import httpx
from typing import List, Dict, Any
from openai import OpenAI
from app.core.config import settings


class Reranker:

    def __init__(self, openai_api_key: str = None, cohere_api_key: str = None):
        self.openai_api_key = openai_api_key or settings.OPENAI_API_KEY
        self.cohere_api_key = cohere_api_key or settings.COHERE_API_KEY
        self.openai_client = (
            OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None
        )

    def rerank(
        self, query: str, documents: List[Dict[str, Any]], limit: int = 5
    ) -> List[Dict[str, Any]]:
        if not documents:
            return []

        # 1. Try Cohere Rerank if configured
        if self.cohere_api_key:
            try:
                cohere_results = self._rerank_cohere(query, documents, limit)
                if cohere_results:
                    return cohere_results
            except Exception as e:
                print(
                    f"Warning: Cohere reranking failed: {e}. Falling back to OpenAI."
                )

        # 2. Try OpenAI LLM-based Reranker
        if self.openai_client:
            try:
                openai_results = self._rerank_openai(query, documents, limit)
                if openai_results:
                    return openai_results
            except Exception as e:
                print(
                    f"Warning: OpenAI reranking failed: {e}. Falling back to default scoring."
                )

        # 3. Fallback: return documents unchanged up to limit
        return documents[:limit]

    def _rerank_cohere(
        self, query: str, documents: List[Dict[str, Any]], limit: int
    ) -> List[Dict[str, Any]]:
        texts = [doc["text"] for doc in documents]

        headers = {
            "Authorization": f"Bearer {self.cohere_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "rerank-english-v3.0",
            "query": query,
            "documents": texts,
            "top_n": limit,
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                "https://api.cohere.com/v1/rerank", headers=headers, json=payload
            )
            if response.status_code != 200:
                raise Exception(
                    f"Cohere API returned status {response.status_code}: {response.text}"
                )

            data = response.json()
            results = data.get("results", [])

            reranked_docs = []
            for item in results:
                idx = item["index"]
                score = item["relevance_score"]

                doc_copy = documents[idx].copy()
                doc_copy["score"] = float(score)
                reranked_docs.append(doc_copy)

            return reranked_docs

    def _rerank_openai(
        self, query: str, documents: List[Dict[str, Any]], limit: int
    ) -> List[Dict[str, Any]]:
        doc_texts = [
            f"Doc {idx}: {doc['text']}" for idx, doc in enumerate(documents)
        ]

        prompt = (
            f"Query: {query}\n\n"
            "Score the relevance of each document below to the query on a scale from 0.0 (completely irrelevant) to 1.0 (highly relevant).\n"
            "Respond ONLY with a JSON list of numbers representing the scores, e.g., [0.95, 0.20, 0.45] in the same order as the documents.\n\n"
            + "\n\n".join(doc_texts)
        )

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise search ranker. Output ONLY a valid JSON list of numbers, e.g., [0.9, 0.1, 0.5]",
                },
                {"role": "user", "content": prompt},
            ],
            response_format=(
                {"type": "json_object"}
                if hasattr(self.openai_client, "chat")
                else None
            ),
            temperature=0.0,
        )

        content = response.choices[0].message.content.strip()
        data = json.loads(content)

        if isinstance(data, dict):
            # Locate any list in the dictionary
            for val in data.values():
                if isinstance(val, list):
                    scores = val
                    break
            else:
                scores = list(data.values())
        elif isinstance(data, list):
            scores = data
        else:
            raise ValueError("Invalid format returned by LLM")

        if len(scores) != len(documents):
            raise ValueError(
                f"Mismatch: got {len(scores)} scores for {len(documents)} documents"
            )

        scored_docs = []
        for doc, score in zip(documents, scores):
            doc_copy = doc.copy()
            doc_copy["score"] = float(score)
            scored_docs.append(doc_copy)

        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        return scored_docs[:limit]
