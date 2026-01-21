"""Feedback learner for environment-coupled learning."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from agents.tool_feedback_tracker import ToolFeedbackTracker
import json


class FeedbackLearner:
    """Learns from tool execution feedback to improve model behavior."""
    
    def __init__(self, feedback_tracker: Optional[ToolFeedbackTracker] = None):
        """Initialize feedback learner.
        
        Args:
            feedback_tracker: Tool feedback tracker instance
        """
        self.feedback_tracker = feedback_tracker or ToolFeedbackTracker()
        self.learning_data: List[Dict[str, Any]] = []
    
    def collect_feedback(self, 
                        tool_name: str,
                        success: bool,
                        execution_time: float,
                        reasoning: Optional[str] = None,
                        prompt_variant: Optional[str] = None,
                        error: Optional[str] = None,
                        parameters: Optional[Dict[str, Any]] = None) -> None:
        """Collect feedback for learning.
        
        Args:
            tool_name: Tool name
            success: Whether execution was successful
            execution_time: Execution time
            reasoning: Model reasoning (if available)
            prompt_variant: Prompt variant used
            error: Error message if failed
            parameters: Tool parameters
        """
        learning_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "tool_name": tool_name,
            "success": success,
            "execution_time": execution_time,
            "reasoning": reasoning,
            "prompt_variant": prompt_variant,
            "error": error,
            "parameters": parameters,
            "reward": 1.0 if success else -0.5  # Simple reward signal
        }
        
        self.learning_data.append(learning_entry)
        self.feedback_tracker.record_execution(
            tool_name=tool_name,
            success=success,
            execution_time=execution_time,
            error=error,
            parameters=parameters
        )
    
    def analyze_patterns(self) -> Dict[str, Any]:
        """Analyze feedback patterns to identify improvements.
        
        Returns:
            Analysis with patterns and recommendations
        """
        patterns = {
            "high_success_tools": [],
            "low_success_tools": [],
            "fast_tools": [],
            "slow_tools": [],
            "common_errors": {},
            "prompt_effectiveness": {}
        }
        
        # Get tool metrics
        tool_metrics = self.feedback_tracker.get_tool_metrics()
        
        for tool_name, metrics in tool_metrics.items():
            success_rate = metrics.get("success_rate", 0.0)
            avg_time = metrics.get("avg_execution_time", 0.0)
            
            if success_rate >= 0.8:
                patterns["high_success_tools"].append({
                    "tool": tool_name,
                    "success_rate": success_rate,
                    "avg_time": avg_time
                })
            elif success_rate < 0.5:
                patterns["low_success_tools"].append({
                    "tool": tool_name,
                    "success_rate": success_rate,
                    "avg_time": avg_time
                })
            
            if avg_time < 5.0:
                patterns["fast_tools"].append({
                    "tool": tool_name,
                    "avg_time": avg_time
                })
            elif avg_time > 30.0:
                patterns["slow_tools"].append({
                    "tool": tool_name,
                    "avg_time": avg_time
                })
            
            # Common errors
            error_types = metrics.get("error_types", {})
            for error_type, count in error_types.items():
                if error_type not in patterns["common_errors"]:
                    patterns["common_errors"][error_type] = 0
                patterns["common_errors"][error_type] += count
        
        # Analyze prompt effectiveness (if prompt_variant tracked)
        prompt_stats = {}
        for entry in self.learning_data:
            variant = entry.get("prompt_variant")
            if variant:
                if variant not in prompt_stats:
                    prompt_stats[variant] = {"success": 0, "total": 0}
                prompt_stats[variant]["total"] += 1
                if entry["success"]:
                    prompt_stats[variant]["success"] += 1
        
        for variant, stats in prompt_stats.items():
            patterns["prompt_effectiveness"][variant] = stats["success"] / stats["total"]
        
        return patterns
    
    def get_recommendations(self) -> List[str]:
        """Get recommendations for improvement.
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        patterns = self.analyze_patterns()
        
        # Low success tools
        if patterns["low_success_tools"]:
            tools = [t["tool"] for t in patterns["low_success_tools"][:3]]
            recommendations.append(
                f"Consider improving prompts or parameters for: {', '.join(tools)} "
                f"(low success rate)"
            )
        
        # Common errors
        if patterns["common_errors"]:
            top_error = max(patterns["common_errors"].items(), key=lambda x: x[1])
            recommendations.append(
                f"Most common error type: {top_error[0]} ({top_error[1]} occurrences). "
                f"Consider adding error handling or parameter validation."
            )
        
        # Prompt effectiveness
        if patterns["prompt_effectiveness"]:
            best_prompt = max(patterns["prompt_effectiveness"].items(), key=lambda x: x[1])
            worst_prompt = min(patterns["prompt_effectiveness"].items(), key=lambda x: x[1])
            if best_prompt[1] > worst_prompt[1] + 0.2:  # Significant difference
                recommendations.append(
                    f"Prompt variant '{best_prompt[0]}' performs better than '{worst_prompt[0]}'. "
                    f"Consider using the better variant more frequently."
                )
        
        return recommendations
    
    def get_tool_selection_hints(self, scenario: str) -> List[str]:
        """Get tool selection hints based on learned patterns.
        
        Args:
            scenario: Scenario type (e.g., "recon", "scanning")
            
        Returns:
            List of recommended tool names
        """
        # Get best tools for scenario
        best_tools = self.feedback_tracker.get_best_tools_for_scenario(scenario, limit=5)
        return [t["tool_name"] for t in best_tools]
    
    def export_learning_data(self, filepath: str) -> None:
        """Export learning data for training.
        
        Args:
            filepath: Path to output file
        """
        export_data = {
            "learning_data": self.learning_data,
            "patterns": self.analyze_patterns(),
            "recommendations": self.get_recommendations(),
            "export_timestamp": datetime.utcnow().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
