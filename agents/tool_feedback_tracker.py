"""Tool execution feedback tracker for learning and improvement."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict
import json


class ToolFeedbackTracker:
    """Tracks tool execution feedback for learning and improvement."""
    
    def __init__(self):
        """Initialize feedback tracker."""
        self.feedback_history: List[Dict[str, Any]] = []
        self.tool_metrics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_execution_time": 0.0,
            "error_types": defaultdict(int),
            "success_rate": 0.0,
            "avg_execution_time": 0.0
        })
    
    def record_execution(self, 
                        tool_name: str,
                        success: bool,
                        execution_time: float,
                        error: Optional[str] = None,
                        parameters: Optional[Dict[str, Any]] = None,
                        results: Optional[Any] = None,
                        agent: Optional[str] = None,
                        session_id: Optional[str] = None) -> None:
        """Record a tool execution for feedback tracking.
        
        Args:
            tool_name: Name of the tool executed
            success: Whether execution was successful
            execution_time: Execution time in seconds
            error: Error message if failed
            parameters: Tool parameters used
            results: Execution results
            agent: Agent that executed the tool
            session_id: Session identifier
        """
        feedback_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "tool_name": tool_name,
            "success": success,
            "execution_time": execution_time,
            "error": error,
            "parameters": parameters,
            "agent": agent,
            "session_id": session_id,
            "has_results": results is not None
        }
        
        self.feedback_history.append(feedback_entry)
        
        # Update metrics
        metrics = self.tool_metrics[tool_name]
        metrics["total_executions"] += 1
        
        if success:
            metrics["successful_executions"] += 1
        else:
            metrics["failed_executions"] += 1
            if error:
                error_type = self._categorize_error(error)
                metrics["error_types"][error_type] += 1
        
        metrics["total_execution_time"] += execution_time
        metrics["success_rate"] = metrics["successful_executions"] / metrics["total_executions"]
        metrics["avg_execution_time"] = metrics["total_execution_time"] / metrics["total_executions"]
    
    def _categorize_error(self, error: str) -> str:
        """Categorize error type.
        
        Args:
            error: Error message
            
        Returns:
            Error category
        """
        error_lower = error.lower()
        
        if "not found" in error_lower or "does not exist" in error_lower:
            return "tool_not_found"
        elif "permission" in error_lower or "unauthorized" in error_lower:
            return "permission_denied"
        elif "timeout" in error_lower:
            return "timeout"
        elif "invalid" in error_lower or "validation" in error_lower:
            return "invalid_parameters"
        elif "no implementation" in error_lower:
            return "no_implementation"
        else:
            return "other"
    
    def get_tool_metrics(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for a specific tool or all tools.
        
        Args:
            tool_name: Tool name (None for all tools)
            
        Returns:
            Metrics dictionary
        """
        if tool_name:
            return self.tool_metrics.get(tool_name, {})
        else:
            return dict(self.tool_metrics)
    
    def get_best_tools_for_scenario(self, 
                                    scenario_type: str,
                                    limit: int = 5) -> List[Dict[str, Any]]:
        """Get best performing tools for a scenario type.
        
        Args:
            scenario_type: Scenario type (e.g., "recon", "scanning", "exploitation")
            limit: Maximum number of tools to return
            
        Returns:
            List of tool metrics sorted by success rate
        """
        # Filter tools by scenario type (would need tool metadata)
        # For now, return all tools sorted by success rate
        sorted_tools = sorted(
            self.tool_metrics.items(),
            key=lambda x: (x[1]["success_rate"], -x[1]["avg_execution_time"]),
            reverse=True
        )
        
        return [
            {"tool_name": name, **metrics}
            for name, metrics in sorted_tools[:limit]
        ]
    
    def get_feedback_dataset(self, 
                             tool_name: Optional[str] = None,
                             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get feedback dataset for training/learning.
        
        Args:
            tool_name: Filter by tool name (None for all)
            limit: Maximum number of entries
            
        Returns:
            List of feedback entries
        """
        dataset = self.feedback_history
        
        if tool_name:
            dataset = [entry for entry in dataset if entry["tool_name"] == tool_name]
        
        if limit:
            dataset = dataset[-limit:]  # Most recent entries
        
        return dataset
    
    def export_feedback(self, filepath: str) -> None:
        """Export feedback data to JSON file.
        
        Args:
            filepath: Path to output file
        """
        export_data = {
            "feedback_history": self.feedback_history,
            "tool_metrics": dict(self.tool_metrics),
            "export_timestamp": datetime.utcnow().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
    
    def load_feedback(self, filepath: str) -> None:
        """Load feedback data from JSON file.
        
        Args:
            filepath: Path to input file
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.feedback_history = data.get("feedback_history", [])
        
        # Reconstruct metrics from history
        self.tool_metrics.clear()
        for entry in self.feedback_history:
            tool_name = entry["tool_name"]
            metrics = self.tool_metrics[tool_name]
            metrics["total_executions"] += 1
            
            if entry["success"]:
                metrics["successful_executions"] += 1
            else:
                metrics["failed_executions"] += 1
                if entry.get("error"):
                    error_type = self._categorize_error(entry["error"])
                    metrics["error_types"][error_type] += 1
            
            metrics["total_execution_time"] += entry["execution_time"]
            metrics["success_rate"] = metrics["successful_executions"] / metrics["total_executions"]
            metrics["avg_execution_time"] = metrics["total_execution_time"] / metrics["total_executions"]
