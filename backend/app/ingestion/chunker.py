from typing import List


class TextChunker:

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]

    def chunk_text(self, text: str, file_type: str = "TXT") -> List[str]:
        if not text:
            return []

        # 1. Get raw contiguous chunks
        if file_type == "MD":
            raw_chunks = self._chunk_markdown(text)
        else:
            raw_chunks = self._chunk_recursive(text, self.separators)

        # 2. Apply overlap merge on the final list of chunks
        overlapped_chunks = []
        for i, chunk in enumerate(raw_chunks):
            if i == 0:
                overlapped_chunks.append(chunk)
                continue

            prev_chunk = raw_chunks[i - 1]
            overlap_part = (
                prev_chunk[-self.chunk_overlap :]
                if len(prev_chunk) >= self.chunk_overlap
                else prev_chunk
            )
            overlapped_chunks.append(overlap_part + "\n" + chunk)

        return overlapped_chunks

    def _chunk_markdown(self, text: str) -> List[str]:
        lines = text.split("\n")
        chunks = []
        current_headers = []
        current_content = []

        for line in lines:
            if line.startswith("#"):
                # Determine header level
                stripped = line.lstrip("#")
                level = len(line) - len(stripped)
                header_text = stripped.strip()

                # Adjust header stack level
                if level <= len(current_headers):
                    current_headers = current_headers[: level - 1]
                while len(current_headers) < level - 1:
                    current_headers.append("")

                # Flush current content block before shifting header context
                if current_content:
                    path = " > ".join([h for h in current_headers if h])
                    header_prefix = f"Context: {path}\n" if path else ""
                    full_text = header_prefix + "\n".join(current_content)
                    chunks.extend(self._chunk_recursive(full_text, self.separators))
                    current_content = []

                if len(current_headers) == level - 1:
                    current_headers.append(header_text)
                else:
                    current_headers[level - 1] = header_text
            else:
                current_content.append(line)

        if current_content:
            path = " > ".join([h for h in current_headers if h])
            header_prefix = f"Context: {path}\n" if path else ""
            full_text = header_prefix + "\n".join(current_content)
            chunks.extend(self._chunk_recursive(full_text, self.separators))

        return chunks

    def _chunk_recursive(self, text: str, separators: List[str]) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]

        if not separators or separators[0] == "":
            # Fallback to plain contiguous character split (no sliding window here, overlap is applied at the end)
            return [
                text[i : i + self.chunk_size]
                for i in range(0, len(text), self.chunk_size)
            ]

        separator = separators[0]
        splits = text.split(separator)
        chunks = []
        current_chunk = ""

        for split in splits:
            sep_len = len(separator) if current_chunk else 0
            if len(current_chunk) + sep_len + len(split) <= self.chunk_size:
                current_chunk = (
                    current_chunk + (separator if current_chunk else "") + split
                )
            else:
                if current_chunk:
                    chunks.append(current_chunk)

                if len(split) > self.chunk_size:
                    sub_chunks = self._chunk_recursive(split, separators[1:])
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = split

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
