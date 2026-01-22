"""Tool execution result analyzer - extracts findings and suggests next tools."""

from typing import Dict, Any, List, Optional
import re
import json
from models.generic_ollama_agent import GenericOllamaAgent


class ResultAnalyzer:
    """Analyzes tool execution results to extract findings and suggest next tools."""
    
    def __init__(self, model_name: str = "mistral:latest"):
        """Initialize result analyzer.
        
        Args:
            model_name: Model to use for intelligent analysis
        """
        self.analysis_model = GenericOllamaAgent(
            model_name=model_name,
            prompt_template="qwen3_system.jinja2"
        )
    
    def analyze_results(self, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze tool execution results to extract findings.
        
        Args:
            tool_results: List of tool execution results
            
        Returns:
            Analysis with findings and suggested next tools
        """
        findings = {
            "subdomains": [],
            "ips": [],
            "open_ports": [],
            "vulnerabilities": [],
            "technologies": [],
            "services": [],
            "domains": []
        }
        
        suggested_tools = []
        
        for result in tool_results:
            if not result.get("success"):
                continue
            
            tool_name = result.get("tool_name", "")
            results_data = result.get("results", {})
            
            # Extract findings based on tool type and results
            if isinstance(results_data, dict):
                # Subdomains
                if "subdomains" in results_data:
                    subdomains = results_data["subdomains"]
                    if isinstance(subdomains, list):
                        findings["subdomains"].extend(subdomains)
                
                # IPs
                if "ips" in results_data:
                    ips = results_data["ips"]
                    if isinstance(ips, list):
                        findings["ips"].extend(ips)
                
                # Open ports
                if "open_ports" in results_data:
                    ports = results_data["open_ports"]
                    if isinstance(ports, list):
                        findings["open_ports"].extend(ports)
                
                # Vulnerabilities
                if "vulnerabilities" in results_data:
                    vulns = results_data["vulnerabilities"]
                    if isinstance(vulns, list):
                        findings["vulnerabilities"].extend(vulns)
                
                # Technologies
                if "technologies" in results_data:
                    techs = results_data["technologies"]
                    if isinstance(techs, list):
                        findings["technologies"].extend(techs)
                
                # Services
                if "services" in results_data:
                    services = results_data["services"]
                    if isinstance(services, list):
                        findings["services"].extend(services)
            
            # Also parse raw output for common patterns
            raw_output = result.get("raw_output", "")
            if raw_output:
                self._parse_raw_output(raw_output, findings)
        
        # Deduplicate findings
        for key in findings:
            if isinstance(findings[key], list):
                findings[key] = list(set(findings[key]))
        
        # Suggest next tools based on findings
        suggested_tools = self._suggest_next_tools(findings)
        
        # Use AI model for intelligent analysis if available
        ai_analysis = self._analyze_with_ai(tool_results, findings)
        
        return {
            "findings": findings,
            "suggested_tools": suggested_tools,
            "summary": self._generate_summary(findings),
            "ai_insights": ai_analysis.get("insights", ""),
            "ai_recommendations": ai_analysis.get("recommendations", [])
        }
    
    def _analyze_with_ai(self, tool_results: List[Dict[str, Any]], findings: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI model to analyze tool results and provide insights.
        
        Args:
            tool_results: List of tool execution results
            findings: Extracted findings
            
        Returns:
            Dict with insights and recommendations
        """
        try:
            # Format tool results for analysis
            results_summary = []
            for result in tool_results[:5]:  # Limit to 5 results
                tool_name = result.get("tool_name", "unknown")
                success = result.get("success", False)
                results_data = result.get("results", {})
                
                summary = f"Tool: {tool_name}, Success: {success}"
                if isinstance(results_data, dict):
                    # Extract key information
                    key_info = []
                    for key in ["subdomains", "ips", "open_ports", "vulnerabilities", "services"]:
                        if key in results_data:
                            key_info.append(f"{key}: {results_data[key]}")
                    if key_info:
                        summary += f", Key findings: {', '.join(key_info)}"
                
                results_summary.append(summary)
            
            analysis_prompt = f"""Analyze the following security tool execution results and provide insights and recommendations.

Tool Results:
{chr(10).join(results_summary)}

Extracted Findings:
- Subdomains: {len(findings.get('subdomains', []))}
- IPs: {len(findings.get('ips', []))}
- Open Ports: {len(findings.get('open_ports', []))}
- Vulnerabilities: {len(findings.get('vulnerabilities', []))}
- Technologies: {len(findings.get('technologies', []))}
- Services: {len(findings.get('services', []))}

Provide:
1. Key insights from the results
2. Security recommendations
3. Suggested next steps

Format your response clearly with insights and recommendations."""
            
            result = self.analysis_model.analyze_and_breakdown(
                user_prompt=analysis_prompt,
                conversation_history=None
            )
            
            if result.get("success"):
                response = result.get("raw_response", "")
                return {
                    "insights": response,
                    "recommendations": self._extract_recommendations(response)
                }
        except Exception as e:
            # Fallback to basic analysis
            pass
        
        return {
            "insights": "",
            "recommendations": []
        }
    
    def _extract_recommendations(self, response: str) -> List[str]:
        """Extract actionable recommendations from AI response.
        
        Args:
            response: AI analysis response
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Look for numbered or bulleted recommendations
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            # Match patterns like "1. ...", "- ...", "* ...", "• ..."
            if re.match(r'^[\d\-\*•]\s+', line):
                recommendations.append(line)
            elif line.startswith("Recommendation:") or line.startswith("Next step:"):
                recommendations.append(line)
        
        return recommendations[:5]  # Limit to 5 recommendations
    
    def _parse_raw_output(self, raw_output: str, findings: Dict[str, Any]) -> None:
        """Parse raw output text for common patterns.
        
        Args:
            raw_output: Raw tool output text
            findings: Findings dictionary to update
        """
        # IP addresses
        ip_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        ips = re.findall(ip_pattern, raw_output)
        findings["ips"].extend(ips)
        
        # Domains/subdomains
        domain_pattern = r'\b([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
        domains = re.findall(domain_pattern, raw_output)
        findings["domains"].extend(domains)
        
        # Port numbers (common patterns)
        port_pattern = r'\b(\d{1,5})\/(?:tcp|udp|open)\b'
        ports = re.findall(port_pattern, raw_output.lower())
        findings["open_ports"].extend([int(p) for p in ports if p.isdigit()])
    
    def _suggest_next_tools(self, findings: Dict[str, Any]) -> List[str]:
        """Suggest next tools based on findings.
        
        Args:
            findings: Extracted findings
            
        Returns:
            List of suggested tool names
        """
        suggestions = []
        
        # If we found subdomains but haven't scanned them
        if findings["subdomains"] and not findings["open_ports"]:
            suggestions.append("ps")  # Port scanner (renamed from nmap)
            suggestions.append("httpx")  # HTTP probe
        
        # If we found open ports but haven't done service detection
        if findings["open_ports"] and not findings["services"]:
            suggestions.append("ps")  # Service detection
        
        # If we found services but haven't done vulnerability scanning
        if findings["services"] and not findings["vulnerabilities"]:
            suggestions.append("vuln_scanner")
            suggestions.append("nikto")
        
        # If we found technologies but haven't done CVE lookup
        if findings["technologies"] and not findings["vulnerabilities"]:
            suggestions.append("cve_lookup")
        
        # If we found IPs but haven't done whois
        if findings["ips"] and not findings.get("whois_done"):
            suggestions.append("whois")
        
        # Always suggest web search for OSINT if we have targets
        if findings["subdomains"] or findings["domains"]:
            suggestions.append("web_search")
        
        return list(set(suggestions))  # Deduplicate
    
    def _generate_summary(self, findings: Dict[str, Any]) -> str:
        """Generate human-readable summary of findings.
        
        Args:
            findings: Extracted findings
            
        Returns:
            Summary string
        """
        summary_parts = []
        
        if findings["subdomains"]:
            summary_parts.append(f"Found {len(findings['subdomains'])} subdomain(s)")
        
        if findings["ips"]:
            summary_parts.append(f"Found {len(findings['ips'])} IP address(es)")
        
        if findings["open_ports"]:
            summary_parts.append(f"Found {len(findings['open_ports'])} open port(s)")
        
        if findings["vulnerabilities"]:
            summary_parts.append(f"Found {len(findings['vulnerabilities'])} vulnerability/vulnerabilities")
        
        if findings["technologies"]:
            summary_parts.append(f"Detected {len(findings['technologies'])} technology/technologies")
        
        if not summary_parts:
            return "No significant findings extracted from tool results."
        
        return ". ".join(summary_parts) + "."
    
    def get_next_subtasks(self, 
                         findings: Dict[str, Any],
                         suggested_tools: List[str]) -> List[Dict[str, Any]]:
        """Generate next subtasks based on findings and suggested tools.
        
        Args:
            findings: Extracted findings
            suggested_tools: List of suggested tool names
            
        Returns:
            List of subtask dictionaries
        """
        subtasks = []
        
        for i, tool_name in enumerate(suggested_tools[:5]):  # Limit to 5 tools
            subtask = {
                "id": f"subtask_followup_{tool_name}_{i}",
                "name": f"Execute {tool_name}",
                "description": f"Execute {tool_name} based on previous findings",
                "type": "tool_execution",
                "required_tools": [tool_name],
                "required_agent": "recon_agent",
                "priority": "medium"
            }
            
            # Add context from findings
            if findings["subdomains"]:
                subtask["description"] += f" on discovered subdomains"
            elif findings["ips"]:
                subtask["description"] += f" on discovered IPs"
            elif findings["open_ports"]:
                subtask["description"] += f" on open ports"
            
            subtasks.append(subtask)
        
        return subtasks
