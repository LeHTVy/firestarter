"""Summary compression for conversation history."""

from typing import Dict, Any, List, Optional
from memory.conversation_store import ConversationStore
from models.llm_client import OllamaLLMClient


class SummaryCompressor:
    """Compress conversation history when buffer gets too long."""
    
    def __init__(self, max_messages: int = 50, compression_threshold: int = 100):
        """Initialize summary compressor.
        
        Args:
            max_messages: Maximum messages to keep in buffer before compression
            compression_threshold: Number of messages that trigger compression
        """
        self.max_messages = max_messages
        self.compression_threshold = compression_threshold
        self.conversation_store = ConversationStore()
        self.model_name = "mistral:latest"  # Use Mistral for summarization (default model)
        
        # Initialize LangChain LLM client
        self.llm_client = OllamaLLMClient(
            model_name=self.model_name,
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            num_predict=2048
        )
    
    def should_compress(self, message_count: int) -> bool:
        """Check if compression needed.
        
        Args:
            message_count: Current number of messages in conversation
            
        Returns:
            True if compression should be performed
        """
        return message_count >= self.compression_threshold
    
    def compress(self, messages: List[Dict[str, Any]], conversation_id: str) -> str:
        """Compress old messages into summary using LLM.
        
        Args:
            messages: List of messages to compress (oldest first)
            conversation_id: Conversation UUID
            
        Returns:
            Compressed summary text
        """
        if not messages:
            return ""
        
        # Format messages for compression
        formatted_messages = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            formatted_messages.append(f"{role.upper()}: {content}")
        
        conversation_text = "\n\n".join(formatted_messages)
        
        # Create compression prompt
        compression_prompt = f"""You need to create a concise summary of a conversation history for a pentest agent system.

The conversation contains multiple turns between user and assistant. Your task is to:
1. Extract key information: targets, findings, tools used, vulnerabilities discovered
2. Preserve important context: verified domains, IPs, ports, subdomains
3. Maintain conversation flow: what was discussed, what actions were taken
4. Keep it concise but comprehensive enough to maintain context

Conversation history to summarize:
{conversation_text}

Create a summary that preserves all critical information for future context retrieval."""

        try:
            # Use Qwen3 via Ollama to generate summary
            system_prompt = "You are a conversation summarizer for a pentest agent system. Create concise but comprehensive summaries that preserve critical context."
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": compression_prompt}
            ]
            
            # Use LangChain client
            response = self.llm_client.generate(
                messages=messages,
                stream=False,
                temperature=0.3,  # Lower temperature for more consistent summaries
                num_predict=1024
            )
            
            if not response.get('success'):
                raise Exception(response.get('error', 'Unknown error'))
            
            summary = response.get('content', '').strip()
            
            # Save summary to conversation
            if summary:
                self.conversation_store.update_conversation_summary(conversation_id, summary)
            
            return summary
        except Exception as e:
            # Fallback on error
            fallback_summary = f"Conversation summary: {len(messages)} messages about {self._extract_key_info(messages)}. Error generating detailed summary: {str(e)}"
            try:
                self.conversation_store.update_conversation_summary(conversation_id, fallback_summary)
            except:
                pass
            return fallback_summary
    
    def _extract_key_info(self, messages: List[Dict]) -> str:
        """Extract key information from messages (fallback method).
        
        Args:
            messages: List of messages
            
        Returns:
            Simple key info string
        """
        targets = set()
        tools = set()
        
        for msg in messages:
            content = msg.get('content', '').lower()
            # Simple extraction (can be improved)
            if 'target' in content or 'domain' in content or 'ip' in content:
                # Try to extract domain/IP patterns
                import re
                domains = re.findall(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+', content)
                ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', content)
                targets.update(domains)
                targets.update(ips)
            
            if 'tool' in content or 'scan' in content or 'nmap' in content:
                tools.add('tools_used')
        
        info_parts = []
        if targets:
            info_parts.append(f"targets: {', '.join(list(targets)[:3])}")
        if tools:
            info_parts.append("tools used")
        
        return "; ".join(info_parts) if info_parts else "general conversation"
    
    def get_context(self, conversation_id: str, query: Optional[str] = None, k_recent: int = 10) -> Dict[str, Any]:
        """Get context: recent messages + summary + semantic search.
        
        Args:
            conversation_id: Conversation UUID
            query: Optional query for semantic search
            k_recent: Number of recent messages to include
            
        Returns:
            Dictionary with recent_messages, summary, and semantic_context
        """
        # Get conversation metadata
        conversation = self.conversation_store.get_conversation(conversation_id)
        summary = conversation.get('summary') if conversation else None
        
        # Get recent messages
        recent_messages = self.conversation_store.get_recent_messages(conversation_id, k=k_recent)
        
        # Format recent messages for context
        formatted_recent = []
        for msg in recent_messages:
            formatted_recent.append({
                "role": msg.get('role'),
                "content": msg.get('content')
            })
        
        context = {
            "recent_messages": formatted_recent,
            "summary": summary,
            "conversation_id": conversation_id
        }
        
        # Add semantic search if query provided
        if query:
            # This will be integrated with ConversationRetriever later
            context["semantic_query"] = query
        
        return context
    
    def auto_compress_if_needed(self, conversation_id: str) -> bool:
        """Automatically compress conversation if needed.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            True if compression was performed, False otherwise
        """
        message_count = self.conversation_store.get_message_count(conversation_id)
        
        if not self.should_compress(message_count):
            return False
        
        # Get messages that should be compressed (all except recent max_messages)
        all_messages = self.conversation_store.get_messages(conversation_id)
        
        if len(all_messages) <= self.max_messages:
            return False
        
        # Messages to compress (oldest ones, excluding recent max_messages)
        messages_to_compress = all_messages[:-self.max_messages]
        recent_messages = all_messages[-self.max_messages:]
        
        if not messages_to_compress:
            return False
        
        # Compress old messages
        summary = self.compress(messages_to_compress, conversation_id)
        
        # Delete compressed messages (they're now in summary)
        # Note: In production, you might want to keep them for audit, but mark as compressed
        # For now, we'll keep them but rely on summary for context
        
        return True
    
    def get_compression_status(self, conversation_id: str) -> Dict[str, Any]:
        """Get compression status for conversation.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Dictionary with compression status info
        """
        conversation = self.conversation_store.get_conversation(conversation_id)
        message_count = self.conversation_store.get_message_count(conversation_id)
        
        return {
            "conversation_id": conversation_id,
            "message_count": message_count,
            "has_summary": bool(conversation and conversation.get('summary')),
            "summary_length": len(conversation.get('summary', '')) if conversation else 0,
            "should_compress": self.should_compress(message_count),
            "compression_threshold": self.compression_threshold,
            "max_messages": self.max_messages
        }
