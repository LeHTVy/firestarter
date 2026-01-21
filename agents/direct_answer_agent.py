"""Direct answer agent for answering questions without tools."""

from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from config import load_config
from models.deepseek_agent import DeepSeekAgent
from models.generic_ollama_agent import GenericOllamaAgent


class DirectAnswerAgent:
    """Agent for answering questions directly using available knowledge."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize direct answer agent.
        
        Args:
            config_path: Path to Ollama config file
        """
        self.config = load_config(config_path) if config_path else self._load_default_config()
        self.deepseek = DeepSeekAgent(config_path)
        # Use Mistral for general analysis (replacing Qwen3)
        self.qwen3 = GenericOllamaAgent(
            model_name="mistral:latest",
            prompt_template="qwen3_system.jinja2"
        )
        
        template_dir = Path(__file__).parent.parent / "prompts"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.answer_prompt_template = self.env.get_template("direct_answer.jinja2")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default config."""
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "ollama_config.yaml"
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def answer_question(self,
                       question: str,
                       rag_results: Optional[List[Dict[str, Any]]] = None,
                       knowledge_results: Optional[Dict[str, Any]] = None,
                       search_results: Optional[Dict[str, Any]] = None,
                       conversation_history: Optional[List[Dict[str, Any]]] = None,
                       stream_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Answer question using available knowledge sources.
        
        Args:
            question: User question
            rag_results: RAG retrieval results (conversation context)
            knowledge_results: Knowledge base results (CVE, exploits, IOC)
            search_results: Web search results
            conversation_history: Previous conversation
            stream_callback: Optional callback for streaming response
            
        Returns:
            Answer result with answer text, sufficiency flag, and tool needs
        """
        # Format context from various sources
        context_parts = []
        
        if rag_results:
            context_parts.append("Conversation Context:")
            # Use intelligent filtering: prioritize by relevance score if available
            # Filter out duplicates and low-relevance results
            seen_content = set()
            filtered_results = []
            for result in rag_results:
                content = result.get('document', '')
                # Skip duplicates
                if content[:100] in seen_content:
                    continue
                seen_content.add(content[:100])
                # Use final_score if available (from ContextRanker)
                score = result.get('final_score', 0.5)
                if score >= 0.3:  # Minimum relevance threshold
                    filtered_results.append((score, result))
            
            # Sort by score and take top 3
            filtered_results.sort(key=lambda x: x[0], reverse=True)
            for score, result in filtered_results[:3]:
                context_parts.append(f"- {result.get('document', '')[:200]}")
        
        if knowledge_results:
            context_parts.append("\nKnowledge Base:")
            for kb_type, results in knowledge_results.items():
                if results:
                    context_parts.append(f"{kb_type.upper()}:")
                    for result in results[:2]:  # Top 2 per type
                        if isinstance(result, dict):
                            context_parts.append(f"- {result.get('response', str(result))[:200]}")
        
        if search_results and search_results.get("success") and search_results.get("results"):
            context_parts.append("\nWeb Search Results:")
            for result in search_results.get("results", [])[:3]:  # Top 3
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                context_parts.append(f"- {title}: {snippet[:200]}")
        
        context = "\n".join(context_parts) if context_parts else "No additional context available."
        
        has_real_search = bool(search_results and search_results.get("success") and search_results.get("results"))
        has_context = bool(context_parts)
        
        if not has_real_search and not has_context:
            return {
                "success": True,
                "answer": (
                    "I don't have any existing scan results, knowledge base entries, or web search results "
                    "for this question yet. To answer reliably, we should first run reconnaissance / scanning "
                    "tools or perform a web search via the agent pipeline."
                ),
                "sufficient": False,
                "needs_tools": True,
                "context_used": False,
                "reasoning": "No context or search results available; tools or web search are required"
            }
        
        # Build prompt (used mainly for debugging / transparency in templates)
        prompt = self.answer_prompt_template.render(
            question=question,
            context=context,
            has_context=has_context
        )
        
        answer_result = self.deepseek.synthesize_answer(
            user_question=question,
            search_results=search_results if has_real_search else None,
            stream_callback=stream_callback
        )
        
        if not answer_result.get("success"):
            return {
                "success": False,
                "answer": "",
                "sufficient": False,
                "needs_tools": True,
                "error": answer_result.get("error", "Unknown error")
            }
        
        answer = answer_result.get("answer", "")
        
        # Evaluate if answer is sufficient
        sufficient = self._evaluate_answer_sufficiency(answer, question, context_parts)
        
        # Determine if tools are needed
        needs_tools = not sufficient and not context_parts
        
        return {
            "success": True,
            "answer": answer,
            "sufficient": sufficient,
            "needs_tools": needs_tools,
            "context_used": bool(context_parts),
            "reasoning": "Answer is sufficient" if sufficient else "Answer may need additional information from tools"
        }
    
    def _evaluate_answer_sufficiency(self, answer: str, question: str, context_parts: List[str]) -> bool:
        """Evaluate if answer is sufficient.
        
        Args:
            answer: Generated answer
            question: Original question
            context_parts: Context parts used
            
        Returns:
            True if answer is sufficient, False otherwise
        """
        # Check answer length (too short might be insufficient)
        if len(answer.strip()) < 50:
            return False
        
        # Check for indicators of insufficient answer
        insufficient_indicators = [
            "i don't know",
            "i cannot",
            "i need more",
            "requires additional",
            "not available",
            "unable to",
            "cannot determine",
            "insufficient information"
        ]
        
        answer_lower = answer.lower()
        if any(indicator in answer_lower for indicator in insufficient_indicators):
            return False
        
        # If we have context and a reasonable answer, it's likely sufficient
        if context_parts and len(answer) > 100:
            return True
        
        # Default: if answer exists and is reasonable length, consider sufficient
        return len(answer) > 100
