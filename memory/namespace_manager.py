"""Namespace manager for conversation isolation."""

from typing import Dict, Any, Optional
from memory.conversation_store import ConversationStore
import json


class NamespaceManager:
    """Manage conversation namespaces for isolation."""
    
    def __init__(self):
        """Initialize namespace manager."""
        self.conversation_store = ConversationStore()
    
    def get_vector_namespace(self, conversation_id: str) -> str:
        """Get vector DB collection name for conversation.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Collection name for this conversation
        """
        # Use conversation_id as part of collection name for isolation
        # Format: "conversation_{conversation_id}" or use conversation_id directly
        return f"conversation_{conversation_id}"
    
    def get_state_namespace(self, conversation_id: str) -> str:
        """Get state store key for conversation.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            State store key
        """
        return f"state:{conversation_id}"
    
    def load_conversation_context(self, conversation_id: str) -> Dict[str, Any]:
        """Load all context for a conversation.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Dictionary with all conversation context:
            - conversation: metadata
            - messages: recent messages
            - summary: compressed summary
            - agent_state: agent state data
            - verified_target: verified target domain
            - topics: conversation topics
            - active_entities: active entities (domains, IPs)
            - open_tasks: open tasks (subtasks not completed)
        """
        # Get conversation metadata
        conversation = self.conversation_store.get_conversation(conversation_id)
        if not conversation:
            return {}
        
        # Get recent messages (last 20 for context)
        recent_messages = self.conversation_store.get_recent_messages(conversation_id, k=20)
        
        # Get verified target
        verified_target = conversation.get('verified_target')
        
        # Get agent state
        agent_state = self._load_agent_state(conversation_id)
        
        # Extract topics, active entities, and open tasks from agent state
        topics = []
        active_entities = []
        open_tasks = []
        
        if agent_state:
            session_memory = agent_state.get("session_memory", {})
            if isinstance(session_memory, dict):
                agent_context = session_memory.get("agent_context", {})
                if isinstance(agent_context, dict):
                    topics = agent_context.get("topics", [])
                    active_entities = agent_context.get("active_entities", [])
                    open_tasks = agent_context.get("open_tasks", [])
        
        # If not in agent state, try to extract from messages
        if not topics and recent_messages:
            from rag.topic_extractor import TopicExtractor
            extractor = TopicExtractor()
            topics = extractor.extract_topics(recent_messages, max_topics=10)
        
        return {
            "conversation": conversation,
            "messages": recent_messages,
            "summary": conversation.get('summary'),
            "agent_state": agent_state,
            "verified_target": verified_target,
            "topics": topics,
            "active_entities": active_entities,
            "open_tasks": open_tasks,
            "vector_namespace": self.get_vector_namespace(conversation_id),
            "state_namespace": self.get_state_namespace(conversation_id)
        }
    
    def unload_conversation_context(self, conversation_id: str):
        """Unload context (cleanup).
        
        Args:
            conversation_id: Conversation UUID
        """
        # In PostgreSQL-based implementation, we don't need explicit unloading
        # Data persists in database. This method is for future Redis-based caching.
        pass
    
    def _load_agent_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Load agent state from database.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Agent state dict or None
        """
        import os
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        postgres_database = os.getenv("POSTGRES_DATABASE", "firestarter_pg")
        postgres_user = os.getenv("POSTGRES_USER", "firestarter_ad")
        postgres_password = os.getenv("POSTGRES_PASSWORD", "")
        
        try:
            conn = psycopg2.connect(
                host=postgres_host,
                port=postgres_port,
                database=postgres_database,
                user=postgres_user,
                password=postgres_password
            )
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Load all state types for this conversation
            cursor.execute("""
                SELECT state_type, state_data
                FROM agent_states
                WHERE conversation_id = %s
            """, (conversation_id,))
            
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if rows:
                # Combine all state types into one dict
                state = {}
                for row in rows:
                    state_type = row['state_type']
                    state_data = row['state_data']
                    if isinstance(state_data, str):
                        try:
                            state_data = json.loads(state_data)
                        except:
                            pass
                    state[state_type] = state_data
                return state
            
            return None
        except Exception as e:
            # Return None on error (state might not exist yet)
            return None
    
    def save_agent_state(self, conversation_id: str, state_type: str, state_data: Dict[str, Any]):
        """Save agent state to database.
        
        Args:
            conversation_id: Conversation UUID
            state_type: Type of state ('session_memory', 'agent_context', etc.)
            state_data: State data dict
        """
        import os
        import psycopg2
        
        postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        postgres_database = os.getenv("POSTGRES_DATABASE", "firestarter_pg")
        postgres_user = os.getenv("POSTGRES_USER", "firestarter_ad")
        postgres_password = os.getenv("POSTGRES_PASSWORD", "")
        
        try:
            conn = psycopg2.connect(
                host=postgres_host,
                port=postgres_port,
                database=postgres_database,
                user=postgres_user,
                password=postgres_password
            )
            cursor = conn.cursor()
            
            # Use UPSERT (INSERT ... ON CONFLICT UPDATE)
            state_json = json.dumps(state_data)
            cursor.execute("""
                INSERT INTO agent_states (conversation_id, state_type, state_data, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (conversation_id, state_type)
                DO UPDATE SET state_data = EXCLUDED.state_data, updated_at = NOW()
            """, (conversation_id, state_type, state_json))
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            conn.rollback()
            conn.close()
            raise Exception(f"Failed to save agent state: {e}")
