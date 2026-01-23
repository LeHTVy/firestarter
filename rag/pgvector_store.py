"""PostgreSQL vector store using pgvector extension.

This replaces ChromaDB with native PostgreSQL + pgvector for production-grade
semantic memory storage.
"""

import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
import json
from rag.embeddings import NemotronEmbeddings


class PgVectorStore:
    """PostgreSQL vector store using pgvector extension.
    
    This implementation uses PostgreSQL directly with pgvector extension,
    eliminating the need for Chroma Server.
    """
    
    def __init__(self, 
                 collection_name: str = "default",
                 embedding_dimension: int = 768):
        """Initialize PostgreSQL vector store.
        
        Args:
            collection_name: Collection/namespace name for organizing embeddings
            embedding_dimension: Dimension of embedding vectors (default: 768 for nomic-embed-text)
        """
        self.collection_name = collection_name
        self.embedding_dimension = embedding_dimension
        self.embeddings = NemotronEmbeddings()
        
        # PostgreSQL connection settings
        self.postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        self.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.postgres_database = os.getenv("POSTGRES_DATABASE", "firestarter_pg")
        self.postgres_user = os.getenv("POSTGRES_USER", "firestarter_ad")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "")
        
        # Ensure table exists on initialization
        self._ensure_table_exists()
    
    def _get_connection(self):
        """Get PostgreSQL connection."""
        return psycopg2.connect(
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_database,
            user=self.postgres_user,
            password=self.postgres_password
        )
    
    def _ensure_table_exists(self):
        """Ensure vector_embeddings table exists with pgvector extension."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Enable pgvector extension if not exists
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            # Create vector_embeddings table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vector_embeddings (
                    id VARCHAR(255) PRIMARY KEY,
                    conversation_id VARCHAR(255),
                    collection_name VARCHAR(255) NOT NULL,
                    text TEXT NOT NULL,
                    embedding vector(%s) NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """, (self.embedding_dimension,))
            
            # Create indexes for better performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_vector_embeddings_collection 
                ON vector_embeddings(collection_name)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_vector_embeddings_conversation 
                ON vector_embeddings(conversation_id) 
                WHERE conversation_id IS NOT NULL
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_vector_embeddings_embedding 
                ON vector_embeddings USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)
            
            conn.commit()
            cursor.close()
        except Exception as e:
            if conn:
                conn.rollback()
            import warnings
            warnings.warn(f"Failed to ensure table exists: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def health_check(self) -> bool:
        """Check if PostgreSQL connection is healthy.
        
        Returns:
            True if connection is accessible, False otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            return True
        except Exception:
            return False
    
    def add_documents(self, 
                     texts: List[str],
                     metadatas: Optional[List[Dict[str, Any]]] = None,
                     ids: Optional[List[str]] = None):
        """Add documents to vector store.
        
        Args:
            texts: List of texts to embed and store
            metadatas: List of metadata dicts (one per text)
            ids: List of document IDs (auto-generated if not provided)
        """
        if not texts:
            return
        
        # Generate embeddings
        embeddings = self.embeddings.embed_documents(texts)
        
        # Validate embeddings
        if not embeddings or len(embeddings) == 0:
            try:
                from models.llm_client import OllamaEmbeddingClient
                fallback_client = OllamaEmbeddingClient(model_name="nomic-embed-text")
                embeddings = fallback_client.embed_documents(texts)
                if not embeddings or len(embeddings) == 0:
                    return
            except Exception:
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
            return
        
        # Generate IDs if not provided
        if not valid_ids:
            valid_ids = [str(uuid.uuid4()) for _ in valid_texts]
        
        # Insert into PostgreSQL
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            for i, (text, embedding, metadata, doc_id) in enumerate(
                zip(valid_texts, valid_embeddings, valid_metadatas, valid_ids)
            ):
                # Extract conversation_id from metadata if present
                conversation_id = metadata.get('conversation_id')
                
                # Ensure timestamp is in metadata for recency scoring
                if 'timestamp' not in metadata and 'created_at' not in metadata:
                    from datetime import datetime, timezone
                    metadata['timestamp'] = datetime.now(timezone.utc).isoformat()
                
                # Convert embedding to PostgreSQL vector format
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                
                cursor.execute("""
                    INSERT INTO vector_embeddings 
                    (id, conversation_id, collection_name, text, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s::vector, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                """, (
                    doc_id,
                    conversation_id,
                    self.collection_name,
                    text,
                    embedding_str,
                    json.dumps(metadata)
                ))
            
            conn.commit()
            cursor.close()
        except Exception as e:
            conn.rollback()
            import warnings
            warnings.warn(f"Failed to add documents to vector store: {str(e)}")
        finally:
            conn.close()
    
    def similarity_search(self, 
                         query: str,
                         k: int = 5,
                         filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Perform similarity search.
        
        Args:
            query: Search query text
            k: Number of results to return
            filter: Metadata filter dict (e.g., {"conversation_id": "...", "type": "..."})
            
        Returns:
            List of similar documents with metadata and distance scores
        """
        # Validate query parameter - must be a string
        if not isinstance(query, str):
            import warnings
            warnings.warn(f"Invalid query parameter: expected string, got {type(query)}. Query: {query}")
            return []
        
        # Generate query embedding with robust error handling
        query_embedding = None
        try:
            query_embedding = self.embeddings.embed_query(query)
        except Exception as e:
            import warnings
            warnings.warn(f"Embedding generation failed for query '{query[:50]}...': {str(e)}")
        
        # Validate query embedding - must be a list/array of numbers
        if not query_embedding:
            try:
                from models.llm_client import OllamaEmbeddingClient
                fallback_client = OllamaEmbeddingClient(model_name="nomic-embed-text")
                query_embedding = fallback_client.embed_query(query)
            except Exception as fallback_error:
                import warnings
                warnings.warn(f"Fallback embedding generation failed for query '{query[:50]}...': {str(fallback_error)}")
                return []
        
        # CRITICAL: Check if query_embedding is a string (which would be wrong)
        if isinstance(query_embedding, str):
            import warnings
            warnings.warn(f"Invalid embedding: received string '{query_embedding[:100]}...' instead of vector. Query was: '{query[:50]}...'. This indicates a bug in embed_query.")
            return []
        
        if not isinstance(query_embedding, (list, tuple)) or len(query_embedding) == 0:
            import warnings
            warnings.warn(f"Invalid embedding format: expected list/array, got {type(query_embedding)}. Query was: '{query[:50]}...'")
            return []
        
        # Additional check: if query looks like a conversation_id or collection name, skip embedding
        if isinstance(query, str) and (query.startswith("conversation_") or query.startswith("session_")):
            import warnings
            warnings.warn(f"Query appears to be a conversation/session ID, not a text query: '{query}'. Skipping similarity search.")
            return []
        
        # Validate all elements are numbers
        try:
            # Try to convert to float to ensure they're numeric
            _ = [float(x) for x in query_embedding]
        except (ValueError, TypeError) as e:
            import warnings
            warnings.warn(f"Embedding contains non-numeric values: {str(e)}. Query was: '{query[:50]}...'")
            return []
        
        # Build query with filters
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Convert to list of floats first
                embedding_floats = [float(x) for x in query_embedding]
                # Format as PostgreSQL vector: [1.0,2.0,3.0,...]
                embedding_str = '[' + ','.join([str(f) for f in embedding_floats]) + ']'
            except (ValueError, TypeError) as e:
                import warnings
                warnings.warn(f"Failed to format embedding vector: {str(e)}")
                return []
            
            # Build WHERE clause for filters
            where_clauses = ["collection_name = %s"]
            params = [self.collection_name]
            
            if filter:
                for key, value in filter.items():
                    if key == 'conversation_id':
                        if not (self.collection_name.startswith("conversation_") and 
                                str(value) in self.collection_name):
                            where_clauses.append("conversation_id = %s")
                            params.append(value)
                    elif key == 'session_id':
                        if not self.collection_name.startswith("conversation_"):
                            where_clauses.append("metadata->>%s = %s")
                            params.extend([key, str(value)])
                    else:
                        # Use JSONB path query for metadata fields
                        where_clauses.append(f"metadata->>%s = %s")
                        params.extend([key, str(value)])
            
            where_sql = " AND ".join(where_clauses)
            
            # IMPORTANT: Parameter order must match the SQL query structure:
            # 1. First %s in SELECT is for distance calculation (embedding_str)
            # 2. Then %s placeholders in WHERE clause (collection_name and filters)
            # 3. Then %s in ORDER BY (embedding_str)
            # 4. Then %s in LIMIT (k)
            complete_params = [embedding_str]  # First: distance calculation in SELECT
            complete_params.extend(params)  # Then: WHERE clause params (collection_name, filters)
            complete_params.append(embedding_str)  # Then: ORDER BY
            complete_params.append(k)  # Finally: LIMIT
            
            query_sql = """
                SELECT 
                    id,
                    conversation_id,
                    text,
                    metadata,
                    1 - (embedding <=> %s::vector) as distance
                FROM vector_embeddings
                WHERE """ + where_sql + """
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            
            cursor.execute(query_sql, complete_params)
            rows = cursor.fetchall()
            cursor.close()
            
            # Format results
            formatted_results = []
            for row in rows:
                formatted_results.append({
                    "document": row['text'],
                    "metadata": dict(row['metadata']) if row['metadata'] else {},
                    "distance": float(row['distance']) if row['distance'] is not None else None,
                    "id": str(row['id'])
                })
            
            return formatted_results
        except Exception as e:
            import warnings
            warnings.warn(f"Similarity search failed: {str(e)}")
            return []
        finally:
            conn.close()
    
    def delete_collection(self):
        """Delete all embeddings in this collection.
        
        Note: This deletes embeddings, not the collection itself (collections are logical).
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM vector_embeddings WHERE collection_name = %s",
                (self.collection_name,)
            )
            conn.commit()
            cursor.close()
        except Exception as e:
            conn.rollback()
            import warnings
            warnings.warn(f"Failed to delete collection: {str(e)}")
        finally:
            conn.close()
