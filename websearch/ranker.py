"""Neural ranking for search results."""

from typing import Dict, Any, List
import numpy as np
from models.llm_client import OllamaEmbeddingClient


class NeuralRanker:
    """Neural ranker using embeddings for semantic similarity."""
    
    def __init__(self, embedding_model: str = "nomic-embed-text"):
        """Initialize neural ranker.
        
        Args:
            embedding_model: Ollama embedding model name (default: nomic-embed-text)
        """
        self.embedding_model = embedding_model
        self.embedding_client = OllamaEmbeddingClient(model_name=embedding_model)
    
    def _embed_text(self, text: str) -> List[float]:
        """Generate embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or empty list on error
        """
        return self.embedding_client.embed_query(text)
    
    def rank_results(self, 
                    query: str,
                    results: List[Dict[str, Any]],
                    top_k: int = 10) -> List[Dict[str, Any]]:
        """Rank search results by semantic similarity.
        
        Args:
            query: Search query
            results: List of search results
            top_k: Number of top results to return
            
        Returns:
            Ranked results
        """
        try:
            # Generate query embedding
            query_embedding_list = self._embed_text(query)
            if not query_embedding_list:
                # Fallback to simple ranking
                return results[:top_k]
            
            query_embedding = np.array(query_embedding_list)
            
            # Generate embeddings for results
            result_embeddings = []
            valid_results = []
            
            for result in results:
                # Combine title and snippet for embedding
                text = f"{result.get('title', '')} {result.get('snippet', '')}"
                embed_list = self._embed_text(text)
                
                if embed_list:
                    result_embeddings.append(np.array(embed_list))
                    valid_results.append(result)
            
            if not result_embeddings:
                return results[:top_k]
            
            # Calculate cosine similarity
            similarities = []
            for emb in result_embeddings:
                similarity = np.dot(query_embedding, emb) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(emb)
                )
                similarities.append(similarity)
            
            # Sort by similarity
            ranked_indices = np.argsort(similarities)[::-1]
            ranked_results = [valid_results[i] for i in ranked_indices[:top_k]]
            
            # Add similarity scores
            for i, result in enumerate(ranked_results):
                result["similarity_score"] = float(similarities[ranked_indices[i]])
            
            return ranked_results
            
        except Exception as e:
            # Fallback to original order
            return results[:top_k]
