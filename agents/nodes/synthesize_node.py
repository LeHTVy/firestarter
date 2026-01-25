"""Synthesize Node - Synthesizes final answer from all sources."""

from typing import Dict, Any, Optional, Callable


class SynthesizeNode:
    """Node for synthesizing final answer from all sources."""
    
    def __init__(self,
                 deepseek_agent,
                 tool_executor_node,
                 memory_manager=None,
                 stream_callback: Optional[Callable[[str, str, Any], None]] = None):
        """Initialize synthesize node.
        
        Args:
            deepseek_agent: DeepSeek agent for synthesis
            tool_executor_node: Tool executor node (for result analyzer)
            memory_manager: Optional memory manager for historical context
            stream_callback: Optional streaming callback
        """
        self.deepseek = deepseek_agent
        self.tool_executor_node = tool_executor_node
        self.memory_manager = memory_manager
        self.stream_callback = stream_callback
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute synthesize node.
        
        Args:
            state: Graph state
            
        Returns:
            Updated state with final_answer
        """
        # MEMORY QUERY: Check if this was answered from memory
        memory_answer = state.get("memory_answer")
        if memory_answer:
            state["final_answer"] = memory_answer["answer"]
            
            if self.stream_callback:
                source = memory_answer.get("source", "unknown")
                count = memory_answer.get("count", 0)
                self.stream_callback("model_response", "system",
                    f"📊 Retrieved {count} item(s) from {source} (instant, no tools executed)")
            
            return state
        
        # Get tool results from current run or retrieve historical context
        tool_results = state.get("tool_results", [])
        
        if not tool_results and self.memory_manager:
            intent = state.get("intent_classification") or {}
            user_prompt = state.get("user_prompt", "")
            
            is_memory_query = intent.get("intent_type") == "memory_query"
            retrieval_keywords = ["show", "list", "what", "found", "result", "previous", "earlier"]
            has_retrieval_keyword = any(kw in user_prompt.lower() for kw in retrieval_keywords)
            
            if is_memory_query or has_retrieval_keyword:
                historical = self._retrieve_historical_context(state)
                if historical:
                    tool_results = historical.get("tool_results", [])
                    if tool_results:
                        state["tool_results"] = tool_results
                        if self.stream_callback:
                            self.stream_callback("model_response", "system",
                                f"📂 Retrieved {len(tool_results)} historical result(s) from memory")
        
        if tool_results:
            tool_count = len(tool_results)
            successful_count = sum(1 for r in tool_results if r.get("success", False))
            tool_names = [r.get("tool_name") or r.get("metadata", {}).get("tool_name") or "unknown" for r in tool_results]
            
            analysis = {
                "summary": f"Executed {tool_count} tool(s): {', '.join(tool_names)}",
                "successful_count": successful_count,
                "failed_count": tool_count - successful_count,
                "tools_used": tool_names
            }
            
            state["result_analysis"] = analysis
            
            if self.stream_callback:
                self.stream_callback("model_response", "result_analyzer", 
                    f"📊 Analysis: {analysis.get('summary', '')}")
        
        direct_answer = state.get("direct_answer")
        if direct_answer and isinstance(direct_answer, dict):
            if direct_answer.get("sufficient") and direct_answer.get("answer"):
                state["final_answer"] = direct_answer.get("answer", "")
                return state
        
        tool_results = state.get("tool_results", [])
        search_results = state.get("search_results")
        knowledge_results = state.get("knowledge_results", {})
        rag_results = state.get("rag_results", [])
        results_qa = state.get("results_qa_answer")
        direct_answer_text = direct_answer.get("answer") if (direct_answer and isinstance(direct_answer, dict)) else None

        has_real_search = bool(search_results and search_results.get("success") and search_results.get("results"))
        has_evidence = bool(
            tool_results or
            has_real_search or
            knowledge_results or
            rag_results or
            results_qa or
            direct_answer_text
        )

        if not has_evidence:
            warning_msg = (
                "I don't have any tool results, web search results, knowledge base entries, or prior context "
                "for this question. To give a reliable answer, we should first run appropriate tools or a web "
                "search through the agent pipeline."
            )
            state["final_answer"] = warning_msg
            if self.stream_callback:
                self.stream_callback("model_response", "system", warning_msg)
            return state

        synthesis_input = {
            "tool_results": tool_results,
            "search_results": search_results if has_real_search else None,
            "knowledge_results": knowledge_results,
            "rag_results": rag_results,
            "results_qa": results_qa,
            "direct_answer": direct_answer_text
        }
        
        model_callback = None
        if self.stream_callback:
            def callback(chunk: str):
                self.stream_callback("model_response", "deepseek", chunk)
            model_callback = callback
        
        answer = self.deepseek.synthesize_answer(
            user_question=state["user_prompt"],
            search_results=synthesis_input,
            stream_callback=model_callback
        )
        
        state["final_answer"] = answer.get("answer", "")
        return state
    
    def _retrieve_historical_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve historical tool results from memory manager.
        
        Args:
            state: Graph state with conversation_id and user_prompt
            
        Returns:
            Dictionary with tool_results from previous runs
        """
        if not self.memory_manager:
            return {}
        
        try:
            conversation_id = state.get("conversation_id") or state.get("session_id")
            user_prompt = state.get("user_prompt", "")
            
            # Retrieve context with tool results
            context = self.memory_manager.retrieve_context(
                query=user_prompt,
                k=10,
                session_id=conversation_id,
                conversation_id=conversation_id,
                include_tool_results=True,
                include_buffer=True
            )
            
            return context
        except Exception as e:
            if self.stream_callback:
                self.stream_callback("model_response", "system", 
                    f"⚠️ Error retrieving historical context: {e}")
            return {}
