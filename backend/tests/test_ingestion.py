import uuid
from unittest.mock import MagicMock, patch
import pytest

from app.ingestion.parser import DocumentParser
from app.ingestion.chunker import TextChunker
from app.ingestion.pipeline import IngestionPipeline
from app.database.models.document import Document
from app.database.models.user import User


def test_document_parser_txt(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, this is a test text file.", encoding="utf-8")

    parser = DocumentParser()
    text = parser.parse(str(file_path))
    assert text == "Hello, this is a test text file."


def test_document_parser_md(tmp_path):
    file_path = tmp_path / "test.md"
    file_path.write_text(
        "# Title\n- Bullet point 1\n- Bullet point 2", encoding="utf-8"
    )

    parser = DocumentParser()
    text = parser.parse(str(file_path))
    assert "# Title" in text
    assert "Bullet point 1" in text


def test_text_chunker():
    chunker = TextChunker(chunk_size=10, chunk_overlap=2)
    text = "abcdefghij"  # length 10
    chunks = chunker.chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == "abcdefghij"

    text2 = "abcdefghijkl"  # length 12
    chunks2 = chunker.chunk_text(text2)
    assert len(chunks2) == 2
    assert chunks2[0] == "abcdefghij"
    assert chunks2[1] == "ij\nkl"


def test_markdown_chunker():
    chunker = TextChunker(chunk_size=100, chunk_overlap=10)
    markdown_text = "# Header 1\nHello world\n## Header 2\nTest markdown content."
    chunks = chunker.chunk_text(markdown_text, file_type="MD")
    assert len(chunks) >= 2
    assert "Context: Header 1" in chunks[0]
    assert "Context: Header 1 > Header 2" in chunks[1]


@patch("app.ingestion.pipeline.QdrantClient")
@patch("app.ingestion.pipeline.OpenAIEmbeddings")
def test_ingestion_pipeline_success(
    mock_embeddings_cls, mock_qdrant_cls, db, tmp_path
):
    # Mock embeddings
    mock_embeddings = MagicMock()
    mock_embeddings.get_embeddings.return_value = [[0.1] * 1536]
    mock_embeddings_cls.return_value = mock_embeddings

    # Mock Qdrant
    mock_qdrant = MagicMock()
    mock_qdrant.get_collections.return_value = MagicMock(collections=[])
    mock_qdrant_cls.return_value = mock_qdrant

    # Create dummy file
    file_path = tmp_path / "test.txt"
    file_path.write_text(
        "This is test text for ingestion pipeline.", encoding="utf-8"
    )

    # Create a user
    user = User(
        email="pipeline_test@example.com", hashed_password="pw", full_name="User"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create a document record
    doc = Document(
        filename="test.txt",
        storage_path=str(file_path),
        file_type="TXT",
        file_size=len(file_path.read_bytes()),
        status="uploaded",
        owner_id=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Run pipeline
    pipeline = IngestionPipeline()
    pipeline.ingest_document(db, doc.id)

    # Verify updates
    db.refresh(doc)
    assert doc.status == "processed"
    mock_qdrant.upsert.assert_called_once()


def test_api_upload_document_success(client, db):
    # Register and login user
    register_payload = {
        "email": "uploader@example.com",
        "password": "securepassword123",
        "full_name": "Uploader User",
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

    # Upload file
    file_content = b"Hello, this is a text file upload test."
    files = {"file": ("test_upload.txt", file_content, "text/plain")}

    with patch(
        "app.api.v1.endpoints.document_router.run_ingestion_pipeline"
    ) as mock_pipeline_task:
        response = client.post(
            "/api/v1/documents/upload", files=files, headers=headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test_upload.txt"
        assert data["file_type"] == "TXT"
        assert data["status"] == "uploaded"

        # Verify db entry
        doc_id = data["id"]
        doc = db.query(Document).filter(Document.id == doc_id).first()
        assert doc is not None
        assert doc.filename == "test_upload.txt"

        # Verify background task was launched
        mock_pipeline_task.assert_called_once_with(uuid.UUID(doc_id))


@patch("app.ingestion.embeddings.OpenAI")
def test_embeddings_batching(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    # Mock response
    def mock_create(**kwargs):
        batch_len = len(kwargs["input"])
        resp = MagicMock()
        resp.data = [MagicMock(embedding=[0.1] * 1536) for _ in range(batch_len)]
        return resp

    mock_client.embeddings.create.side_effect = mock_create

    from app.ingestion.embeddings import OpenAIEmbeddings
    embeddings_service = OpenAIEmbeddings(api_key="test_key")
    texts = ["one", "two", "three", "four", "five"]
    results = embeddings_service.get_embeddings(texts, batch_size=2)

    assert len(results) == 5
    assert mock_client.embeddings.create.call_count == 3


@patch("app.ingestion.embeddings.OpenAI")
def test_embeddings_dimensions(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1] * 512)]
    mock_client.embeddings.create.return_value = mock_response

    from app.ingestion.embeddings import OpenAIEmbeddings
    embeddings_service = OpenAIEmbeddings(
        api_key="test_key", model="text-embedding-3-small", dimensions=512
    )
    results = embeddings_service.get_embeddings(["test_text"])

    assert len(results) == 1
    mock_client.embeddings.create.assert_called_once_with(
        input=["test_text"], model="text-embedding-3-small", dimensions=512
    )
