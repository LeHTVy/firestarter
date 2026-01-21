"""IOC database index."""

from knowledge.llamaindex_setup import LlamaIndexKnowledgeBase
from typing import Dict, Any


class IOCIndex:
    """IOC database index wrapper."""
    
    def __init__(self, knowledge_base: LlamaIndexKnowledgeBase):
        """Initialize IOC index.
        
        Args:
            knowledge_base: LlamaIndex knowledge base instance
        """
        self.kb = knowledge_base
        if "ioc" not in self.kb.indices:
            self.kb.setup_ioc_index()
    
    def query(self, ioc: str, ioc_type: Optional[str] = None, top_k: int = 5) -> Dict[str, Any]:
        """Query IOC database.
        
        Args:
            ioc: IOC value
            ioc_type: IOC type (ip, hash, domain, url)
            top_k: Number of results
            
        Returns:
            Query results
        """
        query_str = ioc
        if ioc_type:
            query_str = f"{ioc_type}: {ioc}"
        
        return self.kb.query(query_str, index_type="ioc", top_k=top_k)
