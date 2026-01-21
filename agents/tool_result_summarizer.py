"""Tool Result Summarizer for context explosion prevention."""

from typing import Dict, Any, Optional
import json
from models.generic_ollama_agent import GenericOllamaAgent


class ToolResultSummarizer:
    """Summarize tool results to prevent context explosion.
    
    Tool Result Summarizer automatically summarizes large tool results
    to keep context manageable while preserving important information.
    """
    
    # Size threshold for summarization (in bytes)
    SUMMARY_THRESHOLD = 10 * 1024  # 10KB
    
    def __init__(self, model_name: str = "mistral:latest"):
        """Initialize Tool Result Summarizer.
        
        Args:
            model_name: LLM model to use for summarization
        """
        self.model_name = model_name
        self.summarizer = GenericOllamaAgent(model_name=model_name)
    
    def should_summarize(self, result: Any) -> bool:
        """Check if result should be summarized.
        
        Args:
            result: Tool execution result
            
        Returns:
            True if result is large enough to warrant summarization
        """
        # Convert result to string for size calculation
        if isinstance(result, dict):
            result_str = json.dumps(result, indent=2)
        else:
            result_str = str(result)
        
        return len(result_str.encode('utf-8')) > self.SUMMARY_THRESHOLD
    
    def summarize(self, tool_name: str, parameters: Dict[str, Any], 
                  results: Any, agent: Optional[str] = None) -> Dict[str, Any]:
        """Summarize tool execution result.
        
        Args:
            tool_name: Tool name
            parameters: Tool parameters
            results: Execution results
            agent: Agent name (optional)
            
        Returns:
            Summary dictionary with key findings and insights
        """
        # Convert results to string for summarization
        if isinstance(results, dict):
            results_str = json.dumps(results, indent=2)
        else:
            results_str = str(results)
        
        # Create summarization prompt
        prompt = self._create_summarization_prompt(tool_name, parameters, results_str, agent)
        
        # Get summary from LLM
        response = self.summarizer.generate(prompt)
        
        # Parse summary (try to extract structured summary if possible)
        summary = self._parse_summary(response, tool_name, results)
        
        return summary
    
    def _create_summarization_prompt(self, tool_name: str, parameters: Dict[str, Any],
                                     results_str: str, agent: Optional[str] = None) -> str:
        """Create summarization prompt.
        
        Args:
            tool_name: Tool name
            parameters: Tool parameters
            results_str: Results as string
            agent: Agent name (optional)
            
        Returns:
            Summarization prompt
        """
        prompt = f"""Summarize the following tool execution result. Extract key findings, insights, and important information.

Tool: {tool_name}
Agent: {agent or 'unknown'}
Parameters: {json.dumps(parameters, indent=2)}

Results:
{results_str[:5000]}  # Truncate if too long for prompt

Please provide a concise summary with:
1. Key findings (important discoveries)
2. Critical information (vulnerabilities, open ports, services, etc.)
3. Actionable insights (what should be done next)
4. Statistics or counts (number of findings, hosts, ports, etc.)

Format your response as JSON with these fields:
- summary: Brief overall summary
- key_findings: List of important findings
- statistics: Object with counts/statistics
- recommendations: List of recommended next steps
"""
        return prompt
    
    def _parse_summary(self, response: str, tool_name: str, original_results: Any) -> Dict[str, Any]:
        """Parse summary response into structured format.
        
        Args:
            response: LLM response
            tool_name: Tool name
            original_results: Original results (for fallback)
            
        Returns:
            Structured summary dictionary
        """
        # Try to extract JSON from response
        try:
            # Look for JSON block in response
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "{" in response and "}" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
            else:
                json_str = None
            
            if json_str:
                summary = json.loads(json_str)
                return summary
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Fallback: create basic summary from response text
        return {
            "summary": response[:500],  # Truncate to 500 chars
            "key_findings": [],
            "statistics": {},
            "recommendations": [],
            "tool_name": tool_name,
            "raw_summary": response
        }
    
    def create_summary_metadata(self, summary: Dict[str, Any], full_result_size: int) -> Dict[str, Any]:
        """Create metadata for summary.
        
        Args:
            summary: Summary dictionary
            full_result_size: Size of full result in bytes
            
        Returns:
            Metadata dictionary
        """
        return {
            "is_summary": True,
            "full_result_size": full_result_size,
            "summary_size": len(json.dumps(summary).encode('utf-8')),
            "compression_ratio": full_result_size / max(1, len(json.dumps(summary).encode('utf-8')))
        }
