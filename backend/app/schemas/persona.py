from typing import Optional
from pydantic import BaseModel  # ok for pydantic v1/v2 here

class PersonaOut(BaseModel):
    id: int
    name: str
    has_style: bool
    style_preview: Optional[str] = None

    class Config:
        orm_mode = True  
