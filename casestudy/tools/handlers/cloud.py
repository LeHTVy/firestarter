"""
Cloud & Container Tool Handlers
===============================

Handles: trufflehog, gitleaks, trivy, docker
"""
from typing import Dict, Any
from app.tools.handlers import register_handler
import subprocess


@register_handler("trufflehog")
def handle_trufflehog(action_input: Dict[str, Any], state: Any) -> str:
    """Scan for secrets in git repos."""
    repo = action_input.get("repo", action_input.get("target", ""))
    
    if not repo:
        return """Error: repo required. Examples:
  trufflehog with {"repo": "https://github.com/user/repo"}
  trufflehog with {"repo": "/path/to/local/repo"}"""
    
    print(f"  🔑 Scanning {repo} for secrets...")
    
    try:
        if repo.startswith("http"):
            cmd = ["trufflehog", "git", repo, "--json"]
        else:
            cmd = ["trufflehog", "filesystem", repo, "--json"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        output = f"═══ TRUFFLEHOG: {repo} ═══\n"
        
        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            output += f"🚨 Found {len(lines)} potential secrets!\n\n"
            output += result.stdout[:3000]
        else:
            output += "No secrets found."
        
        return output
        
    except FileNotFoundError:
        return "⚠️ trufflehog not installed. Install: pip install trufflehog OR brew install trufflehog"
    except subprocess.TimeoutExpired:
        return "trufflehog timed out"
    except Exception as e:
        return f"trufflehog error: {e}"


@register_handler("gitleaks")
def handle_gitleaks(action_input: Dict[str, Any], state: Any) -> str:
    """Scan for secrets with gitleaks."""
    path = action_input.get("path", action_input.get("repo", "."))
    
    print(f"  🔑 Gitleaks scanning {path}...")
    
    try:
        result = subprocess.run(
            ["gitleaks", "detect", "--source", path, "-v"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        output = f"═══ GITLEAKS ═══\n{result.stdout}\n"
        if result.stderr:
            output += result.stderr[:1000]
        
        return output
        
    except FileNotFoundError:
        return "⚠️ gitleaks not installed. Install: brew install gitleaks OR go install github.com/gitleaks/gitleaks/v8@latest"
    except subprocess.TimeoutExpired:
        return "gitleaks timed out"
    except Exception as e:
        return f"gitleaks error: {e}"


@register_handler("trivy")
def handle_trivy(action_input: Dict[str, Any], state: Any) -> str:
    """Scan containers/images for vulnerabilities."""
    image = action_input.get("image", "")
    path = action_input.get("path", "")
    
    if not image and not path:
        return """Error: image or path required. Examples:
  trivy with {"image": "nginx:latest"}
  trivy with {"path": "/path/to/project"}"""
    
    try:
        if image:
            print(f"  🔍 Trivy scanning image: {image}...")
            result = subprocess.run(
                ["trivy", "image", "--severity", "HIGH,CRITICAL", image],
                capture_output=True,
                text=True,
                timeout=300
            )
        else:
            print(f"  🔍 Trivy scanning filesystem: {path}...")
            result = subprocess.run(
                ["trivy", "fs", "--severity", "HIGH,CRITICAL", path],
                capture_output=True,
                text=True,
                timeout=300
            )
        
        return f"═══ TRIVY ═══\n{result.stdout[:4000]}"
        
    except FileNotFoundError:
        return "⚠️ trivy not installed. Install: sudo apt install trivy OR brew install trivy"
    except subprocess.TimeoutExpired:
        return "trivy timed out"
    except Exception as e:
        return f"trivy error: {e}"


@register_handler("docker_scan")
def handle_docker_scan(action_input: Dict[str, Any], state: Any) -> str:
    """Scan docker containers."""
    action = action_input.get("action", "ps")
    image = action_input.get("image", "")
    
    try:
        if action == "ps":
            print("  🐳 Listing Docker containers...")
            result = subprocess.run(["docker", "ps", "-a"], capture_output=True, text=True, timeout=30)
        elif action == "images":
            print("  🐳 Listing Docker images...")
            result = subprocess.run(["docker", "images"], capture_output=True, text=True, timeout=30)
        elif action == "inspect" and image:
            print(f"  🐳 Inspecting {image}...")
            result = subprocess.run(["docker", "inspect", image], capture_output=True, text=True, timeout=30)
        else:
            return """Examples:
  docker_scan with {"action": "ps"}
  docker_scan with {"action": "images"}
  docker_scan with {"action": "inspect", "image": "nginx"}"""
        
        return f"═══ DOCKER ═══\n{result.stdout}"
        
    except FileNotFoundError:
        return "⚠️ docker not installed"
    except Exception as e:
        return f"docker error: {e}"
