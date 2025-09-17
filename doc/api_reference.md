
# API Reference

## POST /chat
**Body**
```json
{
  "persona": "Public Figure",
  "question": "What do you think about ...?",
  "conversation_id": 1,
  "top_k": 6
}
```
**Response**
```json
{
  "conversation_id": 1,
  "answer": "...",
  "sources": [
    {"document_id": 10, "title": "...", "source": "path", "chunk_id": 123, "snippet": "...", "score": 0.81}
  ],
  "model": "gpt-oss"
}
```

## GET /personas
Returns a list of available personas by name and id.

## GET /health
Simple health check.
