
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.app.schemas.chat import ChatRequest, ChatResponse, ChatMessage
from backend.app.db.session import SessionLocal
from backend.app.db import models
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.retrieval import search_chunks
from backend.app.services.llm import LLMClient
from backend.app.services.style import build_style_system_prompt
from backend.app.config import settings
from backend.app.schemas.persona import PersonaOut
import requests
from backend.app.services.retrieval_bio import is_bio_question, search_bio
from backend.app.services.prompting import build_persona_system_message


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Lazily-initialized singletons
_embedder = None
_llm = None

def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = EmbeddingService(settings.embedding_model)
    return _embedder

def get_llm():
    global _llm
    if _llm is None:
        _llm = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
    return _llm

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/personas", response_model=List[PersonaOut])  # you can omit response_model if you prefer
def list_personas():
    with SessionLocal() as s:
        items = s.query(models.PersonaProfile).order_by(models.PersonaProfile.name).all()
        out = []
        for p in items:
            sp = (p.style_prompt or "")
            has_style = bool(sp.strip())
            out.append({
                "id": p.id,
                "name": p.name,
                "has_style": has_style,
                "style_preview": sp[:120] if has_style else None,
            })
        return out

@router.get("/personas/{persona_id}")
def get_persona(persona_id: int):
    with SessionLocal() as s:
        p = s.query(models.PersonaProfile).get(persona_id)
        if not p:
            return {"error": "not found"}
        return {
            "id": p.id,
            "name": p.name,
            "style_prompt": p.style_prompt,
            "top_phrases": p.top_phrases,
        }

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Persona-impersonating chat with biographical grounding.
    Expects ChatRequest (flexible schema) and returns ChatResponse.
    """
    # 1. Resolve persona
    with SessionLocal() as s:
        persona = None
        if req.persona_id is not None:
            persona = s.get(models.PersonaProfile, req.persona_id)

        if persona is None and getattr(req, "persona_name", None):
            persona = (
                s.query(models.PersonaProfile)
                 .filter(models.PersonaProfile.name == req.persona_name)
                 .first()
            )

        if persona is None:
            persona = (
                s.query(models.PersonaProfile)
                 .order_by(models.PersonaProfile.id.asc())
                 .first()
            )

        if persona is None:
            raise HTTPException(status_code=404, detail="No personas exist yet. Ingest content first.")

        # 2. Build system messages (identity + style + bio) 
        # Find the latest user utterance (for bio routing)
        last_user = ""
        for m in reversed(req.messages or []):
            try:
                role = m.role
                content = m.content
            except Exception:
                role = (m.get("role") if isinstance(m, dict) else None)
                content = (m.get("content") if isinstance(m, dict) else None)
            if role == "user" and content:
                last_user = content.strip()
                break

        # Try to fetch bio facts if question is biographical
        bio_facts = []
        if last_user and is_bio_question(last_user):
            try:
                bio_facts = search_bio(persona.id, last_user, k=5)  # List[str]
            except Exception:
                bio_facts = []

        # Identity/impersonation system messages
        system_msgs = build_persona_system_message(
            name=persona.name,
            style_prompt=(persona.style_prompt or ""),
            bio_facts=bio_facts or None,
        )

        # Final message array: system (identity + optional style + optional bio) + user/assistant turns
        payload_msgs: list[dict] = list(system_msgs)

        # Normalize ChatMessage objects into dicts (supports Pydantic v1/v2 or raw dicts)
        for m in (req.messages or []):
            try:
                payload_msgs.append(m.model_dump())  # pydantic v2
            except Exception:
                try:
                    payload_msgs.append(m.dict())      # pydantic v1
                except Exception:
                    # assume already a dict-like
                    payload_msgs.append({"role": m["role"], "content": m["content"]})

    # 3. Call LLM (OpenAI-compatible)
    body = {
        "model": settings.llm_model,           # e.g., "default" for llama.cpp server
        "messages": payload_msgs,
        "temperature": req.temperature,
        "top_p": req.top_p,
        "max_tokens": req.max_tokens,
        "stream": False,
    }
    headers = {}
    if getattr(settings, "llm_api_key", None):
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    try:
        r = requests.post(
            f"{settings.llm_base_url}/chat/completions",
            headers=headers,
            json=body,
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}") from e

    # 4. Parse response safely
    answer = None
    try:
        # OpenAI-style chat response
        answer = data["choices"][0]["message"]["content"]
    except Exception:
        # Some servers use text completion shape
        try:
            answer = data["choices"][0].get("text")
        except Exception:
            answer = None

    if not answer or not isinstance(answer, str):
        raise HTTPException(status_code=502, detail=f"Unexpected LLM response: {data}")

    # 5. Return answer
    return ChatResponse(
        answer=answer,
        persona_id=persona.id,
        persona_name=persona.name,
    )
