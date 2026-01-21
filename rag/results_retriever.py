"""Specialized retriever for tool results."""

from rag.results_storage import ToolResultsStorage
from typing import List, Dict, Any, Optional


class ResultsRetriever:
    """Specialized retriever for tool results Q&A."""
    
    def __init__(self):
        """Initialize results retriever."""
        self.storage = ToolResultsStorage()
    
    def retrieve(self,
                query: str,
                k: int = 5,
                filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve tool results for Q&A.
        
        Args:
            query: User question about results
            k: Number of results
            filters: Additional filters (tool_name, agent, session_id, time_range)
            
        Returns:
            Retrieved results with metadata
        """
        filters = filters or {}
        
        results = self.storage.retrieve_results(
            query=query,
            k=k,
            tool_name=filters.get("tool_name"),
            agent=filters.get("agent"),
            session_id=filters.get("session_id")
        )
        
        return results
