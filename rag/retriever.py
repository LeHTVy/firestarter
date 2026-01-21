"""Semantic retriever for conversation context with namespace isolation."""

from rag.pgvector_store import PgVectorStore
from typing import List, Dict, Any, Optional
from memory.namespace_manager import NamespaceManager


class ConversationRetriever:
    """Retriever for conversation context with namespace isolation."""
    
    def __init__(self, collection_name: str = "conversation"):
        """Initialize conversation retriever.
        
        Args:
            collection_name: Collection name (base name, will be namespaced per conversation)
        """
        self.base_collection_name = collection_name
        self.namespace_manager = NamespaceManager()
        # Default vectorstore (for backward compatibility)
        self.vectorstore = PgVectorStore(collection_name=collection_name)
    
    def _get_collection_for_conversation(self, conversation_id: Optional[str] = None) -> PgVectorStore:
        """Get vectorstore for specific conversation (namespace isolation).
        
        Args:
            conversation_id: Conversation UUID (None for default/legacy)
            
        Returns:
            PgVectorStore instance for this conversation
        """
        if conversation_id:
            # Use conversation-specific collection for namespace isolation
            namespace = self.namespace_manager.get_vector_namespace(conversation_id)
            return PgVectorStore(collection_name=namespace)
        else:
            # Legacy: use default collection
            return self.vectorstore
    
    def add_conversation(self, 
                        messages: List[Dict[str, Any]],
                        session_id: Optional[str] = None,
                        conversation_id: Optional[str] = None):
        """Add conversation to vector store.
        
        Args:
            messages: Conversation messages
            session_id: Session identifier (legacy, for backward compatibility)
            conversation_id: Conversation identifier (preferred, for namespace isolation)
        """
        # Prefer conversation_id over session_id
        conv_id = conversation_id or session_id
        
        try:
            # Get conversation-specific vectorstore
            vectorstore = self._get_collection_for_conversation(conv_id)
            
            texts = []
            metadatas = []
            
            from datetime import datetime, timezone
            current_timestamp = datetime.now(timezone.utc).isoformat()
            
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                
                if content:
                    texts.append(f"{role}: {content}")
                    metadata = {
                        "role": role,
                        "type": "conversation",
                        "timestamp": current_timestamp  # Add timestamp for recency scoring
                    }
                    # Add both for migration compatibility
                    if conversation_id:
                        metadata["conversation_id"] = conversation_id
                    if session_id:
                        metadata["session_id"] = session_id
                    metadatas.append(metadata)
            
            if texts:
                vectorstore.add_documents(texts, metadatas=metadatas)
        except Exception as e:
            # Don't crash if RAG fails - just log warning
            import warnings
            warnings.warn(f"Failed to add conversation to RAG: {str(e)}")
    
    def retrieve_context(self,
                        query: str,
                        k: int = 5,
                        session_id: Optional[str] = None,
                        conversation_id: Optional[str] = None,
                        task_type: Optional[str] = None,
                        use_ranking: bool = True) -> List[Dict[str, Any]]:
        """Retrieve conversation context with namespace isolation and optional ranking.
        
        Args:
            query: Search query
            k: Number of results
            session_id: Filter by session ID (legacy)
            conversation_id: Filter by conversation ID (preferred)
            task_type: Optional task type for relevance scoring (recon, exploitation, analysis, mixed)
            use_ranking: Whether to use ContextRanker for multi-factor ranking (default: True)
            
        Returns:
            Retrieved context (ranked if use_ranking=True)
        """
        # Prefer conversation_id over session_id
        conv_id = conversation_id or session_id
        
        # Get conversation-specific vectorstore for namespace isolation
        vectorstore = self._get_collection_for_conversation(conv_id)
        
        filter_dict = {"type": "conversation"}
        if conversation_id:
            filter_dict["conversation_id"] = conversation_id
        elif session_id:
            filter_dict["session_id"] = session_id
        
        # Get initial results from vector search (get more than k for ranking)
        initial_k = k * 3 if use_ranking else k
        results = vectorstore.similarity_search(query, k=initial_k, filter=filter_dict)
        
        # Apply ranking if enabled
        if use_ranking and results:
            from rag.context_ranker import ContextRanker
            ranker = ContextRanker()
            
            # Extract entities from query for entity matching
            query_entities = ranker._extract_entities(query)
            
            # Rank results
            ranked_results = ranker.rank_contexts(
                query=query,
                contexts=results,
                query_entities=query_entities,
                task_type=task_type
            )
            
            # Return top-k ranked results
            return ranker.get_top_k(ranked_results, k=k, min_score=0.0)
        
        return results
