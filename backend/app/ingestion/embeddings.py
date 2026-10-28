import time
from typing import List
from openai import OpenAI
from app.core.config import settings


class OpenAIEmbeddings:

    def __init__(
        self,
        api_key: str = None,
        model: str = "text-embedding-3-small",
        dimensions: int = None,
    ):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.dimensions = dimensions
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def get_embeddings(
        self, texts: List[str], batch_size: int = 100
    ) -> List[List[float]]:
        if not texts:
            return []

        if not self.client:
            raise ValueError("OpenAI API key is missing or client is not initialized.")

        # Chunk input texts list into sub-batches
        batches = [
            texts[i : i + batch_size] for i in range(0, len(texts), batch_size)
        ]
        all_embeddings = []

        for batch in batches:
            embeddings = self._get_embeddings_with_retry(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    def _get_embeddings_with_retry(
        self, batch: List[str], max_retries: int = 3, initial_delay: float = 1.0
    ) -> List[List[float]]:
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                params = {"input": batch, "model": self.model}
                if self.dimensions and self.model.startswith("text-embedding-3"):
                    params["dimensions"] = self.dimensions

                response = self.client.embeddings.create(**params)
                return [data.embedding for data in response.data]
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(delay)
                delay *= 2
        return []
