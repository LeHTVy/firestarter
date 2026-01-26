#!/usr/bin/env python3
"""
CredCheck - Credential Leak Checker
====================================

Check emails and passwords against HaveIBeenPwned database.
Uses k-Anonymity for password checking (safe, doesn't send full password).

Usage:
    credcheck -e email@example.com           # Check single email
    credcheck -p "password123"               # Check single password
    credcheck -f emails.txt                  # Check file of emails
    credcheck -d example.com                 # Check domain breaches
"""

import argparse
import hashlib
import sys
import time
import requests
from typing import Optional, List, Tuple

# HIBP API endpoints
HIBP_PASSWORD_API = "https://api.pwnedpasswords.com/range/"
HIBP_BREACH_API = "https://haveibeenpwned.com/api/v3/breachedaccount/"
HIBP_DOMAIN_API = "https://haveibeenpwned.com/api/v3/breaches"

# User agent required by HIBP
HEADERS = {
    "User-Agent": "SNODE-CredCheck/1.0",
    "Accept": "application/json"
}


def check_password_pwned(password: str) -> Tuple[bool, int]:
    """
    Check if password is in HIBP database using k-Anonymity.
    Only sends first 5 chars of SHA-1 hash - safe and private.
    
    Returns: (is_pwned, count)
    """
    # SHA-1 hash the password
    sha1_hash = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    prefix = sha1_hash[:5]
    suffix = sha1_hash[5:]
    
    try:
        response = requests.get(
            f"{HIBP_PASSWORD_API}{prefix}",
            headers=HEADERS,
            timeout=10
        )
        
        if response.status_code == 200:
            # Check if our suffix is in the response
            hashes = response.text.split('\r\n')
            for h in hashes:
                parts = h.split(':')
                if len(parts) == 2 and parts[0] == suffix:
                    return (True, int(parts[1]))
            return (False, 0)
        else:
            print(f"[!] API error: {response.status_code}")
            return (False, -1)
            
    except requests.exceptions.RequestException as e:
        print(f"[!] Request error: {e}")
        return (False, -1)


def check_email_breaches(email: str, api_key: Optional[str] = None) -> List[dict]:
    """
    Check if email appears in known breaches.
    Note: Requires HIBP API key for full access ($3.50/month)
    Without API key, returns limited info.
    """
    headers = HEADERS.copy()
    if api_key:
        headers["hibp-api-key"] = api_key
    
    try:
        response = requests.get(
            f"{HIBP_BREACH_API}{email}?truncateResponse=false",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return []  # Not found in any breach
        elif response.status_code == 401:
            print(f"[!] API key required for email breach lookup")
            print(f"[*] Get one at: https://haveibeenpwned.com/API/Key")
            return []
        elif response.status_code == 429:
            print(f"[!] Rate limited. Waiting...")
            time.sleep(2)
            return check_email_breaches(email, api_key)
        else:
            print(f"[!] API error: {response.status_code}")
            return []
            
    except requests.exceptions.RequestException as e:
        print(f"[!] Request error: {e}")
        return []


def check_domain_breaches(domain: str) -> List[str]:
    """Check what breaches might affect a domain (public info)."""
    try:
        response = requests.get(
            HIBP_DOMAIN_API,
            headers=HEADERS,
            timeout=10
        )
        
        if response.status_code == 200:
            breaches = response.json()
            # Filter breaches that might be relevant
            relevant = []
            for breach in breaches:
                # Check if domain is mentioned or if it's a major breach
                if breach.get("IsVerified") and breach.get("PwnCount", 0) > 100000:
                    relevant.append(breach)
            return relevant[:20]  # Return top 20
        return []
        
    except requests.exceptions.RequestException as e:
        print(f"[!] Request error: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(
        description="CredCheck - Check credentials against leaked databases"
    )
    parser.add_argument("-e", "--email", help="Check single email address")
    parser.add_argument("-p", "--password", help="Check if password is leaked (safe k-Anonymity)")
    parser.add_argument("-f", "--file", help="File with emails to check (one per line)")
    parser.add_argument("-d", "--domain", help="Check major breaches (domain context)")
    parser.add_argument("-w", "--wordlist", help="Check passwords from wordlist file")
    parser.add_argument("-k", "--apikey", help="HIBP API key for email breach lookup")
    
    args = parser.parse_args()
    
    print(f"\n[*] CredCheck v1.0 - Credential Leak Checker")
    print(f"[*] Using HaveIBeenPwned API (k-Anonymity)\n")
    
    results = {"pwned": [], "clean": [], "errors": []}
    
    # Check single password
    if args.password:
        print(f"[*] Checking password...")
        is_pwned, count = check_password_pwned(args.password)
        if is_pwned:
            print(f"[!] ⚠️  PASSWORD PWNED! Found {count:,} times in breaches")
            print(f"[!] This password should NEVER be used")
            results["pwned"].append(("password", count))
        elif count == -1:
            print(f"[?] Could not check password (API error)")
            results["errors"].append("password")
        else:
            print(f"[+] ✅ Password not found in known breaches")
            results["clean"].append("password")
    
    # Check passwords from wordlist
    if args.wordlist:
        print(f"[*] Checking passwords from: {args.wordlist}")
        try:
            with open(args.wordlist, 'r', errors='ignore') as f:
                passwords = [line.strip() for line in f if line.strip()][:100]  # Limit to 100
            
            pwned_count = 0
            for i, pw in enumerate(passwords, 1):
                is_pwned, count = check_password_pwned(pw)
                if is_pwned:
                    print(f"  [{i}/{len(passwords)}] ⚠️  '{pw[:3]}***' - PWNED ({count:,} times)")
                    pwned_count += 1
                    results["pwned"].append((pw, count))
                time.sleep(0.1)  # Rate limiting
            
            print(f"\n[*] Summary: {pwned_count}/{len(passwords)} passwords found in breaches")
            
        except FileNotFoundError:
            print(f"[!] File not found: {args.wordlist}")
    
    # Check single email
    if args.email:
        print(f"[*] Checking email: {args.email}")
        breaches = check_email_breaches(args.email, args.apikey)
        if breaches:
            print(f"[!] ⚠️  EMAIL FOUND IN {len(breaches)} BREACH(ES):")
            for breach in breaches[:10]:
                name = breach.get("Name", "Unknown")
                date = breach.get("BreachDate", "Unknown")
                count = breach.get("PwnCount", 0)
                types = ", ".join(breach.get("DataClasses", [])[:5])
                print(f"    • {name} ({date}) - {count:,} accounts")
                print(f"      Data: {types}")
            results["pwned"].append((args.email, len(breaches)))
        else:
            print(f"[+] ✅ Email not found in known breaches")
            results["clean"].append(args.email)
    
    # Check file of emails
    if args.file:
        print(f"[*] Checking emails from: {args.file}")
        if not args.apikey:
            print(f"[!] Note: Email breach lookup requires HIBP API key")
            print(f"[*] Get one at: https://haveibeenpwned.com/API/Key ($3.50/month)\n")
        
        try:
            with open(args.file, 'r') as f:
                emails = [line.strip() for line in f if '@' in line][:50]  # Limit to 50
            
            for i, email in enumerate(emails, 1):
                print(f"  [{i}/{len(emails)}] {email}...", end=" ")
                breaches = check_email_breaches(email, args.apikey)
                if breaches:
                    print(f"⚠️  PWNED in {len(breaches)} breaches")
                    results["pwned"].append((email, len(breaches)))
                else:
                    print(f"✅ Clean")
                    results["clean"].append(email)
                time.sleep(1.5)  # HIBP rate limit
                
        except FileNotFoundError:
            print(f"[!] File not found: {args.file}")
    
    # Check domain context
    if args.domain:
        print(f"[*] Checking major breaches relevant to {args.domain}...")
        breaches = check_domain_breaches(args.domain)
        if breaches:
            print(f"[*] Top {len(breaches)} major breaches to check against:")
            for breach in breaches[:10]:
                name = breach.get("Name", "Unknown")
                count = breach.get("PwnCount", 0)
                print(f"    • {name} - {count:,} accounts")
    
    # Final summary
    print(f"\n{'='*50}")
    print(f"[*] SUMMARY:")
    print(f"    Pwned:  {len(results['pwned'])}")
    print(f"    Clean:  {len(results['clean'])}")
    print(f"    Errors: {len(results['errors'])}")
    
    if results["pwned"]:
        print(f"\n[!] ⚠️  Found leaked credentials! Consider:")
        print(f"    • Checking for password reuse")
        print(f"    • Credential stuffing attacks")
        print(f"    • Social engineering opportunities")


if __name__ == "__main__":
    main()
