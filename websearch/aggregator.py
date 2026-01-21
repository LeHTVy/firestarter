"""Web search aggregator."""

from typing import Dict, Any, List, Optional
from websearch.serpapi_client import SerpAPIClient
from websearch.duckduckgo_client import DuckDuckGoClient
from websearch.fetcher import WebFetcher
from websearch.ranker import NeuralRanker
from websearch.verifier import ResultVerifier


class SearchAggregator:
    """Aggregator for multi-source web search."""
    
    def __init__(self, serpapi_key: Optional[str] = None):
        """Initialize search aggregator.
        
        Args:
            serpapi_key: SerpAPI key
        """
        # Try to initialize SerpAPI (primary)
        self.serpapi = None
        self.serpapi_available = False
        try:
            self.serpapi = SerpAPIClient(api_key=serpapi_key)
            self.serpapi_available = True
        except (ValueError, Exception) as e:
            # SerpAPI not available (no key or error)
            pass
        
        # Initialize DuckDuckGo (fallback)
        self.duckduckgo = None
        self.duckduckgo_available = False
        try:
            self.duckduckgo = DuckDuckGoClient()
            self.duckduckgo_available = True
        except (ImportError, Exception) as e:
            # DuckDuckGo not available
            pass
        
        self.fetcher = WebFetcher()
        self.ranker = NeuralRanker()
        self.verifier = ResultVerifier()
    
    def search(self, 
              query: str,
              num_results: int = 10,
              fetch_content: bool = True,
              rank_results: bool = True,
              verify_results: bool = True) -> Dict[str, Any]:
        """Perform aggregated web search.
        
        Args:
            query: Search query
            num_results: Number of results
            fetch_content: Whether to fetch full content
            rank_results: Whether to rank results
            verify_results: Whether to verify results
            
        Returns:
            Aggregated search results
        """
        # Step 1: Search with SerpAPI (primary) or DuckDuckGo (fallback)
        search_result = None
        search_source = None
        
        # Try SerpAPI first if available
        if self.serpapi_available and self.serpapi:
            try:
                search_result = self.serpapi.search(query, num_results=num_results * 2)
                if search_result.get("success"):
                    search_source = "serpapi"
                else:
                    # Check if it's a quota/rate limit error
                    error = search_result.get("error", "").lower()
                    if any(keyword in error for keyword in ["quota", "rate limit", "limit exceeded", "429"]):
                        # Fallback to DuckDuckGo
                        search_result = None
            except Exception as e:
                # SerpAPI failed, try fallback
                search_result = None
        
        # Fallback to DuckDuckGo if SerpAPI failed or unavailable
        if not search_result or not search_result.get("success"):
            if self.duckduckgo_available and self.duckduckgo:
                try:
                    search_result = self.duckduckgo.search(query, num_results=num_results * 2)
                    if search_result.get("success"):
                        search_source = "duckduckgo"
                except Exception as e:
                    pass
        
        # If both failed, return error
        if not search_result or not search_result.get("success"):
            return {
                "success": False,
                "error": search_result.get("error", "All search providers failed") if search_result else "No search providers available",
                "query": query,
                "results": None
            }
        
        results = search_result["results"]["results"]
        
        # Step 2: Fetch content if requested
        if fetch_content:
            urls = [r["link"] for r in results[:num_results]]
            fetched = self.fetcher.fetch_multiple_urls(urls)
            
            # Merge fetched content with results
            for result in results:
                url = result.get("link", "")
                if url in fetched.get("results", {}):
                    fetched_content = fetched["results"][url]
                    if fetched_content.get("success"):
                        result["full_content"] = fetched_content.get("text", "")
                        result["authors"] = fetched_content.get("authors", [])
                        result["publish_date"] = fetched_content.get("publish_date")
        
        # Step 3: Neural ranking
        if rank_results:
            results = self.ranker.rank_results(query, results, top_k=num_results)
        
        # Step 4: Verification
        if verify_results:
            verification = self.verifier.verify_results(results)
            for i, result in enumerate(results):
                if i < len(verification.get("verified_results", [])):
                    verified = verification["verified_results"][i]
                    result["confidence"] = verified.get("confidence", 0.5)
                    result["verification_status"] = verified.get("verification_status", "unverified")
        
        return {
            "success": True,
            "query": query,
            "results": results[:num_results],
            "total_found": len(results),
            "search_source": search_source,  # "serpapi" or "duckduckgo"
            "aggregation_steps": {
                "search": True,
                "fetch": fetch_content,
                "rank": rank_results,
                "verify": verify_results
            }
        }
    
    def search_multiple_queries(self,
                               queries: List[str],
                               num_results: int = 10) -> Dict[str, Any]:
        """Search multiple queries and aggregate.
        
        Args:
            queries: List of queries
            num_results: Results per query
            
        Returns:
            Aggregated results
        """
        all_results = []
        
        for query in queries:
            result = self.search(query, num_results=num_results)
            if result.get("success"):
                all_results.extend(result["results"])
        
        # Deduplicate and re-rank
        seen_urls = set()
        unique_results = []
        for result in all_results:
            url = result.get("link", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        
        # Re-rank all unique results
        if unique_results:
            # Use first query for ranking
            unique_results = self.ranker.rank_results(queries[0], unique_results, top_k=num_results)
        
        return {
            "success": True,
            "queries": queries,
            "results": unique_results[:num_results],
            "total_results": len(unique_results)
        }
