
"""Initialize DB schema (run once).

Usage:
    python -m backend.app.db.init_db
"""
from sqlalchemy import text
from backend.app.db.session import engine, Base
from backend.app.db import models

def ensure_pgvector():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

def create_all():
    ensure_pgvector()
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    create_all()
    print("DB initialized.")
