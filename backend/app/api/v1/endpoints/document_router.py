from typing import List
from pathlib import Path
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    BackgroundTasks,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.database.models.user import User
from app.database.models.document import Document
from app.schemas.document import DocumentResponse
from app.storage.local import LocalStorageManager
from app.ingestion.pipeline import IngestionPipeline

router = APIRouter(prefix="/documents")
storage_manager = LocalStorageManager()

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def run_ingestion_pipeline(document_id: str):
    from app.database.session import SessionLocal

    db = SessionLocal()
    try:
        pipeline = IngestionPipeline()
        pipeline.ingest_document(db, document_id)
    except Exception as e:
        print(f"Error in background ingestion for document {document_id}: {e}")
    finally:
        db.close()


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: {ext}. Supported formats: PDF, DOCX, TXT, Markdown",
        )

    content = await file.read()
    file_size = len(content)

    try:
        storage_path = storage_manager.save_file(content, file.filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store file: {str(e)}",
        )

    db_document = Document(
        filename=file.filename,
        storage_path=storage_path,
        file_type=ext.replace(".", "").upper(),
        file_size=file_size,
        status="uploaded",
        owner_id=current_user.id,
    )

    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    # Run ingestion pipeline as background task
    background_tasks.add_task(run_ingestion_pipeline, db_document.id)

    return db_document


@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Document).filter(Document.owner_id == current_user.id).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner_id == current_user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
