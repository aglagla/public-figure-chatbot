import os
import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# Load .env if available (harmless in Docker)
load_dotenv()

# Inside Docker, backend is reachable via service DNS; outside, use localhost
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000").rstrip("/")
def render_footer(
   text: str = "",
    height_px: int = 44,
    light_bg: str = "rgba(255, 255, 255, 0.92)",  # light translucent
    dark_bg: str  = "rgba(0, 0, 0, 0.65)",        # dark translucent
    light_fg: str = "rgba(17, 17, 17, 0.98)",     # near-black text
    dark_fg: str  = "rgba(255, 255, 255, 0.98)",  # near-white text
):
    st.markdown(
        f"""
        <style>
          :root {{
            --footer-h: {height_px}px;
            --footer-pad: max(8px, env(safe-area-inset-bottom));
            --footer-bg: {light_bg};
            --footer-fg: {light_fg};
            --footer-border: rgba(49,51,63,.2);
          }}
          @media (prefers-color-scheme: dark) {{
            :root {{
              --footer-bg: {dark_bg};
              --footer-fg: {dark_fg};
              --footer-border: rgba(255,255,255,.18);
            }}
          }}

          /* Lift ONLY the chat input so the footer fits underneath */
          .stApp [data-testid="stChatInput"],
          div[data-testid="stChatInput"],
          .stChatInput,
          [class*="stChatInput"] {{
            bottom: calc(var(--footer-h) + var(--footer-pad)) !important;
          }}

          /* Fixed footer with centered text and its own background */
          #app-centered-footer {{
            position: fixed; left: 0; right: 0; bottom: 0;
            height: calc(var(--footer-h) + var(--footer-pad));
            display: flex; align-items: center; justify-content: center;
            padding: 0 12px var(--footer-pad) 12px;
            background-color: var(--footer-bg);
            color: var(--footer-fg) !important;
            border-top: 1px solid var(--footer-border);
            font-size: .85rem;
            z-index: 99999;
            text-align: center;
            backdrop-filter: saturate(125%) blur(6px);
            -webkit-backdrop-filter: saturate(125%) blur(6px);
            pointer-events: none; /* don't block clicks */
          }}
        </style>
        <div id="app-centered-footer">{text}</div>
        """,
        unsafe_allow_html=True,
    )
st.set_page_config(page_title="Public Figure Chatbot", page_icon="🗣️", layout="wide")
st.title("🗣️ Public Figure Chatbot")

# -------- Helpers --------

@st.cache_data(ttl=15, show_spinner=False)
def fetch_personas():
    url = f"{BACKEND_URL}/personas"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    # Normalize to include has_style flag if backend didn't send it
    for p in data:
        if "has_style" not in p:
            p["has_style"] = False
    return data

def fetch_persona_detail(pid: int):
    url = f"{BACKEND_URL}/personas/{pid}"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        return r.json()
    return {}

def post_chat(persona_id, persona_name, messages, **gen):
    # Send a flexible payload the backend /chat accepts.
    payload = {
        "persona_id": persona_id,
        "persona_name": persona_name,
        "messages": messages,
    }
    # Generation knobs if provided
    payload.update({k: v for k, v in gen.items() if v is not None})
    url = f"{BACKEND_URL}/chat"
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()

def ensure_session():
    if "history" not in st.session_state:
        st.session_state.history = []  # list of {"role": ..., "content": ...}
    if "selected_persona" not in st.session_state:
        st.session_state.selected_persona = None

ensure_session()

# -------- Sidebar: persona + controls --------
with st.sidebar:
    st.subheader("Persona")
    try:
        personas = fetch_personas()
    except Exception as e:
        st.error(f"Failed to load personas: {e}")
        personas = []

    # Refresh button clears cache
    if st.button("↻ Refresh personas", use_container_width=True):
        fetch_personas.clear()
        st.experimental_rerun()

    if personas:
        names = [p["name"] for p in personas]
        idx_default = 0
        # Keep previous selection if present
        if st.session_state.selected_persona:
            try:
                idx_default = names.index(st.session_state.selected_persona["name"])
            except ValueError:
                pass
        selected_name = st.selectbox("Choose a persona:", names, index=idx_default)
        selected = next(p for p in personas if p["name"] == selected_name)
        st.session_state.selected_persona = selected

        if not selected.get("has_style", False):
            st.info("No style profile yet — chatting will still work, but tone-matching may be less accurate.")

        # Show style preview if available
        if selected.get("has_style"):
            # try to fetch full style prompt for transparency
            detail = fetch_persona_detail(selected["id"])
            sp = (detail.get("style_prompt") or selected.get("style_preview") or "").strip()
            if sp:
                with st.expander("Style profile (preview)", expanded=False):
                    st.markdown(sp[:1200] + ("…" if len(sp) > 1200 else ""))

    else:
        st.warning("No personas found. Ingest transcripts or books first.")

    st.divider()
    if st.button("🧹 New chat", use_container_width=True):
        st.session_state.history = []
        st.experimental_rerun()

# -------- Main chat area --------

# Render existing history
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input (disabled until a persona is selected)
user_input = st.chat_input("Ask me anything…" if st.session_state.get("selected_persona") else "Select a persona to start…", disabled=not st.session_state.get("selected_persona"))

render_footer(
    text="© 2025 Alexis Gil Gonzales - ELVTR AISA Capstone Project",
    light_fg="rgba(255, 215, 0, 1)",  # gold
    dark_fg="rgba(255, 215, 0, 1)"
)

if user_input and st.session_state.selected_persona:
    # show user message
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.history.append({"role": "user", "content": user_input})

    # Build OpenAI-style messages: history includes user/assistant turns
    messages = [ {"role": m["role"], "content": m["content"]} for m in st.session_state.history ]

    # Call backend
    try:
        sel = st.session_state.selected_persona
        persona_id = sel.get("id")
        persona_name = sel.get("name")
        with st.spinner("Thinking…"):
            data = post_chat(
                persona_id=persona_id,
                persona_name=persona_name,
                messages=messages,
                temperature=float(os.getenv("CHAT_TEMPERATURE", "0.7")),
                top_p=float(os.getenv("CHAT_TOP_P", "0.9")),
                max_tokens=int(os.getenv("CHAT_MAX_TOKENS", "512")),
            )
        answer = data.get("answer", "")
        if not answer:
            answer = "_(no answer)_"
        with st.chat_message("assistant"):
            st.markdown(answer)
        st.session_state.history.append({"role": "assistant", "content": answer})

    except requests.HTTPError as e:
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text if e.response is not None else str(e)
        st.error(f"Request failed ({e.response.status_code if e.response else ''}): {detail}")
    except Exception as e:
        st.error(f"Request failed: {e}")
