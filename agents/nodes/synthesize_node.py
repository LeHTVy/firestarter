"""Synthesize Node - Synthesizes final answer from all sources."""

from typing import Dict, Any, Optional, Callable


class SynthesizeNode:
    """Node for synthesizing final answer from all sources."""
    
    def __init__(self,
                 deepseek_agent,
                 tool_executor_node,
                 stream_callback: Optional[Callable[[str, str, Any], None]] = None):
        """Initialize synthesize node.
        
        Args:
            deepseek_agent: DeepSeek agent for synthesis
            tool_executor_node: Tool executor node (for result analyzer)
            stream_callback: Optional streaming callback
        """
        self.deepseek = deepseek_agent
        self.tool_executor_node = tool_executor_node
        self.stream_callback = stream_callback
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute synthesize node.
        
        Args:
            state: Graph state
            
        Returns:
            Updated state with final_answer
        """
        # Analyze tool results if available
        tool_results = state.get("tool_results", [])
        if tool_results:
            # Use result analyzer to get insights
            analysis = self.tool_executor_node.result_analyzer.analyze_results(tool_results)
            
            # Add analysis to state for synthesis
            state["result_analysis"] = analysis
            
            # Stream insights if available
            if self.stream_callback and analysis.get("ai_insights"):
                self.stream_callback("model_response", "result_analyzer", 
                    f"📊 Analysis: {analysis.get('summary', '')}\n\n{analysis.get('ai_insights', '')}")
        
        # Check if we already have a direct answer
        direct_answer = state.get("direct_answer")
        if direct_answer and isinstance(direct_answer, dict):
            if direct_answer.get("sufficient") and direct_answer.get("answer"):
                # Use direct answer if sufficient
                state["final_answer"] = direct_answer.get("answer", "")
                return state
        
        # Otherwise, synthesize from all sources
        tool_results = state.get("tool_results", [])
        search_results = state.get("search_results")
        knowledge_results = state.get("knowledge_results", {})
        rag_results = state.get("rag_results", [])
        results_qa = state.get("results_qa_answer")
        direct_answer_text = direct_answer.get("answer") if (direct_answer and isinstance(direct_answer, dict)) else None

        # Determine if we actually have any real evidence
        has_real_search = bool(search_results and search_results.get("success") and search_results.get("results"))
        has_evidence = bool(
            tool_results or
            has_real_search or
            knowledge_results or
            rag_results or
            results_qa or
            direct_answer_text
        )

        # If we have no evidence at all, do NOT call DeepSeek to avoid hallucinations.
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
        
        # Create streaming callback for DeepSeek
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
