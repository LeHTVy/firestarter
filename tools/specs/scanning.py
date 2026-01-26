"""Scanning Tools Specifications.

Port scanning, service detection, network mapping.
"""
from typing import List
from tools.specs import ToolSpec, ToolCategory, CommandTemplate


def get_specs() -> List[ToolSpec]:
    """Get scanning tool specifications."""
    return [
        # ─────────────────────────────────────────────────────────
        # NMAP - Port Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="nmap",
            category=ToolCategory.SCANNING,
            description="Network exploration and port scanner",
            executable_names=["nmap"],
            install_hint="apt install nmap",
            aliases=["nmap_scan"],
            commands={
                "quick": CommandTemplate(
                    args=["-T4", "-F", "{target}"],
                    timeout=120,
                    description="Fast scan of common ports"
                ),
                "full": CommandTemplate(
                    args=["-T4", "-p-", "{target}"],
                    timeout=1800,
                    description="Full port scan"
                ),
                "service": CommandTemplate(
                    args=["-sV", "-T4", "{target}"],
                    timeout=600,
                    description="Service version detection"
                ),
                "os": CommandTemplate(
                    args=["-O", "-T4", "{target}"],
                    timeout=300,
                    requires_sudo=True,
                    description="OS detection"
                ),
                "vuln": CommandTemplate(
                    args=["--script", "vuln", "-T4", "{target}"],
                    timeout=600,
                    description="Vulnerability scan"
                ),
                "stealth": CommandTemplate(
                    args=["-sS", "-T2", "-Pn", "{target}"],
                    timeout=600,
                    requires_sudo=True,
                    description="Stealth SYN scan"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # MASSCAN - Fast Port Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="masscan",
            category=ToolCategory.SCANNING,
            description="Mass IP port scanner",
            executable_names=["masscan"],
            install_hint="apt install masscan",
            commands={
                "top1000": CommandTemplate(
                    args=["--top-ports", "1000", "-p1-65535", "--rate=1000", "{target}"],
                    timeout=300,
                    requires_sudo=True,
                    description="Top 1000 ports"
                ),
                "all": CommandTemplate(
                    args=["-p1-65535", "--rate=10000", "{target}"],
                    timeout=600,
                    requires_sudo=True,
                    description="All ports"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # NUCLEI - Vulnerability Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="nuclei",
            category=ToolCategory.VULN,
            description="Fast vulnerability scanner",
            executable_names=["nuclei"],
            install_hint="go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
            commands={
                "scan": CommandTemplate(
                    args=["-u", "{url}", "-silent"],
                    timeout=600,
                    description="Basic vulnerability scan"
                ),
                "cves": CommandTemplate(
                    args=["-u", "{url}", "-t", "cves/", "-silent"],
                    timeout=1200,
                    description="CVE-specific scan"
                ),
                "tech": CommandTemplate(
                    args=["-u", "{url}", "-t", "technologies/", "-silent"],
                    timeout=300,
                    description="Technology detection"
                ),
            }
        ),
        # ─────────────────────────────────────────────────────────
        # SSLSCAN - SSL/TLS Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="sslscan",
            category=ToolCategory.SCANNING,
            description="SSL/TLS vulnerability scanner",
            executable_names=["sslscan"],
            install_hint="apt install sslscan",
            aliases=["ssl_cert_scan", "tls_scan"],
            commands={
                "scan": CommandTemplate(
                    args=["{target}"],
                    timeout=300,
                    description="Full SSL/TLS scan"
                ),
                "fast": CommandTemplate(
                    args=["--no-failed", "{target}"],
                    timeout=120,
                    description="Fast SSL scan"
                ),
            }
        ),
    ]
