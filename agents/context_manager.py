"""Context Manager - Centralized Context Handling for Firestarter.

Single source of truth for session context.
All nodes and agents use this instead of scattered context dicts.

Adapted from rutx with enhancements for firestarter.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime
import re


@dataclass
class SessionContext:
    """
    Immutable snapshot of context for a single request.
    
    This is the structured representation passed between nodes,
    replacing the ad-hoc Dict[str, Any] that was losing data.
    """
    # Target information (prioritized: target_domain > last_domain > url > ip)
    target_domain: Optional[str] = None
    target_ip: Optional[str] = None
    url_target: Optional[str] = None
    last_domain: Optional[str] = None
    last_candidate: Optional[str] = None  # For target verification flow
    
    # Discovered assets
    subdomains: List[str] = field(default_factory=list)
    open_ports: List[Dict[str, Any]] = field(default_factory=list)
    detected_tech: List[str] = field(default_factory=list)
    vulns_found: List[Dict[str, Any]] = field(default_factory=list)
    
    # Session tracking
    tools_run: List[str] = field(default_factory=list)
    current_phase: int = 1
    last_agent: Optional[str] = None
    current_agent: Optional[str] = None
    
    # Counts (for quick access)
    subdomain_count: int = 0
    port_count: int = 0
    
    # Flags
    has_subdomains: bool = False
    has_ports: bool = False
    is_correction: bool = False  # User correcting target
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def get_target(self) -> Optional[str]:
        """
        Get the prioritized target.
        
        Priority order:
        1. target_domain (explicitly verified)
        2. last_domain (from conversation)
        3. Extract from url_target
        4. target_ip
        """
        if self.target_domain and self._is_valid_domain(self.target_domain):
            return self.target_domain
        if self.last_domain and self._is_valid_domain(self.last_domain):
            return self.last_domain
        if self.url_target:
            domain = self._extract_domain_from_url(self.url_target)
            if domain:
                return domain
        if self.target_ip and self._is_valid_ip(self.target_ip):
            return self.target_ip
        return None
    
    def _is_valid_domain(self, domain: str) -> bool:
        """Check if string looks like a valid domain."""
        if not domain:
            return False
        pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        return bool(re.match(pattern, domain))
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Check if string looks like a valid IP."""
        if not ip:
            return False
        pattern = r'^(?:\d{1,3}\.){3}\d{1,3}$'
        return bool(re.match(pattern, ip))
    
    def _extract_domain_from_url(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc if parsed.netloc else None
        except:
            return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionContext":
        """
        Create SessionContext from dictionary.
        
        Handles legacy context dicts gracefully.
        """
        # Map legacy keys to new structure
        mapped = {}
        
        # Target fields
        mapped["target_domain"] = data.get("target_domain")
        mapped["target_ip"] = data.get("target_ip")
        mapped["url_target"] = data.get("url_target")
        mapped["last_domain"] = data.get("last_domain")
        mapped["last_candidate"] = data.get("last_candidate")
        
        # Assets
        mapped["subdomains"] = data.get("subdomains", [])
        mapped["open_ports"] = data.get("open_ports", [])
        mapped["detected_tech"] = data.get("detected_tech", [])
        mapped["vulns_found"] = data.get("vulns_found", [])
        
        # Session
        mapped["tools_run"] = data.get("tools_run", [])
        mapped["current_phase"] = data.get("current_phase", 1)
        mapped["last_agent"] = data.get("last_agent")
        mapped["current_agent"] = data.get("current_agent")
        
        # Counts
        mapped["subdomain_count"] = data.get("subdomain_count", len(mapped["subdomains"]))
        mapped["port_count"] = data.get("port_count", len(mapped["open_ports"]))
        
        # Flags
        mapped["has_subdomains"] = data.get("has_subdomains", len(mapped["subdomains"]) > 0)
        mapped["has_ports"] = data.get("has_ports", len(mapped["open_ports"]) > 0)
        mapped["is_correction"] = data.get("is_correction", False)
        
        return cls(**{k: v for k, v in mapped.items() if v is not None or k in ["target_domain", "target_ip"]})
    
    def merge_with(self, updates: Dict[str, Any]) -> "SessionContext":
        """
        Create new SessionContext with updates applied.
        
        Immutable pattern - returns new instance.
        """
        current = self.to_dict()
        
        # Handle list merges specially (don't replace, extend)
        list_fields = ["subdomains", "open_ports", "detected_tech", "vulns_found", "tools_run"]
        for field in list_fields:
            if field in updates and updates[field]:
                existing = current.get(field, [])
                new_items = updates[field]
                if isinstance(new_items, list):
                    # Dedupe while preserving order
                    combined = existing + [x for x in new_items if x not in existing]
                    updates[field] = combined
        
        # Apply updates
        current.update(updates)
        current["updated_at"] = datetime.now().isoformat()
        
        # Update counts
        current["subdomain_count"] = len(current.get("subdomains", []))
        current["port_count"] = len(current.get("open_ports", []))
        current["has_subdomains"] = current["subdomain_count"] > 0
        current["has_ports"] = current["port_count"] > 0
        
        return SessionContext.from_dict(current)


class ContextManager:
    """
    Centralized context handling - single source of truth.
    
    Aggregates from:
    - Session state (current request)
    - Memory Manager (persistent findings)
    - Agent Context (shared findings)
    
    Usage:
        ctx_mgr = get_context_manager()
        context = ctx_mgr.get_context()
        target = context.get_target()
    """
    
    def __init__(self):
        self._session_context: Optional[SessionContext] = None
        self._memory_manager = None
    
    def set_memory_manager(self, memory_manager):
        """Set memory manager instance."""
        self._memory_manager = memory_manager
    
    def get_context(self, state: Optional[Dict[str, Any]] = None) -> SessionContext:
        """
        Get current session context.
        
        Args:
            state: Optional state dictionary to extract context from
            
        Returns:
            SessionContext instance
        """
        if state:
            # Extract from state
            return SessionContext.from_dict(state.get("context", {}))
        
        if self._session_context:
            return self._session_context
        
        # Create new context
        self._session_context = SessionContext()
        return self._session_context
    
    def update_context(self, updates: Dict[str, Any], state: Optional[Dict[str, Any]] = None) -> SessionContext:
        """
        Update context with new information.
        
        Args:
            updates: Dictionary with context updates
            state: Optional state dictionary
            
        Returns:
            Updated SessionContext
        """
        current = self.get_context(state)
        updated = current.merge_with(updates)
        
        # Update internal state
        self._session_context = updated
        
        # Also update memory manager if available
        if self._memory_manager:
            self._memory_manager.update_agent_context(updates)
        
        return updated
    
    def get_target(self, state: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get current target (domain/IP)."""
        context = self.get_context(state)
        return context.get_target()


# Singleton instance
_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """Get singleton context manager instance."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
