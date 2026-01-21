"""CVE database index."""

from knowledge.llamaindex_setup import LlamaIndexKnowledgeBase


class CVEIndex:
    """CVE database index wrapper."""
    
    def __init__(self, knowledge_base: LlamaIndexKnowledgeBase):
        """Initialize CVE index.
        
        Args:
            knowledge_base: LlamaIndex knowledge base instance
        """
        self.kb = knowledge_base
        if "cve" not in self.kb.indices:
            self.kb.setup_cve_index()
    
    def query(self, cve_id: Optional[str] = None, query: Optional[str] = None, top_k: int = 5) -> Dict[str, Any]:
        """Query CVE database.
        
        Args:
            cve_id: Specific CVE ID
            query: General query
            top_k: Number of results
            
        Returns:
            Query results
        """
        if cve_id:
            query_str = f"CVE-{cve_id}"
        elif query:
            query_str = query
        else:
            return {"success": False, "error": "Either cve_id or query must be provided"}
        
        return self.kb.query(query_str, index_type="cve", top_k=top_k)
