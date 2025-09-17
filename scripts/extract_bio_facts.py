#!/usr/bin/env python3
"""
Extract concise biographical facts from biography books already ingested as chunks.

Heuristics-only (fast, CPU): trigger keywords + name presence + simple date/location parsing.
No Torch. Uses your existing EmbeddingService (TEI or local ST).

Run:
  docker compose exec backend python scripts/extract_bio_from_books.py --persona "Richard Feynman" --source "User curated"
"""

from __future__ import annotations
import os, re, datetime as dt
from typing import List, Dict, Iterable, Optional
from sqlalchemy import insert, select
from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal
from backend.app.db import models
from backend.app.services.embeddings import EmbeddingService
from backend.app.config import settings

BIO_TRIGGERS = [
    "born", "birth", "grew up", "upbringing", "childhood", "parents", "mother", "father",
    "family", "married", "spouse", "wife", "husband", "children", "son", "daughter",
    "school", "college", "university", "education", "degree", "phd", "doctorate",
    "career", "appointed", "professor", "tenure", "joined", "worked at",
    "prize", "award", "nobel", "fellow", "elected", "won",
    "moved to", "emigrated", "immigrated", "lived in", "resided", "died", "passed away"
]
TRIGGER_RE = re.compile("|".join(re.escape(t) for t in BIO_TRIGGERS), re.I)
SPLIT_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")  # simple sentence splitter

DATE_RE = re.compile(r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
                     r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
                     r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s+\d{4}|\d{4})\b")
LOCATION_HINT_RE = re.compile(r"\b(in|at|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})")

def split_sentences(text: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = SPLIT_SENT_RE.split(text)
    out = []
    for p in parts:
        s = p.strip()
        if s:
            out.append(s)
    return out

def looks_bio_sentence(s: str, persona_name: str) -> bool:
    if len(s) < 30:  # avoid stubs
        return False
    if not TRIGGER_RE.search(s):
        return False
    # Must reference the persona somehow (full or last name)
    name = persona_name.strip()
    toks = name.split()
    last = toks[-1] if toks else name
    return (name in s) or (last in s)

def normalize_fact(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    # remove trailing parentheses clutter if too long
    s = re.sub(r"\s*\([^)]{30,}\)$", "", s)
    return s

def guess_tags(s: str) -> List[str]:
    ss = s.lower()
    tags = []
    if any(t in ss for t in ["born", "birth", "grew up", "childhood", "parents","family"]):
        tags.append("early-life")
    if any(t in ss for t in ["school", "college", "university", "education", "degree","phd","doctorate"]):
        tags.append("education")
    if any(t in ss for t in ["prize","award","nobel","fellow","won"]):
        tags.append("awards")
    if any(t in ss for t in ["career","appointed","professor","joined","worked at","tenure"]):
        tags.append("career")
    if any(t in ss for t in ["died","passed away"]):
        tags.append("death")
    if not tags:
        tags.append("biography")
    return tags

def parse_date(s: str) -> Optional[dt.date]:
    # try to get a year or "Month Day, Year"
    m = DATE_RE.search(s)
    if not m:
        return None
    txt = m.group(1)
    try:
        if txt.isdigit() and len(txt) == 4:
            return dt.date(int(txt), 1, 1)
        # try Month Day, Year
        return dt.datetime.strptime(txt, "%B %d, %Y").date()
    except Exception:
        return None

def parse_location(s: str) -> Optional[str]:
    m = LOCATION_HINT_RE.search(s)
    if m:
        return m.group(2)
    return None

def upsert_biosource(session: Session, name: str, url: Optional[str] = None) -> models.BioSource:
    src = session.query(models.BioSource).filter(models.BioSource.name == name).one_or_none()
    if not src:
        src = models.BioSource(name=name, url=url, reliability=0.8)
        session.add(src)
        session.flush()
    return src

def already_exists(session: Session, persona_id: int, fact_text: str) -> bool:
    q = session.query(models.BioFact.id).filter(
        models.BioFact.persona_id == persona_id,
        models.BioFact.fact_text == fact_text
    ).limit(1).one_or_none()
    return q is not None

def extract_from_document(session: Session, persona: models.PersonaProfile, doc: models.Document,
                          embedder: EmbeddingService, preview: bool=False) -> int:
    # gather all sentences from chunks
    chunks = (session.query(models.Chunk)
              .filter(models.Chunk.document_id == doc.id)
              .order_by(models.Chunk.order.asc())
              .all())
    cand: List[str] = []
    for c in chunks:
        for s in split_sentences(c.text):
            if looks_bio_sentence(s, persona.name):
                cand.append(normalize_fact(s))
    # dedupe conservatively
    seen = set()
    facts = [x for x in cand if not (x in seen or seen.add(x))]
    if not facts:
        return 0

    # embed
    vecs = embedder.embed(facts)

    # insert source
    src = upsert_biosource(session, name=doc.title or "Biography Book", url=doc.source)

    rows = []
    for s, v in zip(facts, vecs):
        if already_exists(session, persona.id, s):
            continue
        rows.append({
            "persona_id": persona.id,
            "source_id": src.id,
            "fact_text": s,
            "date_start": parse_date(s),
            "date_end": None,
            "location": parse_location(s),
            "tags": guess_tags(s),
            "embedding": v.tolist(),
        })
    if not rows:
        return 0
    session.execute(insert(models.BioFact), rows)
    return len(rows)

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", required=True, help="Persona name (exact)")
    ap.add_argument("--source-name", default="Biography Book", help="Label for BioSource rows")
    ap.add_argument("--doc-type", default="biography", help="Document.doc_type to use (default: biography)")
    ap.add_argument("--preview", action="store_true", help="Print candidates instead of inserting")
    args = ap.parse_args()

    # embedder
    embedder = EmbeddingService(
        getattr(settings, "EMBEDDING_MODEL", os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")),
        base_url=getattr(settings, "EMBEDDINGS_BASE_URL", os.getenv("EMBEDDINGS_BASE_URL")),
        batch_size=int(os.getenv("EMBEDDINGS_MAX_CLIENT_BATCH_SIZE", "256")),
    )

    s: Session = SessionLocal()
    persona = s.query(models.PersonaProfile).filter(models.PersonaProfile.name == args.persona).one_or_none()
    if not persona:
        print(f"[error] persona '{args.persona}' not found")
        return 2

    docs = (s.query(models.Document)
            .filter(models.Document.persona_id == persona.id)
            .filter((models.Document.doc_type == args.doc_type) | (models.Document.content_type == args.doc_type))
            .order_by(models.Document.id.asc())
            .all())
    if not docs:
        print(f"[warn] no documents with doc_type='{args.doc_type}' for {args.persona}")
        return 0

    total = 0
    for d in docs:
        n = extract_from_document(s, persona, d, embedder, preview=args.preview)
        total += n
        s.commit()
        print(f"[ok] {d.title or d.id}: added {n} bio facts")

    print(f"[done] inserted {total} bio facts for {args.persona}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
