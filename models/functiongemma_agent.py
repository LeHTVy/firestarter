"""FunctionGemma agent for tool calling."""

import json
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

from tools.registry import get_registry
from tools.executor import get_executor
from config import load_config
from models.llm_client import OllamaLLMClient


class FunctionGemmaAgent:
    """FunctionGemma agent for semantic tool calling."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize FunctionGemma agent.
        
        Args:
            config_path: Path to Ollama config file
        """
        self.config = load_config(config_path) if config_path else self._load_default_config()
        self.model_config = self.config['models']['functiongemma']
        self.ollama_base_url = self.config['ollama']['base_url']
        
        # Initialize LangChain LLM client for FunctionGemma
        self.llm_client = OllamaLLMClient(
            model_name=self.model_config['model_name'],
            base_url=self.ollama_base_url,
            config_path=config_path,
            temperature=self.model_config.get('temperature', 0.0),
            top_p=self.model_config.get('top_p', 0.9),
            top_k=self.model_config.get('top_k', 40),
            num_predict=self.model_config.get('num_predict', 512)
        )
        
        self.registry = get_registry()
        self.executor = get_executor()
        
        # Load prompt template
        template_dir = Path(__file__).parent.parent / "prompts"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.system_prompt_template = self.env.get_template("functiongemma_system.jinja2")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default config."""
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "ollama_config.yaml"
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def get_system_prompt(self, tools: Optional[List[Dict]] = None, 
                         subtask: Optional[str] = None,
                         conversation_history: Optional[str] = None) -> str:
        """Get system prompt for FunctionGemma.
        
        Args:
            tools: List of available tools
            subtask: Current subtask
            conversation_history: Conversation history
            
        Returns:
            System prompt string
        """
        return self.system_prompt_template.render(
            tools=tools or [],
            subtask=subtask,
            conversation_history=conversation_history
        )
    
    def call_with_tools(self,
                       user_prompt: str,
                       tools: Optional[List[str]] = None,
                       agent: Optional[str] = None,
                       session_id: Optional[str] = None,
                       conversation_history: Optional[List[Dict]] = None,
                       stream_callback: Optional[Callable[[str], None]] = None,
                       tool_stream_callback: Optional[Callable[[str, str, str], None]] = None) -> Dict[str, Any]:
        """Call FunctionGemma with tool calling support.
        
        Args:
            user_prompt: User prompt or subtask
            tools: List of tool names to make available. If None, uses all tools for agent
            agent: Agent name (for tool filtering)
            session_id: Session identifier
            conversation_history: Previous conversation messages
            
        Returns:
            Response with tool calls or final answer
        """
        # Get available tools
        if tools is None:
            if agent:
                tool_defs = self.registry.get_tools_for_agent(agent)
            else:
                tool_defs = self.registry.list_tools()
        else:
            tool_defs = [self.registry.get_tool(t) for t in tools if self.registry.get_tool(t)]
        
        # Convert to Ollama format
        ollama_tools = self.registry.get_all_tool_schemas_for_ollama()
        if agent:
            # Filter by agent
            agent_tools = self.registry.get_tools_for_agent(agent)
            tool_names = {t.name for t in agent_tools}
            ollama_tools = [t for t in ollama_tools if t['function']['name'] in tool_names]
        
        # Build messages
        messages = []
        
        # Add system prompt
        system_prompt = self.get_system_prompt(
            tools=tool_defs,
            subtask=user_prompt,
            conversation_history=self._format_history(conversation_history) if conversation_history else None
        )
        messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history:
                if msg.get("role") in ["user", "assistant"]:
                    messages.append(msg)
        
        # Add current user prompt
        messages.append({"role": "user", "content": user_prompt})
        
        # Call Ollama with tools
        try:
            if stream_callback:
                # Streaming mode with function calling
                # Note: LangChain doesn't support streaming with function calling well,
                # so we use direct ollama.chat() for this case
                import ollama
                response_content = ""
                response = ollama.chat(
                    model=self.model_config['model_name'],
                    messages=messages,
                    tools=ollama_tools,
                    stream=True,
                    options={
                        "temperature": self.model_config.get('temperature', 0.0),
                        "top_p": self.model_config.get('top_p', 0.9),
                        "top_k": self.model_config.get('top_k', 40),
                        "num_predict": self.model_config.get('num_predict', 512)
                    }
                )
                
                # Collect streaming chunks
                for chunk in response:
                    chunk_content = chunk.get('message', {}).get('content', '')
                    if chunk_content:
                        response_content += chunk_content
                        stream_callback(chunk_content)
                    
                    # Check if we have a complete message with tool_calls
                    if chunk.get('message', {}).get('tool_calls'):
                        # Reconstruct response from chunks
                        message = chunk.get('message', {})
                        break
                else:
                    # No tool calls, get final message using LangChain client
                    response = self.llm_client.generate_with_tools(
                        messages=messages,
                        tools=ollama_tools,
                        temperature=self.model_config.get('temperature', 0.0),
                        top_p=self.model_config.get('top_p', 0.9),
                        top_k=self.model_config.get('top_k', 40),
                        num_predict=self.model_config.get('num_predict', 512)
                    )
                    if response.get('success'):
                        message = response.get('message', {})
                    else:
                        # Fallback to direct call
                        import ollama
                        response = ollama.chat(
                            model=self.model_config['model_name'],
                            messages=messages,
                            tools=ollama_tools,
                            options={
                                "temperature": self.model_config.get('temperature', 0.0),
                                "top_p": self.model_config.get('top_p', 0.9),
                                "top_k": self.model_config.get('top_k', 40),
                                "num_predict": self.model_config.get('num_predict', 512)
                            }
                        )
                        message = response.get('message', {})
            else:
                # Non-streaming mode - use LangChain client
                response = self.llm_client.generate_with_tools(
                    messages=messages,
                    tools=ollama_tools,
                    temperature=self.model_config.get('temperature', 0.0),
                    top_p=self.model_config.get('top_p', 0.9),
                    top_k=self.model_config.get('top_k', 40),
                    num_predict=self.model_config.get('num_predict', 512)
                )
                
                if not response.get('success'):
                    # Fallback to direct call on error
                    import ollama
                    response = ollama.chat(
                        model=self.model_config['model_name'],
                        messages=messages,
                        tools=ollama_tools,
                        options={
                            "temperature": self.model_config.get('temperature', 0.0),
                            "top_p": self.model_config.get('top_p', 0.9),
                            "top_k": self.model_config.get('top_k', 40),
                            "num_predict": self.model_config.get('num_predict', 512)
                        }
                    )
                    message = response.get('message', {})
                else:
                    message = response.get('message', {})
            
            # Check for tool calls
            if message.get('tool_calls'):
                # Execute tools and continue conversation
                tool_results = []
                for tool_call in message['tool_calls']:
                    func = tool_call.get('function', {})
                    tool_name_full = func.get('name')
                    arguments = func.get('arguments', {})
                    
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            arguments = {}
                    
                    # Parse tool_name:command_name format
                    command_name = None
                    if ":" in tool_name_full:
                        parts = tool_name_full.split(":", 1)
                        tool_name = parts[0]
                        command_name = parts[1] if len(parts) > 1 else None
                    else:
                        tool_name = tool_name_full
                    
                    # Validate arguments are provided
                    if not arguments or len(arguments) == 0:
                        error_msg = f"Tool '{tool_name_full}' called without parameters. Please extract parameters from the context."
                        tool_results.append({
                            "tool_call_id": tool_call.get('id'),
                            "tool_name": tool_name,
                            "result": {
                                "success": False,
                                "error": error_msg,
                                "tool_name": tool_name,
                                "parameters": {},
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        })
                        continue
                    
                    # Execute tool with streaming if callback provided
                    if tool_stream_callback:
                        def tool_callback(line: str):
                            tool_stream_callback(tool_name, command_name or "", line)
                        
                        exec_result = self.executor.execute_tool_streaming(
                            tool_name=tool_name,
                            parameters=arguments,
                            stream_callback=tool_callback,
                            agent=agent,
                            session_id=session_id,
                            command_name=command_name
                        )
                    else:
                        exec_result = self.executor.execute_tool(
                            tool_name=tool_name,
                            parameters=arguments,
                            agent=agent,
                            session_id=session_id,
                            command_name=command_name
                        )
                    
                    tool_results.append({
                        "tool_call_id": tool_call.get('id'),
                        "tool_name": tool_name,
                        "result": exec_result
                    })
                
                # Add tool call message to history
                messages.append(message)
                
                # Add tool results
                for tr in tool_results:
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(tr['result']),
                        "name": tr['tool_name']
                    })
                
                # Continue conversation to get final answer
                if stream_callback:
                    # Streaming mode for final response
                    final_content = ""
                    final_response_gen = ollama.chat(
                        model=self.model_config['model_name'],
                        messages=messages,
                        tools=ollama_tools,
                        stream=True,
                        options={
                            "temperature": self.model_config.get('temperature', 0.0),
                            "top_p": self.model_config.get('top_p', 0.9),
                            "top_k": self.model_config.get('top_k', 40),
                            "num_predict": self.model_config.get('num_predict', 512)
                        }
                    )
                    
                    for chunk in final_response_gen:
                        chunk_content = chunk.get('message', {}).get('content', '')
                        if chunk_content:
                            final_content += chunk_content
                            stream_callback(chunk_content)
                    
                    # Reconstruct final response
                    final_response = {'message': {'content': final_content}}
                else:
                    final_response = ollama.chat(
                        model=self.model_config['model_name'],
                        messages=messages,
                        tools=ollama_tools,
                        options={
                            "temperature": self.model_config.get('temperature', 0.0),
                            "top_p": self.model_config.get('top_p', 0.9),
                            "top_k": self.model_config.get('top_k', 40),
                            "num_predict": self.model_config.get('num_predict', 512)
                        }
                    )
                
                # Extract reasoning from final response if present
                # Handle both LangChain format and direct ollama format
                if isinstance(final_response, dict) and 'message' in final_response:
                    final_answer_content = final_response.get('message', {}).get('content', '')
                elif isinstance(final_response, dict) and 'content' in final_response:
                    final_answer_content = final_response.get('content', '')
                else:
                    final_answer_content = str(final_response)
                final_reasoning = reasoning
                if final_answer_content and "<reasoning>" in final_answer_content and "</reasoning>" in final_answer_content:
                    reasoning_start = final_answer_content.find("<reasoning>") + len("<reasoning>")
                    reasoning_end = final_answer_content.find("</reasoning>", reasoning_start)
                    if reasoning_end > reasoning_start:
                        final_reasoning = final_answer_content[reasoning_start:reasoning_end].strip()
                
                return {
                    "success": True,
                    "tool_calls": [tr['tool_name'] for tr in tool_results],
                    "tool_results": tool_results,
                    "final_answer": final_answer_content,
                    "reasoning": final_reasoning,  # Store reasoning for debugging and learning
                    "message": final_response.get('message', {})
                }
            else:
                # No tool calls, return direct answer
                return {
                    "success": True,
                    "tool_calls": [],
                    "final_answer": message.get('content', ''),
                    "reasoning": reasoning,  # Store reasoning even if no tool calls
                    "message": message
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool_calls": [],
                "final_answer": None
            }
    
    def _format_history(self, history: List[Dict]) -> str:
        """Format conversation history for prompt.
        
        Args:
            history: Conversation history
            
        Returns:
            Formatted history string
        """
        formatted = []
        for msg in history:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)
    
    def multi_turn_tool_calling(self,
                                initial_prompt: str,
                                max_turns: int = 5,
                                agent: Optional[str] = None,
                                session_id: Optional[str] = None) -> Dict[str, Any]:
        """Perform multi-turn tool calling.
        
        Args:
            initial_prompt: Initial user prompt
            max_turns: Maximum number of tool calling turns
            agent: Agent name
            session_id: Session identifier
            
        Returns:
            Final result after multiple turns
        """
        conversation_history = []
        all_tool_results = []
        turn = 0
        
        current_prompt = initial_prompt
        
        while turn < max_turns:
            response = self.call_with_tools(
                user_prompt=current_prompt,
                agent=agent,
                session_id=session_id,
                conversation_history=conversation_history
            )
            
            if not response.get('success'):
                return response
            
            # Add to history
            conversation_history.append({"role": "user", "content": current_prompt})
            if response.get('message'):
                conversation_history.append(response['message'])
            
            # Collect tool results
            if response.get('tool_results'):
                all_tool_results.extend(response['tool_results'])
            
            # If no more tool calls, return final answer
            if not response.get('tool_calls'):
                return {
                    "success": True,
                    "final_answer": response.get('final_answer', ''),
                    "tool_results": all_tool_results,
                    "turns": turn + 1
                }
            
            # Continue with next turn
            turn += 1
            current_prompt = "Continue processing with the tool results above."
        
        # Max turns reached
        return {
            "success": True,
            "final_answer": response.get('final_answer', ''),
            "tool_results": all_tool_results,
            "turns": turn,
            "max_turns_reached": True
        }
