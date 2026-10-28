from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise AI Platform"

    DATABASE_URL: str

    REDIS_URL: str

    QDRANT_HOST: str

    QDRANT_PORT: int

    OPENAI_API_KEY: str = ""
    COHERE_API_KEY: str = ""

    SECRET_KEY: str = "django-insecure-change-me-in-production-super-secret-key"
    ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"


settings = Settings()