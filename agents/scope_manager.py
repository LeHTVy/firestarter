"""Scope Manager for authorized target validation."""

from typing import List, Optional, Set
from memory.manager import get_memory_manager
from memory.session import AgentContext


class ScopeManager:
    """Manage authorized scope per conversation.
    
    Scope Manager ensures that tools only execute on authorized targets,
    providing an important security and legal safeguard.
    """
    
    def __init__(self):
        """Initialize Scope Manager."""
        self.memory_manager = get_memory_manager()
    
    def is_target_authorized(self, target: str, conversation_id: Optional[str] = None) -> bool:
        """Check if target is in authorized scope.
        
        Args:
            target: Target domain, IP, or hostname to check
            conversation_id: Conversation UUID (optional)
            
        Returns:
            True if target is authorized, False otherwise
        """
        if not conversation_id:
            # If no conversation_id, check if target was verified in current session
            conversation_id = self.memory_manager.get_current_conversation_id()
        
        if not conversation_id:
            # No conversation context, default to unauthorized for safety
            return False
        
        # Get authorized scope from agent context
        authorized_scope = self.get_authorized_scope(conversation_id)
        
        # Normalize target for comparison
        target_normalized = self._normalize_target(target)
        
        # Check if target matches any authorized scope entry
        for scope_target in authorized_scope:
            scope_normalized = self._normalize_target(scope_target)
            
            # Exact match
            if target_normalized == scope_normalized:
                return True
            
            # Subdomain match (e.g., target=sub.example.com, scope=example.com)
            if target_normalized.endswith('.' + scope_normalized):
                return True
            
            # IP range match (simple CIDR check - can be enhanced)
            if self._is_ip_range_match(target_normalized, scope_normalized):
                return True
        
        return False
    
    def add_to_scope(self, target: str, conversation_id: Optional[str] = None) -> bool:
        """Add target to authorized scope.
        
        Args:
            target: Target domain, IP, or hostname to add
            conversation_id: Conversation UUID (optional)
            
        Returns:
            True if added successfully, False otherwise
        """
        if not conversation_id:
            conversation_id = self.memory_manager.get_current_conversation_id()
        
        if not conversation_id:
            return False
        
        # Get current session memory
        session_memory = self.memory_manager.session_memory
        if not session_memory:
            return False
        
        # Get authorized scope from agent context
        authorized_scope = session_memory.agent_context.get("authorized_scope", [])
        
        # Normalize target
        target_normalized = self._normalize_target(target)
        
        # Add if not already in scope
        if target_normalized not in authorized_scope:
            authorized_scope.append(target_normalized)
            # Update agent context (will be saved when turn is saved)
            # For now, we'll update the session memory directly
            # Note: This requires updating AgentContext to support authorized_scope
            # For immediate implementation, we'll store in a separate field
            session_memory.agent_context.authorized_scope = authorized_scope
        
        return True
    
    def get_authorized_scope(self, conversation_id: Optional[str] = None) -> List[str]:
        """Get authorized scope for conversation.
        
        Args:
            conversation_id: Conversation UUID (optional)
            
        Returns:
            List of authorized targets
        """
        if not conversation_id:
            conversation_id = self.memory_manager.get_current_conversation_id()
        
        if not conversation_id:
            return []
        
        # Try to get from session memory first
        session_memory = self.memory_manager.session_memory
        if session_memory:
            scope = session_memory.agent_context.authorized_scope
            if scope:
                return scope
        
        # Fallback: get verified target from memory manager
        verified_target = self.memory_manager.get_verified_target(
            session_id=conversation_id,
            conversation_id=conversation_id
        )
        
        if verified_target:
            return [verified_target]
        
        return []
    
    def remove_from_scope(self, target: str, conversation_id: Optional[str] = None) -> bool:
        """Remove target from authorized scope.
        
        Args:
            target: Target to remove
            conversation_id: Conversation UUID (optional)
            
        Returns:
            True if removed successfully, False otherwise
        """
        if not conversation_id:
            conversation_id = self.memory_manager.get_current_conversation_id()
        
        if not conversation_id:
            return False
        
        session_memory = self.memory_manager.session_memory
        if not session_memory:
            return False
        
        authorized_scope = session_memory.agent_context.get("authorized_scope", [])
        target_normalized = self._normalize_target(target)
        
        if target_normalized in authorized_scope:
            authorized_scope.remove(target_normalized)
            session_memory.agent_context.authorized_scope = authorized_scope
            return True
        
        return False
    
    def _normalize_target(self, target: str) -> str:
        """Normalize target for comparison.
        
        Args:
            target: Target string
            
        Returns:
            Normalized target string
        """
        # Remove protocol if present
        target = target.replace('https://', '').replace('http://', '').replace('//', '')
        
        # Remove path and query
        if '/' in target:
            target = target.split('/')[0]
        if '?' in target:
            target = target.split('?')[0]
        
        # Remove port if present
        if ':' in target and not target.startswith('['):  # IPv6 check
            parts = target.split(':')
            # Only remove port if second part is numeric
            if len(parts) == 2 and parts[1].isdigit():
                target = parts[0]
        
        # Lowercase and strip
        return target.lower().strip()
    
    def _is_ip_range_match(self, target: str, scope: str) -> bool:
        """Check if target matches IP range in scope.
        
        Args:
            target: Target IP or hostname
            scope: Scope entry (can be IP, CIDR, or domain)
            
        Returns:
            True if matches, False otherwise
        """
        import ipaddress
        
        # Try to parse as IP addresses
        try:
            target_ip = ipaddress.ip_address(target)
            scope_ip = ipaddress.ip_address(scope)
            return target_ip == scope_ip
        except ValueError:
            pass
        
        # Try CIDR match
        try:
            scope_network = ipaddress.ip_network(scope, strict=False)
            target_ip = ipaddress.ip_address(target)
            return target_ip in scope_network
        except (ValueError, ipaddress.AddressValueError):
            pass
        
        return False
