
# Design Patterns

## 1. Hexagonal Architecture (Ports & Adapters)
- **Ports:** `LLMClient`, `EmbeddingService`, `search_chunks` (Vector DB port)
- **Adapters:** `openai` SDK client, `sentence-transformers` implementation, `pgvector` SQL.
- Facilitates swapping models/vector DBs without touching core flow.

## 2. Command-Query Responsibility Segregation (CQRS)-like Separation
- **Reads:** Retrieval and generation for chat requests.
- **Writes:** Ingestion scripts handle heavy writes; chat only appends messages.

## 3. Dependency Injection (Lite)
- Use simple `get_llm()`, `get_embedder()` factories to avoid global config in routes.
- Easy to mock in tests.

## 4. RAG Prompt Templating
- System prompt builder (`style.py`) composes persona voice with a strict set of rules to avoid hallucinations.
- Context blocks are assembled separately to improve controllability.

## 5. Idempotent Ingestion
- Persona ensured by name; multiple documents attach to the same persona.
- Chunking deterministic given config.

## 6. Testability
- Business logic kept in `services/` and `utils/` where possible.
- Example test shows how to stub LLM and embeddings.

## 7. Observability Hooks (TODO)
- Add logging, tracing, token usage metrics from `LLMClient.chat`.
- Capture retrieval scores to help debug bad answers.
