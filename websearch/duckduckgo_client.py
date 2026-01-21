"""DuckDuckGo client for web search (free fallback)."""

import time
from typing import Dict, Any, List, Optional

# Try to import duckduckgo-search library (supports both old and new package names)
try:
    try:
        from ddgs import DDGS  # New package name
        DDGS_AVAILABLE = True
    except ImportError:
        from duckduckgo_search import DDGS  # Old package name
        DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    DDGS = None


class DuckDuckGoClient:
    """Client for DuckDuckGo search (free, no API key required)."""
    
    def __init__(self):
        """Initialize DuckDuckGo client."""
        if not DDGS_AVAILABLE:
            raise ImportError(
                "duckduckgo-search library not installed. "
                "Install with: pip install duckduckgo-search"
            )
        self.ddgs = DDGS()
    
    def search(self, query: str, num_results: int = 10, **kwargs) -> Dict[str, Any]:
        """Perform web search using DuckDuckGo.
        
        Args:
            query: Search query
            num_results: Number of results to return
            **kwargs: Additional search parameters (ignored for now)
            
        Returns:
            Search results in same format as SerpAPI
        """
        try:
            # DuckDuckGo search
            results = list(self.ddgs.text(
                query,
                max_results=num_results,
                safesearch='moderate'
            ))
            
            # Format results to match SerpAPI format
            formatted_results = {
                "query": query,
                "total_results": len(results),
                "results": []
            }
            
            for i, result in enumerate(results, 1):
                formatted_results["results"].append({
                    "title": result.get("title", ""),
                    "link": result.get("href", ""),
                    "snippet": result.get("body", ""),
                    "position": i,
                    "date": None  # DuckDuckGo doesn't provide dates
                })
            
            return {
                "success": True,
                "results": formatted_results,
                "raw": results,
                "source": "duckduckgo"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "results": None,
                "source": "duckduckgo"
            }
    
    def search_multiple_queries(self, queries: List[str], num_results: int = 10) -> Dict[str, Any]:
        """Search multiple queries and aggregate results.
        
        Args:
            queries: List of search queries
            num_results: Number of results per query
            
        Returns:
            Aggregated search results
        """
        all_results = []
        
        for query in queries:
            result = self.search(query, num_results=num_results)
            if result.get("success"):
                all_results.extend(result["results"]["results"])
            
            # Small delay between queries to avoid rate limiting
            time.sleep(0.5)
        
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            url = result.get("link", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        
        return {
            "success": True,
            "results": unique_results,
            "total_queries": len(queries),
            "total_results": len(unique_results),
            "source": "duckduckgo"
        }
