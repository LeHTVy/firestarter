"""
Cloud and Container Tools Specifications
=========================================

Cloud security, container scanning, and secrets detection.
"""
from typing import List
from app.tools.registry import ToolSpec, ToolCategory, CommandTemplate


def get_specs() -> List[ToolSpec]:
    """Get cloud/container tool specifications."""
    return [
        # ─────────────────────────────────────────────────────────
        # TRUFFLEHOG - Secrets Detection
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="trufflehog",
            category=ToolCategory.RECON,
            description="Find leaked credentials in git repos",
            executable_names=["trufflehog"],
            install_hint="pip install trufflehog OR brew install trufflehog",
            commands={
                "git": CommandTemplate(
                    args=["git", "{repo_url}", "--only-verified"],
                    timeout=600,
                    success_codes=[0]
                ),
                "github": CommandTemplate(
                    args=["github", "--org={org}", "--only-verified"],
                    timeout=900,
                    success_codes=[0]
                ),
                "filesystem": CommandTemplate(
                    args=["filesystem", "{path}"],
                    timeout=300,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # GITLEAKS - Git Secrets Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="gitleaks",
            category=ToolCategory.RECON,
            description="Scan git repos for secrets and keys",
            executable_names=["gitleaks"],
            install_hint="brew install gitleaks OR go install github.com/gitleaks/gitleaks/v8@latest",
            commands={
                "detect": CommandTemplate(
                    args=["detect", "--source", "{path}", "-v"],
                    timeout=600,
                    success_codes=[0, 1]
                ),
                "protect": CommandTemplate(
                    args=["protect", "--source", "{path}", "-v"],
                    timeout=300,
                    success_codes=[0, 1]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # TRIVY - Container Vulnerability Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="trivy",
            category=ToolCategory.VULN,
            description="Vulnerability scanner for containers and IaC",
            executable_names=["trivy"],
            install_hint="apt install trivy OR brew install trivy",
            commands={
                "image": CommandTemplate(
                    args=["image", "{image}"],
                    timeout=300,
                    success_codes=[0]
                ),
                "fs": CommandTemplate(
                    args=["fs", "{path}"],
                    timeout=300,
                    success_codes=[0]
                ),
                "repo": CommandTemplate(
                    args=["repo", "{repo_url}"],
                    timeout=600,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # PROWLER - AWS Security Auditor
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="prowler",
            category=ToolCategory.VULN,
            description="AWS Security best practices checker",
            executable_names=["prowler"],
            install_hint="pip install prowler",
            commands={
                "aws": CommandTemplate(
                    args=["-M", "text"],
                    timeout=1800,  # 30 min
                    success_codes=[0]
                ),
                "aws_service": CommandTemplate(
                    args=["-S", "{service}", "-M", "text"],
                    timeout=600,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # SCOUT SUITE - Multi-Cloud Security Auditing
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="scout",
            category=ToolCategory.VULN,
            description="Multi-cloud security auditing tool",
            executable_names=["scout"],
            install_hint="pip install scoutsuite",
            commands={
                "aws": CommandTemplate(
                    args=["aws", "--no-browser"],
                    timeout=1800,
                    success_codes=[0]
                ),
                "azure": CommandTemplate(
                    args=["azure", "--no-browser"],
                    timeout=1800,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # DOCKER - Container Management
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="docker",
            category=ToolCategory.UTIL,
            description="Container runtime and management",
            executable_names=["docker"],
            install_hint="apt install docker.io",
            commands={
                "ps": CommandTemplate(
                    args=["ps", "-a"],
                    timeout=30,
                    success_codes=[0]
                ),
                "images": CommandTemplate(
                    args=["images"],
                    timeout=30,
                    success_codes=[0]
                ),
                "inspect": CommandTemplate(
                    args=["inspect", "{container}"],
                    timeout=30,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # KUBECTL - Kubernetes CLI
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="kubectl",
            category=ToolCategory.UTIL,
            description="Kubernetes command-line tool",
            executable_names=["kubectl"],
            install_hint="snap install kubectl --classic",
            commands={
                "get_pods": CommandTemplate(
                    args=["get", "pods", "-A"],
                    timeout=60,
                    success_codes=[0]
                ),
                "get_secrets": CommandTemplate(
                    args=["get", "secrets", "-A"],
                    timeout=60,
                    success_codes=[0]
                ),
                "describe": CommandTemplate(
                    args=["describe", "{resource}", "{name}"],
                    timeout=60,
                    success_codes=[0]
                ),
            }
        ),
    ]
