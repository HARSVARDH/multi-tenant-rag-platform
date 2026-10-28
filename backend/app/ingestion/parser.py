from pathlib import Path
from docx import Document as DocxDocument
from pypdf import PdfReader


class DocumentParser:

    def parse(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()
        if ext in [".txt", ".md"]:
            return self._parse_text(path)
        elif ext == ".pdf":
            return self._parse_pdf(path)
        elif ext == ".docx":
            return self._parse_docx(path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _parse_text(self, path: Path) -> str:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _parse_pdf(self, path: Path) -> str:
        reader = PdfReader(path)
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n\n".join(text_parts)

    def _parse_docx(self, path: Path) -> str:
        doc = DocxDocument(path)
        text_parts = [para.text for para in doc.paragraphs if para.text]
        return "\n\n".join(text_parts)
