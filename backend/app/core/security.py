import uuid
from datetime import datetime, timedelta
from typing import Union
import bcrypt

from jose import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    password_bytes = password.encode('utf-8')
    hashed_bytes = hashed.encode('utf-8')
    try:
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(user_id: Union[uuid.UUID, str, int]) -> str:
    expire = datetime.utcnow() + timedelta(hours=1)

    payload = {
        "sub": str(user_id),
        "exp": expire,
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)