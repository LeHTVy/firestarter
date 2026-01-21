"""Embedding wrapper using LangChain Ollama embeddings."""

from typing import List
from models.llm_client import OllamaEmbeddingClient


class NemotronEmbeddings:
    """Wrapper for Ollama embeddings using LangChain (replacing Nemotron).
    
    Uses LangChain's OllamaEmbeddings for consistent embedding generation.
    """
    
    def __init__(self, model_name: str = "nomic-embed-text"):
        """Initialize embeddings.
        
        Args:
            model_name: Ollama embedding model name (default: nomic-embed-text)
        """
        self.model_name = model_name
        self.embedding_client = OllamaEmbeddingClient(model_name=model_name)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed documents.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings
        """
        return self.embedding_client.embed_documents(texts)
    
    def embed_query(self, text: str) -> List[float]:
        """Embed query.
        
        Args:
            text: Query text
            
        Returns:
            Embedding vector
        """
        return self.embedding_client.embed_query(text)
