import re
from typing import List

class RecursiveTextSplitter:
    """按段落、句子和空白递归切分知识文档。

    在限制 Chunk 长度的同时保留适量重叠上下文。
    """
    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 120):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        if not text or not text.strip():
            return []

        # List of separators from largest to smallest
        separators = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]
        return self._split(text, separators)

    def _split(self, text: str, separators: List[str]) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text.strip()]

        if not separators:
            # Fallback to force slice
            return [text[i:i+self.chunk_size].strip() for i in range(0, len(text), self.chunk_size - self.chunk_overlap)]

        separator = separators[0]
        remaining_separators = separators[1:]

        # Split the text by the current separator
        if separator == "":
            splits = list(text)
        else:
            splits = re.split(re.escape(separator), text)
            # Re-add separator for readability (except newlines)
            if separator in [". ", "? ", "! "]:
                splits = [s + separator.strip() for s in splits if s]

        chunks = []
        current_chunk = ""

        for part in splits:
            if not part:
                continue

            # If a single part exceeds the chunk size, split it with smaller separators
            if len(part) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                sub_chunks = self._split(part, remaining_separators)
                chunks.extend(sub_chunks)
                continue

            # Check if adding this part would exceed chunk size
            if len(current_chunk) + len(part) + (1 if current_chunk else 0) <= self.chunk_size:
                current_chunk += (" " if current_chunk and not current_chunk.endswith("\n") else "") + part
            else:
                chunks.append(current_chunk.strip())
                # Start new chunk with overlap only if it doesn't cause it to exceed self.chunk_size
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                overlap_text = current_chunk[overlap_start:]
                if len(overlap_text) + len(part) + 1 <= self.chunk_size:
                    current_chunk = overlap_text + (" " if overlap_text else "") + part
                else:
                    current_chunk = part

        if current_chunk:
            chunks.append(current_chunk.strip())

        # Filter out empty chunks
        return [c for c in chunks if len(c.strip()) > 5]
