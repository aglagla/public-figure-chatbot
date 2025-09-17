# backend/app/services/retrieval_bio.py
import os
from typing import List
from sqlalchemy import text
from backend.app.db.session import engine
from backend.app.services.embeddings import EmbeddingService
from backend.app.config import settings

BIO_TRIGGERS = ["born","birth","upbringing","grew up","family","parents","married","children",
                "where from","education","school","university","college","early life",
                "when did","where did","timeline","award","prize","nobel"]

def is_bio_question(q: str) -> bool:
    ql = q.lower()
    return any(t in ql for t in BIO_TRIGGERS)

def search_bio(persona_id: int, question: str, k: int = 5):
    emb = EmbeddingService(settings.EMBEDDING_MODEL,
                           base_url=getattr(settings, "EMBEDDINGS_BASE_URL", os.getenv("EMBEDDINGS_BASE_URL")))
    qv = emb.embed([question])[0].tolist()
    sql = """
      SELECT fact_text
      FROM bio_facts
      WHERE persona_id=:pid
      ORDER BY embedding <-> :qvec
      LIMIT :k
    """
    with engine.begin() as conn:
        rows = conn.execute(text(sql), {"pid": persona_id, "qvec": qv, "k": k}).fetchall()
    return [r[0] for r in rows]
