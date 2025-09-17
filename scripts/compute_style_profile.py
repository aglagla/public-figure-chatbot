
#!/usr/bin/env python3
"""Compute a lightweight style profile from ingested transcripts.

This extracts top n-grams and sample phrases to seed a style prompt.
You can later refine `style_prompt` manually in the DB if desired.

Usage:
  python scripts/compute_style_profile.py --persona "Public Figure"
"""
import argparse, re, collections
from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal
from backend.app.db import models

STOPWORDS = set("""a an the and or but if is are was were be being been of to in on for with as by from at that this these those i you he she it we they me him her us them my your his her its our their not no do does did so such just really very like kind sort lot lots maybe perhaps actually honestly literally""".split())

def tokenize(text):
    return [t.lower() for t in re.findall(r"[a-zA-Z']+", text)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", required=True)
    ap.add_argument("--top", type=int, default=30, help="Top n-grams per category")
    args = ap.parse_args()
    with SessionLocal() as session:
        persona = session.query(models.PersonaProfile).filter_by(name=args.persona).one_or_none()
        if not persona:
            print("Persona not found. Ingest transcripts first.")
            return
        # Collect all text
        texts = []
        for doc in persona.documents:
            for ch in doc.chunks:
                texts.append(ch.text)
        text = "\n".join(texts)

        toks = tokenize(text)
        unigrams = [t for t in toks if t not in STOPWORDS and len(t) > 2]
        bigrams = [" ".join(pair) for pair in zip(toks, toks[1:]) if all(len(w)>2 and w not in STOPWORDS for w in pair)]
        trigrams = [" ".join(tri) for tri in zip(toks, toks[1:], toks[2:]) if all(len(w)>2 and w not in STOPWORDS for w in tri)]

        cnt_uni = collections.Counter(unigrams).most_common(args.top)
        cnt_bi = collections.Counter(bigrams).most_common(args.top)
        cnt_tri = collections.Counter(trigrams).most_common(args.top)

        style_prompt = (
            f"Use concise sentences. Favor the most frequent words and collocations below. "
            f"Show warmth yet directness if appropriate. Avoid exaggerated verbosity. Reflect the cadence of interview answers."
        )
        top_phrases = {
            "unigrams": [w for w,_ in cnt_uni],
            "bigrams": [w for w,_ in cnt_bi],
            "trigrams": [w for w,_ in cnt_tri],
            "catchphrases": [w for w,_ in cnt_bi[:10]],
        }

        persona.style_prompt = style_prompt
        persona.top_phrases = top_phrases
        session.commit()
        print("Updated style profile for:", args.persona)

if __name__ == "__main__":
    main()
