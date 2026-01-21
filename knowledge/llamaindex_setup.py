"""LlamaIndex knowledge base setup."""

from typing import Dict, Any, Optional
from pathlib import Path

# Try different import paths for LlamaIndex
_llamaindex_available = False
OllamaEmbedding = None
try:
    # LlamaIndex v0.10+ (new structure)
    from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
    ServiceContext = None 
    try:
        from llama_index.embeddings.ollama import OllamaEmbedding
    except ImportError:
        OllamaEmbedding = None
    _llamaindex_available = True
except ImportError:
    try:
        # LlamaIndex v0.9
        from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, ServiceContext
        try:
            from llama_index.embeddings.ollama import OllamaEmbedding
        except ImportError:
            OllamaEmbedding = None
        _llamaindex_available = True
    except ImportError:
        try:
            # Older versions
            from llama_index import VectorStoreIndex, SimpleDirectoryReader, ServiceContext
            try:
                from llama_index.embeddings import OllamaEmbedding
            except ImportError:
                OllamaEmbedding = None
            _llamaindex_available = True
        except ImportError:
            # Fallback: make it optional
            VectorStoreIndex = None
            SimpleDirectoryReader = None
            ServiceContext = None
            OllamaEmbedding = None
            _llamaindex_available = False


class LlamaIndexKnowledgeBase:
    """LlamaIndex knowledge base for CVE, exploits, IOC, logs."""
    
    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize LlamaIndex knowledge base.
        
        Args:
            data_dir: Directory containing knowledge base data
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        
        self.data_dir = data_dir
        self.indices: Dict[str, Any] = {} 
        
        # Check if LlamaIndex is available
        if not _llamaindex_available or VectorStoreIndex is None:
            self.embed_model = None
            self.service_context = None
            self._available = False
            return
        
        self._available = True
        
        # Initialize embeddings (OllamaEmbedding is optional)
        self.embed_model = None
        if OllamaEmbedding is not None:
            try:
                import yaml
                config_path = Path(__file__).parent.parent / "config" / "ollama_config.yaml"
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    embed_model_name = config.get('models', {}).get('nemotron_3_nano', {}).get('model_name', 'nomic-embed-text')
            except:
                embed_model_name = "nomic-embed-text"
            
            try:
                self.embed_model = OllamaEmbedding(model_name=embed_model_name)
            except Exception:
                self.embed_model = None
        
        # ServiceContext is optional in newer versions
        self.service_context = None
        if ServiceContext and self.embed_model:
            try:
                self.service_context = ServiceContext.from_defaults(embed_model=self.embed_model)
            except Exception:
                self.service_context = None
    
    def setup_cve_index(self):
        """Setup CVE database index.
        
        Returns:
            CVE index
        """
        if not self._available or VectorStoreIndex is None or SimpleDirectoryReader is None:
            return None
            
        cve_dir = self.data_dir / "cve"
        if not cve_dir.exists():
            cve_dir.mkdir(parents=True, exist_ok=True)
        
        documents = SimpleDirectoryReader(str(cve_dir)).load_data()
        if self.service_context:
            index = VectorStoreIndex.from_documents(documents, service_context=self.service_context)
        elif self.embed_model:
            index = VectorStoreIndex.from_documents(documents, embed_model=self.embed_model)
        else:
            # Use default embeddings if no custom model
            index = VectorStoreIndex.from_documents(documents)
        self.indices["cve"] = index
        return index
    
    def setup_exploit_index(self):
        """Setup exploit database index.
        
        Returns:
            Exploit index
        """
        exploit_dir = self.data_dir / "exploits"
        if not exploit_dir.exists():
            exploit_dir.mkdir(parents=True, exist_ok=True)
        
        if not self._available or VectorStoreIndex is None or SimpleDirectoryReader is None:
            return None
            
        documents = SimpleDirectoryReader(str(exploit_dir)).load_data()
        if self.service_context:
            index = VectorStoreIndex.from_documents(documents, service_context=self.service_context)
        else:
            index = VectorStoreIndex.from_documents(documents, embed_model=self.embed_model)
        self.indices["exploits"] = index
        return index
    
    def setup_ioc_index(self):
        """Setup IOC database index.
        
        Returns:
            IOC index
        """
        ioc_dir = self.data_dir / "ioc"
        if not ioc_dir.exists():
            ioc_dir.mkdir(parents=True, exist_ok=True)
        
        if not self._available or VectorStoreIndex is None or SimpleDirectoryReader is None:
            return None
            
        documents = SimpleDirectoryReader(str(ioc_dir)).load_data()
        if self.service_context:
            index = VectorStoreIndex.from_documents(documents, service_context=self.service_context)
        else:
            index = VectorStoreIndex.from_documents(documents, embed_model=self.embed_model)
        self.indices["ioc"] = index
        return index
    
    def setup_logs_index(self):
        """Setup logs patterns index.
        
        Returns:
            Logs index
        """
        logs_dir = self.data_dir / "logs"
        if not logs_dir.exists():
            logs_dir.mkdir(parents=True, exist_ok=True)
        
        if not self._available or VectorStoreIndex is None or SimpleDirectoryReader is None:
            return None
            
        documents = SimpleDirectoryReader(str(logs_dir)).load_data()
        if self.service_context:
            index = VectorStoreIndex.from_documents(documents, service_context=self.service_context)
        else:
            index = VectorStoreIndex.from_documents(documents, embed_model=self.embed_model)
        self.indices["logs"] = index
        return index
    
    def setup_all(self):
        """Setup all knowledge base indices."""
        self.setup_cve_index()
        self.setup_exploit_index()
        self.setup_ioc_index()
        self.setup_logs_index()
    
    def query(self, 
             query: str,
             index_type: str = "cve",
             top_k: int = 5) -> Dict[str, Any]:
        """Query knowledge base.
        
        Args:
            query: Query string
            index_type: Type of index (cve, exploits, ioc, logs)
            top_k: Number of results
            
        Returns:
            Query results
        """
        if not self._available:
            return {
                "success": False,
                "error": "LlamaIndex not available",
                "results": []
            }
        
        if index_type not in self.indices:
            return {
                "success": False,
                "error": f"Index '{index_type}' not found. Available: {list(self.indices.keys())}"
            }
        
        index = self.indices[index_type]
        query_engine = index.as_query_engine(similarity_top_k=top_k)
        
        try:
            response = query_engine.query(query)
            return {
                "success": True,
                "query": query,
                "index_type": index_type,
                "response": str(response),
                "source_nodes": [
                    {
                        "text": node.node.text,
                        "score": node.score,
                        "metadata": node.node.metadata
                    }
                    for node in response.source_nodes
                ]
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
