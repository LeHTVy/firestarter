"""
Brute-Force Tool Handlers
=========================

Handles: hydra, medusa, john, hashcat, crackmapexec
"""
from typing import Dict, Any
from app.tools.handlers import register_handler
import subprocess


@register_handler("hydra")
def handle_hydra(action_input: Dict[str, Any], state: Any) -> str:
    """Hydra network login cracker."""
    target = action_input.get("target", "")
    user = action_input.get("user", action_input.get("username", ""))
    wordlist = action_input.get("wordlist", "/usr/share/wordlists/rockyou.txt")
    service = action_input.get("service", "ssh")
    
    if not target:
        return """Error: target is required. Examples:
  hydra with {"target": "192.168.1.1", "user": "admin", "service": "ssh"}
  hydra with {"target": "192.168.1.1", "user": "root", "service": "ftp"}
  hydra with {"target": "192.168.1.1", "user": "admin", "service": "rdp"}
  
Supported services: ssh, ftp, rdp, smb, http-get, http-post-form"""
    
    if not user:
        return "Error: user/username is required"
    
    print(f"  🔓 Hydra attacking {service}://{target} as {user}...")
    
    try:
        cmd = ["hydra", "-l", user, "-P", wordlist, "-t", "4", "-V", f"{service}://{target}"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        output = f"═══ HYDRA: {service}://{target} ═══\n"
        
        # Check for success
        if "login:" in result.stdout.lower() or "password:" in result.stdout.lower():
            output += "🎉 CREDENTIALS FOUND!\n\n"
        else:
            output += "No valid credentials found.\n\n"
        
        output += result.stdout[:2000]
        return output
        
    except FileNotFoundError:
        return "⚠️ hydra not installed. Install: sudo apt install hydra"
    except subprocess.TimeoutExpired:
        return "Hydra timed out (10 min limit)"
    except Exception as e:
        return f"Hydra error: {e}"


@register_handler("john")
def handle_john(action_input: Dict[str, Any], state: Any) -> str:
    """John the Ripper password cracker."""
    hashfile = action_input.get("hashfile", "")
    wordlist = action_input.get("wordlist", "/usr/share/wordlists/rockyou.txt")
    format_type = action_input.get("format", "")
    show = action_input.get("show", False)
    
    if not hashfile:
        return """Error: hashfile is required. Examples:
  john with {"hashfile": "/tmp/hashes.txt"}
  john with {"hashfile": "/tmp/hashes.txt", "format": "md5crypt"}
  john with {"hashfile": "/tmp/hashes.txt", "show": true}
  
Common formats: md5crypt, sha512crypt, bcrypt, ntlm, raw-md5, raw-sha1"""
    
    print(f"  🔓 John cracking {hashfile}...")
    
    try:
        if show:
            cmd = ["john", "--show", hashfile]
        elif format_type:
            cmd = ["john", f"--format={format_type}", f"--wordlist={wordlist}", hashfile]
        else:
            cmd = ["john", f"--wordlist={wordlist}", hashfile]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        
        output = f"═══ JOHN THE RIPPER ═══\n{result.stdout}\n"
        if result.stderr:
            output += f"Info: {result.stderr[:500]}"
        
        return output
        
    except FileNotFoundError:
        return "⚠️ john not installed. Install: sudo apt install john"
    except subprocess.TimeoutExpired:
        return "John timed out (30 min limit)"
    except Exception as e:
        return f"John error: {e}"


@register_handler("hashcat")
def handle_hashcat(action_input: Dict[str, Any], state: Any) -> str:
    """Hashcat GPU password cracker."""
    hashfile = action_input.get("hashfile", "")
    wordlist = action_input.get("wordlist", "/usr/share/wordlists/rockyou.txt")
    mode = action_input.get("mode", "0")  # 0=MD5, 1000=NTLM, 1800=sha512crypt
    
    if not hashfile:
        return """Error: hashfile is required. Examples:
  hashcat with {"hashfile": "/tmp/hashes.txt", "mode": "0"}
  hashcat with {"hashfile": "/tmp/hashes.txt", "mode": "1000"}
  
Common modes:
  0     = MD5
  100   = SHA1
  1000  = NTLM
  1800  = sha512crypt
  3200  = bcrypt
  22000 = WPA-PBKDF2-PMKID+EAPOL"""
    
    print(f"  🔥 Hashcat cracking (mode {mode})...")
    
    try:
        cmd = ["hashcat", "-m", str(mode), "-a", "0", hashfile, wordlist, "--force"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        
        return f"═══ HASHCAT ═══\n{result.stdout[:3000]}"
        
    except FileNotFoundError:
        return "⚠️ hashcat not installed. Install: sudo apt install hashcat"
    except subprocess.TimeoutExpired:
        return "Hashcat timed out (60 min limit)"
    except Exception as e:
        return f"Hashcat error: {e}"


@register_handler("crackmapexec")
def handle_crackmapexec(action_input: Dict[str, Any], state: Any) -> str:
    """CrackMapExec for AD/SMB attacks."""
    target = action_input.get("target", "")
    user = action_input.get("user", "")
    password = action_input.get("password", "")
    protocol = action_input.get("protocol", "smb")
    action = action_input.get("action", "shares")  # shares, users, groups, sessions
    
    if not target:
        return """Error: target is required. Examples:
  crackmapexec with {"target": "192.168.1.1", "action": "shares"}
  crackmapexec with {"target": "192.168.1.1", "user": "admin", "password": "pass123"}
  crackmapexec with {"target": "192.168.1.0/24", "protocol": "smb"}
  
Actions: shares, users, groups, sessions, disks, loggedon-users"""
    
    print(f"  🔓 CrackMapExec {protocol}://{target}...")
    
    try:
        cmd = ["crackmapexec", protocol, target]
        
        if user and password:
            cmd.extend(["-u", user, "-p", password])
        
        if action == "shares":
            cmd.append("--shares")
        elif action == "users":
            cmd.append("--users")
        elif action == "groups":
            cmd.append("--groups")
        elif action == "sessions":
            cmd.append("--sessions")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        return f"═══ CRACKMAPEXEC ═══\n{result.stdout}\n{result.stderr}"
        
    except FileNotFoundError:
        return "⚠️ crackmapexec not installed. Install: sudo apt install crackmapexec OR pipx install crackmapexec"
    except subprocess.TimeoutExpired:
        return "CrackMapExec timed out"
    except Exception as e:
        return f"CrackMapExec error: {e}"


@register_handler("medusa")
def handle_medusa(action_input: Dict[str, Any], state: Any) -> str:
    """Medusa parallel password cracker."""
    target = action_input.get("target", "")
    user = action_input.get("user", "")
    wordlist = action_input.get("wordlist", "/usr/share/wordlists/rockyou.txt")
    module = action_input.get("module", "ssh")
    
    if not target or not user:
        return """Error: target and user required. Examples:
  medusa with {"target": "192.168.1.1", "user": "admin", "module": "ssh"}
  medusa with {"target": "192.168.1.1", "user": "admin", "module": "ftp"}"""
    
    print(f"  🔓 Medusa attacking {module}://{target}...")
    
    try:
        cmd = ["medusa", "-h", target, "-u", user, "-P", wordlist, "-M", module]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        return f"═══ MEDUSA ═══\n{result.stdout[:3000]}"
        
    except FileNotFoundError:
        return "⚠️ medusa not installed. Install: sudo apt install medusa"
    except subprocess.TimeoutExpired:
        return "Medusa timed out"
    except Exception as e:
        return f"Medusa error: {e}"
