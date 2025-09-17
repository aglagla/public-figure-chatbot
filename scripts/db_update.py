#!/usr/bin/env python3
import os
from sqlalchemy import create_engine, text
from backend.app.db.session import Base
from backend.app.db import models  # registers BioSource/BioFact

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/chatbot")

def main():
    eng = create_engine(DB_URL, future=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        Base.metadata.create_all(bind=conn)  # creates missing tables only
    print("Ensured bio tables and pgvector extension.")

if __name__ == "__main__":
    main()
