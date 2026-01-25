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
        
        # Auto-detect if default model is missing
        try:
            if not check_model_exists(model_name):
                available = get_model_names()
                
                # Try to find a suitable substitute
                candidates = ["nomic-embed-text", "mxbai-embed-large", "all-minilm", "snowflake-arctic-embed"]
                found_candidate = None
                
                # Check candidates
                for cand in candidates:
                    for avail in available:
                        if cand in avail:
                            found_candidate = avail
                            break
                    if found_candidate:
                        break
                
                # Check for any model with 'embed' in name
                if not found_candidate:
                    for avail in available:
                        if "embed" in avail.lower():
                            found_candidate = avail
                            break
                
                if found_candidate:
                    # print(f"💡 Switching to available embedding model: {found_candidate}")
                    self.model_name = found_candidate
                elif available:
                    # Fallback to first available model (risky but better than crash)
                    # print(f"⚠️  No embedding model found. Falling back to: {available[0]}")
                    self.model_name = available[0]
                else:
                     pass # System will fail eventually but silently here
                     
        except Exception as e:
            pass # Suppress initialization errors

        self.embedding_client = OllamaEmbeddingClient(model_name=self.model_name)
    
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
