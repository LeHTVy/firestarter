"""
Memory Tool Handlers
====================

Handles: read_memory, write_memory, forget_memory, summarize_target, clear_memory, show_results

Uses unified memory system from app.memory:
- SessionMemory for in-session facts
- MemoryManager for persistent conversation history
"""
from typing import Dict, Any
from app.tools.handlers import register_handler


@register_handler("read_memory")
def handle_read_memory(action_input: Dict[str, Any], state: Any) -> str:
    """Search memory for past findings."""
    query = action_input.get("query", "")
    if not query:
        return 'Error: No query specified. Example: read_memory with {"query": "snode.com ports"}'
    
    print(f"  🧠 Searching memory for: {query}...")
    
    from app.memory import get_session_memory, get_memory_manager
    
    results = []
    
    # 1. Search session memory (in-session facts)
    session = get_session_memory()
    facts = session.get_facts()
    matching_facts = [f for f in facts if query.lower() in str(f.data).lower() or query.lower() in f.target.lower()]
    
    if matching_facts:
        results.append("## Session Facts")
        for fact in matching_facts[:10]:
            results.append(f"- [{fact.fact_type}] {fact.target}: {fact.data}")
    
    # 2. Search conversation history (semantic search)
    try:
        history = get_memory_manager()
        context = history.get_context_for_query(query, include_history=False, include_semantic=True)
        
        if context.get("semantic"):
            results.append("\n## Related Conversations")
            for mem in context["semantic"][:5]:
                results.append(f"- {mem['content'][:150]}...")
        
        if context.get("findings"):
            results.append("\n## Historical Findings")
            for finding in context["findings"][:5]:
                results.append(f"- [{finding['type']}] {finding['data']}")
    except Exception as e:
        results.append(f"\n⚠️ History search unavailable: {e}")
    
    return "\n".join(results) if results else f"No memories found for: {query}"


@register_handler("write_memory")
def handle_write_memory(action_input: Dict[str, Any], state: Any) -> str:
    """Store facts to memory."""
    fact_type = action_input.get("fact_type", "note")
    target = action_input.get("target", "")
    data = action_input.get("data", {})
    
    if not target:
        return 'Error: Target is required. Example: write_memory with {"fact_type": "note", "target": "domain.com", "data": {"note": "..."}}'
    
    print(f"  🧠 Writing to memory: [{fact_type}] {target}...")
    
    from app.memory import get_session_memory
    
    session = get_session_memory()
    fact = session.add_fact(fact_type, target, data, source_tool="agent")
    
    return f"✅ Stored fact [{fact_type}] for {target} (ID: {fact.id})"


@register_handler("forget_memory")
def handle_forget_memory(action_input: Dict[str, Any], state: Any) -> str:
    """Remove facts from memory."""
    fact_id = action_input.get("fact_id", "")
    if not fact_id:
        return 'Error: fact_id is required. Example: forget_memory with {"fact_id": "abc123"}'
    
    print(f"  🧠 Forgetting memory: {fact_id}...")
    
    from app.memory import get_session_memory
    
    session = get_session_memory()
    
    if fact_id in session.facts:
        del session.facts[fact_id]
        return f"✅ Forgot fact: {fact_id}"
    else:
        return f"⚠️ Fact not found: {fact_id}"


@register_handler("summarize_target")
def handle_summarize_target(action_input: Dict[str, Any], state: Any) -> str:
    """Get comprehensive summary of a target."""
    domain = action_input.get("domain", "")
    if not domain:
        return 'Error: Domain is required. Example: summarize_target with {"domain": "snode.com"}'
    
    print(f"  🧠 Summarizing target: {domain}...")
    
    from app.memory import get_session_memory
    
    session = get_session_memory()
    ctx = session.get_context()
    
    parts = [f"## Target Summary: {domain}"]
    
    if ctx.subdomains:
        parts.append(f"\n### Subdomains ({len(ctx.subdomains)})")
        for sub in ctx.subdomains[:20]:
            parts.append(f"- {sub}")
    
    if ctx.ips:
        parts.append(f"\n### IP Addresses ({len(ctx.ips)})")
        for ip in ctx.ips[:10]:
            parts.append(f"- {ip}")
    
    if ctx.open_ports:
        parts.append(f"\n### Open Ports ({len(ctx.open_ports)})")
        for port in ctx.open_ports[:20]:
            parts.append(f"- {port['host']}:{port['port']} ({port.get('service', 'unknown')})")
    
    if ctx.vulnerabilities:
        parts.append(f"\n### Vulnerabilities ({len(ctx.vulnerabilities)})")
        for vuln in ctx.vulnerabilities[:10]:
            parts.append(f"- [{vuln.get('severity', 'medium')}] {vuln.get('type', 'unknown')} on {vuln.get('target', 'N/A')}")
    
    if ctx.technologies:
        parts.append(f"\n### Technologies ({len(ctx.technologies)})")
        parts.append(f"- {', '.join(ctx.technologies)}")
    
    if ctx.tools_run:
        parts.append(f"\n### Tools Run")
        parts.append(f"- {', '.join(ctx.tools_run)}")
    
    return "\n".join(parts)


@register_handler("clear_memory")
def handle_clear_memory(action_input: Dict[str, Any], state: Any) -> str:
    """Clear stored facts."""
    domain = action_input.get("domain", "")
    
    from app.memory import get_session_memory
    
    session = get_session_memory()
    
    if domain:
        # Filter facts by domain
        original_count = len(session.facts)
        session.facts = {k: v for k, v in session.facts.items() if domain not in v.target}
        removed = original_count - len(session.facts)
        print(f"  🧹 Cleared {removed} facts for {domain}")
        return f"✅ Cleared {removed} facts related to {domain}. {len(session.facts)} facts remaining."
    else:
        count = len(session.facts)
        session.clear()
        print(f"  🧹 Cleared all {count} facts")
        return f"✅ Cleared all session memory. Starting fresh."


@register_handler("show_results")
def handle_show_results(action_input: Dict[str, Any], state: Any) -> str:
    """Show recent scan results."""
    limit = action_input.get("limit", 10)
    result_type = action_input.get("type", "all")
    
    from app.memory import get_session_memory
    
    session = get_session_memory()
    facts = session.get_facts()
    
    if result_type != "all":
        facts = [f for f in facts if f.fact_type == result_type]
    
    facts = facts[-limit:]
    
    if not facts:
        return f"No {result_type} results found in current session."
    
    parts = [f"## Recent Results ({len(facts)})"]
    for fact in facts:
        parts.append(f"- [{fact.fact_type}] {fact.target}: {fact.data}")
    
    return "\n".join(parts)
