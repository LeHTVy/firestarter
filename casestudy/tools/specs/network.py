"""
Network Tools Specifications
============================

Network analysis, packet capture, and exploitation.
"""
from typing import List
from app.tools.registry import ToolSpec, ToolCategory, CommandTemplate


def get_specs() -> List[ToolSpec]:
    """Get network tool specifications."""
    return [
        # ─────────────────────────────────────────────────────────
        # NETCAT - Network Swiss Army Knife
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="nc",
            category=ToolCategory.UTIL,
            description="Netcat - read/write network connections",
            executable_names=["nc", "netcat", "ncat"],
            install_hint="apt install netcat-openbsd",
            commands={
                "connect": CommandTemplate(
                    args=["-v", "{host}", "{port}"],
                    timeout=30,
                    success_codes=[0, 1]
                ),
                "listen": CommandTemplate(
                    args=["-lvnp", "{port}"],
                    timeout=3600,  # 1 hour listener
                    success_codes=[0, 1]
                ),
                "scan": CommandTemplate(
                    args=["-zv", "{host}", "{port_range}"],
                    timeout=60,
                    success_codes=[0, 1]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # RESPONDER - LLMNR/NBT-NS Poisoner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="responder",
            category=ToolCategory.EXPLOIT,
            description="LLMNR, NBT-NS and MDNS poisoner",
            executable_names=["responder", "Responder.py"],
            install_hint="apt install responder",
            commands={
                "analyze": CommandTemplate(
                    args=["-I", "{interface}", "-A"],
                    timeout=300,
                    requires_sudo=True,
                    success_codes=[0]
                ),
                "poison": CommandTemplate(
                    args=["-I", "{interface}", "-wFb"],
                    timeout=3600,
                    requires_sudo=True,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # TCPDUMP - Packet Capture
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="tcpdump",
            category=ToolCategory.UTIL,
            description="Network packet analyzer",
            executable_names=["tcpdump"],
            install_hint="apt install tcpdump",
            commands={
                "capture": CommandTemplate(
                    args=["-i", "{interface}", "-c", "{count}", "-w", "{output}"],
                    timeout=300,
                    requires_sudo=True,
                    success_codes=[0]
                ),
                "read": CommandTemplate(
                    args=["-r", "{file}", "-n"],
                    timeout=60,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # ENUM4LINUX - SMB/Samba Enumeration
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="enum4linux",
            category=ToolCategory.ENUM,
            description="Windows/Samba enumeration tool",
            executable_names=["enum4linux", "enum4linux-ng"],
            install_hint="apt install enum4linux",
            commands={
                "all": CommandTemplate(
                    args=["-a", "{target}"],
                    timeout=300,
                    success_codes=[0]
                ),
                "users": CommandTemplate(
                    args=["-U", "{target}"],
                    timeout=120,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # NBTSTAT/NBTSCAN - NetBIOS Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="nbtscan",
            category=ToolCategory.SCANNING,
            description="NetBIOS name scanner",
            executable_names=["nbtscan"],
            install_hint="apt install nbtscan",
            commands={
                "scan": CommandTemplate(
                    args=["-r", "{target}"],
                    timeout=120,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # SMBCLIENT - SMB Client
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="smbclient",
            category=ToolCategory.UTIL,
            description="SMB/CIFS client for Windows shares",
            executable_names=["smbclient"],
            install_hint="apt install smbclient",
            commands={
                "list": CommandTemplate(
                    args=["-L", "//{target}", "-N"],
                    timeout=60,
                    success_codes=[0, 1]
                ),
                "connect": CommandTemplate(
                    args=["//{target}/{share}", "-U", "{user}%{password}"],
                    timeout=60,
                    success_codes=[0, 1]
                ),
            }
        ),
    ]
