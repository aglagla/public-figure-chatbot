# backend/app/services/prompting.py
from datetime import date

DEFAULT_IDENTITY_TEMPLATE = """\
You are {name}. Answer in first person as {name}.
Stay in character: tone={tone_hint}. Use typical phrases and cadence {phrase_hint}.
Do not say you are an AI or language model. Do not mention training or datasets.

Ground rules:
- If asked about your life (birthplace, childhood, family, education, jobs, awards), answer from your perspective.
- Prefer concrete, concise statements. If you don't recall a detail, say "I don't recall" or "I'm not certain," not that you are an AI.
- If the user asks about events after your active period, say you can't personally know and speak hypothetically if helpful.

Context date: {today}
"""

def build_persona_system_message(
    name: str,
    style_prompt: str | None = None,
    bio_facts: list[str] | None = None,
    today: str | None = None,
) -> list[dict]:
    today = today or date.today().isoformat()
    tone_hint = "clear, curious, witty"  # default if no style prompt
    phrase_hint = "when appropriate"     # default

    # If you’ve stored a richer style prompt, use it as the tone scaffold.
    style = (style_prompt or "").strip()
    if style:
        tone_hint = "based on the style prompt below"
        phrase_hint = "matching the style prompt below"

    identity = DEFAULT_IDENTITY_TEMPLATE.format(
        name=name, tone_hint=tone_hint, phrase_hint=phrase_hint, today=today
    )

    msgs = [{"role": "system", "content": identity}]
    if style:
        msgs.append({"role": "system", "content": f"Style prompt for {name}:\n{style}"})
    if bio_facts:
        joined = "\n".join(f"- {f}" for f in bio_facts)
        msgs.append({"role": "system", "content": f"Biographical facts (authoritative; do not contradict):\n{joined}"})
    return msgs
