"""
Web Tools Specifications
========================

Web fuzzing, CMS scanning, directory discovery.
"""
from typing import List
from app.tools.registry import ToolSpec, ToolCategory, CommandTemplate


def get_specs() -> List[ToolSpec]:
    """Get web tool specifications."""
    return [
        # ─────────────────────────────────────────────────────────
        # WFUZZ - Web Fuzzer
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="wfuzz",
            category=ToolCategory.ENUM,
            description="Web application bruteforcer and fuzzer",
            executable_names=["wfuzz"],
            install_hint="apt install wfuzz OR pip install wfuzz",
            commands={
                "dir": CommandTemplate(
                    args=["-c", "-w", "{wordlist}", "--hc", "404", "{url}/FUZZ"],
                    timeout=300,
                    success_codes=[0]
                ),
                "param": CommandTemplate(
                    args=["-c", "-w", "{wordlist}", "--hc", "404", "{url}?{param}=FUZZ"],
                    timeout=300,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # FEROXBUSTER - Fast Directory Discovery
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="feroxbuster",
            category=ToolCategory.ENUM,
            description="Fast, recursive content discovery tool",
            executable_names=["feroxbuster"],
            install_hint="apt install feroxbuster OR cargo install feroxbuster",
            commands={
                "scan": CommandTemplate(
                    args=["-u", "{url}", "-w", "{wordlist}", "-t", "50", "-q"],
                    timeout=600,
                    success_codes=[0]
                ),
                "recursive": CommandTemplate(
                    args=["-u", "{url}", "-w", "{wordlist}", "-d", "3", "-t", "50", "-q"],
                    timeout=900,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # WPSCAN - WordPress Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="wpscan",
            category=ToolCategory.VULN,
            description="WordPress vulnerability scanner",
            executable_names=["wpscan"],
            install_hint="gem install wpscan",
            commands={
                "enum": CommandTemplate(
                    args=["--url", "{url}", "--enumerate", "vp,vt,u", "--random-user-agent", "--no-banner"],
                    timeout=600,
                    success_codes=[0, 4]  # 4 = WAF detected but continued
                ),
                "brute": CommandTemplate(
                    args=["--url", "{url}", "-U", "{users}", "-P", "{wordlist}", "--random-user-agent", "--no-banner"],
                    timeout=900,
                    success_codes=[0]
                ),
                "stealth": CommandTemplate(
                    args=["--url", "{url}", "--enumerate", "vp,vt,u", "--random-user-agent", "--throttle", "500", "--no-banner"],
                    timeout=900,
                    success_codes=[0, 4]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # WHATWEB - Web Technology Fingerprinting
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="whatweb",
            category=ToolCategory.RECON,
            description="Next generation web scanner",
            executable_names=["whatweb"],
            install_hint="apt install whatweb",
            commands={
                "scan": CommandTemplate(
                    args=["-a", "3", "{url}"],
                    timeout=120,
                    success_codes=[0]
                ),
                "quick": CommandTemplate(
                    args=["-a", "1", "{url}"],
                    timeout=60,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # WAFW00F - WAF Detection
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="wafw00f",
            category=ToolCategory.RECON,
            description="Web Application Firewall detection tool",
            executable_names=["wafw00f"],
            install_hint="pip install wafw00f",
            commands={
                "detect": CommandTemplate(
                    args=["{url}"],
                    timeout=60,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # ARJUN - HTTP Parameter Discovery
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="arjun",
            category=ToolCategory.ENUM,
            description="HTTP parameter discovery suite",
            executable_names=["arjun"],
            install_hint="pip install arjun",
            commands={
                "discover": CommandTemplate(
                    args=["-u", "{url}", "-t", "10"],
                    timeout=300,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # DIRSEARCH - Web Path Scanner
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="dirsearch",
            category=ToolCategory.ENUM,
            description="Web path scanner",
            executable_names=["dirsearch"],
            install_hint="pip install dirsearch",
            commands={
                "scan": CommandTemplate(
                    args=["-u", "{url}", "-t", "30", "-q"],
                    timeout=600,
                    success_codes=[0]
                ),
                "ext": CommandTemplate(
                    args=["-u", "{url}", "-e", "{extensions}", "-t", "30", "-q"],
                    timeout=600,
                    success_codes=[0]
                ),
            }
        ),
    ]
