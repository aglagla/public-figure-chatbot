#!/usr/bin/env python3
"""
Convert all PDFs in a directory (recursively) to UTF-8 .txt files,
with light cleanup (de-hyphenation, header/footer heuristics).

Usage:
  python scripts/pdf_to_text.py path/to/books_dir --out scripts/converted_txt
"""
import argparse, os, re, sys
from pathlib import Path

def dehyphenate(text: str) -> str:
    # Join words split across line breaks with hyphens
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)

def strip_headers_footers(pages):
    """
    Remove lines that look like running headers/footers:
    - Page numbers
    - Repeated short lines across many pages
    """
    from collections import Counter
    line_counts = Counter()
    for pg in pages:
        for ln in pg.splitlines():
            s = ln.strip()
            if s:
                line_counts[s] += 1

    threshold = max(3, int(len(pages) * 0.5))
    repeated = {ln for ln, c in line_counts.items() if c >= threshold and len(ln) <= 60}

    clean_pages = []
    for pg in pages:
        keep = []
        for ln in pg.splitlines():
            s = ln.strip()
            if not s: 
                keep.append("")
                continue
            if s.isdigit() or re.fullmatch(r"Page\s*\d+\s*", s, flags=re.I):
                continue
            if s in repeated:
                continue
            keep.append(ln)
        clean_pages.append("\n".join(keep))
    return clean_pages

def pdf_to_text_single(pdf_path: Path) -> str:
    try:
        from pdfminer.high_level import extract_text
    except Exception as e:
        print("ERROR: pdfminer.six is required. Install with: python -m pip install pdfminer.six", file=sys.stderr)
        raise

    raw = extract_text(str(pdf_path)) or ""
    if not raw.strip():
        return raw

    pages = re.split(r"\f", raw)
    if len(pages) == 1:
        pages = re.split(r"\n\s*Page\s+\d+\s*\n", raw, flags=re.I)

    pages = strip_headers_footers(pages)
    text = "\n\n".join(pages)
    text = dehyphenate(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="Directory with .pdf files (recursive)")
    ap.add_argument("--out", default="scripts/converted_txt", help="Output directory for .txt files")
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    count = 0
    for pdf in src.rglob("*.pdf"):
        rel = pdf.relative_to(src)
        txt_path = out / rel.with_suffix(".txt")
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = pdf_to_text_single(pdf)
        except Exception as e:
            print(f"[warn] failed to read {pdf}: {e}", file=sys.stderr)
            continue
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[ok] {txt_path}")
        count += 1

    print(f"Done. Converted {count} PDFs to text in {out}.")

if __name__ == "__main__":
    main()
