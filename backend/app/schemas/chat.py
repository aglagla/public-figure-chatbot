from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class ChatRequest(BaseModel):
    # persona selectors
    persona_id: Optional[int] = None
    persona_name: Optional[str] = Field(default=None, alias="persona")  # accept "persona" too

    # message(s)
    message: Optional[str] = Field(default=None, alias="question")      # accept "question" too
    messages: Optional[List[ChatMessage]] = None

    # generation parameters
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 512
    stream: bool = False

    model_config = ConfigDict(populate_by_name=True)  # allow aliases

    @model_validator(mode="after")
    def _ensure_input(self):
        if not self.message and not self.messages:
            raise ValueError("Either 'message' (or 'question') or 'messages' is required.")
        return self

class ChatResponse(BaseModel):
    answer: str
    persona_id: int
    persona_name: str

