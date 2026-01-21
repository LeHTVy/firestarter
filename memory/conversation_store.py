"""Persistent conversation store for production memory architecture."""

import os
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import json


class ConversationStore:
    """Persistent store for conversation metadata and buffer."""
    
    def __init__(self):
        """Initialize conversation store with PostgreSQL connection."""
        self.postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        self.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.postgres_database = os.getenv("POSTGRES_DATABASE", "firestarter_pg")
        self.postgres_user = os.getenv("POSTGRES_USER", "firestarter_ad")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "")
    
    def _get_connection(self):
        """Get PostgreSQL connection."""
        return psycopg2.connect(
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_database,
            user=self.postgres_user,
            password=self.postgres_password
        )
    
    def create_conversation(self, title: Optional[str] = None, session_id: Optional[str] = None) -> str:
        """Create new conversation, return conversation_id.
        
        Args:
            title: Optional conversation title
            session_id: Optional legacy session_id for migration
            
        Returns:
            conversation_id (UUID string)
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            conversation_id = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO conversations (id, title, session_id, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                RETURNING id
            """, (conversation_id, title, session_id))
            
            conn.commit()
            cursor.close()
            return conversation_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to create conversation: {e}")
        finally:
            conn.close()
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation metadata.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Conversation metadata dict or None
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, title, created_at, updated_at, user_id, metadata, summary, 
                       session_id, verified_target
                FROM conversations
                WHERE id = %s
            """, (conversation_id,))
            
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                return dict(row)
            return None
        except Exception as e:
            raise Exception(f"Failed to get conversation: {e}")
        finally:
            conn.close()
    
    def list_conversations(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List all conversations.
        
        Args:
            limit: Maximum number of conversations to return
            offset: Offset for pagination
            
        Returns:
            List of conversation metadata dicts
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, title, created_at, updated_at, user_id, metadata, summary,
                       session_id, verified_target
                FROM conversations
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            
            rows = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            raise Exception(f"Failed to list conversations: {e}")
        finally:
            conn.close()
    
    def update_conversation_title(self, conversation_id: str, title: str):
        """Update conversation title.
        
        Args:
            conversation_id: Conversation UUID
            title: New title
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE conversations
                SET title = %s, updated_at = NOW()
                WHERE id = %s
            """, (title, conversation_id))
            
            conn.commit()
            cursor.close()
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to update conversation title: {e}")
        finally:
            conn.close()
    
    def update_conversation_summary(self, conversation_id: str, summary: str):
        """Update conversation summary (compressed history).
        
        Args:
            conversation_id: Conversation UUID
            summary: Compressed summary text
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE conversations
                SET summary = %s, updated_at = NOW()
                WHERE id = %s
            """, (summary, conversation_id))
            
            conn.commit()
            cursor.close()
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to update conversation summary: {e}")
        finally:
            conn.close()
    
    def update_verified_target(self, conversation_id: str, target: str, structured_info: Optional[Dict] = None):
        """Update verified target for conversation.
        
        Args:
            conversation_id: Conversation UUID
            target: Verified target domain (for backward compatibility)
            structured_info: Optional structured target info dict with:
                - legal_name: str
                - country: str
                - domain: str
                - asn: Optional[str]
                - ip_ranges: List[str]
                - confidence: float
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Store both simple domain (for backward compatibility) and structured info
            if structured_info:
                # Store structured info in metadata JSONB field
                cursor.execute("""
                    UPDATE conversations
                    SET verified_target = %s,
                        metadata = jsonb_set(
                            COALESCE(metadata, '{}'::jsonb),
                            '{verified_target_structured}',
                            %s::jsonb
                        ),
                        updated_at = NOW()
                    WHERE id = %s
                """, (target, json.dumps(structured_info), conversation_id))
            else:
                # Just update domain (backward compatible)
                cursor.execute("""
                    UPDATE conversations
                    SET verified_target = %s, updated_at = NOW()
                    WHERE id = %s
                """, (target, conversation_id))
            
            conn.commit()
            cursor.close()
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to update verified target: {e}")
        finally:
            conn.close()
    
    def get_verified_target(self, conversation_id: str, structured: bool = False) -> Optional[Any]:
        """Get verified target for conversation.
        
        Args:
            conversation_id: Conversation UUID
            structured: If True, return structured dict; if False, return domain string (backward compatible)
            
        Returns:
            Verified target domain (str) or structured dict, or None
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT verified_target, metadata
                FROM conversations
                WHERE id = %s
            """, (conversation_id,))
            
            row = cursor.fetchone()
            cursor.close()
            
            if not row:
                return None
            
            if structured:
                # Return structured info if available
                metadata = row.get('metadata') or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                
                structured_info = metadata.get('verified_target_structured')
                if structured_info:
                    return structured_info
                
                # Fallback: return simple dict with domain
                domain = row.get('verified_target')
                if domain:
                    return {
                        "domain": domain,
                        "legal_name": "",
                        "country": "",
                        "asn": None,
                        "ip_ranges": [],
                        "confidence": 0.5
                    }
                return None
            else:
                # Backward compatible: return domain string
                return row.get('verified_target')
        except Exception as e:
            raise Exception(f"Failed to get verified target: {e}")
        finally:
            conn.close()
    
    def add_message(self, conversation_id: str, role: str, content: str, metadata: Optional[Dict] = None):
        """Add message to conversation buffer.
        
        Args:
            conversation_id: Conversation UUID
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            metadata: Optional metadata dict
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get next sequence number
            cursor.execute("""
                SELECT COALESCE(MAX(sequence_number), 0) + 1
                FROM conversation_messages
                WHERE conversation_id = %s
            """, (conversation_id,))
            
            sequence_number = cursor.fetchone()[0]
            
            # Insert message
            metadata_json = json.dumps(metadata or {})
            cursor.execute("""
                INSERT INTO conversation_messages 
                (conversation_id, role, content, sequence_number, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (conversation_id, role, content, sequence_number, metadata_json))
            
            # Update conversation updated_at
            cursor.execute("""
                UPDATE conversations
                SET updated_at = NOW()
                WHERE id = %s
            """, (conversation_id,))
            
            conn.commit()
            cursor.close()
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to add message: {e}")
        finally:
            conn.close()
    
    def get_messages(self, conversation_id: str, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        """Get messages with pagination support.
        
        Args:
            conversation_id: Conversation UUID
            limit: Maximum number of messages (None for all)
            offset: Offset for pagination
            
        Returns:
            List of message dicts ordered by sequence_number
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if limit:
                cursor.execute("""
                    SELECT id, role, content, sequence_number, created_at, metadata
                    FROM conversation_messages
                    WHERE conversation_id = %s
                    ORDER BY sequence_number ASC
                    LIMIT %s OFFSET %s
                """, (conversation_id, limit, offset))
            else:
                cursor.execute("""
                    SELECT id, role, content, sequence_number, created_at, metadata
                    FROM conversation_messages
                    WHERE conversation_id = %s
                    ORDER BY sequence_number ASC
                    OFFSET %s
                """, (conversation_id, offset))
            
            rows = cursor.fetchall()
            cursor.close()
            
            messages = []
            for row in rows:
                msg = dict(row)
                if msg.get('metadata'):
                    try:
                        msg['metadata'] = json.loads(msg['metadata']) if isinstance(msg['metadata'], str) else msg['metadata']
                    except:
                        msg['metadata'] = {}
                messages.append(msg)
            
            return messages
        except Exception as e:
            raise Exception(f"Failed to get messages: {e}")
        finally:
            conn.close()
    
    def get_recent_messages(self, conversation_id: str, k: int = 10) -> List[Dict[str, Any]]:
        """Get last K messages (sliding window).
        
        Args:
            conversation_id: Conversation UUID
            k: Number of recent messages to return
            
        Returns:
            List of message dicts (most recent first, then reversed to chronological order)
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, role, content, sequence_number, created_at, metadata
                FROM conversation_messages
                WHERE conversation_id = %s
                ORDER BY sequence_number DESC
                LIMIT %s
            """, (conversation_id, k))
            
            rows = cursor.fetchall()
            cursor.close()
            
            messages = []
            for row in reversed(rows):  # Reverse to get chronological order
                msg = dict(row)
                if msg.get('metadata'):
                    try:
                        msg['metadata'] = json.loads(msg['metadata']) if isinstance(msg['metadata'], str) else msg['metadata']
                    except:
                        msg['metadata'] = {}
                messages.append(msg)
            
            return messages
        except Exception as e:
            raise Exception(f"Failed to get recent messages: {e}")
        finally:
            conn.close()
    
    def get_message_count(self, conversation_id: str) -> int:
        """Get total message count for conversation.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Total number of messages
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM conversation_messages
                WHERE conversation_id = %s
            """, (conversation_id,))
            
            count = cursor.fetchone()[0]
            cursor.close()
            return count
        except Exception as e:
            raise Exception(f"Failed to get message count: {e}")
        finally:
            conn.close()
    
    def delete_conversation(self, conversation_id: str):
        """Delete conversation and all associated data (CASCADE).
        
        Args:
            conversation_id: Conversation UUID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM conversations
                WHERE id = %s
            """, (conversation_id,))
            
            conn.commit()
            cursor.close()
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to delete conversation: {e}")
        finally:
            conn.close()
    
    def get_conversation_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation by legacy session_id (for migration).
        
        Args:
            session_id: Legacy session ID
            
        Returns:
            Conversation metadata dict or None
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, title, created_at, updated_at, user_id, metadata, summary,
                       session_id, verified_target
                FROM conversations
                WHERE session_id = %s
            """, (session_id,))
            
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                return dict(row)
            return None
        except Exception as e:
            raise Exception(f"Failed to get conversation by session_id: {e}")
        finally:
            conn.close()
