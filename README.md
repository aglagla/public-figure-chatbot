# EVTR AI Solution Architect certificate capstone project
# Public Figure Chatbot (RAG + Persona Style + impersonation)

The chatbot uses RAG (retrieval-augmented generation) over your transcripts/books and answers in the figure's tone, vocabulary, and idiosyncrasies.

## Components

- **Frontend:** Streamlit (modern, simple UX, all-Python)
- **Backend:** FastAPI
- **DB:** PostgreSQL + `pgvector` for embeddings
- **Models:** Open‑source LLMs (e.g., `gpt-oss`, Llama/Mistral via an OpenAI-compatible endpoint)
- **Embeddings:** Text-Embedding Inference (TEI) as first choice.  sentence-transformers  as fallback.

> ⚠️ You can point this to any OpenAI-compatible LLM server (local or remote). See `doc/deployment.md`.

## Quick Start (Docker)

2 profiles for model inference servers : cpu and gpu

1. Copy `.env.example` to `.env` and fill values.
2. Put books into `scripts/sample_data/books_txt/` (text files).
3. Run:
   ```bash
   docker compose up --profile cpu --build -d
   docker compose exec backend bash -lc "python -m backend.app.db.init_db && python scripts/ingest_books.py --doc-type book --persona 'Your Figure' scripts/sample_data/books_txt"
   docker compose exec backend bash -lc "python scripts/compute_style_profile.py --persona 'Your Figure'"
   ```
4. Open Streamlit at http://localhost:8501

## Without Docker (dev only)
- Start Postgres with pgvector extension and set `DATABASE_URL`.
- `pip install -r backend/requirements.txt`
- `pip install -r frontend/requirements.txt`
- Initialize DB and ingest transcripts as above, then:
  ```bash
  uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
  streamlit run frontend/streamlit_app.py
  ```

## Documentation

[Architecture Overview](doc/architecture_overview.md)
[Design Patterns](doc/design_patterns.md)
[Deployment](doc/deployment.md)
[Frontend UX](doc/frontend_ux.md)


## Helper scripts

A few helper scripts are present : 

- `pdf_to_text.py` : 	convert pdf documents into text files. Does a little cleanup to remove headers, footers, and clutter.
- `db_reset.py` :	reset database
- `db_update.py` : 	update database after changing the model
