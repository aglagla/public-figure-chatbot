
#!/usr/bin/env python3
"""Ingest interview transcripts from a directory into the DB with chunks + embeddings.

Usage:
  python scripts/ingest_transcripts.py --persona "Public Figure" path/to/transcripts_dir
"""
import os, glob, argparse
from sqlalchemy.orm import Session
from sqlalchemy import select
from backend.app.db.session import SessionLocal
from backend.app.db import models
from backend.app.utils.text import simple_chunk
from backend.app.services.embeddings import EmbeddingService
from backend.app.config import settings

def ensure_persona(session: Session, name: str) -> models.PersonaProfile:
    p = session.query(models.PersonaProfile).filter_by(name=name).one_or_none()
    if p: return p
    p = models.PersonaProfile(name=name, style_prompt=None, top_phrases=None)
    session.add(p); session.commit(); session.refresh(p)
    return p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", required=True, help="Persona name (public figure) for these transcripts")
    ap.add_argument("dir", help="Directory containing .txt transcript files")
    ap.add_argument("--chunk-size", type=int, default=800)
    ap.add_argument("--overlap", type=int, default=100)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "*.txt")))
    if not files:
        print("No .txt files found.")
        return

    embedder = EmbeddingService(settings.embedding_model)
    with SessionLocal() as session:
        persona = ensure_persona(session, args.persona)

        for fp in files:
            title = os.path.basename(fp)
            with open(fp, "r", encoding="utf-8") as f:
                text = f.read()
            doc = models.Document(title=title, source=fp, persona_id=persona.id)
            session.add(doc); session.commit(); session.refresh(doc)

            chunks = simple_chunk(text, chunk_size=args.chunk_size, overlap=args.overlap)
            # Insert chunks
            chunk_objs = []
            for idx, ch in enumerate(chunks):
                c = models.Chunk(document_id=doc.id, idx=idx, text=ch)
                session.add(c); session.flush()
                chunk_objs.append(c)
            session.commit()

            # Embeddings
            vectors = embedder.embed([c.text for c in chunk_objs])
            for c, v in zip(chunk_objs, vectors):
                e = models.Embedding(chunk_id=c.id, vector=v.tolist())
                session.add(e)
            session.commit()
            print(f"Ingested {title}: {len(chunk_objs)} chunks.")

if __name__ == "__main__":
    main()
