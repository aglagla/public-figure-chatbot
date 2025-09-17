
# Deployment Guide

## Prerequisites
- Docker and Docker Compose (recommended) OR Python 3.11 environment + Postgres with `pgvector`.
- An OpenAI-compatible LLM endpoint for an open-source model (e.g., vLLM serving `llama-3.1-8b-instruct`).

Note: if you don't have a moderl server, just download them with the huggingface-cli (see below).

## Environment

Decide how you're going to serve LLM and TEI models.

If local, run (for example) : 
```bash
python -m pip install -U "huggingface_hub[cli]"
huggingface-cli download BAAI/bge-small-en-v1.5 --local-dir /models/embeddings/bge-small-en-v1.5/
huggingface-cli download   bartowski/Meta-Llama-3.1-8B-Instruct-GGUF   --include "Meta-Llama-3.1-8B-Instruct-Q5_K_S.gguf"   --local-dir /models/llm/llama-3.1-8b-instruct-gguf
```

Copy `.env.example` → `.env` and set:
- `DATABASE_URL`: e.g. `postgresql+psycopg2://postgres:postgres@db:5432/chatbot`
- `LLM_BASE_URL`: e.g. `http://llm:8001/v1`
- `LLM_API_KEY`: a token if your server requires one (dummy otherwise)
- `LLM_MODEL`: e.g. `gpt-oss`, `llama-3.1-8b-instruct`, `mistral-7b-instruct`
- `EMBEDDING_MODEL`: default `sentence-transformers/all-MiniLM-L6-v2`

## Bringup (Docker)

We have 2 different profiles : cpu and gpu
cpu is faster and images are small. Be aware than building the gpu profile may require quite some disk space (downloads lots of pytorch libs).

```bash
# build & start with your profile
docker compose up --profile <cpu | gpu> --build -d
# initialize db
docker compose exec backend bash -lc "python -m backend.app.db.init_db"
# optional : convert pdf to txt
python3 scripts/pdf_to_text.py --out scripts/sample_data/books_txt/ scripts/sample_data/books_pdf
# ingest documents (books in this example)
docker compose exec backend bash -lc "python scripts/ingest_books.py --doc-type book --debug --persona 'Your Figure' scripts/sample_data/books_txt/"
# extract style & tone
docker compose exec backend bash -lc "python scripts/compute_style_profile.py --persona 'Your Figure'"
```

Open frontend: http://localhost:8501

## Bringup (Manual)
- Start Postgres with `pgvector` extension enabled.
- Install requirements:
  ```bash
  pip install -r backend/requirements.txt
  pip install -r frontend/requirements.txt
  ```
- Initialize DB:
  ```bash
  python -m backend.app.db.init_db
  ```
- Ingest transcripts and compute style profile (see above).
- Start services:
  ```bash
  uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
  streamlit run frontend/streamlit_app.py
  ```

## Model Serving Examples

### vLLM
Run an OpenAI-compatible API (example):
```bash
docker run --gpus all -p 8001:8000   -v ~/.cache/huggingface:/root/.cache/huggingface   vllm/vllm-openai:latest   --model meta-llama/Meta-Llama-3.1-8B-Instruct --host 0.0.0.0 --port 8000
```
Then set `LLM_BASE_URL=http://localhost:8001/v1` and `LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct`.

### LM Studio
Enable the OpenAI-compatible server and set base URL accordingly.

### Text Generation Inference (TGI)
Use an OpenAI proxy or call via a small adapter (extend `LLMClient`).

## Production Hardening - next steps

- Add auth (API keys/JWT) and rate limiting at an API gateway.
- Add Alembic for migrations if you change schemas.
- Observability: logs, metrics, tracing; persist token usage from LLM responses.
- Consider moderation filters and output-guardrails if going public.
