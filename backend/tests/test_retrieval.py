import uuid
from unittest.mock import MagicMock, patch
import pytest

from app.retrieval.vector_search import VectorSearch
from app.ingestion.pipeline import IngestionPipeline


@patch("app.retrieval.vector_search.QdrantClient")
@patch("app.retrieval.vector_search.OpenAIEmbeddings")
def test_vector_search_tenant_isolation(mock_embeddings_cls, mock_qdrant_cls):
    # Mock embeddings
    mock_embeddings = MagicMock()
    mock_embeddings.get_embeddings.return_value = [[0.1] * 1536]
    mock_embeddings_cls.return_value = mock_embeddings

    # Mock Qdrant
    mock_qdrant = MagicMock()
    mock_qdrant.query_points.return_value = MagicMock(points=[])
    mock_qdrant_cls.return_value = mock_qdrant

    owner_id = uuid.uuid4()
    search_service = VectorSearch()
    search_service.search("test query", owner_id, limit=3)

    # Verify search is filtered by owner_id
    args, kwargs = mock_qdrant.query_points.call_args
    assert kwargs["collection_name"] == "documents"
    assert kwargs["limit"] == 3
    
    tenant_filter = kwargs["query_filter"]
    assert tenant_filter is not None
    # Check that owner_id is in the conditions
    condition = tenant_filter.must[0]
    assert condition.key == "owner_id"
    assert condition.match.value == str(owner_id)


@patch("app.ingestion.pipeline.QdrantClient")
def test_delete_document_vectors(mock_qdrant_cls):
    mock_qdrant = MagicMock()
    mock_qdrant.get_collections.return_value = MagicMock(collections=[])
    mock_qdrant_cls.return_value = mock_qdrant

    doc_id = uuid.uuid4()
    pipeline = IngestionPipeline()
    pipeline.delete_document_vectors(doc_id)

    mock_qdrant.delete.assert_called_once()
    args, kwargs = mock_qdrant.delete.call_args
    assert kwargs["collection_name"] == "documents"
    condition = kwargs["points_selector"].must[0]
    assert condition.key == "document_id"
    assert condition.match.value == str(doc_id)


def test_api_search_unauthorized(client):
    response = client.get("/api/v1/retrieval/search?q=test")
    assert response.status_code == 401


@patch("app.api.v1.endpoints.retrieval_router.VectorSearch.search")
def test_api_search_success(mock_search, client, db):
    # Mock search service return value
    dummy_hits = [
        {
            "id": "1",
            "score": 0.9,
            "document_id": str(uuid.uuid4()),
            "filename": "doc.txt",
            "chunk_index": 0,
            "text": "dummy chunk match"
        }
    ]
    mock_search.return_value = dummy_hits

    # Register and login
    register_payload = {
        "email": "searcher@example.com",
        "password": "securepassword123",
        "full_name": "Searcher User",
    }
    client.post("/api/v1/auth/register", json=register_payload)
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": register_payload["email"],
            "password": register_payload["password"],
        },
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/retrieval/search?q=hello&limit=3&search_type=vector", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["text"] == "dummy chunk match"
    mock_search.assert_called_once()


@patch("app.api.v1.endpoints.retrieval_router.HybridSearch.search")
def test_api_search_hybrid_success(mock_search, client, db):
    dummy_hits = [
        {
            "id": "1",
            "score": 0.0325,
            "document_id": str(uuid.uuid4()),
            "filename": "doc.txt",
            "chunk_index": 0,
            "text": "fused hybrid match"
        }
    ]
    mock_search.return_value = dummy_hits

    # Register and login
    register_payload = {
        "email": "hybrid_searcher@example.com",
        "password": "securepassword123",
        "full_name": "Hybrid Searcher User",
    }
    client.post("/api/v1/auth/register", json=register_payload)
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": register_payload["email"],
            "password": register_payload["password"],
        },
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/retrieval/search?q=hello&limit=3&search_type=hybrid", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["text"] == "fused hybrid match"
    mock_search.assert_called_once()


@patch("app.retrieval.bm25.QdrantClient")
def test_bm25_search_success(mock_qdrant_cls):
    mock_point1 = MagicMock()
    mock_point1.id = "1"
    mock_point1.payload = {
        "document_id": "doc1",
        "owner_id": "owner1",
        "filename": "file1.txt",
        "chunk_index": 0,
        "text": "The quick brown fox jumps over the lazy dog",
    }
    mock_point2 = MagicMock()
    mock_point2.id = "2"
    mock_point2.payload = {
        "document_id": "doc1",
        "owner_id": "owner1",
        "filename": "file1.txt",
        "chunk_index": 1,
        "text": "Apples and bananas are delicious fruits",
    }
    mock_point3 = MagicMock()
    mock_point3.id = "3"
    mock_point3.payload = {
        "document_id": "doc1",
        "owner_id": "owner1",
        "filename": "file1.txt",
        "chunk_index": 2,
        "text": "Unrelated text containing different words",
    }

    mock_qdrant = MagicMock()
    mock_qdrant.scroll.return_value = ([mock_point1, mock_point2, mock_point3], None)
    mock_qdrant_cls.return_value = mock_qdrant

    from app.retrieval.bm25 import BM25Search
    bm25 = BM25Search()
    owner_id = uuid.uuid4()

    hits1 = bm25.search("fox jumps", owner_id, limit=5)
    assert len(hits1) == 1
    assert hits1[0]["id"] == "1"

    hits2 = bm25.search("apples fruits", owner_id, limit=5)
    assert len(hits2) == 1
    assert hits2[0]["id"] == "2"


def test_rrf_hybrid_fusion():
    from app.retrieval.hybrid_search import HybridSearch
    hybrid = HybridSearch()
    hybrid.vector_search = MagicMock()
    hybrid.bm25_search = MagicMock()

    doc_a = {"id": "docA", "score": 0.9, "text": "A"}
    doc_b = {"id": "docB", "score": 0.8, "text": "B"}
    doc_c = {"id": "docC", "score": 0.7, "text": "C"}

    hybrid.vector_search.search.return_value = [doc_a, doc_b, doc_c]
    hybrid.bm25_search.search.return_value = [doc_b, doc_a]

    fused = hybrid.search("query", uuid.uuid4(), limit=3, k=60)

    assert len(fused) == 3
    assert fused[0]["id"] in ["docA", "docB"]
    assert fused[1]["id"] in ["docA", "docB"]
    assert fused[2]["id"] == "docC"


@patch("app.retrieval.reranker.OpenAI")
def test_reranker_openai_success(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "[0.1, 0.95, 0.4]"
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    from app.retrieval.reranker import Reranker
    reranker = Reranker(openai_api_key="test_key")

    docs = [
        {"id": "doc1", "text": "one", "score": 0.5},
        {"id": "doc2", "text": "two", "score": 0.5},
        {"id": "doc3", "text": "three", "score": 0.5},
    ]

    results = reranker.rerank("query", docs, limit=2)
    assert len(results) == 2
    # Verify sorted by the openai mock scores: doc2 (0.95), doc3 (0.4)
    assert results[0]["id"] == "doc2"
    assert results[0]["score"] == 0.95
    assert results[1]["id"] == "doc3"
    assert results[1]["score"] == 0.4


@patch("httpx.Client.post")
def test_reranker_cohere_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"index": 1, "relevance_score": 0.99},
            {"index": 0, "relevance_score": 0.12},
        ]
    }
    mock_post.return_value = mock_response

    from app.retrieval.reranker import Reranker
    reranker = Reranker(cohere_api_key="cohere_test_key")

    docs = [
        {"id": "doc1", "text": "one", "score": 0.5},
        {"id": "doc2", "text": "two", "score": 0.5},
    ]

    results = reranker.rerank("query", docs, limit=5)
    assert len(results) == 2
    # Sorted by cohere score: doc2 (index 1 -> 0.99), doc1 (index 0 -> 0.12)
    assert results[0]["id"] == "doc2"
    assert results[0]["score"] == 0.99
    assert results[1]["id"] == "doc1"
    assert results[1]["score"] == 0.12


@patch("app.api.v1.endpoints.retrieval_router.VectorSearch.search")
@patch("app.api.v1.endpoints.retrieval_router.Reranker.rerank")
def test_api_search_with_rerank_success(mock_rerank, mock_search, client):
    mock_search.return_value = [{"id": "1", "score": 0.5, "text": "match"}]
    mock_rerank.return_value = [{"id": "1", "score": 0.99, "text": "match"}]

    # Register and login
    register_payload = {
        "email": "rerank_api@example.com",
        "password": "securepassword123",
        "full_name": "Rerank API User",
    }
    client.post("/api/v1/auth/register", json=register_payload)
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": register_payload["email"],
            "password": register_payload["password"],
        },
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/api/v1/retrieval/search?q=hello&limit=3&search_type=vector&rerank=true",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["score"] == 0.99
    mock_rerank.assert_called_once()


@patch("app.retrieval.citations.OpenAI")
@patch("app.retrieval.citations.HybridSearch.search")
@patch("app.retrieval.citations.Reranker.rerank")
def test_citation_manager_success(mock_rerank, mock_search, mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "According to [0] we have John, and according to [2] we have fruits."
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    docs = [
        {"id": "doc1", "document_id": "d1", "text": "John is here", "filename": "file1.txt", "chunk_index": 0},
        {"id": "doc2", "document_id": "d2", "text": "Mary is here", "filename": "file2.txt", "chunk_index": 1},
        {"id": "doc3", "document_id": "d3", "text": "bananas and fruits", "filename": "file3.txt", "chunk_index": 0},
    ]
    mock_search.return_value = docs
    mock_rerank.return_value = docs

    from app.retrieval.citations import CitationManager
    cm = CitationManager()
    owner_id = uuid.uuid4()

    result = cm.generate_answer_with_citations("query", owner_id)
    assert "John" in result["answer"]
    assert len(result["sources"]) == 2
    cited_ids = [s["document_id"] for s in result["sources"]]
    assert "d1" in cited_ids
    assert "d3" in cited_ids
    assert "d2" not in cited_ids


@patch("app.api.v1.endpoints.retrieval_router.CitationManager.generate_answer_with_citations")
def test_api_query_citations_success(mock_gen_answer, client):
    mock_gen_answer.return_value = {
        "answer": "This is the answer [0]",
        "sources": [
            {
                "document_id": str(uuid.uuid4()),
                "filename": "doc.txt",
                "text": "snippet text",
                "chunk_index": 0
            }
        ]
    }

    register_payload = {
        "email": "citations_api@example.com",
        "password": "securepassword123",
        "full_name": "Citations API User",
    }
    client.post("/api/v1/auth/register", json=register_payload)
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": register_payload["email"],
            "password": register_payload["password"],
        },
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/retrieval/query",
        json={"query": "test query"},
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert len(data["sources"]) == 1
    assert data["sources"][0]["filename"] == "doc.txt"


@patch("app.retrieval.evaluation.HybridSearch.search")
def test_evaluate_retrieval_metrics(mock_search):
    from app.retrieval.evaluation import RAGEvaluator
    evaluator = RAGEvaluator()

    # Query 1: doc1 is first (Rank 1). expected_ids has doc1. RR: 1.0, Hit: True
    # Query 2: doc2 is first, doc3 is second (Rank 2). expected_ids has doc3. RR: 0.5, Hit: True
    # Query 3: doc1 is first, doc2 is second. expected_ids has doc4. RR: 0.0, Hit: False
    mock_search.side_effect = [
        [{"document_id": "doc1"}, {"document_id": "doc2"}],
        [{"document_id": "doc2"}, {"document_id": "doc3"}],
        [{"document_id": "doc1"}, {"document_id": "doc2"}],
    ]

    dataset = [
        {"query": "q1", "expected_document_ids": ["doc1"]},
        {"query": "q2", "expected_document_ids": ["doc3"]},
        {"query": "q3", "expected_document_ids": ["doc4"]},
    ]

    metrics = evaluator.evaluate_retrieval(dataset, uuid.uuid4(), limit=5)
    # Hit rate: 2/3 = 0.666...
    assert abs(metrics["hit_rate"] - 0.666666666) < 1e-5
    # MRR: (1.0 + 0.5 + 0.0) / 3 = 0.5
    assert metrics["mrr"] == 0.5


@patch("app.retrieval.evaluation.OpenAI")
def test_evaluate_generation_metrics(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = '{"faithfulness": 0.95, "relevance": 0.88}'
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    from app.retrieval.evaluation import RAGEvaluator
    evaluator = RAGEvaluator()

    scores = evaluator.evaluate_generation("query", ["context"], "answer")
    assert scores["faithfulness"] == 0.95
    assert scores["relevance"] == 0.88


@patch("app.api.v1.endpoints.retrieval_router.RAGEvaluator.evaluate_retrieval")
@patch("app.api.v1.endpoints.retrieval_router.RAGEvaluator.evaluate_generation")
def test_api_evaluate_endpoints(mock_gen, mock_ret, client):
    mock_ret.return_value = {"hit_rate": 0.8, "mrr": 0.75}
    mock_gen.return_value = {"faithfulness": 0.9, "relevance": 0.95}

    # Register and login
    register_payload = {
        "email": "eval_api@example.com",
        "password": "securepassword123",
        "full_name": "Eval API User",
    }
    client.post("/api/v1/auth/register", json=register_payload)
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": register_payload["email"],
            "password": register_payload["password"],
        },
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test retrieval eval endpoint
    ret_response = client.post(
        "/api/v1/retrieval/evaluate/retrieval",
        json={
            "dataset": [
                {"query": "q1", "expected_document_ids": [str(uuid.uuid4())]}
            ],
            "limit": 5
        },
        headers=headers
    )
    assert ret_response.status_code == 200
    ret_data = ret_response.json()
    assert ret_data["hit_rate"] == 0.8
    assert ret_data["mrr"] == 0.75

    # Test generation eval endpoint
    gen_response = client.post(
        "/api/v1/retrieval/evaluate/generation",
        json={
            "query": "test query",
            "contexts": ["dummy context"],
            "answer": "dummy answer"
        },
        headers=headers
    )
    assert gen_response.status_code == 200
    gen_data = gen_response.json()
    assert gen_data["faithfulness"] == 0.9
    assert gen_data["relevance"] == 0.95




