#!/usr/bin/env python3
"""
Fast book ingester with optional progress/debug logs and doc_type support.

- One DB transaction per file
- Bulk insert chunks (single round-trip)
- Batched embeddings (client-side batching; TEI also batches internally)
- --doc-type lets you tag documents as 'book' | 'biography' | 'transcript'
- --debug prints progress and timings

Usage:
  python scripts/ingest_books.py <path-to-.txt-or-dir>
      [--persona "Name"]
      [--chunk-size 1800]
      [--chunk-overlap 240]
      [--batch-size 256]
      [--doc-type book]
      [--debug]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Iterable, List, Set
from sqlalchemy import insert
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.db.session import SessionLocal
from backend.app.db import models
from backend.app.services.embeddings import EmbeddingService

def log(msg: str, *, debug: bool = False):
    if debug:
        print(msg, flush=True)


def list_txt_files(path: Path) -> List[Path]:
    if path.is_file():
        return [path]
    return sorted([p for p in path.glob("*.txt") if p.is_file()])


def normalize_dialogue(raw: str, persona_name: str) -> str:
    """
    Keep this simple & linear-time; plug in your richer normalizer if needed.
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n"))


def simple_chunk(text: str, chunk_size: int = 1800, overlap: int = 240) -> List[str]:
    out: List[str] = []
    n = len(text)
    if n == 0:
        return out
    chunk_size = max(400, int(chunk_size))
    overlap = max(0, min(int(overlap), chunk_size // 2))
    i = 0
    while i < n:
        j = min(i + chunk_size, n)
        out.append(text[i:j])
        if j >= n:
            break
        i = j - overlap
    return out


def _doc_columns() -> Set[str]:
    try:
        return set(models.Document.__table__.columns.keys())  # type: ignore[attr-defined]
    except Exception:
        return set()

def ingest_text_fast(
    title: str,
    persona: str,
    source_path: str,
    text: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
    batch_size: int,
    doc_type: str,              # <-- pass doc_type in here
    debug: bool = False,
) -> None:
    t0 = time.perf_counter()

    # TEI-first embedder (falls back to local ST only if EMBEDDINGS_BASE_URL unset and ST installed)
    embedder = EmbeddingService(
        getattr(settings, "EMBEDDING_MODEL", os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")),
        base_url=getattr(settings, "EMBEDDINGS_BASE_URL", os.getenv("EMBEDDINGS_BASE_URL")),
        batch_size=batch_size,
    )
    t1 = time.perf_counter()
    log(f"[debug] embedder ready in {t1 - t0:.2f}s", debug=debug)

    with SessionLocal() as session:  
        # persona upsert-ish
        persona_obj = (
            session.query(models.PersonaProfile)
            .filter(models.PersonaProfile.name == persona)
            .one_or_none()
        )
        if not persona_obj:
            persona_obj = models.PersonaProfile(name=persona)
            session.add(persona_obj)
            session.flush()  # get id
            log(f"[debug] created persona id={persona_obj.id}", debug=debug)

        # Create Document; set optional fields only if present on the model
        cols = _doc_columns()
        doc_kwargs = dict(persona_id=persona_obj.id)
        if "title" in cols:
            doc_kwargs["title"] = title
        if "source" in cols:
            doc_kwargs["source"] = source_path
        if "doc_type" in cols:
            doc_kwargs["doc_type"] = doc_type            # <-- use function param, not args
        if "content_type" in cols:
            doc_kwargs["content_type"] = doc_type        # optional mirror

        doc = models.Document(**doc_kwargs)
        session.add(doc)
        session.flush()  # get doc.id
        log(f"[debug] document id={doc.id}", debug=debug)

        # Normalize + chunk
        t_chunk0 = time.perf_counter()
        normalized = normalize_dialogue(text, persona_name=persona)
        chunks = simple_chunk(normalized, chunk_size=chunk_size, overlap=chunk_overlap)
        t_chunk1 = time.perf_counter()
        if not chunks:
            print(f"[warn] No chunks produced for {title}")
            session.rollback()
            return
        log(f"[debug] chunked into {len(chunks)} chunks in {t_chunk1 - t_chunk0:.2f}s", debug=debug)

        # BULK insert chunks; get ids back in order
        values = [{"document_id": doc.id, "order": i + 1, "text": ch} for i, ch in enumerate(chunks)]
        t_ins0 = time.perf_counter()
        stmt = insert(models.Chunk).returning(models.Chunk.id)
        result = session.execute(stmt, values)
        chunk_ids = [row[0] for row in result]
        t_ins1 = time.perf_counter()
        log(f"[debug] inserted {len(chunk_ids)} chunks in {t_ins1 - t_ins0:.2f}s", debug=debug)

        # Embeddings – batched with progress
        total = len(chunks)
        vectors_list: List[List[float]] = []
        t_emb0 = time.perf_counter()
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch_texts = chunks[start:end]
            b0 = time.perf_counter()
            vecs = embedder.embed(batch_texts)  # np.ndarray (B, D)
            b1 = time.perf_counter()
            vectors_list.extend(v.tolist() for v in vecs)
            if debug:
                pct = 100.0 * end / total
                log(f"[debug] embedded {end}/{total} ({pct:.1f}%) batch={len(batch_texts)} in {b1 - b0:.2f}s", debug=debug)
        t_emb1 = time.perf_counter()
        log(f"[debug] embedded all chunks in {t_emb1 - t_emb0:.2f}s", debug=debug)

        # BULK insert embeddings
        t_eins0 = time.perf_counter()
        emb_values = [{"chunk_id": cid, "vector": vec} for cid, vec in zip(chunk_ids, vectors_list)]
        session.execute(insert(models.Embedding), emb_values)
        session.commit()
        t_eins1 = time.perf_counter()
        log(f"[debug] inserted {len(emb_values)} embeddings in {t_eins1 - t_eins0:.2f}s", debug=debug)

    t2 = time.perf_counter()
    print(f"[ok] Ingested '{title}' ({len(chunks)} chunks, type={doc_type}) in {t2 - t0:.2f}s")

def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fast ingest of .txt books with optional debug and doc_type.")
    ap.add_argument("path", help="Path to a .txt file or a directory of .txt files")
    ap.add_argument("--persona", default="Richard Feynman", help="Persona name (default: %(default)s)")
    ap.add_argument("--chunk-size", type=int, default=int(os.getenv("CHUNK_SIZE", "1800")), help="Chunk size (chars)")
    ap.add_argument("--chunk-overlap", type=int, default=int(os.getenv("CHUNK_OVERLAP", "240")), help="Chunk overlap (chars)")
    ap.add_argument("--batch-size", type=int, default=int(os.getenv("EMBEDDINGS_MAX_CLIENT_BATCH_SIZE", "256")), help="Embedding batch size")
    ap.add_argument("--doc-type", choices=["book", "biography", "transcript"], default="book", help="Document type tag (default: book)")
    ap.add_argument("--debug", action="store_true", help="Print progress/debug messages")
    args = ap.parse_args(list(argv) if argv is not None else None)

    path = Path(args.path)
    files = list_txt_files(path)
    if not files:
        print(f"[warn] No .txt files found at {path}")
        return 1

    print(f"[info] persona='{args.persona}', files={len(files)}, chunk={args.chunk_size}/{args.chunk_overlap}, batch={args.batch_size}, doc_type={args.doc_type}")
    for fp in files:
        try:
            t0 = time.perf_counter()
            text = fp.read_text(encoding="utf-8", errors="ignore")
            ingest_text_fast(
                title=fp.stem.replace("_", " "),
                persona=args.persona,
                source_path=str(fp),
                text=text,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                batch_size=args.batch_size,
                doc_type=args.doc_type,     # <-- pass it down here
                debug=args.debug,
            )
            t1 = time.perf_counter()
            if args.debug:
                print(f"[debug] file '{fp.name}' done in {t1 - t0:.2f}s", flush=True)
        except Exception as e:
            print(f"[warn] Failed on {fp}: {e}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
