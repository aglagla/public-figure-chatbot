
from typing import List, Tuple
from sqlalchemy import select, text
from sqlalchemy.orm import Session
import numpy as np
from backend.app.db import models

def search_chunks(session: Session, question_vec: np.ndarray, persona_id: int, top_k: int = 6) -> List[Tuple]:
    """Return top_k (chunk, document, score) for a persona using pgvector cosine distance."""
    # Prepare a SQL with pgvector cosine distance
    sql = text(
        """
        SELECT c.id as chunk_id, c.text, d.id as document_id, d.title, d.source,
               1 - (e.vector <=> :qvec) as score
        FROM embeddings e
        JOIN chunks c ON c.id = e.chunk_id
        JOIN documents d ON d.id = c.document_id
        WHERE d.persona_id = :persona_id
        ORDER BY e.vector <=> :qvec ASC
        LIMIT :top_k
        """
    ).bindparams(qvec=question_vec.tolist(), persona_id=persona_id, top_k=top_k)
    rows = session.execute(sql).fetchall()
    return rows
