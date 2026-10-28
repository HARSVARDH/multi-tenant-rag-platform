import uuid
from datetime import datetime
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
