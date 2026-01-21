"""Cross-source verification for search results."""

from typing import Dict, Any, List
from collections import Counter


class ResultVerifier:
    """Verifier for cross-checking search results."""
    
    def verify_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Verify and cross-check search results.
        
        Args:
            results: List of search results
            
        Returns:
            Verification results with confidence scores
        """
        verified_results = []
        
        for result in results:
            verification = {
                "result": result,
                "confidence": self._calculate_confidence(result, results),
                "sources_count": self._count_similar_sources(result, results),
                "verification_status": "verified" if self._is_verified(result, results) else "unverified"
            }
            verified_results.append(verification)
        
        return {
            "success": True,
            "verified_results": verified_results,
            "total_results": len(results),
            "verified_count": sum(1 for v in verified_results if v["verification_status"] == "verified")
        }
    
    def _calculate_confidence(self, result: Dict[str, Any], all_results: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for a result.
        
        Args:
            result: Result to evaluate
            all_results: All search results
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 0.5  # Base confidence
        
        # Check domain authority (simple heuristic)
        domain = self._extract_domain(result.get("link", ""))
        if domain:
            # Trusted domains get higher confidence
            trusted_domains = [".edu", ".gov", ".org", "wikipedia.org", "github.com"]
            if any(trusted in domain for trusted in trusted_domains):
                confidence += 0.2
        
        # Check if information appears in multiple sources
        similar_count = self._count_similar_sources(result, all_results)
        if similar_count > 1:
            confidence += min(0.3, similar_count * 0.1)
        
        # Check recency (if date available)
        if result.get("date"):
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _count_similar_sources(self, result: Dict[str, Any], all_results: List[Dict[str, Any]]) -> int:
        """Count similar sources for a result.
        
        Args:
            result: Result to check
            all_results: All search results
            
        Returns:
            Number of similar sources
        """
        result_text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
        count = 0
        
        for other_result in all_results:
            if other_result == result:
                continue
            
            other_text = f"{other_result.get('title', '')} {other_result.get('snippet', '')}".lower()
            
            # Simple similarity check (word overlap)
            result_words = set(result_text.split())
            other_words = set(other_text.split())
            
            if len(result_words & other_words) > 3:  # At least 3 common words
                count += 1
        
        return count
    
    def _is_verified(self, result: Dict[str, Any], all_results: List[Dict[str, Any]]) -> bool:
        """Check if result is verified by multiple sources.
        
        Args:
            result: Result to check
            all_results: All search results
            
        Returns:
            True if verified
        """
        similar_count = self._count_similar_sources(result, all_results)
        return similar_count >= 2
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL.
        
        Args:
            url: URL
            
        Returns:
            Domain name
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return ""
