import uuid
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    PayloadSchemaType,
)

from app.core.config import settings
from app.database.models.document import Document
from app.ingestion.parser import DocumentParser
from app.ingestion.chunker import TextChunker
from app.ingestion.embeddings import OpenAIEmbeddings


class IngestionPipeline:

    def __init__(self, qdrant_host: str = None, qdrant_port: int = None):
        host = qdrant_host or settings.QDRANT_HOST
        port = qdrant_port or settings.QDRANT_PORT

        try:
            self.qdrant = QdrantClient(host=host, port=port)
            self.qdrant.get_collections()
        except Exception:
            # Fallback to localhost if host is not reachable (common in local tests running on host)
            if host == "qdrant":
                self.qdrant = QdrantClient(host="localhost", port=port)
            else:
                raise

        self.parser = DocumentParser()
        self.chunker = TextChunker()
        self.embeddings = OpenAIEmbeddings()
        self.collection_name = "documents"
        self.vector_dim = 1536

        self._ensure_collection()

    def _ensure_collection(self):
        try:
            collections = self.qdrant.get_collections()
            collection_names = [col.name for col in collections.collections]
            if self.collection_name not in collection_names:
                self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_dim, distance=Distance.COSINE
                    ),
                )
                # Create keyword indexes for metadata payload fields to speed up filters
                self.qdrant.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="owner_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                self.qdrant.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="document_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
        except Exception as e:
            # Log failure but allow class initialization to succeed
            print(f"Warning: Qdrant initialization failed: {e}")

    def ingest_document(self, db: Session, document_id: uuid.UUID) -> None:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found in DB")

        try:
            document.status = "processing"
            db.commit()

            # 1. Parse Text
            text = self.parser.parse(document.storage_path)
            if not text.strip():
                raise ValueError("No text extracted from document")

            # 2. Chunk Text
            chunks = self.chunker.chunk_text(text, file_type=document.file_type)
            if not chunks:
                raise ValueError("No chunks created from text")

            # 3. Generate Embeddings
            vector_list = self.embeddings.get_embeddings(chunks)

            # 4. Upsert to Qdrant
            points = []
            for idx, (chunk, vector) in enumerate(zip(chunks, vector_list)):
                point_id = str(uuid.uuid4())
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "document_id": str(document.id),
                            "owner_id": str(document.owner_id),
                            "filename": document.filename,
                            "chunk_index": idx,
                            "text": chunk,
                        },
                    )
                )

            self.qdrant.upsert(collection_name=self.collection_name, points=points)

            document.status = "processed"
            db.commit()

        except Exception as e:
            document.status = "failed"
            db.commit()
            raise e

    def delete_document_vectors(self, document_id: uuid.UUID) -> None:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        try:
            self.qdrant.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id", match=MatchValue(value=str(document_id))
                        )
                    ]
                ),
            )
        except Exception as e:
            print(f"Warning: Failed to delete vectors for document {document_id}: {e}")
