-- eProc Agent — Database Schema
-- PostgreSQL + pgvector for RAG

CREATE EXTENSION IF NOT EXISTS vector;

-- ── Documents table ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documentos (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    titulo TEXT,
    tipo TEXT DEFAULT 'Manual',              -- Manual, FAQ, Tutorial, Guia
    secao TEXT,                               -- Seção do manual
    assunto_resumo TEXT,                      -- Resumo gerado por LLM
    tags TEXT[] DEFAULT '{}',
    total_chunks INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Chunks table (with vector embeddings) ───────────────────────
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    documento_id INTEGER REFERENCES documentos(id) ON DELETE CASCADE,
    conteudo_texto TEXT NOT NULL,
    chunk_index INTEGER,
    pagina INTEGER,
    secao TEXT,
    embedding vector(3072),                   -- OpenAI text-embedding-3-large
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indexes ─────────────────────────────────────────────────────
-- Vector similarity search (IVFFlat)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Full-text search (Portuguese)
CREATE INDEX IF NOT EXISTS idx_chunks_fulltext
    ON chunks USING gin (to_tsvector('portuguese', conteudo_texto));

-- Foreign key lookup
CREATE INDEX IF NOT EXISTS idx_chunks_documento_id
    ON chunks (documento_id);

-- ── Conversations table (optional history) ──────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_session
    ON conversations (session_id, created_at);
