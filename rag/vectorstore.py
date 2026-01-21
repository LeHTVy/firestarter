"""Chroma vector store setup with PostgreSQL backend via Chroma Server.

DEPRECATED: This module is deprecated. Use rag.pgvector_store.PgVectorStore instead.
This file is kept for backward compatibility only and will be removed in a future version.
"""

import warnings
warnings.warn(
    "rag.vectorstore.ChromaVectorStore is deprecated. Use rag.pgvector_store.PgVectorStore instead.",
    DeprecationWarning,
    stacklevel=2
)

import os
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from rag.embeddings import NemotronEmbeddings


class ChromaVectorStore:
    """Chroma vector store wrapper using Chroma Server with PostgreSQL backend.
    
    This implementation requires Chroma Server to be running and connected to PostgreSQL.
    SQLite3 support has been removed for production readiness.
    """
    
    def __init__(self, 
                 collection_name: str = "default",
                 server_host: Optional[str] = None,
                 server_port: Optional[int] = None,
                 server_auth_token: Optional[str] = None):
        """Initialize Chroma vector store with Chroma Server.
        
        Args:
            collection_name: Collection name
            server_host: Chroma server host. If None, reads from CHROMA_SERVER_HOST env var (default: localhost)
            server_port: Chroma server port. If None, reads from CHROMA_SERVER_PORT env var (default: 8000)
            server_auth_token: Authentication token for Chroma server. If None, reads from CHROMA_SERVER_AUTH_TOKEN env var
            
        Raises:
            ConnectionError: If Chroma Server is not available
        """
        # Read from environment variables if not provided
        if server_host is None:
            server_host = os.getenv("CHROMA_SERVER_HOST", "localhost")
        
        if server_port is None:
            server_port = int(os.getenv("CHROMA_SERVER_PORT", "8000"))
        
        if server_auth_token is None:
            server_auth_token = os.getenv("CHROMA_SERVER_AUTH_TOKEN")
        
        # Configure settings
        settings = Settings(anonymized_telemetry=False)
        if server_auth_token:
            # Enable authentication if token provided
            settings.chroma_client_auth_provider = "chromadb.auth.token.TokenAuthClientProvider"
            settings.chroma_client_auth_credentials = server_auth_token
        
        # Connect to Chroma Server
        try:
            self.client = chromadb.HttpClient(
                host=server_host,
                port=server_port,
                settings=settings
            )
            
            # Test connection
            self.client.heartbeat()
            self.backend_type = "server"
        except Exception as e:
            raise ConnectionError(
                f"Cannot connect to Chroma Server at {server_host}:{server_port}. "
                f"Make sure Chroma Server is running and accessible. Error: {e}"
            )
        
        self.collection_name = collection_name
        self.server_host = server_host
        self.server_port = server_port
        
        # Get or create collection
        try:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            raise ConnectionError(
                f"Failed to get or create collection '{collection_name}'. "
                f"Chroma Server may not be properly configured. Error: {e}"
            )
        
        self.embeddings = NemotronEmbeddings()
    
    def health_check(self) -> bool:
        """Check if Chroma Server is healthy.
        
        Returns:
            True if server is accessible, False otherwise
        """
        try:
            self.client.heartbeat()
            return True
        except Exception:
            return False
    
    def add_documents(self, 
                     texts: List[str],
                     metadatas: Optional[List[Dict[str, Any]]] = None,
                     ids: Optional[List[str]] = None):
        """Add documents to vector store.
        
        Args:
            texts: List of texts
            metadatas: List of metadata dicts
            ids: List of document IDs
        """
        if not texts:
            return
        
        # Generate embeddings
        embeddings = self.embeddings.embed_documents(texts)
        
        # Validate embeddings
        if not embeddings or len(embeddings) == 0:
            # Try fallback embedding model
            try:
                import ollama
                embeddings = []
                for text in texts:
                    try:
                        result = ollama.embeddings(
                            model="nomic-embed-text",
                            prompt=text
                        )
                        embedding = result.get('embedding', [])
                        if embedding:
                            embeddings.append(embedding)
                        else:
                            # Skip if still empty
                            return
                    except Exception as e:
                        # Skip if embeddings fail
                        return
            except Exception:
                # If all embeddings fail, skip adding documents
                return
        
        # Filter out empty embeddings
        valid_embeddings = []
        valid_texts = []
        valid_metadatas = []
        valid_ids = []
        
        for i, emb in enumerate(embeddings):
            if emb and len(emb) > 0:
                valid_embeddings.append(emb)
                valid_texts.append(texts[i])
                valid_metadatas.append((metadatas or [{}] * len(texts))[i])
                if ids:
                    valid_ids.append(ids[i])
        
        if not valid_embeddings:
            # No valid embeddings, skip
            return
        
        # Generate IDs if not provided
        if not valid_ids:
            import uuid
            valid_ids = [str(uuid.uuid4()) for _ in valid_texts]
        
        # Add to collection
        try:
            self.collection.add(
                embeddings=valid_embeddings,
                documents=valid_texts,
                metadatas=valid_metadatas,
                ids=valid_ids
            )
        except Exception as e:
            # Log error but don't crash
            import warnings
            warnings.warn(f"Failed to add documents to vector store: {str(e)}")
    
    def similarity_search(self, 
                         query: str,
                         k: int = 5,
                         filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Perform similarity search.
        
        Args:
            query: Search query
            k: Number of results
            filter: Metadata filter
            
        Returns:
            List of similar documents
        """
        query_embedding = self.embeddings.embed_query(query)
        
        # Validate query embedding
        if not query_embedding or len(query_embedding) == 0:
            # Try fallback
            try:
                import ollama
                result = ollama.embeddings(
                    model="nomic-embed-text",
                    prompt=query
                )
                query_embedding = result.get('embedding', [])
            except Exception:
                # Return empty if embeddings fail
                return []
        
        if not query_embedding or len(query_embedding) == 0:
            return []
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                where=filter
            )
            
            # Format results
            formatted_results = []
            if results['documents']:
                for i in range(len(results['documents'][0])):
                    formatted_results.append({
                        "document": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results['distances'] else None,
                        "id": results['ids'][0][i] if results['ids'] else None
                    })
            
            return formatted_results
        except Exception as e:
            # Return empty on error
            import warnings
            warnings.warn(f"Similarity search failed: {str(e)}")
            return []
    
    def delete_collection(self):
        """Delete collection."""
        self.client.delete_collection(name=self.collection_name)
