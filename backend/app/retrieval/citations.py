import uuid
import re
from typing import List, Dict, Any
from openai import OpenAI

from app.core.config import settings
from app.retrieval.hybrid_search import HybridSearch
from app.retrieval.reranker import Reranker


class CitationManager:

    def __init__(self, qdrant_host: str = None, qdrant_port: int = None):
        self.hybrid_search = HybridSearch(qdrant_host, qdrant_port)
        self.reranker = Reranker()
        self.client = (
            OpenAI(api_key=settings.OPENAI_API_KEY)
            if settings.OPENAI_API_KEY
            else None
        )

    def generate_answer_with_citations(
        self, query: str, owner_id: uuid.UUID
    ) -> Dict[str, Any]:
        candidates = self.hybrid_search.search(query, owner_id, limit=10)
        retrieved_docs = self.reranker.rerank(query, candidates, limit=5)

        if not retrieved_docs:
            return {
                "answer": "I could not find any relevant documents to answer your query.",
                "sources": [],
            }

        if not self.client:
            return {
                "answer": "OpenAI client is not configured. Snippets:\n\n"
                + "\n\n".join(
                    [
                        f"[{idx}] {doc['filename']}: {doc['text']}"
                        for idx, doc in enumerate(retrieved_docs)
                    ]
                ),
                "sources": retrieved_docs,
            }

        contexts = []
        for idx, doc in enumerate(retrieved_docs):
            contexts.append(
                f"Document [{idx}]:\nFilename: {doc['filename']}\nContent: {doc['text']}"
            )
        contexts_block = "\n\n".join(contexts)

        prompt = (
            "You are a precise Q&A assistant. Answer the user's query based ONLY on the provided document contexts.\n"
            "Every time you reference facts from a context, cite it by placing the document index in square brackets, e.g. [0], [1].\n"
            "If multiple documents support a statement, cite all of them, e.g. [0][2].\n"
            "Do not make up facts. If the contexts do not contain the answer, reply with: 'I cannot find the answer in the provided documents.'\n\n"
            f"Contexts:\n{contexts_block}\n\n"
            f"Query: {query}\n"
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise search and citation assistant. Only answer based on provided contexts. Do not hallucinate citations.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )
            answer = response.choices[0].message.content.strip()

            matches = re.findall(r"\[(\d+)\]", answer)
            cited_indices = set()
            for m in matches:
                idx = int(m)
                if 0 <= idx < len(retrieved_docs):
                    cited_indices.add(idx)

            sources = []
            seen_doc_ids = set()
            for idx in sorted(list(cited_indices)):
                doc = retrieved_docs[idx]
                doc_id = doc.get("document_id")

                if doc_id not in seen_doc_ids:
                    seen_doc_ids.add(doc_id)
                    sources.append(
                        {
                            "document_id": doc_id,
                            "filename": doc.get("filename"),
                            "text": doc.get("text"),
                            "chunk_index": doc.get("chunk_index"),
                        }
                    )

            return {"answer": answer, "sources": sources}

        except Exception as e:
            return {
                "answer": f"An error occurred while generating the answer: {str(e)}",
                "sources": [],
            }
