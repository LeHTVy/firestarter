"""
Network Tool Handlers
=====================

Handles: netcat, tcpdump, enum4linux, nbtscan, smbclient
"""
from typing import Dict, Any
from app.tools.handlers import register_handler
import subprocess


@register_handler("netcat")
def handle_netcat(action_input: Dict[str, Any], state: Any) -> str:
    """Netcat network utility."""
    target = action_input.get("target", "")
    port = action_input.get("port", "")
    listen = action_input.get("listen", False)
    
    if listen:
        return f"""To start netcat listener:
  nc -lvnp {port or 4444}
  
Note: Listeners must be run interactively, not through SNODE."""
    
    if not target or not port:
        return """Error: target and port required. Examples:
  netcat with {"target": "192.168.1.1", "port": "80"}
  netcat with {"listen": true, "port": "4444"}"""
    
    print(f"  🔌 Connecting to {target}:{port}...")
    
    try:
        result = subprocess.run(
            ["nc", "-zv", "-w", "3", target, str(port)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if "open" in result.stderr.lower() or "succeeded" in result.stderr.lower():
            return f"✅ Port {port} is OPEN on {target}"
        else:
            return f"❌ Port {port} is CLOSED on {target}\n{result.stderr}"
            
    except FileNotFoundError:
        return "⚠️ netcat not installed. Install: sudo apt install netcat-openbsd"
    except subprocess.TimeoutExpired:
        return f"Connection to {target}:{port} timed out"
    except Exception as e:
        return f"Netcat error: {e}"


@register_handler("enum4linux")
def handle_enum4linux(action_input: Dict[str, Any], state: Any) -> str:
    """Enumerate SMB/Windows info."""
    target = action_input.get("target", "")
    
    if not target:
        return "Error: target is required. Example: enum4linux with {\"target\": \"192.168.1.1\"}"
    
    print(f"  🔍 Enumerating {target} with enum4linux...")
    
    try:
        result = subprocess.run(
            ["enum4linux", "-a", target],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        return f"═══ ENUM4LINUX: {target} ═══\n{result.stdout[:5000]}"
        
    except FileNotFoundError:
        return "⚠️ enum4linux not installed. Install: sudo apt install enum4linux"
    except subprocess.TimeoutExpired:
        return "enum4linux timed out"
    except Exception as e:
        return f"enum4linux error: {e}"


@register_handler("nbtscan")
def handle_nbtscan(action_input: Dict[str, Any], state: Any) -> str:
    """Scan for NetBIOS names."""
    target = action_input.get("target", "")
    
    if not target:
        return "Error: target is required. Example: nbtscan with {\"target\": \"192.168.1.0/24\"}"
    
    print(f"  🔍 NBTScan on {target}...")
    
    try:
        result = subprocess.run(
            ["nbtscan", target],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        return f"═══ NBTSCAN: {target} ═══\n{result.stdout}"
        
    except FileNotFoundError:
        return "⚠️ nbtscan not installed. Install: sudo apt install nbtscan"
    except subprocess.TimeoutExpired:
        return "nbtscan timed out"
    except Exception as e:
        return f"nbtscan error: {e}"


@register_handler("smbclient")
def handle_smbclient(action_input: Dict[str, Any], state: Any) -> str:
    """List SMB shares."""
    target = action_input.get("target", "")
    user = action_input.get("user", "")
    password = action_input.get("password", "")
    share = action_input.get("share", "")
    
    if not target:
        return """Error: target is required. Examples:
  smbclient with {"target": "192.168.1.1"}
  smbclient with {"target": "192.168.1.1", "user": "admin", "password": "pass"}"""
    
    print(f"  📁 Listing SMB shares on {target}...")
    
    try:
        if share:
            # Access specific share
            cmd = ["smbclient", f"//{target}/{share}"]
        else:
            # List shares
            cmd = ["smbclient", "-L", target]
        
        if user and password:
            cmd.extend(["-U", f"{user}%{password}"])
        else:
            cmd.extend(["-N"])  # No password
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        return f"═══ SMBCLIENT: {target} ═══\n{result.stdout}\n{result.stderr}"
        
    except FileNotFoundError:
        return "⚠️ smbclient not installed. Install: sudo apt install smbclient"
    except subprocess.TimeoutExpired:
        return "smbclient timed out"
    except Exception as e:
        return f"smbclient error: {e}"


@register_handler("tcpdump")
def handle_tcpdump(action_input: Dict[str, Any], state: Any) -> str:
    """Capture network traffic (brief)."""
    interface = action_input.get("interface", "any")
    filter_expr = action_input.get("filter", "")
    count = action_input.get("count", 10)
    
    print(f"  📡 Capturing {count} packets on {interface}...")
    
    try:
        cmd = ["tcpdump", "-i", interface, "-c", str(count), "-nn"]
        if filter_expr:
            cmd.append(filter_expr)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        return f"═══ TCPDUMP ═══\n{result.stdout}"
        
    except FileNotFoundError:
        return "⚠️ tcpdump not installed. Install: sudo apt install tcpdump"
    except subprocess.TimeoutExpired:
        return "tcpdump capture timeout"
    except PermissionError:
        return "⚠️ tcpdump requires root. Run: sudo tcpdump -i any -c 10"
    except Exception as e:
        return f"tcpdump error: {e}"
