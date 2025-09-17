from __future__ import annotations
import os
from typing import Iterable, List, Optional, Any
import numpy as np

DEFAULT_EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
DEFAULT_TIMEOUT = float(os.getenv("EMBEDDINGS_HTTP_TIMEOUT", "60"))
DEFAULT_BATCH = int(os.getenv("EMBEDDINGS_MAX_CLIENT_BATCH_SIZE", "32"))

class EmbeddingService:
    """
    TEI-first embedding client with local SentenceTransformers fallback.
    Accepts multiple response shapes:
      - {"embeddings": [[...], ...]}           # TEI
      - [{"embedding":[...]} , ...]            # some proxies
      - {"data":[{"embedding":[...]} , ...]}   # OpenAI-style
      - [[...], ...]                           # bare list
    Returns float32, L2-normalized.
    """
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        batch_size: Optional[int] = None,
    ):
        self.model_name = model_name or DEFAULT_EMBED_MODEL
        if base_url is None:
            base_url = os.getenv("EMBEDDINGS_BASE_URL")
            if not base_url:
                try:
                    from backend.app.config import settings  # type: ignore
                    base_url = getattr(settings, "embeddings_base_url", None) or getattr(settings, "EMBEDDINGS_BASE_URL", None)
                except Exception:
                    base_url = None
        self.base = (base_url or "").rstrip("/")
        self.timeout = float(timeout or DEFAULT_TIMEOUT)
        self.batch_size = int(batch_size or DEFAULT_BATCH)
        self._st = None
        self._requests = None
        if not self.base:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                self._st = SentenceTransformer(self.model_name)
            except Exception as e:
                raise RuntimeError(
                    "No EMBEDDINGS_BASE_URL set and SentenceTransformers not available. "
                    "Set EMBEDDINGS_BASE_URL to TEI or install sentence-transformers."
                ) from e

    def embed(self, texts: Iterable[str]) -> np.ndarray:
        items = [t if isinstance(t, str) else str(t) for t in texts]
        if not items:
            return np.zeros((0, 0), dtype="float32")
        vecs = self._embed_remote(items) if self.base else self._embed_local(items)
        arr = np.asarray(vecs, dtype="float32")
        return self._l2_normalize(arr)

    # ---------- HTTP (TEI / proxies) ----------
    def _embed_remote(self, items: List[str]) -> List[List[float]]:
        if self._requests is None:
            import requests  # lazy
            self._requests = requests
        out: List[List[float]] = []
        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            r = self._requests.post(
                f"{self.base}/embed",
                json={"inputs": batch, "normalize": True, "truncate": True},
                timeout=self.timeout,
            )
            try:
                r.raise_for_status()
            except Exception as e:
                raise RuntimeError(f"TEI /embed failed (status {r.status_code}): {r.text[:500]}") from e
            out.extend(self._parse_embeddings_json(r.json()))
        return out

    @staticmethod
    def _parse_embeddings_json(data: Any) -> List[List[float]]:
        # TEI canonical
        if isinstance(data, dict) and "embeddings" in data:
            emb = data["embeddings"]
            if isinstance(emb, list):
                return [v if isinstance(v, list) else list(v) for v in emb]
        # OpenAI-style
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            return [item["embedding"] for item in data["data"] if "embedding" in item]
        # Bare list of vectors, or list of {"embedding": ...}
        if isinstance(data, list):
            if data and isinstance(data[0], dict) and "embedding" in data[0]:
                return [item["embedding"] for item in data]
            # assume list of vectors
            return [v if isinstance(v, list) else list(v) for v in data]
        raise RuntimeError("Unrecognized embeddings JSON shape")

    # Local (SentenceTransformers) 
    def _embed_local(self, items: List[str]) -> np.ndarray:
        assert self._st is not None, "Local ST model not initialized"
        vecs = self._st.encode(
            items,
            normalize_embeddings=False,  # normalize explicitly for consistency
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vecs

    @staticmethod
    def _l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
        if x.size == 0:
            return x.astype("float32", copy=False)
        n = np.linalg.norm(x, axis=1, keepdims=True)
        n = np.maximum(n, eps)
        return (x / n).astype("float32", copy=False)
