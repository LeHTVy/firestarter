"""
Brute-Force Tools Specifications
=================================

Password cracking and authentication testing.
"""
from typing import List
from app.tools.registry import ToolSpec, ToolCategory, CommandTemplate


def get_specs() -> List[ToolSpec]:
    """Get brute-force tool specifications."""
    return [
        # ─────────────────────────────────────────────────────────
        # HYDRA - Network Login Cracker
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="hydra",
            category=ToolCategory.BRUTE,
            description="Fast network login cracker (SSH, FTP, HTTP, etc.)",
            executable_names=["hydra"],
            install_hint="apt install hydra",
            commands={
                "ssh": CommandTemplate(
                    args=["-l", "{user}", "-P", "{wordlist}", "-t", "4", "-f", "ssh://{target}"],
                    timeout=300,
                    success_codes=[0, 1]
                ),
                "ftp": CommandTemplate(
                    args=["-l", "{user}", "-P", "{wordlist}", "-t", "4", "-f", "ftp://{target}"],
                    timeout=300,
                    success_codes=[0, 1]
                ),
                "http_post": CommandTemplate(
                    args=["-l", "{user}", "-P", "{wordlist}", "{target}", "http-post-form", 
                          "{path}:{form}:{fail_msg}"],
                    timeout=300,
                    success_codes=[0, 1]
                ),
                "http_get": CommandTemplate(
                    # Basic/Digest Authentication
                    args=["-l", "{user}", "-P", "{wordlist}", "{target}", "http-get", "{path}"],
                    timeout=300,
                    success_codes=[0, 1]
                ),
                "cpanel": CommandTemplate(
                    # cPanel WHM login brute-force (port 2087)
                    args=["-l", "{user}", "-P", "{wordlist}", "-s", "2087", "-f", 
                          "{target}", "https-post-form",
                          "/login/:user=^USER^&pass=^PASS^:failed"],
                    timeout=300,
                    success_codes=[0, 1]
                ),
                "rdp": CommandTemplate(
                    args=["-l", "{user}", "-P", "{wordlist}", "-t", "1", "-f", "rdp://{target}"],
                    timeout=300,
                    success_codes=[0, 1]
                ),
                "smb": CommandTemplate(
                    args=["-l", "{user}", "-P", "{wordlist}", "-t", "1", "-f", "smb://{target}"],
                    timeout=300,
                    success_codes=[0, 1]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # MEDUSA - Parallel Password Cracker
        # Supports: ssh, ftp, http, mysql, mssql, telnet, vnc, smb, pop3, imap
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="medusa",
            category=ToolCategory.BRUTE,
            description="Speedy parallel network login auditor",
            executable_names=["medusa"],
            install_hint="apt install medusa",
            commands={
                "http": CommandTemplate(
                    # HTTP Basic Auth brute force (most common for web)
                    args=["-h", "{target}", "-u", "{user}", "-P", "{wordlist}", "-M", "http", "-m", "AUTH:BASIC"],
                    timeout=600,
                    success_codes=[0]
                ),
                "ssh": CommandTemplate(
                    args=["-h", "{target}", "-u", "{user}", "-P", "{wordlist}", "-M", "ssh"],
                    timeout=600,
                    success_codes=[0]
                ),
                "ftp": CommandTemplate(
                    args=["-h", "{target}", "-u", "{user}", "-P", "{wordlist}", "-M", "ftp"],
                    timeout=600,
                    success_codes=[0]
                ),
                "mysql": CommandTemplate(
                    args=["-h", "{target}", "-u", "{user}", "-P", "{wordlist}", "-M", "mysql"],
                    timeout=600,
                    success_codes=[0]
                ),
                "rdp": CommandTemplate(
                    args=["-h", "{target}", "-u", "{user}", "-P", "{wordlist}", "-M", "rdp"],
                    timeout=600,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # CPANELBRUTE - Dedicated cPanel/WHM Brute Force
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="cpanelbrute",
            category=ToolCategory.BRUTE,
            description="Dedicated cPanel/WHM brute force tool",
            executable_names=["cpanelbrute", "python3"],
            install_hint="Built into SNODE: app/tools/custom/cpanelbrute.py",
            commands={
                "cpanel": CommandTemplate(
                    # cPanel user login (port 2083)
                    args=["-t", "{target}", "-u", "{user}", "-w", "{wordlist}", "-p", "2083", "-T", "10"],
                    timeout=600,
                    success_codes=[0]
                ),
                "whm": CommandTemplate(
                    # WHM admin login (port 2087)
                    args=["-t", "{target}", "-u", "root", "-w", "{wordlist}", "-p", "2087", "-T", "10"],
                    timeout=600,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # PASSGEN - Smart Targeted Password Generator
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="passgen",
            category=ToolCategory.BRUTE,
            description="Smart targeted password generator based on company/keywords",
            executable_names=["passgen", "python3"],
            install_hint="Built into SNODE: app/tools/custom/passgen.py",
            commands={
                "generate": CommandTemplate(
                    # Generate wordlist from company name
                    args=["-c", "{company}", "-o", "discoveries/wordlists/{company}_passwords.txt", "-v"],
                    timeout=60,
                    success_codes=[0]
                ),
                "keywords": CommandTemplate(
                    # Generate with additional keywords
                    args=["-c", "{company}", "-k", "{keywords}", "-o", "discoveries/wordlists/{company}_passwords.txt", "-v"],
                    timeout=60,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # CREDCHECK - Credential Leak Checker (HIBP)
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="credcheck",
            category=ToolCategory.OSINT,
            description="Check credentials against leaked databases (HaveIBeenPwned)",
            executable_names=["credcheck", "python3"],
            install_hint="Built into SNODE: app/tools/custom/credcheck.py",
            commands={
                "password": CommandTemplate(
                    # Check single password (safe k-Anonymity)
                    args=["-p", "{password}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "email": CommandTemplate(
                    # Check email against breaches
                    args=["-e", "{email}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "wordlist": CommandTemplate(
                    # Check passwords from wordlist
                    args=["-w", "{wordlist}"],
                    timeout=120,
                    success_codes=[0]
                ),
                "domain": CommandTemplate(
                    # Check domain-relevant breaches
                    args=["-d", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # JOHN - Password Hash Cracker
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="john",
            category=ToolCategory.BRUTE,
            description="John the Ripper password cracker",
            executable_names=["john"],
            install_hint="apt install john",
            commands={
                "crack": CommandTemplate(
                    args=["--wordlist={wordlist}", "{hashfile}"],
                    timeout=1800,  # 30 min
                    success_codes=[0]
                ),
                "show": CommandTemplate(
                    args=["--show", "{hashfile}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "format": CommandTemplate(
                    args=["--format={format}", "--wordlist={wordlist}", "{hashfile}"],
                    timeout=1800,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # HASHCAT - GPU Password Cracker
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="hashcat",
            category=ToolCategory.BRUTE,
            description="Advanced GPU-based password recovery",
            executable_names=["hashcat"],
            install_hint="apt install hashcat",
            commands={
                "crack": CommandTemplate(
                    args=["-m", "{mode}", "-a", "0", "{hashfile}", "{wordlist}"],
                    timeout=3600,  # 1 hour
                    success_codes=[0, 1]
                ),
                "benchmark": CommandTemplate(
                    args=["-b"],
                    timeout=300,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # CRACKMAPEXEC - Network Protocol Attacks
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="crackmapexec",
            category=ToolCategory.BRUTE,
            description="Swiss army knife for pentesting AD environments",
            executable_names=["crackmapexec", "cme"],
            install_hint="apt install crackmapexec OR pip install crackmapexec",
            commands={
                "smb_enum": CommandTemplate(
                    args=["smb", "{target}", "--shares"],
                    timeout=120,
                    success_codes=[0]
                ),
                "smb_auth": CommandTemplate(
                    args=["smb", "{target}", "-u", "{user}", "-p", "{password}"],
                    timeout=120,
                    success_codes=[0]
                ),
                "smb_pass_spray": CommandTemplate(
                    args=["smb", "{target}", "-u", "{userlist}", "-p", "{password}"],
                    timeout=300,
                    success_codes=[0]
                ),
            }
        ),
    ]
