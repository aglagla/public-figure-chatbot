
from typing import Dict, List
from sqlalchemy.orm import Session
from backend.app.db import models

def build_style_system_prompt(session: Session, persona_name: str) -> str:
    """Fetch PersonaProfile and form a system style prompt."""
    persona = session.query(models.PersonaProfile).filter_by(name=persona_name).one_or_none()
    if not persona:
        return f"You are to answer as {persona_name}. Keep responses concise, direct, and authentic."
    catch = persona.top_phrases.get("catchphrases") if persona.top_phrases else None
    bullets = "\n".join([f"- {c}" for c in (catch or [])])
    style = persona.style_prompt or "Speak naturally."
    return f"""
You are simulating **{persona.name}**. Adopt their tone, vocabulary, pacing, and rhetorical style.

Style guardrails:
{style}

Signature expressions and phrases:
{bullets}

Rules:
- Answer truthfully based on the provided context from their interviews.
- If unsure or outside their public record, say so—don't invent personal facts.
- Keep it grounded; avoid generic filler.
- Cite sources briefly as [#] where relevant.
"""
