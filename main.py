"""Main entry point for AI Pentest Agent."""

import sys
import uuid
import os
import io
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from agents.pentest_graph import PentestGraph
from rag.retriever import ConversationRetriever
from rag.results_storage import ToolResultsStorage
from ui.streaming_manager import StreamingManager
from utils.input_normalizer import InputNormalizer
from websearch.aggregator import SearchAggregator
from api.conversation_api import ConversationAPI

os.environ['PYTHONIOENCODING'] = 'utf-8'

if hasattr(sys.stdin, 'buffer'):
    try:
        if sys.stdin.encoding != 'utf-8':
            sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

console = Console()


def safe_prompt_ask(prompt_text: str, default: Optional[str] = None) -> str:
    """Safely ask for user input with encoding error handling.
    
    Args:
        prompt_text: Prompt text to display
        default: Default value if user just presses Enter
        
    Returns:
        User input string
        
    Raises:
        KeyboardInterrupt: Re-raised to allow graceful exit handling
    """
    # Strip Rich markup for plain text fallback
    import re
    plain_prompt = re.sub(r'\[.*?\]', '', prompt_text).strip()
    if not plain_prompt:
        plain_prompt = "You"
    
    try:
        result = Prompt.ask(prompt_text, default=default)
        return str(result) if result is not None else ""
    except KeyboardInterrupt:
        raise
    except (UnicodeDecodeError, UnicodeError) as e:
        try:
            if hasattr(sys.stdin, 'buffer'):
                sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
        except:
            pass
        
        # Use standard input as fallback with clean prompt
        try:
            if default:
                result = input(f"{plain_prompt} (default: {default}): ").strip()
                return result if result else default
            else:
                return input(f"{plain_prompt}: ").strip()
        except KeyboardInterrupt:
            raise
    except Exception as e:
        # Last resort fallback - use standard input with clean prompt
        try:
            if default:
                result = input(f"{plain_prompt} (default: {default}): ").strip()
                return result if result else default
            else:
                return input(f"{plain_prompt}: ").strip()
        except KeyboardInterrupt:
            raise
        except Exception:
            # Ultimate fallback - return default or empty
            return default if default else ""


def main():
    """Main entry point."""
    console.print(Panel.fit(
        "[bold cyan]AI Pentest Agent Multi-Model[/bold cyan]\n"
        "Ollama, AutoGen, LangGraph, LlamaIndex, RAG\n"
        "[dim]With Live Streaming & Typo Handling[/dim]",
        border_style="cyan"
    ))
    
    # Initialize components
    # Enable keyboard listener for expand/collapse (only if stdin is a terminal)
    enable_keyboard = sys.stdin.isatty() if hasattr(sys.stdin, 'isatty') else True
    streaming_manager = StreamingManager(console=console, enable_keyboard=enable_keyboard)
    search_aggregator = SearchAggregator()
    
    # Create interactive callback for asking user questions
    def ask_user_question(question: str) -> str:
        """Ask user a question and return their answer."""
        return safe_prompt_ask(f"\n[bold yellow]❓ {question}[/bold yellow]")
    
    # Initialize Mistral for semantic understanding in input normalizer (replacing Qwen3)
    from models.generic_ollama_agent import GenericOllamaAgent
    mistral_agent = GenericOllamaAgent(
        model_name="mistral:latest",
        prompt_template="qwen3_system.jinja2"
    )
    
    input_normalizer = InputNormalizer(
        search_aggregator=search_aggregator,
        interactive_callback=ask_user_question,
        ai_model=mistral_agent  # Enable AI-based semantic understanding
    )
    conversation_retriever = ConversationRetriever()
    results_storage = ToolResultsStorage()
    
    # Initialize memory manager and conversation API
    from memory.manager import get_memory_manager
    memory_manager = get_memory_manager()
    conversation_api = ConversationAPI(memory_manager=memory_manager)
    
    # Create streaming callback for graph
    def graph_stream_callback(event_type: str, event_name: str, event_data: any):
        """Handle streaming events from graph."""
        try:
            if event_type == "model_response":
                # Model response streaming
                panel_id = streaming_manager.create_model_panel(event_name)
                if isinstance(event_data, str):
                    streaming_manager.stream_model_response(panel_id, event_data)
            elif event_type == "tool_output":
                # Tool output streaming
                # event_name format: "tool_name" or "tool_name:command_name"
                parts = event_name.split(":", 1)
                tool_name = parts[0]
                command_name = parts[1] if len(parts) > 1 else None
                
                panel_id = streaming_manager.create_tool_panel(
                    tool_name=tool_name,
                    command_name=command_name
                )
                if isinstance(event_data, str):
                    streaming_manager.update_tool_output(panel_id, event_data)
            elif event_type == "state_update":
                # State update
                streaming_manager.update_progress(f"Node: {event_name}")
                pass
        except Exception as e:

            pass
    
    # Multi-Agent Model Selection - Auto-detect available Ollama models
    agent_model_config = {} 
    selected_model = "mistral:latest"  
    
    try:
        from utils.ollama_helper import get_model_names, check_model_exists
        from utils.model_selector import MultiAgentModelSelector
        
        console.print("\n[bold cyan]Model Selection[/bold cyan]")
        
        # Get available models from Ollama
        available_models = get_model_names()
        
        if not available_models:
            console.print("[yellow]⚠️  No models found in Ollama. Please install at least one model.[/yellow]")
            console.print("[dim]Example: ollama pull mistral:latest[/dim]\n")
            selected_model = "mistral:latest"  
            agent_model_config = {
                "recon_agent": selected_model,
                "exploit_agent": selected_model,
                "analysis_agent": selected_model,
                "results_qa_agent": selected_model,
            }
        else:
            # Ask user for model selection mode
            console.print(f"[dim]Found {len(available_models)} model(s) in Ollama.[/dim]\n")
            console.print("1. Quick mode: Use same model for all agents")
            console.print("2. Multi-agent mode: Assign different models to different agents")
            
            mode_choice = safe_prompt_ask("\n[dim]Select mode (1-2, default: 2)[/dim]", default="2")
            
            if mode_choice == "1":
                # Quick mode: Single model for all agents
                console.print("\n[bold]Available Models:[/bold]")
                for i, model_name in enumerate(available_models, 1):
                    is_recommended = any(keyword in model_name.lower() for keyword in ["pentest", "qwen2", "deepseek"])
                    marker = " ⭐ (recommended)" if is_recommended else ""
                    console.print(f"  {i}. {model_name}{marker}")
                
                max_choice = len(available_models)
                model_choice = safe_prompt_ask(
                    f"\n[dim]Select model for all agents (1-{max_choice}, default: 1)[/dim]",
                    default="1"
                )
                
                if model_choice.isdigit() and 1 <= int(model_choice) <= max_choice:
                    selected_model = available_models[int(model_choice) - 1]
                else:
                    selected_model = available_models[0]
                
                agent_model_config = {
                    "recon_agent": selected_model,
                    "exploit_agent": selected_model,
                    "analysis_agent": selected_model,
                    "results_qa_agent": selected_model,
                }
                console.print(f"\n[green]✅ Using {selected_model} for all agents[/green]")
            else:
                # Multi-agent mode: Different models for different agents
                model_selector = MultiAgentModelSelector(console=console)
                agent_model_config = model_selector.select_models(
                    available_models=available_models,
                    prompt_func=safe_prompt_ask
                )
                # Use analysis_agent model as the "main" selected model for backward compatibility
                selected_model = agent_model_config.get("analysis_agent", available_models[0])
                
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user. Goodbye![/yellow]")
        sys.exit(0)
    except Exception as e:
        # Fallback if Ollama detection fails
        console.print(f"[yellow]⚠️  Could not detect Ollama models: {e}[/yellow]")
        console.print("[dim]Using default model: mistral:latest[/dim]")
        selected_model = "mistral:latest"
        agent_model_config = {
            "recon_agent": selected_model,
            "exploit_agent": selected_model,
            "analysis_agent": selected_model,
            "results_qa_agent": selected_model,
        }
    
    # Tool calling model selection
    tool_calling_model_name = "json_tool_calling"
    
    try:
        from models.tool_calling_registry import get_tool_calling_registry
        tool_registry = get_tool_calling_registry()
        available_tool_models = tool_registry.list_models()
        
        console.print("\n[bold cyan]Tool Calling Model Selection[/bold cyan]")
        for i, model_name in enumerate(available_tool_models, 1):
            display_name = "JSON Tool Calling (JSON string format)"
            default_marker = " (default)" if model_name == "json_tool_calling" else ""
            console.print(f"{i}. {display_name}{default_marker}")
        
        tool_model_choice = safe_prompt_ask(f"\n[dim]Select tool calling model (1-{len(available_tool_models)}, default: 1)[/dim]", default="1")
        
        if tool_model_choice.isdigit() and 1 <= int(tool_model_choice) <= len(available_tool_models):
            selected_tool_model = available_tool_models[int(tool_model_choice) - 1]
            tool_registry.set_default(selected_tool_model)
            tool_calling_model_name = selected_tool_model
            console.print(f"[green]✅ Using tool calling model: {selected_tool_model}[/green]\n")
        else:
            tool_calling_model_name = "json_tool_calling"
            console.print(f"[green]✅ Using default tool calling model: json_tool_calling[/green]\n")
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user. Goodbye![/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[yellow]⚠️  Tool calling model selection failed: {e}. Using default.[/yellow]\n")
        tool_calling_model_name = "json_tool_calling"
    
    # Autonomy Level Selection
    from agents.autonomy_controller import get_autonomy_controller, AutonomyLevel, LEVEL_DESCRIPTIONS
    autonomy_controller = get_autonomy_controller()
    
    try:
        console.print("[bold cyan]Autonomy Level Selection[/bold cyan]")
        for lvl in AutonomyLevel:
            marker = " (default)" if lvl == AutonomyLevel.COPILOT else ""
            console.print(f"{lvl.value}. {LEVEL_DESCRIPTIONS[lvl]}{marker}")
        
        autonomy_choice = safe_prompt_ask(
            "\n[dim]Select autonomy level (0-3, default: 1)[/dim]", 
            default="1"
        )
        
        try:
            level = AutonomyLevel(int(autonomy_choice))
            autonomy_controller.set_level(level)
            console.print(f"[green]✅ Autonomy level: {LEVEL_DESCRIPTIONS[level]}[/green]\n")
        except (ValueError, KeyError):
            console.print("[yellow]Using default: COPILOT[/yellow]\n")
            autonomy_controller.set_level(AutonomyLevel.COPILOT)
        
        # Set confirmation callback for gated actions
        def confirm_action(message: str, context) -> str:
            return safe_prompt_ask(f"[bold yellow]⚠️ {message}[/bold yellow] [dim](yes/no)[/dim]", default="no")
        
        autonomy_controller.confirm_callback = confirm_action
        
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user. Goodbye![/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[yellow]⚠️  Autonomy selection failed: {e}. Using default COPILOT.[/yellow]\n")
        autonomy_controller.set_level(AutonomyLevel.COPILOT)
    
    graph = PentestGraph(
        stream_callback=graph_stream_callback,
        analysis_model=selected_model,
        tool_calling_model=tool_calling_model_name,
        agent_model_config=agent_model_config
    )
    
    # Conversation management
    current_conversation_id: Optional[str] = None
    session_id: Optional[str] = None  # Legacy support
    
    # Show conversation selection menu
    try:
        console.print("\n[bold cyan]Conversation Management[/bold cyan]")
        console.print("1. Create new conversation")
        console.print("2. List existing conversations")
        console.print("3. Load existing conversation")
        console.print("4. Continue with new conversation (default)")
        
        choice = safe_prompt_ask("\n[dim]Choice (1-4, default: 4)[/dim]", default="4")
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user. Goodbye![/yellow]")
        sys.exit(0)
    
    if choice == "1":
        try:
            title = safe_prompt_ask("[dim]Conversation title (optional)[/dim]", default="")
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Interrupted by user. Goodbye![/yellow]")
            sys.exit(0)
        result = conversation_api.create_conversation(title=title if title else None)
        if result.get("success"):
            current_conversation_id = result["conversation_id"]
            console.print(f"[green]✅ Created conversation: {current_conversation_id}[/green]")
        else:
            console.print(f"[red]❌ Failed to create conversation: {result.get('error')}[/red]")
            current_conversation_id = memory_manager.start_conversation()
    elif choice == "2":
        result = conversation_api.list_conversations(limit=10)
        if result.get("success"):
            conversations = result["conversations"]
            if conversations:
                console.print("\n[bold]Existing conversations:[/bold]")
                for i, conv in enumerate(conversations, 1):
                    title = conv.get("title") or "Untitled"
                    conv_id = conv.get("id")
                    updated = str(conv.get("updated_at", ""))[:10] if conv.get("updated_at") else ""
                    console.print(f"  {i}. {title} ({conv_id[:8]}...) - Updated: {updated}")
                
                try:
                    load_choice = safe_prompt_ask("\n[dim]Load conversation number (or Enter to create new)[/dim]", default="")
                except KeyboardInterrupt:
                    console.print("\n\n[yellow]Interrupted by user. Goodbye![/yellow]")
                    sys.exit(0)
                if load_choice.isdigit():
                    idx = int(load_choice) - 1
                    if 0 <= idx < len(conversations):
                        current_conversation_id = conversations[idx]["id"]
                        switch_result = conversation_api.switch_conversation(current_conversation_id, memory_manager)
                        if switch_result.get("success"):
                            console.print(f"[green]✅ Loaded conversation: {conversations[idx].get('title', 'Untitled')}[/green]")
                        else:
                            console.print(f"[red]❌ Failed to load conversation[/red]")
                            current_conversation_id = memory_manager.start_conversation()
                    else:
                        current_conversation_id = memory_manager.start_conversation()
                else:
                    current_conversation_id = memory_manager.start_conversation()
            else:
                console.print("[yellow]No existing conversations. Creating new...[/yellow]")
                current_conversation_id = memory_manager.start_conversation()
        else:
            console.print(f"[red]❌ Failed to list conversations[/red]")
            current_conversation_id = memory_manager.start_conversation()
    elif choice == "3":
        try:
            conv_id = safe_prompt_ask("[dim]Conversation ID[/dim]")
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Interrupted by user. Goodbye![/yellow]")
            sys.exit(0)
        if conv_id:
            switch_result = conversation_api.switch_conversation(conv_id, memory_manager)
            if switch_result.get("success"):
                current_conversation_id = conv_id
                console.print(f"[green]✅ Loaded conversation: {conv_id}[/green]")
            else:
                console.print(f"[red]❌ Failed to load conversation: {switch_result.get('error')}[/red]")
                current_conversation_id = memory_manager.start_conversation()
        else:
            current_conversation_id = memory_manager.start_conversation()
    else:
        # Default: Create new conversation
        current_conversation_id = memory_manager.start_conversation()
    
    # Get session_id for legacy compatibility
    session_id = memory_manager.session_id
    
    console.print(f"[dim]Conversation ID: {current_conversation_id}[/dim]")
    if session_id:
        console.print(f"[dim]Session ID (legacy): {session_id}[/dim]")
    console.print("")
    
    try:
        while True:
            # Get user input
            user_prompt = safe_prompt_ask("\n[bold green]You[/bold green]")
            
            if user_prompt.lower() in ["exit", "quit", "q"]:
                console.print("\n[cyan]Goodbye![/cyan]")
                break
            
            # Normalize input (fix typos, extract targets, verify DNS with web search)
            normalized = input_normalizer.normalize_input(user_prompt, verify_domains=True)
            normalized_prompt = normalized.get("normalized_text", user_prompt)
            
            # Show normalization if there were corrections
            corrections = []
            if normalized.get("corrected_tools"):
                for old, new in normalized["corrected_tools"].items():
                    corrections.append(f"Tool '{old}' → '{new}'")
            if normalized.get("corrected_targets"):
                for old, new in normalized["corrected_targets"].items():
                    corrections.append(f"Target '{old}' → '{new}' (verified via web search)")
            if normalized.get("normalized_targets"):
                for i, target in enumerate(normalized.get("targets", [])):
                    normalized_target = normalized["normalized_targets"][i]
                    if normalized_target != target and target not in normalized.get("corrected_targets", {}):
                        corrections.append(f"Target normalized: {target} → {normalized_target}")
            
            if corrections:
                console.print(f"[dim]Corrections: {', '.join(corrections)}[/dim]")
            
            # Check for special commands
            if user_prompt.lower().startswith("/"):
                cmd_parts = user_prompt[1:].split()
                cmd = cmd_parts[0].lower() if cmd_parts else ""
                
                if cmd == "list":
                    # List conversations
                    result = conversation_api.list_conversations(limit=20)
                    if result.get("success"):
                        conversations = result["conversations"]
                        console.print("\n[bold]Conversations:[/bold]")
                        for conv in conversations:
                            title = conv.get("title") or "Untitled"
                            conv_id = conv.get("id")
                            updated = conv.get("updated_at", "")[:19] if conv.get("updated_at") else ""
                            console.print(f"  • {title} - {conv_id[:8]}... - {updated}")
                    continue
                elif cmd == "switch" and len(cmd_parts) > 1:
                    # Switch conversation
                    conv_id = cmd_parts[1]
                    switch_result = conversation_api.switch_conversation(conv_id, memory_manager)
                    if switch_result.get("success"):
                        current_conversation_id = conv_id
                        session_id = memory_manager.session_id
                        console.print(f"[green]✅ Switched to conversation: {conv_id}[/green]")
                    else:
                        console.print(f"[red]❌ Failed to switch: {switch_result.get('error')}[/red]")
                    continue
                elif cmd == "new":
                    # Create new conversation
                    current_conversation_id = memory_manager.start_conversation()
                    session_id = memory_manager.session_id
                    console.print(f"[green]✅ Created new conversation: {current_conversation_id}[/green]")
                    continue
                elif cmd == "save":
                    # Save current conversation state
                    if current_conversation_id:
                        # State is already persisted, just confirm
                        console.print(f"[green]✅ Conversation state saved[/green]")
                    continue
                elif cmd == "autonomy":
                    # Autonomy level control
                    from agents.autonomy_controller import get_autonomy_controller, AutonomyLevel, LEVEL_DESCRIPTIONS
                    controller = get_autonomy_controller()
                    
                    if len(cmd_parts) > 1:
                        try:
                            new_level = int(cmd_parts[1])
                            if 0 <= new_level <= 3:
                                controller.set_level(AutonomyLevel(new_level), current_conversation_id)
                                console.print(f"[green]✅ Autonomy level set to: {LEVEL_DESCRIPTIONS[AutonomyLevel(new_level)]}[/green]")
                            else:
                                console.print("[red]Invalid level. Use 0-3.[/red]")
                        except ValueError:
                            console.print("[red]Invalid level. Use a number 0-3.[/red]")
                    else:
                        current = controller.get_level(current_conversation_id)
                        console.print(f"\n[bold]Current Autonomy Level: {LEVEL_DESCRIPTIONS[current]}[/bold]")
                        console.print("\nAvailable levels:")
                        for lvl in AutonomyLevel:
                            marker = " ← current" if lvl == current else ""
                            console.print(f"  {lvl.value} = {LEVEL_DESCRIPTIONS[lvl]}{marker}")
                        console.print("\n[dim]Usage: /autonomy <level>[/dim]")
                    continue
                elif cmd == "help":
                    console.print("\n[bold]Commands:[/bold]")
                    console.print("  /list - List all conversations")
                    console.print("  /switch <id> - Switch to conversation")
                    console.print("  /new - Create new conversation")
                    console.print("  /save - Save current conversation")
                    console.print("  /autonomy [level] - View or set autonomy level (0-3)")
                    console.print("  /help - Show this help")
                    continue
            
            # Add to persistent conversation buffer (production)
            if current_conversation_id:
                try:
                    memory_manager.conversation_store.add_message(current_conversation_id, "user", user_prompt)
                except Exception:
                    # Fallback to legacy
                    memory_manager.add_to_conversation_buffer(session_id, "user", user_prompt, conversation_id=current_conversation_id)
            else:
                # Legacy fallback
                memory_manager.add_to_conversation_buffer(session_id, "user", user_prompt)
            
            # Start streaming display
            streaming_manager.start()
            streaming_manager.clear()
            streaming_manager.set_total_steps(5)
            streaming_manager.update_progress("Starting workflow...")
            
            try:
                # Run graph with conversation_id (with Human in the Loop support)
                # We'll handle approval in the callback
                pending_approval_state = None
                
                # Modified callback to handle approval
                def approval_aware_callback(event_type: str, event_name: str, event_data: any):
                    nonlocal pending_approval_state
                    
                    # Call original callback
                    graph_stream_callback(event_type, event_name, event_data)
                    
                    # Check if this is a recommend_tools node that needs approval
                    if event_type == "state_update" and event_name == "recommend_tools":
                        if isinstance(event_data, dict):
                            recommendations = event_data.get("tool_recommendations")
                            approval = event_data.get("user_approval")
                            
                            if recommendations and recommendations.get("needs_approval") and approval is None:
                                # Store state for approval
                                pending_approval_state = event_data
                
                # Set up approval-aware callback temporarily
                original_callback = graph.stream_callback
                graph.stream_callback = approval_aware_callback
                
                # Run graph
                result = graph.run_streaming(
                    user_prompt, 
                    session_id=session_id,  # Legacy support
                    conversation_id=current_conversation_id  # Production
                )
                
                # Restore original callback
                graph.stream_callback = original_callback
                
                # Check if we need to ask for approval
                if result.get("needs_approval") and result.get("approval_state"):
                    approval_state = result["approval_state"]
                    recommendations = approval_state.get("tool_recommendations", {})
                    tool_subtasks = recommendations.get("subtasks", [])
                    
                    console.print()
                    console.print("[bold yellow]💡 Recommended Tools:[/bold yellow]")
                    for i, subtask in enumerate(tool_subtasks[:5], 1):
                        tool_names = ", ".join(subtask.get("required_tools", []))
                        console.print(f"  {i}. [cyan]{subtask.get('name', 'Tool execution')}[/cyan] - {tool_names}")
                    
                    console.print()
                    try:
                        approval_response = safe_prompt_ask(
                            "[bold yellow]❓ Execute recommended tools?[/bold yellow] [dim](yes/no)[/dim]",
                            default="yes"
                        )
                    except KeyboardInterrupt:
                        console.print("\n\n[yellow]Interrupted by user. Goodbye![/yellow]")
                        sys.exit(0)
                    
                    if approval_response.lower() in ["yes", "y", "approve", "ok", "okay"]:
                        # User approved, update state and continue execution
                        approval_state["user_approval"] = "yes"
                        approval_state.pop("_needs_approval", None)  # Remove flag
                        
                        console.print("[green]✅ Executing tools...[/green]\n")
                        
                        # Continue graph execution from approval state
                        # Stream from the updated state
                        for event in graph.graph.stream(approval_state):
                            for node_name, node_state in event.items():
                                if graph.stream_callback:
                                    graph.stream_callback("state_update", node_name, node_state)
                                
                                # Update result with final state
                                if node_name == "synthesize":
                                    result["answer"] = node_state.get("final_answer", result.get("answer", ""))
                                    result["tool_results"] = node_state.get("tool_results", [])
                                    result["search_results"] = node_state.get("search_results")
                                    result["knowledge_results"] = node_state.get("knowledge_results")
                    else:
                        # User rejected, skip tools and go to synthesis
                        console.print("[yellow]⏭️  Skipping tools. Proceeding to synthesis...[/yellow]\n")
                        
                        # Update state to skip tools
                        approval_state["user_approval"] = "no"
                        approval_state.pop("_needs_approval", None)
                        
                        # Continue to synthesize directly
                        from agents.pentest_graph import GraphState
                        synthesize_state = approval_state.copy()
                        synthesize_result = graph._synthesize_node(synthesize_state)
                        
                        result["answer"] = synthesize_result.get("final_answer", "Tools were skipped as requested.")
                        result["tool_results"] = []
                
                # Get answer with robust None handling
                answer = result.get("answer") or result.get("final_answer") or "No answer generated."
                # Ensure answer is always a string, never None
                if answer is None:
                    answer = "No answer was generated. Please try again."
                if not isinstance(answer, str):
                    answer = str(answer)
                
                # Add to persistent conversation buffer (production)
                if current_conversation_id:
                    try:
                        memory_manager.conversation_store.add_message(current_conversation_id, "assistant", answer)
                        # Auto-compress if needed
                        memory_manager.summary_compressor.auto_compress_if_needed(current_conversation_id)
                    except Exception:
                        # Fallback to legacy
                        memory_manager.add_to_conversation_buffer(session_id, "assistant", answer, conversation_id=current_conversation_id)
                else:
                    # Legacy fallback
                    memory_manager.add_to_conversation_buffer(session_id, "assistant", answer)
                
                # Save conversation turn to memory manager (includes RAG, buffer, verified targets)
                try:
                    # Extract tools used from result
                    tools_used = []
                    tool_results = result.get("tool_results", [])
                    if tool_results:
                        tools_used = [tr.get("tool_name", "") for tr in tool_results if tr.get("tool_name")]
                    
                    # Extract verified target from result state if available
                    verified_target = None
                    result_state = result.get("state", {})
                    if result_state:
                        target_clarification = result_state.get("target_clarification", {})
                        verified_target = target_clarification.get("verified_domain")
                        if not verified_target:
                            session_context = result_state.get("session_context", {})
                            verified_target = session_context.get("target_domain")
                    
                    if not verified_target:
                        extracted_targets = normalized.get("targets", [])
                        if extracted_targets:
                            verified_target = extracted_targets[0]
                    
                    memory_manager.save_turn(
                        user_message=user_prompt,
                        assistant_message=answer,
                        tools_used=tools_used,
                        session_id=session_id,  
                        conversation_id=current_conversation_id,  
                        context={"target_domain": verified_target}
                    )
                except Exception as e:
                    import warnings
                    warnings.warn(f"Failed to save to memory: {str(e)}")
                
                streaming_manager.complete_progress_step("Workflow completed")
                
                streaming_manager.stop()
                
                console.print()  
                if not answer or not isinstance(answer, str):
                    answer = "No answer was generated. Please try again."
                console.print(Panel(
                    answer,
                    title="[bold blue]Final Answer[/bold blue]",
                    border_style="blue"
                ))
                
                # Show tool results if any
                tool_results = result.get("tool_results", [])
                if tool_results:
                    console.print(f"\n[dim]Executed {len(tool_results)} tool(s)[/dim]")
                    
            except Exception as e:
                streaming_manager.stop()
                raise e
    
    except KeyboardInterrupt:
        streaming_manager.stop()
        console.print("\n\n[yellow]Interrupted by user. Goodbye![/yellow]")
        sys.exit(0)
    except Exception as e:
        streaming_manager.stop()
        if isinstance(e, KeyboardInterrupt):
            console.print("\n\n[yellow]Interrupted by user. Goodbye![/yellow]")
            sys.exit(0)
        else:
            console.print(f"\n[red]Error: {str(e)}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console = Console()
        console.print("\n\n[yellow]Interrupted by user. Goodbye![/yellow]")
        sys.exit(0)
