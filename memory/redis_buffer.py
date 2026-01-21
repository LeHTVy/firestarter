"""Redis buffer for short-term memory (conversation buffer and active state).

This implements the short-term memory layer for ChatGPT-like architecture:
- Sliding window of recent messages
- Active agent state
- Chain-of-thought reasoning
- Automatic TTL for cleanup
"""

import os
import json
from typing import List, Dict, Any, Optional
from datetime import timedelta
import redis


class RedisBuffer:
    """Redis-based short-term memory buffer.
    
    Stores:
    - Recent conversation messages (sliding window)
    - Active agent state
    - Chain-of-thought reasoning
    - Temporary context
    """
    
    def __init__(self, 
                 default_ttl: int = 3600,
                 max_messages: int = 50):
        """Initialize Redis buffer.
        
        Args:
            default_ttl: Default TTL in seconds for buffer entries (default: 1 hour)
            max_messages: Maximum number of messages to keep in buffer (default: 50)
        """
        self.default_ttl = default_ttl
        self.max_messages = max_messages
        
        # Redis connection settings
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD", None)
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        
        # Initialize Redis client
        try:
            self.client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                db=self.redis_db,
                decode_responses=True
            )
            # Test connection
            self.client.ping()
        except Exception as e:
            import warnings
            warnings.warn(f"Redis connection failed: {e}. Buffer operations will be disabled.")
            self.client = None
    
    def _key(self, conversation_id: str, key_type: str) -> str:
        """Generate Redis key.
        
        Args:
            conversation_id: Conversation UUID
            key_type: Type of key (messages, state, etc.)
            
        Returns:
            Redis key string
        """
        return f"firestarter:buffer:{conversation_id}:{key_type}"
    
    def health_check(self) -> bool:
        """Check if Redis connection is healthy.
        
        Returns:
            True if Redis is accessible, False otherwise
        """
        if self.client is None:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            return False
    
    def add_message(self, 
                   conversation_id: str,
                   role: str,
                   content: str,
                   metadata: Optional[Dict[str, Any]] = None):
        """Add message to conversation buffer.
        
        Args:
            conversation_id: Conversation UUID
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata
        """
        if self.client is None:
            return
        
        try:
            key = self._key(conversation_id, "messages")
            
            from datetime import datetime
            message = {
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Add to list (right push)
            self.client.rpush(key, json.dumps(message))
            
            # Trim to max_messages (keep most recent)
            self.client.ltrim(key, -self.max_messages, -1)
            
            # Set TTL
            self.client.expire(key, self.default_ttl)
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to add message to Redis buffer: {str(e)}")
    
    def get_recent_messages(self, 
                           conversation_id: str,
                           n: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages from buffer.
        
        Args:
            conversation_id: Conversation UUID
            n: Number of messages to retrieve (default: 10)
            
        Returns:
            List of message dicts
        """
        if self.client is None:
            return []
        
        try:
            key = self._key(conversation_id, "messages")
            
            # Get last n messages
            messages_json = self.client.lrange(key, -n, -1)
            
            messages = []
            for msg_json in messages_json:
                try:
                    messages.append(json.loads(msg_json))
                except json.JSONDecodeError:
                    continue
            
            return messages
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to get messages from Redis buffer: {str(e)}")
            return []
    
    def clear_messages(self, conversation_id: str):
        """Clear all messages for a conversation.
        
        Args:
            conversation_id: Conversation UUID
        """
        if self.client is None:
            return
        
        try:
            key = self._key(conversation_id, "messages")
            self.client.delete(key)
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to clear messages from Redis buffer: {str(e)}")
    
    def set_state(self, 
                 conversation_id: str,
                 state_type: str,
                 data: Dict[str, Any],
                 ttl: Optional[int] = None):
        """Set agent state.
        
        Args:
            conversation_id: Conversation UUID
            state_type: Type of state (e.g., 'agent_context', 'chain_of_thought')
            data: State data dict
            ttl: Optional TTL in seconds (uses default if None)
        """
        if self.client is None:
            return
        
        try:
            key = self._key(conversation_id, f"state:{state_type}")
            
            self.client.set(
                key,
                json.dumps(data),
                ex=ttl or self.default_ttl
            )
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to set state in Redis buffer: {str(e)}")
    
    def get_state(self, 
                 conversation_id: str,
                 state_type: str) -> Optional[Dict[str, Any]]:
        """Get agent state.
        
        Args:
            conversation_id: Conversation UUID
            state_type: Type of state
            
        Returns:
            State data dict or None if not found
        """
        if self.client is None:
            return None
        
        try:
            key = self._key(conversation_id, f"state:{state_type}")
            
            data_json = self.client.get(key)
            if data_json:
                return json.loads(data_json)
            return None
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to get state from Redis buffer: {str(e)}")
            return None
    
    def delete_state(self, conversation_id: str, state_type: str):
        """Delete agent state.
        
        Args:
            conversation_id: Conversation UUID
            state_type: Type of state
        """
        if self.client is None:
            return
        
        try:
            key = self._key(conversation_id, f"state:{state_type}")
            self.client.delete(key)
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to delete state from Redis buffer: {str(e)}")
    
    def clear_conversation(self, conversation_id: str):
        """Clear all buffer data for a conversation.
        
        Args:
            conversation_id: Conversation UUID
        """
        if self.client is None:
            return
        
        try:
            # Get all keys for this conversation
            pattern = self._key(conversation_id, "*")
            keys = self.client.keys(pattern)
            
            if keys:
                self.client.delete(*keys)
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to clear conversation from Redis buffer: {str(e)}")
