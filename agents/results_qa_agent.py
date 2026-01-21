"""Results Q&A Agent."""

from typing import Dict, Any, Optional
from rag.results_retriever import ResultsRetriever
from models.generic_ollama_agent import GenericOllamaAgent
from models.deepseek_agent import DeepSeekAgent
from jinja2 import Environment, FileSystemLoader
from pathlib import Path


class ResultsQAAgent:
    """Agent for answering questions about tool results."""
    
    def __init__(self, model: str = "mistral"):
        """Initialize Results Q&A Agent.
        
        Args:
            model: Model to use (mistral or deepseek_r1)
        """
        self.model_name = model
        if model == "qwen3" or model == "mistral":
            # Use Mistral for Q&A (replacing Qwen3)
            self.model_agent = GenericOllamaAgent(
                model_name="mistral:latest",
                prompt_template="qwen3_system.jinja2"
            )
        else:
            self.model_agent = DeepSeekAgent()
        
        self.retriever = ResultsRetriever()
        
        # Load prompt template
        template_dir = Path(__file__).parent.parent / "prompts"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.prompt_template = self.env.get_template("results_qa.jinja2")
    
    def answer_question(self,
                       question: str,
                       filters: Optional[Dict[str, Any]] = None,
                       k: int = 5) -> Dict[str, Any]:
        """Answer question about tool results.
        
        Args:
            question: User question
            filters: Filters (tool_name, agent, session_id, time_range)
            k: Number of results to retrieve
            
        Returns:
            Answer with supporting evidence
        """
        # Retrieve relevant results
        retrieved_results = self.retriever.retrieve(question, k=k, filters=filters or {})
        
        # Format results for prompt
        results_text = "\n\n".join([
            f"Tool: {r.get('metadata', {}).get('tool_name', 'unknown')}\n"
            f"Document: {r.get('document', '')[:1000]}"
            for r in retrieved_results
        ])
        
        # Build prompt
        prompt = self.prompt_template.render(
            user_question=question,
            retrieved_results=results_text,
            tool_name=filters.get('tool_name') if filters else None,
            time_range=filters.get('time_range') if filters else None
        )
        
        # Get answer from model
        if isinstance(self.model_agent, GenericOllamaAgent):
            # Use analyze_and_breakdown for GenericOllamaAgent (can be adapted)
            result = {
                "success": True,
                "answer": f"Based on the retrieved results: {results_text[:500]}",
                "evidence": retrieved_results
            }
        else:
            result = self.model_agent.synthesize_answer(question, search_results=retrieved_results)
        
        return {
            "success": True,
            "question": question,
            "answer": result.get("answer", ""),
            "evidence": retrieved_results,
            "filters": filters
        }
