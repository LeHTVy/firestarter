"""Wrapper for web search tool to match tool executor interface."""

from typing import Dict, Any, Optional
from websearch.aggregator import SearchAggregator
import os


def search(query: str, num_results: int = 10, **kwargs) -> Dict[str, Any]:
    """Web search wrapper for tool executor.
    
    Args:
        query: Search query
        num_results: Number of results
        **kwargs: Additional parameters
        
    Returns:
        Search results in tool executor format
    """
    try:
        serpapi_key = os.getenv('SERPAPI_API_KEY')
        aggregator = SearchAggregator(serpapi_key=serpapi_key)
        
        result = aggregator.search(
            query=query,
            num_results=num_results,
            fetch_content=kwargs.get('fetch_content', True),
            rank_results=kwargs.get('rank_results', True),
            verify_results=kwargs.get('verify_results', True)
        )
        
        if result.get("success"):
            return {
                "success": True,
                "results": result.get("results", []),
                "raw_output": str(result),
                "query": query,
                "total_found": result.get("total_found", 0)
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "results": None
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "results": None
        }
