-- Production Memory Architecture Schema
-- PostgreSQL schema for conversation management, message storage, and agent state persistence

-- Conversation metadata table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    user_id TEXT,  -- For future multi-user support
    metadata JSONB DEFAULT '{}'::jsonb,
    summary TEXT,  -- Compressed summary of old messages
    session_id TEXT UNIQUE,  -- Legacy session_id for migration compatibility
    verified_target TEXT  -- Verified target domain for this conversation
);

-- Conversation messages (full history buffer)
CREATE TABLE IF NOT EXISTS conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for conversation_messages
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON conversation_messages(conversation_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_messages_created ON conversation_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_role ON conversation_messages(conversation_id, role);

-- Agent state (persistent state storage)
CREATE TABLE IF NOT EXISTS agent_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    state_type TEXT NOT NULL,  -- 'session_memory', 'agent_context', 'context', etc.
    state_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(conversation_id, state_type)  -- One state per type per conversation
);

-- Indexes for agent_states
CREATE INDEX IF NOT EXISTS idx_states_conversation ON agent_states(conversation_id);
CREATE INDEX IF NOT EXISTS idx_states_type ON agent_states(state_type);
CREATE INDEX IF NOT EXISTS idx_states_updated ON agent_states(updated_at);

-- Indexes for conversations
CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to auto-update updated_at
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agent_states_updated_at BEFORE UPDATE ON agent_states
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Vector embeddings table for semantic memory (pgvector)
-- This table stores embeddings for long-term semantic memory
CREATE TABLE IF NOT EXISTS vector_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    collection_name TEXT NOT NULL DEFAULT 'default',
    text TEXT NOT NULL,
    embedding vector(768),  -- nomic-embed-text uses 768 dimensions
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- HNSW index for fast similarity search (cosine distance)
CREATE INDEX IF NOT EXISTS idx_vector_embeddings_hnsw ON vector_embeddings 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Indexes for filtering and namespace isolation
CREATE INDEX IF NOT EXISTS idx_vector_embeddings_conversation_collection 
    ON vector_embeddings(conversation_id, collection_name);
CREATE INDEX IF NOT EXISTS idx_vector_embeddings_collection 
    ON vector_embeddings(collection_name);
CREATE INDEX IF NOT EXISTS idx_vector_embeddings_created 
    ON vector_embeddings(created_at);

-- GIN index for JSONB metadata filtering
CREATE INDEX IF NOT EXISTS idx_vector_embeddings_metadata 
    ON vector_embeddings USING gin(metadata);
