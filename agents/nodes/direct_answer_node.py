"""Direct answer node for question handling.

Provides direct answers to user questions using RAG and knowledge base.
"""

from typing import Dict, Any, Optional, Callable


class DirectAnswerNode:
    """Handles direct answering of user questions."""
    
    def __init__(self,
                 memory_manager,
                 context_manager,
                 direct_answer_agent,
                 search_aggregator,
                 stream_callback: Optional[Callable[[str, str, Any], None]] = None):
        """Initialize direct answer node.
        
        Args:
            memory_manager: Memory manager for context retrieval
            context_manager: Context manager for session context
            direct_answer_agent: Agent for generating direct answers
            search_aggregator: Aggregator for web search
            stream_callback: Optional callback for streaming events
        """
        self.memory_manager = memory_manager
        self.context_manager = context_manager
        self.direct_answer_agent = direct_answer_agent
        self.search_aggregator = search_aggregator
        self.stream_callback = stream_callback
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute direct answer node.
        
        Args:
            state: Graph state
            
        Returns:
            Updated state with direct_answer
        """
        user_prompt = state["user_prompt"]
        conversation_id = state.get("conversation_id") or state.get("session_id")
        
        # Get comprehensive context from memory manager
        memory_context = self.memory_manager.retrieve_context(
            query=user_prompt,
            k=5,
            session_id=conversation_id,
            include_tool_results=True,
            include_buffer=True
        )
        
        # Retrieve RAG context
        rag_context = memory_context.get("conversation_context", [])
        
        # Get knowledge base results
        knowledge_results = self._get_knowledge_results(state)
        
        # Get web search results if needed
        search_results = self._get_search_results(state)
        
        # Create streaming callback
        model_callback = self._create_model_callback()
        
        # Get conversation history
        conversation_history = memory_context.get("conversation_buffer", [])
        if not conversation_history:
            conversation_history = state.get("conversation_history", [])
        
        # Get direct answer
        answer_result = self.direct_answer_agent.answer_question(
            question=user_prompt,
            rag_results=rag_context,
            knowledge_results=knowledge_results if knowledge_results else None,
            search_results=search_results,
            conversation_history=conversation_history,
            stream_callback=model_callback
        )
        
        # Update state
        state["direct_answer"] = answer_result
        state["rag_results"] = rag_context
        state["knowledge_results"] = knowledge_results if knowledge_results else None
        state["search_results"] = search_results
        
        return state
    
    def _get_knowledge_results(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Get knowledge base results based on analysis.
        
        Args:
            state: Graph state
            
        Returns:
            Knowledge results dictionary
        """
        knowledge_results = {}
        analysis = state.get("analysis")
        
        if analysis is None or not isinstance(analysis, dict):
            return knowledge_results
        
        knowledge_queries = analysis.get("resources", {}).get("knowledge_queries", {})
        
        for kb_type, queries in knowledge_queries.items():
            for query in queries[:2]:  # Limit queries
                # LlamaIndex disabled - return empty result
                result = {}
                if kb_type not in knowledge_results:
                    knowledge_results[kb_type] = []
                if result.get("success"):
                    knowledge_results[kb_type].append(result)
        
        return knowledge_results
    
    def _get_search_results(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get web search results if needed.
        
        Args:
            state: Graph state
            
        Returns:
            Search results or None
        """
        analysis = state.get("analysis")
        
        if not analysis or not isinstance(analysis, dict):
            return None
        
        queries = analysis.get("resources", {}).get("web_search_queries", [])
        
        if queries:
            return self.search_aggregator.search_multiple_queries(queries[:2], num_results=3)
        
        return None
    
    def _create_model_callback(self) -> Optional[Callable[[str], None]]:
        """Create streaming callback for model output."""
        if not self.stream_callback:
            return None
        
        def callback(chunk: str):
            self.stream_callback("model_response", "direct_answer", chunk)
        
        return callback
