"""Generic Ollama agent that can work with any Ollama model."""

import json
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from config import load_config
from tools.registry import get_registry
from models.llm_client import OllamaLLMClient


class GenericOllamaAgent:
    """Generic agent that can work with any Ollama model for task analysis."""
    
    def __init__(self, 
                 model_name: str,
                 prompt_template: str = "autogen_recon.jinja2",
                 config_path: Optional[Path] = None):
        """Initialize generic Ollama agent.
        
        Args:
            model_name: Ollama model name (e.g., "llama3.1:8b", "mistral:7b")
            prompt_template: Prompt template file name (default: autogen_recon.jinja2)
            config_path: Optional path to config file
        """
        self.model_name = model_name
        self.config = load_config(config_path) if config_path else self._load_default_config()
        self.ollama_base_url = self.config['ollama']['base_url']
        self.llm_client = OllamaLLMClient(
            model_name=model_name,
            base_url=self.ollama_base_url,
            config_path=config_path,
            temperature=0.3,
            top_p=0.9,
            top_k=40,
            num_predict=2048,
            repeat_penalty=1.1
        )
        
        self.registry = get_registry()
        
        template_dir = Path(__file__).parent.parent / "prompts"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        try:
            self.system_prompt_template = self.env.get_template(prompt_template)
        except:
            # Fallback to base autogen prompt
            self.system_prompt_template = self.env.get_template("autogen_recon.jinja2")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default config."""
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "ollama_config.yaml"
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def analyze_and_breakdown(self,
                             user_prompt: str,
                             conversation_history: Optional[str] = None,
                             tool_results: Optional[str] = None,
                             stream_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Analyze user prompt and breakdown into subtasks.
        
        Args:
            user_prompt: User prompt
            conversation_history: Conversation history
            tool_results: Previous tool results
            stream_callback: Optional callback for streaming response chunks
            
        Returns:
            Analysis result with subtasks
        """
        # Get available tools
        all_tools = self.registry.list_tools()
        priority_tools = [t for t in all_tools if t.priority]
        other_tools = [t for t in all_tools if not t.priority]
        
        # Combine: priority tools first, then others (limit to 150 total)
        tools_to_show = priority_tools + other_tools[:150-len(priority_tools)]
        
        # Format tools for display
        tools_summary = [
            {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "assigned_agents": tool.assigned_agents,
                "commands": tool.list_commands() if tool.commands else [],
                "priority": tool.priority
            }
            for tool in tools_to_show
        ]
        
        # Also provide category-based tool lists
        tools_by_category = {}
        for tool in all_tools:
            if tool.category not in tools_by_category:
                tools_by_category[tool.category] = []
            tools_by_category[tool.category].append(tool.name)
        
        system_prompt = self.system_prompt_template.render(
            conversation_history=conversation_history,
            tool_results=tool_results,
            available_tools=tools_summary,
            tools_by_category=tools_by_category
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self.llm_client.generate(
                messages=messages,
                stream=stream_callback is not None,
                stream_callback=stream_callback,
                temperature=0.9,
                top_p=0.95,
                top_k=50,
                num_predict=2048,
                repeat_penalty=1.1
            )
            
            if not response.get('success'):
                return {
                    "success": False,
                    "error": response.get('error', 'Unknown error'),
                    "refused": False
                }
            
            content = response.get('content', '')
            
            # Extract reasoning and output from structured format
            reasoning = None
            output_content = content
            
            # Try to extract <reasoning> and <output> blocks
            if "<reasoning>" in content and "</reasoning>" in content:
                reasoning_start = content.find("<reasoning>") + len("<reasoning>")
                reasoning_end = content.find("</reasoning>", reasoning_start)
                if reasoning_end > reasoning_start:
                    reasoning = content[reasoning_start:reasoning_end].strip()
            
            if "<output>" in content and "</output>" in content:
                output_start = content.find("<output>") + len("<output>")
                output_end = content.find("</output>", output_start)
                if output_end > output_start:
                    output_content = content[output_start:output_end].strip()
            
            # Try to parse JSON from response
            try:
                # Extract JSON from markdown code blocks if present
                if "```json" in output_content:
                    json_start = output_content.find("```json") + 7
                    json_end = output_content.find("```", json_start)
                    output_content = output_content[json_start:json_end].strip()
                elif "```" in output_content:
                    json_start = output_content.find("```") + 3
                    json_end = output_content.find("```", json_start)
                    output_content = output_content[json_start:json_end].strip()
                
                # Parse JSON
                analysis_data = json.loads(output_content)
                
                return {
                    "success": True,
                    "analysis": analysis_data,
                    "reasoning": reasoning,
                    "raw_response": content,
                    "refused": False
                }
            except json.JSONDecodeError:
                # JSON parsing failed - try to extract JSON from anywhere in the response
                import re
                json_match = re.search(r'\{.*\}', output_content, re.DOTALL)
                if json_match:
                    try:
                        analysis_data = json.loads(json_match.group())
                        return {
                            "success": True,
                            "analysis": analysis_data,
                            "reasoning": reasoning,
                            "raw_response": content,
                            "refused": False
                        }
                    except:
                        pass
                
                return {
                    "success": False,
                    "error": "Failed to parse JSON from response",
                    "raw_response": content,
                    "refused": False
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "refused": False
            }
    
    def analyze(self,
               target: str,
               previous_results: Any,
               task: str,
               stream_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Analyze results for Q&A (Results QA Agent).
        
        Args:
            target: Target domain
            previous_results: Tool results from memory
            task: User question/task
            stream_callback: Optional streaming callback
            
        Returns:
            Analysis result
        """
        # Map variables to template
        retrieved_results = previous_results
        
        # Render system prompt
        system_prompt = self.system_prompt_template.render(
            user_question=task,
            retrieved_results=retrieved_results,
            target=target,
            tool_name="ResultsQA"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ]
        
        try:
            response = self.llm_client.generate(
                messages=messages,
                stream=stream_callback is not None,
                stream_callback=stream_callback,
                temperature=0.5,
                num_predict=2048
            )
            
            if not response.get('success'):
                return {
                    "success": False,
                    "error": response.get('error', 'Unknown error')
                }
            
            return {
                "success": True,
                "analysis": response.get('content', '')
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    
    def synthesize_answer(self,
                         user_question: str,
                         search_results: Optional[Dict[str, Any]] = None,
                         stream_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Synthesize final answer from tool results and search results.
        
        Args:
            user_question: Original user question
            search_results: Dict containing tool_results, search_results, etc.
            stream_callback: Optional callback for streaming response chunks
            
        Returns:
            Dict with 'answer' key containing synthesized answer
        """
        # Build context from results
        context_parts = []
        
        if search_results:
            # Tool results
            tool_results = search_results.get("tool_results", [])
            if tool_results:
                context_parts.append("## Tool Execution Results:\n")
                for result in tool_results:
                    tool_name = result.get("tool_name", "unknown")
                    success = result.get("success", False)
                    output = result.get("results") or result.get("raw_output") or result.get("error", "")
                    context_parts.append(f"### {tool_name} ({'Success' if success else 'Failed'}):\n{output}\n")
            
            # Web search results
            web_results = search_results.get("search_results")
            if web_results and web_results.get("results"):
                context_parts.append("\n## Web Search Results:\n")
                for r in web_results.get("results", [])[:5]:
                    context_parts.append(f"- {r.get('title', '')}: {r.get('snippet', '')}\n")
            
            # Results Q&A (Memory Query) results
            results_qa = search_results.get("results_qa")
            if results_qa:
                context_parts.append(f"\n## Summary of Findings from Memory:\n{results_qa}\n")
            
            # Direct answer if available
            direct = search_results.get("direct_answer")
            if direct:
                context_parts.append(f"\n## Previous Analysis:\n{direct}\n")
        
        context = "\n".join(context_parts) if context_parts else "No results available."
        
        # Build synthesis prompt
        synthesis_prompt = f"""Based on the following results, provide a comprehensive answer to the user's question.

User Question: {user_question}

{context}

Provide a clear, structured summary of the findings. Include:
1. Key findings
2. Potential vulnerabilities or points of interest
3. Recommendations for next steps

Be concise but thorough. Use markdown formatting."""

        messages = [
            {"role": "system", "content": "You are a security analyst synthesizing reconnaissance and security assessment results. Provide clear, actionable insights."},
            {"role": "user", "content": synthesis_prompt}
        ]
        
        try:
            response = self.llm_client.generate(
                messages=messages,
                stream=stream_callback is not None,
                stream_callback=stream_callback,
                temperature=0.7,
                num_predict=2048
            )
            
            if response.get('success'):
                return {
                    "success": True,
                    "answer": response.get('content', '')
                }
            else:
                return {
                    "success": False,
                    "answer": f"Error: {response.get('error', 'Unknown error')}"
                }
        except Exception as e:
            return {
                "success": False,
                "answer": f"Synthesis failed: {str(e)}"
            }

