import uuid
from pathlib import Path


class LocalStorageManager:

    def __init__(self, upload_dir: str = None):
        if upload_dir is None:
            # Default to backend/uploads
            base_path = Path(__file__).resolve().parents[2]
            self.upload_dir = base_path / "uploads"
        else:
            self.upload_dir = Path(upload_dir)

        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, content: bytes, original_filename: str) -> str:
        ext = Path(original_filename).suffix
        unique_name = f"{uuid.uuid4()}{ext}"
        target_path = self.upload_dir / unique_name

        with open(target_path, "wb") as f:
            f.write(content)

        return str(target_path.resolve())

    def delete_file(self, file_path: str) -> None:
        path = Path(file_path)
        if path.exists():
            path.unlink()
