# backend/app/config.py
from typing import Optional

# Support both pydantic v2 (pydantic-settings) and v1
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict  # v2
except Exception:  # pragma: no cover
    try:
        from pydantic import BaseSettings  # v1
        SettingsConfigDict = None  # type: ignore
    except Exception:
        # Absolute fallback if pydantic is very old
        from pydantic import BaseModel as BaseSettings  # type: ignore
        SettingsConfigDict = None  # type: ignore

from pydantic import Field


class Settings(BaseSettings):
    # ---- Core backend ----
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@db:5432/chatbot",
        env="DATABASE_URL",
    )
    backend_host: str = Field(default="0.0.0.0", env="BACKEND_HOST")
    backend_port: int = Field(default=8000, env="BACKEND_PORT")

    # ---- LLM (OpenAI-compatible endpoint) ----
    llm_base_url: str = Field(default="http://llm_cpu:8000/v1", env="LLM_BASE_URL")
    llm_api_key: str = Field(default="not-needed", env="LLM_API_KEY")
    llm_model: str = Field(default="default", env="LLM_MODEL")

    # ---- Embeddings ----
    # If you call a remote TEI server, set EMBEDDINGS_BASE_URL (e.g., http://embeddings_cpu:80)
    embeddings_base_url: Optional[str] = Field(default=None, env="EMBEDDINGS_BASE_URL")

    # The embedding model **name** (used by local fallback or for consistency with TEI)
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        env="EMBEDDING_MODEL",
    )

    # v2 config
    if SettingsConfigDict:
        model_config = SettingsConfigDict(
            env_file=".env",
            extra="ignore",
            case_sensitive=False,
        )
    else:
        # v1 config
        class Config:  # type: ignore
            env_file = ".env"
            case_sensitive = False
            extra = "ignore"

    # ---------- Back-compat uppercase aliases ----------
    # Some parts of the code or scripts may reference uppercase names.
    @property
    def LLM_BASE_URL(self) -> str:  # noqa: N802
        return self.llm_base_url

    @property
    def LLM_API_KEY(self) -> str:  # noqa: N802
        return self.llm_api_key

    @property
    def LLM_MODEL(self) -> str:  # noqa: N802
        return self.llm_model

    @property
    def EMBEDDING_MODEL(self) -> str:  # noqa: N802
        # singular alias
        return self.embedding_model

    @property
    def EMBEDDINGS_MODEL(self) -> str:  # noqa: N802
        # plural alias for older scripts
        return self.embedding_model

    @property
    def EMBEDDINGS_BASE_URL(self) -> Optional[str]:  # noqa: N802
        return self.embeddings_base_url


# Instantiate a single settings object to import elsewhere
settings = Settings()
