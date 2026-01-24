"""
Scanning Tools Specifications
=============================

Port scanners, HTTP probers, service detection.
"""
from typing import List
from app.tools.registry import ToolSpec, ToolCategory, CommandTemplate


def get_specs() -> List[ToolSpec]:
    """Get scanning tool specifications."""
    return [
        # ─────────────────────────────────────────────────────────
        # HTTPX - HTTP Probing
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="httpx",
            category=ToolCategory.SCANNING,
            description="Fast HTTP probing with tech detection",
            executable_names=["httpx"],
            install_hint="go install github.com/projectdiscovery/httpx/cmd/httpx@latest",
            commands={
                "probe": CommandTemplate(
                    args=["-u", "{target}", "-sc", "-title", "-td", "-silent"],
                    timeout=60,
                    success_codes=[0]
                ),
                "probe_list": CommandTemplate(
                    args=["-l", "{file}", "-sc", "-title", "-td", "-silent"],
                    timeout=300,
                    success_codes=[0]
                ),
                "tech_detect": CommandTemplate(
                    args=["-u", "{target}", "-td", "-json"],
                    timeout=60,
                    success_codes=[0],
                    output_format="json"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # NMAP - Port Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="nmap",
            category=ToolCategory.SCANNING,
            description="Network port scanner with service detection",
            executable_names=["nmap"],
            install_hint="apt install nmap",
            commands={
                # Basic scans
                "quick_scan": CommandTemplate(
                    args=["-v", "-F", "{target}"],
                    timeout=120,
                    success_codes=[0]
                ),
                "syn_scan": CommandTemplate(
                    # -sS: TCP SYN scan (stealth, requires root)
                    args=["-v", "-sS", "-p", "{ports}", "{target}"],
                    timeout=300,
                    requires_sudo=True,
                    success_codes=[0]
                ),
                "tcp_scan": CommandTemplate(
                    # -sT: TCP connect scan (no root needed)
                    args=["-v", "-sT", "-p", "{ports}", "{target}"],
                    timeout=300,
                    success_codes=[0]
                ),
                "udp_scan": CommandTemplate(
                    # -sU: UDP scan (requires root, very slow)
                    args=["-v", "-sU", "--top-ports", "100", "{target}"],
                    timeout=600,
                    requires_sudo=True,
                    success_codes=[0]
                ),
                # Service/Version detection
                "service_scan": CommandTemplate(
                    args=["-v", "-sV", "-sC", "-p", "{ports}", "{target}"],
                    timeout=300,
                    success_codes=[0]
                ),
                "version_scan": CommandTemplate(
                    # -sV: Version detection only
                    args=["-v", "-sV", "-p", "{ports}", "{target}"],
                    timeout=300,
                    success_codes=[0]
                ),
                "os_detect": CommandTemplate(
                    # -O: OS detection (requires root)
                    args=["-v", "-O", "{target}"],
                    timeout=300,
                    requires_sudo=True,
                    success_codes=[0]
                ),
                # Aggressive scans
                "aggressive": CommandTemplate(
                    # -A: OS detection, version, scripts, traceroute
                    args=["-v", "-A", "-p", "{ports}", "{target}"],
                    timeout=600,
                    requires_sudo=True,
                    success_codes=[0]
                ),
                "full_scan": CommandTemplate(
                    args=["-v", "-sV", "-sC", "-A", "-p-", "{target}"],
                    timeout=1800,  # 30 min for full scan
                    success_codes=[0]
                ),
                # Script scans
                "vuln_scan": CommandTemplate(
                    # NSE vulnerability scripts
                    args=["-v", "--script", "vuln", "-p", "{ports}", "{target}"],
                    timeout=600,
                    success_codes=[0]
                ),
                "default_scripts": CommandTemplate(
                    # -sC: Default scripts
                    args=["-v", "-sC", "-p", "{ports}", "{target}"],
                    timeout=300,
                    success_codes=[0]
                ),
                # Discovery
                "ping_sweep": CommandTemplate(
                    # -sn: Ping scan, no port scan
                    args=["-sn", "{target}"],
                    timeout=120,
                    success_codes=[0]
                ),
                "top_ports": CommandTemplate(
                    args=["-v", "-sV", "--top-ports", "{count}", "{target}"],
                    timeout=300,
                    success_codes=[0]
                ),
                "from_file": CommandTemplate(
                    # --stats-every 10s shows progress for large scans
                    args=["-v", "-sV", "--stats-every", "10s", "-p", "{ports}", "-iL", "{file}"],
                    timeout=1800,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # MASSCAN - Fast Port Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="masscan",
            category=ToolCategory.SCANNING,
            description="Fast port scanner for large ranges",
            executable_names=["masscan"],
            install_hint="apt install masscan",
            commands={
                "scan": CommandTemplate(
                    args=["{target}", "-p", "{ports}", "--rate=1000", "-oL", "-"],
                    timeout=120,
                    requires_sudo=True,
                    success_codes=[0]
                ),
                "fast_scan": CommandTemplate(
                    args=["{target}", "-p", "{ports}", "--rate=10000", "-oL", "-"],
                    timeout=60,
                    requires_sudo=True,
                    success_codes=[0]
                ),
            }
        ),
    ]
