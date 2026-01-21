"""Logs patterns index."""

from knowledge.llamaindex_setup import LlamaIndexKnowledgeBase
from typing import Dict, Any


class LogsIndex:
    """Logs patterns index wrapper."""
    
    def __init__(self, knowledge_base: LlamaIndexKnowledgeBase):
        """Initialize logs index.
        
        Args:
            knowledge_base: LlamaIndex knowledge base instance
        """
        self.kb = knowledge_base
        if "logs" not in self.kb.indices:
            self.kb.setup_logs_index()
    
    def query(self, pattern: str, top_k: int = 5) -> Dict[str, Any]:
        """Query logs patterns.
        
        Args:
            pattern: Log pattern to search
            top_k: Number of results
            
        Returns:
            Query results
        """
        return self.kb.query(pattern, index_type="logs", top_k=top_k)
