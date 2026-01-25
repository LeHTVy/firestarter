"""Tool results storage with namespace isolation."""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from rag.pgvector_store import PgVectorStore
from memory.namespace_manager import NamespaceManager
# ToolResultSummarizer removed
import uuid


class ToolResultsStorage:
    """Storage for tool execution results with namespace isolation."""
    
    def __init__(self, collection_name: str = "tool_results", auto_summarize: bool = True):
        """Initialize tool results storage.
        
        Args:
            collection_name: Collection name (base name, will be namespaced per conversation)
            auto_summarize: Whether to automatically summarize large results (default: True)
        """
        self.base_collection_name = collection_name
        self.namespace_manager = NamespaceManager()
        # Default vectorstore (for backward compatibility)
        self.vectorstore = PgVectorStore(collection_name=collection_name)
        self.auto_summarize = auto_summarize
        # ToolResultSummarizer removed
    
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
            # Append "_results" to namespace for tool results
            results_namespace = f"{namespace}_results"
            return PgVectorStore(collection_name=results_namespace)
        else:
            # Legacy: use default collection
            return self.vectorstore
    
    def store_result(self,
                    tool_name: str,
                    parameters: Dict[str, Any],
                    results: Any,
            success: bool = True,  
            agent: Optional[str] = None,
            session_id: Optional[str] = None,
            conversation_id: Optional[str] = None,
                    execution_id: Optional[str] = None) -> str:
        """Store tool execution result.
        
        Args:
            tool_name: Tool name
            parameters: Tool parameters
            results: Execution results
            agent: Agent name
            session_id: Session identifier (legacy)
            conversation_id: Conversation identifier (preferred)
            execution_id: Execution ID
            
        Returns:
            Stored document ID
        """
        # Prefer conversation_id over session_id
        conv_id = conversation_id or session_id
        
        doc_id = execution_id or str(uuid.uuid4())
        
        # Format result text
        result_text = json.dumps(results, indent=2) if isinstance(results, dict) else str(results)
        result_size = len(result_text.encode('utf-8'))
        
        # Auto-summarize removed - using full result
        summary = None
        summary_metadata = None
        
        # Create document text (limit to 10KB to prevent context explosion)
        doc_text = f"Tool: {tool_name}\nParameters: {json.dumps(parameters)}\nResults: {result_text[:10000]}"
        
        # Create metadata
        metadata = {
            "tool_name": tool_name,
            "timestamp": datetime.utcnow().isoformat(),
            "agent": agent or "",
            "type": "tool_result",
            "execution_id": doc_id,
            "result_size": result_size,
            "has_summary": summary is not None,
            "success": success  # Store success status
        }
        
        # Add summary metadata if available
        if summary_metadata:
            metadata.update(summary_metadata)
        
        # Add both for migration compatibility
        if conversation_id:
            metadata["conversation_id"] = conversation_id
        if session_id:
            metadata["session_id"] = session_id
        
        # Get conversation-specific vectorstore
        vectorstore = self._get_collection_for_conversation(conv_id)
        
        # Store in vector DB
        vectorstore.add_documents(
            texts=[doc_text],
            metadatas=[metadata],
            ids=[doc_id]
        )
        
        # Also store full result separately if summarized (for Q&A and detailed analysis)
        if summary and summary_metadata:
            full_result_doc_id = f"{doc_id}_full"
            full_result_text = f"Tool: {tool_name}\nParameters: {json.dumps(parameters)}\nResults: {result_text}"
            full_result_metadata = {
                **metadata,
                "type": "tool_result_full",
                "execution_id": doc_id,  # Reference to summary document
                "is_summary": False,
                "summary_id": doc_id
            }
            vectorstore.add_documents(
                texts=[full_result_text],
                metadatas=[full_result_metadata],
                ids=[full_result_doc_id]
            )
        
        return doc_id
    
    def retrieve_results(self,
                        query: str,
                        k: int = 5,
                        tool_name: Optional[str] = None,
                        agent: Optional[str] = None,
                        session_id: Optional[str] = None,
                        conversation_id: Optional[str] = None,
                        use_ranking: bool = True,
                        task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve tool results with namespace isolation and optional ranking.
        
        Args:
            query: Search query
            k: Number of results
            tool_name: Filter by tool name
            agent: Filter by agent
            session_id: Filter by session ID (legacy)
            conversation_id: Filter by conversation ID (preferred)
            use_ranking: Whether to use ContextRanker for multi-factor ranking (default: True)
            task_type: Optional task type for relevance scoring
            
        Returns:
            Retrieved results (ranked if use_ranking=True)
        """
        # Prefer conversation_id over session_id
        conv_id = conversation_id or session_id
        
        # Get conversation-specific vectorstore
        vectorstore = self._get_collection_for_conversation(conv_id)
        
        filter_dict = {"type": "tool_result"}
        
        if tool_name:
            filter_dict["tool_name"] = tool_name
        if agent:
            filter_dict["agent"] = agent
        if conversation_id:
            filter_dict["conversation_id"] = conversation_id
        elif session_id:
            filter_dict["session_id"] = session_id
        
        # Get initial results from vector search (get more than k for ranking)
        initial_k = k * 3 if use_ranking else k
        
        # Execute search
        results = vectorstore.similarity_search(query, k=initial_k, filter=filter_dict)
        
        # Post-processing: Prioritize successful results if available
        if results:
            def is_success(doc):
                if isinstance(doc, dict):
                    return doc.get("metadata", {}).get("success", False)
                return getattr(doc, "metadata", {}).get("success", False)
            
            successful_results = [doc for doc in results if is_success(doc)]
            failed_results = [doc for doc in results if not is_success(doc)]
            results = successful_results + failed_results
            
            # Truncate back to initial_k if needed
            results = results[:initial_k]
        
        # Apply ranking if enabled
        if use_ranking and results:
            from rag.context_ranker import ContextRanker
            ranker = ContextRanker()
            query_entities = ranker._extract_entities(query)
            ranked_results = ranker.rank_contexts(
                query=query,
                contexts=results,
                query_entities=query_entities,
                task_type=task_type
            )
            return ranker.get_top_k(ranked_results, k=k, min_score=0.0)
        
        return results
