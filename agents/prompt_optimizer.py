"""Prompt optimizer based on feedback and success metrics."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from agents.feedback_learner import FeedbackLearner
import json


class PromptOptimizer:
    """Optimizes prompts based on feedback and success metrics."""
    
    def __init__(self, feedback_learner: Optional[FeedbackLearner] = None):
        """Initialize prompt optimizer.
        
        Args:
            feedback_learner: Feedback learner instance
        """
        self.feedback_learner = feedback_learner or FeedbackLearner()
        self.prompt_variants: Dict[str, Dict[str, Any]] = {}
        self.variant_performance: Dict[str, Dict[str, float]] = {}
    
    def register_prompt_variant(self, 
                               variant_id: str,
                               prompt_text: str,
                               description: str = "") -> None:
        """Register a prompt variant for A/B testing.
        
        Args:
            variant_id: Unique identifier for variant
            prompt_text: Prompt text
            description: Description of variant
        """
        self.prompt_variants[variant_id] = {
            "prompt": prompt_text,
            "description": description,
            "created_at": datetime.utcnow().isoformat()
        }
        self.variant_performance[variant_id] = {
            "success_rate": 0.0,
            "total_uses": 0,
            "successful_uses": 0
        }
    
    def record_variant_usage(self, 
                            variant_id: str,
                            success: bool) -> None:
        """Record usage and success of a prompt variant.
        
        Args:
            variant_id: Variant identifier
            success: Whether it led to successful execution
        """
        if variant_id not in self.variant_performance:
            self.variant_performance[variant_id] = {
                "success_rate": 0.0,
                "total_uses": 0,
                "successful_uses": 0
            }
        
        perf = self.variant_performance[variant_id]
        perf["total_uses"] += 1
        if success:
            perf["successful_uses"] += 1
        perf["success_rate"] = perf["successful_uses"] / perf["total_uses"]
    
    def get_best_variant(self, context: Optional[str] = None) -> Optional[str]:
        """Get best performing prompt variant.
        
        Args:
            context: Optional context (e.g., "tool_execution", "analysis")
            
        Returns:
            Best variant ID or None
        """
        if not self.variant_performance:
            return None
        
        # Filter by context if needed (future enhancement)
        # For now, return overall best
        best_variant = max(
            self.variant_performance.items(),
            key=lambda x: (x[1]["success_rate"], x[1]["total_uses"]),
            default=None
        )
        
        if best_variant and best_variant[1]["total_uses"] >= 5:  # Minimum samples
            return best_variant[0]
        
        return None
    
    def analyze_prompt_effectiveness(self) -> Dict[str, Any]:
        """Analyze prompt effectiveness from feedback.
        
        Returns:
            Analysis with recommendations
        """
        patterns = self.feedback_learner.analyze_patterns()
        
        analysis = {
            "variant_performance": dict(self.variant_performance),
            "recommendations": [],
            "patterns": patterns
        }
        
        # Compare variants
        if len(self.variant_performance) > 1:
            sorted_variants = sorted(
                self.variant_performance.items(),
                key=lambda x: x[1]["success_rate"],
                reverse=True
            )
            
            best = sorted_variants[0]
            worst = sorted_variants[-1]
            
            if best[1]["total_uses"] >= 5 and worst[1]["total_uses"] >= 5:
                if best[1]["success_rate"] > worst[1]["success_rate"] + 0.1:  # 10% difference
                    analysis["recommendations"].append(
                        f"Variant '{best[0]}' outperforms '{worst[0]}' "
                        f"({best[1]['success_rate']:.1%} vs {worst[1]['success_rate']:.1%}). "
                        f"Consider using '{best[0]}' more frequently."
                    )
        
        # Add recommendations from feedback learner
        analysis["recommendations"].extend(self.feedback_learner.get_recommendations())
        
        return analysis
    
    def suggest_prompt_improvements(self, 
                                   current_prompt: str,
                                   context: str = "general") -> List[str]:
        """Suggest improvements to a prompt based on feedback.
        
        Args:
            current_prompt: Current prompt text
            context: Context (e.g., "tool_execution", "analysis")
            
        Returns:
            List of improvement suggestions
        """
        suggestions = []
        patterns = self.feedback_learner.analyze_patterns()
        
        # Check for common errors
        if patterns.get("common_errors"):
            top_error = max(patterns["common_errors"].items(), key=lambda x: x[1])
            if top_error[0] == "invalid_parameters":
                suggestions.append(
                    "Add more explicit parameter extraction examples in prompt. "
                    "Emphasize extracting ALL required parameters from context."
                )
            elif top_error[0] == "tool_not_found":
                suggestions.append(
                    "Ensure prompt clearly lists available tools. "
                    "Add examples of correct tool names."
                )
        
        # Check tool success rates
        low_success = patterns.get("low_success_tools", [])
        if low_success:
            tools = [t["tool"] for t in low_success[:3]]
            suggestions.append(
                f"For tools {', '.join(tools)}: Consider adding tool-specific examples "
                f"or clarifying parameter requirements in prompt."
            )
        
        # Check reasoning quality (if tracked)
        # This would require analyzing reasoning content (future enhancement)
        
        return suggestions
    
    def export_optimization_data(self, filepath: str) -> None:
        """Export optimization data for analysis.
        
        Args:
            filepath: Path to output file
        """
        export_data = {
            "prompt_variants": self.prompt_variants,
            "variant_performance": self.variant_performance,
            "effectiveness_analysis": self.analyze_prompt_effectiveness(),
            "export_timestamp": datetime.utcnow().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
