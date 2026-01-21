-- Migration: Initial Production Memory Architecture Schema
-- Run this migration to set up the conversation management system

-- Check if tables already exist (idempotent migration)
DO $$
BEGIN
    -- Create conversations table if not exists
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'conversations') THEN
        CREATE TABLE conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            user_id TEXT,
            metadata JSONB DEFAULT '{}'::jsonb,
            summary TEXT,
            session_id TEXT UNIQUE,
            verified_target TEXT
        );
        
        CREATE INDEX idx_conversations_created ON conversations(created_at);
        CREATE INDEX idx_conversations_updated ON conversations(updated_at);
        CREATE INDEX idx_conversations_user ON conversations(user_id);
        
        RAISE NOTICE 'Created conversations table';
    ELSE
        RAISE NOTICE 'conversations table already exists';
    END IF;
    
    -- Create conversation_messages table if not exists
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'conversation_messages') THEN
        CREATE TABLE conversation_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            sequence_number INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            metadata JSONB DEFAULT '{}'::jsonb
        );
        
        CREATE INDEX idx_messages_conversation ON conversation_messages(conversation_id, sequence_number);
        CREATE INDEX idx_messages_created ON conversation_messages(created_at);
        CREATE INDEX idx_messages_conversation_role ON conversation_messages(conversation_id, role);
        
        RAISE NOTICE 'Created conversation_messages table';
    ELSE
        RAISE NOTICE 'conversation_messages table already exists';
    END IF;
    
    -- Create agent_states table if not exists
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'agent_states') THEN
        CREATE TABLE agent_states (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            state_type TEXT NOT NULL,
            state_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(conversation_id, state_type)
        );
        
        CREATE INDEX idx_states_conversation ON agent_states(conversation_id);
        CREATE INDEX idx_states_type ON agent_states(state_type);
        CREATE INDEX idx_states_updated ON agent_states(updated_at);
        
        RAISE NOTICE 'Created agent_states table';
    ELSE
        RAISE NOTICE 'agent_states table already exists';
    END IF;
    
    -- Create update function if not exists
    IF NOT EXISTS (SELECT FROM pg_proc WHERE proname = 'update_updated_at_column') THEN
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        RAISE NOTICE 'Created update_updated_at_column function';
    END IF;
    
    -- Create triggers if not exist
    IF NOT EXISTS (SELECT FROM pg_trigger WHERE tgname = 'update_conversations_updated_at') THEN
        CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        RAISE NOTICE 'Created update_conversations_updated_at trigger';
    END IF;
    
    IF NOT EXISTS (SELECT FROM pg_trigger WHERE tgname = 'update_agent_states_updated_at') THEN
        CREATE TRIGGER update_agent_states_updated_at BEFORE UPDATE ON agent_states
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        RAISE NOTICE 'Created update_agent_states_updated_at trigger';
    END IF;
END $$;
