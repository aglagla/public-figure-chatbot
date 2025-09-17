
import re
from typing import List

def simple_chunk(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks by words, preserving sentence boundaries when possible."""
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split(" ")
    chunks = []
    start = 0
    while start < len(words):
        end = min(len(words), start + chunk_size)
        chunk_words = words[start:end]
        # Try to end on a sentence boundary
        chunk_text = " ".join(chunk_words)
        last_period = chunk_text.rfind(".")
        if last_period > 200 and end < len(words):  # heuristically cut at sentence end
            chunk_text = chunk_text[: last_period + 1]
            end = start + len(chunk_text.split(" "))
        chunks.append(chunk_text.strip())
        if end == len(words):
            break
        start = max(0, end - overlap)
    return chunks
