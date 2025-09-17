import os
from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, Float, Date, DateTime, func, JSON
)
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from backend.app.db.session import Base

# Try to pick up the embedding dimension from env (or keep a sane default).
# TEI models like BAAI/bge-small-en-v1.5 -> 384; bge-large -> 1024; MiniLM -> 384.
_EMB_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

# Core domain entities

class PersonaProfile(Base):
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)

    # Optional, can store the curated "voice prompt" and lexical stats
    style_prompt = Column(Text, nullable=True)
    top_phrases = Column(JSON, nullable=True)  # e.g., {"catchphrases": [...], "bigrams": [...]}

    # Relationships
    documents = relationship("Document", back_populates="persona", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="persona", cascade="all, delete-orphan")


class Document(Base):
    """
    A source document attached to a persona. Can be a transcript, book, article, etc.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), index=True, nullable=False)

    # Optional metadata
    title = Column(String(512), nullable=True)
    source = Column(String(1024), nullable=True)

    # Back-compat for scripts that set doc_type="book"|"transcript"
    doc_type = Column(String(32), nullable=True)

    # Future-proof: a more generic content type and a JSON blob for extra fields
    content_type = Column(String(32), nullable=True)   # e.g., "book", "transcript"
    meta = Column(JSON, nullable=True)                 # e.g., {"date":"...", "interviewer":"..."}

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    persona = relationship("PersonaProfile", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """
    A retrievable chunk of a document.
    """
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), index=True, nullable=False)
    order = Column(Integer, nullable=False, default=0)  # chunk order in the document
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="chunks")
    embedding = relationship("Embedding", back_populates="chunk", uselist=False, cascade="all, delete-orphan")


class Embedding(Base):
    """
    Vector embedding for a chunk (pgvector).
    Ensure EMBEDDING_DIM matches the dimension of your embedding model.
    """
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id"), unique=True, nullable=False)
    vector = Column(Vector(_EMB_DIM), nullable=False)  # float4[] using pgvector
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chunk = relationship("Chunk", back_populates="embedding")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), index=True, nullable=False)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    persona = relationship("PersonaProfile", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True, nullable=False)
    role = Column(String(20), nullable=False)  # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")

# Biographical data

class BioSource(Base):
    __tablename__ = "bio_sources"
    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)       # e.g., "Wikipedia", "Authorized biography"
    url = Column(String(1024), nullable=True)
    license = Column(String(128), nullable=True)
    reliability = Column(Float, default=0.7)

class BioFact(Base):
    __tablename__ = "bio_facts"
    id = Column(Integer, primary_key=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), index=True, nullable=False)
    source_id = Column(Integer, ForeignKey("bio_sources.id"), nullable=True)
    fact_text = Column(Text, nullable=False)         # 1–3 sentences, atomic fact
    date_start = Column(Date, nullable=True)
    date_end = Column(Date, nullable=True)
    location = Column(String(256), nullable=True)
    tags = Column(JSON, nullable=True)               # ["early-life","education","award",...]
    embedding = Column(Vector(_EMB_DIM), nullable=False)

    source = relationship("BioSource")

