"""Web Application Tools Specifications.

Web scanning, directory bruteforce, SQL injection.
"""
from typing import List
from tools.specs import ToolSpec, ToolCategory, CommandTemplate


def get_specs() -> List[ToolSpec]:
    """Get web application tool specifications."""
    return [
        # ─────────────────────────────────────────────────────────
        # GOBUSTER - Directory Bruteforce
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="gobuster",
            category=ToolCategory.WEB,
            description="Directory/file bruteforcer",
            executable_names=["gobuster"],
            install_hint="go install github.com/OJ/gobuster/v3@latest",
            aliases=["directory_bruteforce"],
            commands={
                "dir": CommandTemplate(
                    args=["dir", "-u", "{url}", "-w", "/usr/share/wordlists/dirb/common.txt", "-q"],
                    timeout=600,
                    description="Directory bruteforce"
                ),
                "vhost": CommandTemplate(
                    args=["vhost", "-u", "{url}", "-w", "/usr/share/wordlists/dirb/common.txt", "-q"],
                    timeout=600,
                    description="Virtual host discovery"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # FFUF - Fast Fuzzer
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="ffuf",
            category=ToolCategory.WEB,
            description="Fast web fuzzer",
            executable_names=["ffuf"],
            install_hint="go install github.com/ffuf/ffuf/v2@latest",
            commands={
                "dir": CommandTemplate(
                    args=["-u", "{url}/FUZZ", "-w", "/usr/share/wordlists/dirb/common.txt", "-s"],
                    timeout=600,
                    description="Directory fuzzing"
                ),
                "param": CommandTemplate(
                    args=["-u", "{url}?FUZZ=test", "-w", "/usr/share/wordlists/dirb/common.txt", "-s"],
                    timeout=300,
                    description="Parameter fuzzing"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # SQLMAP - SQL Injection
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="sqlmap",
            category=ToolCategory.VULN,
            description="SQL injection testing tool",
            executable_names=["sqlmap"],
            install_hint="uv pip install sqlmap",
            aliases=["sql_injection_test"],
            commands={
                "test": CommandTemplate(
                    args=["-u", "{url}", "--batch", "--forms"],
                    timeout=600,
                    description="Basic SQL injection test"
                ),
                "dump": CommandTemplate(
                    args=["-u", "{url}", "--batch", "--dump"],
                    timeout=1800,
                    description="Dump database contents"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # NIKTO - Web Server Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="nikto",
            category=ToolCategory.WEB,
            description="Web server vulnerability scanner",
            executable_names=["nikto"],
            install_hint="apt install nikto",
            commands={
                "scan": CommandTemplate(
                    args=["-h", "{url}", "-C", "all"],
                    timeout=600,
                    description="Full web server scan"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # WPSCAN - WordPress Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="wpscan",
            category=ToolCategory.WEB,
            description="WordPress vulnerability scanner",
            executable_names=["wpscan"],
            install_hint="gem install wpscan",
            commands={
                "enum": CommandTemplate(
                    args=["--url", "{url}", "--enumerate", "vp,vt,u"],
                    timeout=600,
                    description="Enumerate plugins, themes, users"
                ),
            }
        ),
    ]
