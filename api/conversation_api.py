"""Conversation management API for production memory architecture."""

from typing import Dict, Any, List, Optional
from memory.conversation_store import ConversationStore
from memory.namespace_manager import NamespaceManager
from memory.manager import MemoryManager


class ConversationAPI:
    """API for conversation management and switching."""
    
    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        """Initialize conversation API.
        
        Args:
            memory_manager: Optional MemoryManager instance (creates new if None)
        """
        self.conversation_store = ConversationStore()
        self.namespace_manager = NamespaceManager()
        self.memory_manager = memory_manager
    
    def create_conversation(self, title: Optional[str] = None, target_domain: Optional[str] = None) -> Dict[str, Any]:
        """Create new conversation.
        
        Args:
            title: Optional conversation title
            target_domain: Optional target domain
            
        Returns:
            Conversation metadata dict
        """
        conversation_id = self.conversation_store.create_conversation(title=title)
        
        # Update verified target if provided
        if target_domain:
            self.conversation_store.update_verified_target(conversation_id, target_domain)
        
        # Get created conversation
        conversation = self.conversation_store.get_conversation(conversation_id)
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "conversation": conversation
        }
    
    def list_conversations(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List all conversations.
        
        Args:
            limit: Maximum number of conversations to return
            offset: Offset for pagination
            
        Returns:
            Dictionary with conversations list
        """
        conversations = self.conversation_store.list_conversations(limit=limit, offset=offset)
        
        return {
            "success": True,
            "conversations": conversations,
            "count": len(conversations)
        }
    
    def get_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Get conversation details.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Dictionary with conversation details
        """
        conversation = self.conversation_store.get_conversation(conversation_id)
        
        if not conversation:
            return {
                "success": False,
                "error": f"Conversation {conversation_id} not found"
            }
        
        # Get message count
        message_count = self.conversation_store.get_message_count(conversation_id)
        
        return {
            "success": True,
            "conversation": conversation,
            "message_count": message_count
        }
    
    def switch_conversation(self, conversation_id: str, memory_manager: Optional[MemoryManager] = None) -> Dict[str, Any]:
        """Switch active conversation.
        
        Args:
            conversation_id: Conversation UUID to switch to
            memory_manager: Optional MemoryManager instance (uses self.memory_manager if None)
            
        Returns:
            Dictionary with switch result
        """
        mgr = memory_manager or self.memory_manager
        
        if not mgr:
            return {
                "success": False,
                "error": "MemoryManager not provided"
            }
        
        try:
            # Switch conversation in memory manager
            mgr.switch_conversation(conversation_id)
            
            # Get conversation context
            context = self.namespace_manager.load_conversation_context(conversation_id)
            
            return {
                "success": True,
                "conversation_id": conversation_id,
                "context": context
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Delete conversation and all associated data.
        
        Args:
            conversation_id: Conversation UUID to delete
            
        Returns:
            Dictionary with deletion result
        """
        try:
            # Verify conversation exists
            conversation = self.conversation_store.get_conversation(conversation_id)
            if not conversation:
                return {
                    "success": False,
                    "error": f"Conversation {conversation_id} not found"
                }
            
            # Delete conversation (CASCADE will delete messages and states)
            self.conversation_store.delete_conversation(conversation_id)
            
            return {
                "success": True,
                "conversation_id": conversation_id,
                "message": "Conversation deleted successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def update_conversation_title(self, conversation_id: str, title: str) -> Dict[str, Any]:
        """Update conversation title.
        
        Args:
            conversation_id: Conversation UUID
            title: New title
            
        Returns:
            Dictionary with update result
        """
        try:
            self.conversation_store.update_conversation_title(conversation_id, title)
            return {
                "success": True,
                "conversation_id": conversation_id,
                "title": title
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_conversation_messages(self, conversation_id: str, limit: Optional[int] = None, offset: int = 0) -> Dict[str, Any]:
        """Get messages for a conversation.
        
        Args:
            conversation_id: Conversation UUID
            limit: Maximum number of messages (None for all)
            offset: Offset for pagination
            
        Returns:
            Dictionary with messages
        """
        try:
            messages = self.conversation_store.get_messages(conversation_id, limit=limit, offset=offset)
            return {
                "success": True,
                "conversation_id": conversation_id,
                "messages": messages,
                "count": len(messages)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_recent_messages(self, conversation_id: str, k: int = 10) -> Dict[str, Any]:
        """Get recent messages for a conversation.
        
        Args:
            conversation_id: Conversation UUID
            k: Number of recent messages to return
            
        Returns:
            Dictionary with recent messages
        """
        try:
            messages = self.conversation_store.get_recent_messages(conversation_id, k=k)
            return {
                "success": True,
                "conversation_id": conversation_id,
                "messages": messages,
                "count": len(messages)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
