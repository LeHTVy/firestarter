"""
Vulnerability Tools Specifications
===================================

Vulnerability scanners and security testing.
"""
from typing import List
from app.tools.registry import ToolSpec, ToolCategory, CommandTemplate


def get_specs() -> List[ToolSpec]:
    """Get vulnerability tool specifications."""
    return [
        # ─────────────────────────────────────────────────────────
        # NUCLEI - Template-based Vulnerability Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="nuclei",
            category=ToolCategory.VULN,
            description="Fast template-based vulnerability scanner",
            executable_names=["nuclei"],
            install_hint="go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
            commands={
                "scan": CommandTemplate(
                    # Removed -silent, added -stats for live progress
                    args=["-u", "{target}", "-severity", "critical,high", "-stats", "-stats-interval", "3", "-rate-limit", "50", "-timeout", "10"],
                    timeout=180,
                    success_codes=[0, 2]  # Exit 2 = no vulns found (not an error!)
                ),
                "scan_fast": CommandTemplate(
                    # Fast scan with only top CVE templates
                    args=["-u", "{target}", "-severity", "critical,high", "-stats", "-stats-interval", "3", "-rate-limit", "100", "-timeout", "5", "-tags", "cve,rce,sqli,auth-bypass"],
                    timeout=120,
                    success_codes=[0, 2]
                ),
                "scan_json": CommandTemplate(
                    # JSON output - keep silent for parsing
                    args=["-u", "{target}", "-severity", "critical,high", "-json", "-silent", "-rate-limit", "50"],
                    timeout=180,
                    success_codes=[0, 2],
                    output_format="json"
                ),
                "scan_all": CommandTemplate(
                    args=["-u", "{target}", "-stats", "-stats-interval", "5", "-rate-limit", "30"],
                    timeout=300,
                    success_codes=[0, 2]
                ),
                "scan_list": CommandTemplate(
                    args=["-l", "{file}", "-severity", "critical,high", "-stats", "-stats-interval", "5", "-rate-limit", "50", "-timeout", "10"],
                    timeout=300,
                    success_codes=[0, 2]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # NIKTO - Web Server Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="nikto",
            category=ToolCategory.VULN,
            description="Web server vulnerability scanner",
            executable_names=["nikto"],
            install_hint="apt install nikto",
            commands={
                "scan_https": CommandTemplate(
                    # Default: HTTPS scan on port 443
                    args=["-h", "{host}", "-port", "443", "-ssl", "-timeout", "20"],
                    timeout=300,
                    success_codes=[0]
                ),
                "scan_http": CommandTemplate(
                    args=["-h", "{host}", "-port", "80", "-timeout", "20"],
                    timeout=300,
                    success_codes=[0]
                ),
                "scan": CommandTemplate(
                    # Custom port scan
                    args=["-h", "{host}", "-port", "{port}", "-ssl", "-timeout", "20"],
                    timeout=300,  # 5 min - nikto is thorough
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # SQLMAP - SQL Injection Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="sqlmap",
            category=ToolCategory.EXPLOIT,
            description="Automatic SQL injection detection and exploitation",
            executable_names=["sqlmap"],
            install_hint="apt install sqlmap",
            commands={
                "test": CommandTemplate(
                    args=["-u", "{url}", "--batch", "--level=1", "--risk=1", "--threads=4"],
                    timeout=180,
                    success_codes=[0]
                ),
                "deep_test": CommandTemplate(
                    args=["-u", "{url}", "--batch", "--level=3", "--risk=2", "--threads=4"],
                    timeout=300,
                    success_codes=[0]
                ),
                "dump": CommandTemplate(
                    args=["-u", "{url}", "--batch", "--dump", "--threads=4"],
                    timeout=600,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # GOBUSTER - Directory/DNS Brute Force
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="gobuster",
            category=ToolCategory.ENUM,
            description="Directory and DNS brute-forcing",
            executable_names=["gobuster"],
            install_hint="apt install gobuster",
            commands={
                "dir": CommandTemplate(
                    # Using --force to continue even if wildcard detected
                    args=["dir", "-u", "{url}", "-w", "{wordlist}", "-q", "-t", "20", "--no-error", "-k", "--force"],
                    timeout=300,
                    success_codes=[0, 1]  # Exit 1 can happen with no results
                ),
                "dir_redirects": CommandTemplate(
                    # Exclude redirects (useful when 404s redirect to login)
                    args=["dir", "-u", "{url}", "-w", "{wordlist}", "-q", "-t", "20", "--no-error", "-k", "-b", "301,302,404"],
                    timeout=300,
                    success_codes=[0]
                ),
                "dns": CommandTemplate(
                    args=["dns", "-d", "{domain}", "-w", "{wordlist}", "-q", "-t", "20"],
                    timeout=300,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # FFUF - Web Fuzzer
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="ffuf",
            category=ToolCategory.ENUM,
            description="Fast web fuzzer",
            executable_names=["ffuf"],
            install_hint="go install github.com/ffuf/ffuf/v2@latest",
            commands={
                "fuzz": CommandTemplate(
                    args=["-u", "{url}", "-w", "{wordlist}", "-mc", "200,301,302,403", "-s"],
                    timeout=300,
                    success_codes=[0]
                ),
                "fuzz_json": CommandTemplate(
                    args=["-u", "{url}", "-w", "{wordlist}", "-mc", "200,301,302,403", "-o", "-", "-of", "json"],
                    timeout=300,
                    success_codes=[0],
                    output_format="json"
                ),
            }
        ),
    ]
