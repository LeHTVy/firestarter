"""
Training Tool Handlers
======================

Handles: show_training, correct_action, export_training
"""
from typing import Dict, Any
from app.tools.handlers import register_handler


@register_handler("show_training")
def handle_show_training(action_input: Dict[str, Any], state: Any) -> str:
    """Show training data stats and pending corrections."""
    from app.agent.training import get_training_collector
    collector = get_training_collector()
    stats = collector.get_stats()
    
    output = "═══ 🎓 TRAINING DATA STATS ═══\n\n"
    output += f"Total examples: {stats['total']}\n"
    output += f"  ✓ Successes: {stats['successes']}\n"
    output += f"  ✗ Failures: {stats['failures']}\n"
    output += f"  📝 Pending corrections: {stats['pending_corrections']}\n"
    output += f"  ✅ Corrected: {stats['corrected']}\n"
    
    pending = collector.get_pending_corrections()
    if pending:
        output += "\n═══ PENDING CORRECTIONS ═══\n"
        for ex in pending[:10]:
            output += f"\n[{ex.id}] {ex.action_taken} → {ex.result}\n"
            output += f"   Query: {ex.query[:50]}...\n"
            output += f"   Observation: {ex.observation[:100]}...\n"
    
    return output


@register_handler("correct_action")
def handle_correct_action(action_input: Dict[str, Any], state: Any) -> str:
    """Correct a failed action for training."""
    example_id = action_input.get("id", "")
    correct_act = action_input.get("action", "")
    correct_inp = action_input.get("input", {})
    feedback = action_input.get("feedback", "")
    
    if not example_id or not correct_act:
        return 'Error: Provide "id" and "action". Example: correct_action with {"id": "abc123", "action": "vuln_scan_batch"}'
    
    from app.agent.training import get_training_collector
    collector = get_training_collector()
    
    success = collector.add_correction(example_id, correct_act, correct_inp, feedback)
    
    if success:
        return f"✅ Correction saved for [{example_id}]: {correct_act}"
    else:
        return f"❌ Example [{example_id}] not found. Use show_training to see available IDs."


@register_handler("export_training")
def handle_export_training(action_input: Dict[str, Any], state: Any) -> str:
    """Export training data for PyTorch fine-tuning."""
    include_successes = action_input.get("include_successes", False)
    
    from app.agent.training import get_training_collector
    collector = get_training_collector()
    
    export_path = collector.export_for_training(include_successes=include_successes)
    stats = collector.get_stats()
    
    output = f"═══ 🎓 TRAINING EXPORT ═══\n\n"
    output += f"Exported to: {export_path}\n"
    output += f"Corrected examples: {stats['corrected']}\n"
    output += f"\nUse this file for PyTorch fine-tuning:\n"
    output += f"  python scripts/train_snode.py --data {export_path}\n"
    
    return output
