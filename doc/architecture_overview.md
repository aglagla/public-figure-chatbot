
# Architecture Overview

**Goal:** A chatbot that answers like a specific public figure using books, biographical books and interviews as the knowledge base, with a consistent voice (tone, vocabulary, idiosyncrasies).
The chatbot will impersonate the public figure and detect biographical questions.

## Components

- **Frontend (Streamlit):** Minimal, modern Python UI. Renders chat, maintains a `conversation_id`, and displays sources.
- **Backend (FastAPI):** REST API powering chat:
  - `POST /chat` — retrieval + LLM call; persists conversation.
  - `GET /personas` — list of personas loaded.
  - `GET /health` — health check.
- **Database (PostgreSQL + pgvector):**
  - Stores books, biographic books and transcripts as `documents` and `chunks`.
  - Stores embeddings in `embeddings` with `vector` column (vector type).
  - Stores biographic facts in `bio_facts` with `embeddings` column (vector type).
  - Stores biographic source in `bio_sources`.
  - `personas` holds style metadata: `style_prompt`, `top_phrases`.
  - `conversations` and `messages` persist chat history.


## Data Flow

1. **Ingest**: 
	- `scripts/ingest_books.py` chunks books and computes embeddings. Specify doc-type 'book' or 'biography'.
	- `scripts/ingest_transcripts.py` chunks transcripts and computes embeddings.
	- `scripts/extract_bio_facts.py` extracts biographic facts (start/end dates, location, tags) and compute embeddings.
2. **Style**: `scripts/compute_style_profile.py` creates a lightweight style profile.
3. **Query**: Frontend posts a question to backend with the chosen persona.
4. **Retrieve**: 2 levels 
	- Backend tries first to fetch bio facts if it detects a bio question ;
	- Backend embeds the question and runs pgvector similarity to fetch top chunks.
	Also, the backend will inject a system prompt to impersonate the persona (identity).
5. **Compose**: Backend constructs a system style prompt + context blocks.
6. **Generate**: Backend calls an open-source LLM via an OpenAI-compatible API.
7. **Persist**: Messages saved; response returned with [#]-style citations.

## Model Serving

- Any OpenAI-compatible endpoint works (e.g., **vLLM**, **TGI**, **LM Studio**, **Ollama with openai-proxy**).
- Set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` in `.env`.
- Examples: `llama-3.1-8b-instruct`, `mistral-7b-instruct`, or a generic `gpt-oss` alias on your server.

## Embeddings

- Default: Text-Embeddings Inference (TEI) as first choice, fallbacks to  sentence-transformers/all-MiniLM-L6-v2 (384 dims) if not available.
- Change the embedding model in `.env` and update EMBEDDING_DIM dimension accordingly (via migration).

## Data Model

[Data Model Diagram](img/chatbot.svg)


## Citations

- Each retrieved chunk is labeled `[1]... [k]`. The LLM is instructed to cite as `[#]` to keep answers grounded.

## Security & Privacy

- Keep books/bio books and transcripts local if needed.
- TODO: Use role-based auth or a gateway if exposing the backend publicly.

