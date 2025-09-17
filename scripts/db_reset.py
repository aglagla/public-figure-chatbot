#!/usr/bin/env python3
"""
Drop & recreate all ORM tables based on current models.
Requires DATABASE_URL env (your .env already has it).
"""

import os
from sqlalchemy import create_engine, text
from backend.app.db.session import Base
from backend.app.db import models  # ensure models are imported/registered

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@db:5432/chatbot",
)

def main():
    engine = create_engine(DB_URL, future=True)
    with engine.begin() as conn:
        # Ensure pgvector exists before creating tables with Vector columns
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        # Drop then create (respect FK order)
        Base.metadata.drop_all(bind=conn)
        Base.metadata.create_all(bind=conn)
    print("Database schema re-initialized from current models.")

if __name__ == "__main__":
    main()
