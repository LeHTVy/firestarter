"""Answer synthesizer."""

from typing import Dict, Any, List, Optional
from models.deepseek_agent import DeepSeekAgent
from models.generic_ollama_agent import GenericOllamaAgent


class AnswerSynthesizer:
    """Synthesizer for combining results from multiple sources."""
    
    def __init__(self):
        """Initialize synthesizer."""
        self.deepseek = DeepSeekAgent()
        # Use Mistral for synthesis (replacing Qwen3)
        self.qwen3 = GenericOllamaAgent(
            model_name="mistral:latest",
            prompt_template="qwen3_system.jinja2"
        )
    
    def synthesize(self,
                  user_question: str,
                  tool_results: Optional[List[Dict[str, Any]]] = None,
                  search_results: Optional[Dict[str, Any]] = None,
                  knowledge_results: Optional[Dict[str, Any]] = None,
                  rag_results: Optional[List[Dict[str, Any]]] = None,
                  results_qa: Optional[str] = None) -> Dict[str, Any]:
        """Synthesize answer from multiple sources.
        
        Args:
            user_question: Original user question
            tool_results: Tool execution results
            search_results: Web search results
            knowledge_results: Knowledge base results
            rag_results: RAG retrieval results
            results_qa: Results Q&A answer
            
        Returns:
            Synthesized answer
        """
        # Format inputs for synthesis
        synthesis_prompt = f"User question: {user_question}\n\n"
        
        if tool_results:
            synthesis_prompt += f"Tool Results:\n{self._format_tool_results(tool_results)}\n\n"
        
        if search_results:
            synthesis_prompt += f"Web Search Results:\n{self._format_search_results(search_results)}\n\n"
        
        if knowledge_results:
            synthesis_prompt += f"Knowledge Base Results:\n{self._format_knowledge_results(knowledge_results)}\n\n"
        
        if rag_results:
            synthesis_prompt += f"Context from Conversation:\n{self._format_rag_results(rag_results)}\n\n"
        
        if results_qa:
            synthesis_prompt += f"Results Q&A Answer:\n{results_qa}\n\n"
        
        synthesis_prompt += "Please synthesize a comprehensive answer based on the above information."
        
        # Use DeepSeek for synthesis
        result = self.deepseek.synthesize_answer(
            user_question=synthesis_prompt,
            search_results=None
        )
        
        return {
            "success": True,
            "answer": result.get("answer", ""),
            "sources": {
                "tools": len(tool_results) if tool_results else 0,
                "web_search": search_results is not None,
                "knowledge": knowledge_results is not None,
                "rag": len(rag_results) if rag_results else 0,
                "results_qa": results_qa is not None
            }
        }
    
    def _format_tool_results(self, results: List[Dict[str, Any]]) -> str:
        """Format tool results for synthesis."""
        formatted = []
        for result in results:
            if result.get("success"):
                formatted.append(f"Tool: {result.get('tool_name', 'unknown')}\nResults: {str(result.get('results', ''))[:500]}")
        return "\n\n".join(formatted)
    
    def _format_search_results(self, results: Dict[str, Any]) -> str:
        """Format search results for synthesis."""
        if not results.get("success"):
            return "No search results"
        
        formatted = []
        for result in results.get("results", [])[:5]:
            formatted.append(f"Title: {result.get('title', '')}\nSnippet: {result.get('snippet', '')}\nURL: {result.get('link', '')}")
        return "\n\n".join(formatted)
    
    def _format_knowledge_results(self, results: Dict[str, Any]) -> str:
        """Format knowledge results for synthesis."""
        formatted = []
        for kb_type, kb_results in results.items():
            for result in kb_results:
                if result.get("success"):
                    formatted.append(f"{kb_type}: {result.get('response', '')[:500]}")
        return "\n\n".join(formatted)
    
    def _format_rag_results(self, results: List[Dict[str, Any]]) -> str:
        """Format RAG results for synthesis."""
        formatted = []
        for result in results[:3]:
            formatted.append(result.get("document", "")[:500])
        return "\n\n".join(formatted)
