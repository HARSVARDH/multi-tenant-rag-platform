from sqlalchemy.orm import Session

from app.database.models.user import User
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
)


class AuthService:

    def register(self, db: Session, user):
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user.email).first()
        if existing_user:
            raise ValueError("Email already registered")

        db_user = User(
            email=user.email,
            full_name=user.full_name,
            hashed_password=hash_password(user.password),
        )

        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    def login(self, db: Session, email: str, password: str):
        user = db.query(User).filter(User.email == email).first()

        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        return create_access_token(user.id)