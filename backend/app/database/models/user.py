import uuid
from datetime import datetime

from sqlalchemy import String, UUID
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.orm import mapped_column

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )

    hashed_password: Mapped[str]

    full_name: Mapped[str]

    role: Mapped[str] = mapped_column(default="user")

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="owner",
        cascade="all, delete-orphan",
    )