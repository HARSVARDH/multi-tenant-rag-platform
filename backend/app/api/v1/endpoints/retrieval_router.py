import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any

from app.api.dependencies import get_current_user
from app.database.models.user import User
from app.retrieval.vector_search import VectorSearch
from app.retrieval.bm25 import BM25Search
from app.retrieval.hybrid_search import HybridSearch
from app.retrieval.reranker import Reranker
from app.retrieval.citations import CitationManager
from app.retrieval.evaluation import RAGEvaluator

router = APIRouter(prefix="/retrieval")
vector_search = VectorSearch()
bm25_search = BM25Search()
hybrid_search = HybridSearch()
reranker = Reranker()
citation_manager = CitationManager()
rag_evaluator = RAGEvaluator()


# Search and query schemas
class QueryRequest(BaseModel):
    query: str


class SourceDetail(BaseModel):
    document_id: str
    filename: str
    text: str
    chunk_index: int


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceDetail]


# Evaluation schemas
class RetrievalEvalItem(BaseModel):
    query: str
    expected_document_ids: List[uuid.UUID]


class RetrievalEvalRequest(BaseModel):
    dataset: List[RetrievalEvalItem]
    limit: int = 5


class RetrievalEvalResponse(BaseModel):
    hit_rate: float
    mrr: float


class GenerationEvalRequest(BaseModel):
    query: str
    contexts: List[str]
    answer: str


class GenerationEvalResponse(BaseModel):
    faithfulness: float
    relevance: float


@router.get("/search")
def search_documents(
    q: str = Query(..., description="Query string for search"),
    limit: int = Query(
        5, ge=1, le=50, description="Max number of results to return"
    ),
    search_type: str = Query(
        "hybrid", description="Search type: 'vector', 'keyword', or 'hybrid'"
    ),
    rerank: bool = Query(
        True, description="Whether to rerank results using a cross-encoder"
    ),
    current_user: User = Depends(get_current_user),
):
    try:
        fetch_limit = limit * 2 if rerank else limit

        if search_type == "vector":
            results = vector_search.search(q, current_user.id, limit=fetch_limit)
        elif search_type == "keyword":
            results = bm25_search.search(q, current_user.id, limit=fetch_limit)
        elif search_type == "hybrid":
            results = hybrid_search.search(q, current_user.id, limit=fetch_limit)
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid search type. Choose: 'vector', 'keyword', or 'hybrid'",
            )

        if rerank:
            results = reranker.rerank(q, results, limit=limit)

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/query", response_model=QueryResponse)
def query_documents(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        response_data = citation_manager.generate_answer_with_citations(
            request.query, current_user.id
        )
        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/evaluate/retrieval", response_model=RetrievalEvalResponse)
def evaluate_retrieval_endpoint(
    request: RetrievalEvalRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        # Convert request items to dicts
        dataset_dicts = []
        for item in request.dataset:
            dataset_dicts.append(
                {
                    "query": item.query,
                    "expected_document_ids": [
                        str(eid) for eid in item.expected_document_ids
                    ],
                }
            )

        results = rag_evaluator.evaluate_retrieval(
            dataset_dicts, current_user.id, limit=request.limit
        )
        return results
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Retrieval evaluation failed: {str(e)}"
        )


@router.post("/evaluate/generation", response_model=GenerationEvalResponse)
def evaluate_generation_endpoint(
    request: GenerationEvalRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        results = rag_evaluator.evaluate_generation(
            request.query, request.contexts, request.answer
        )
        return results
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Generation evaluation failed: {str(e)}"
        )
