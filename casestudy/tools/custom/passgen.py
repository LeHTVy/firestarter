#!/usr/bin/env python3
"""
PassGen - Smart Targeted Password Generator
============================================

Generates targeted password wordlists based on:
- Company/organization name
- Common patterns (years, seasons, leet speak)
- Industry-specific keywords
- Keyboard patterns

Usage:
    passgen -c "Company Name" -o wordlist.txt
    passgen -c "HelloGroup" -k "cpanel,admin,root" -o custom.txt
"""

import argparse
import itertools
from datetime import datetime

# Common password patterns
YEARS = [str(y) for y in range(2020, 2026)]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
SEASONS = ["spring", "summer", "fall", "autumn", "winter"]
COMMON_SUFFIXES = ["!", "@", "#", "$", "123", "1234", "12345", "1", "01", "007", "2024", "2025", "!!", "123!", "@123"]
COMMON_PREFIXES = ["@", "#", "!"]
SPECIAL_CHARS = ["!", "@", "#", "$", "%", "&", "*"]

# Leet speak mappings
LEET_MAP = {
    'a': ['4', '@'],
    'e': ['3'],
    'i': ['1', '!'],
    'o': ['0'],
    's': ['5', '$'],
    't': ['7'],
    'l': ['1'],
    'b': ['8'],
    'g': ['9'],
}

# Common weak passwords (always include)
COMMON_PASSWORDS = [
    "password", "Password", "PASSWORD",
    "admin", "Admin", "ADMIN",
    "root", "Root", "ROOT",
    "123456", "12345678", "123456789",
    "qwerty", "letmein", "welcome",
    "monkey", "dragon", "master",
    "login", "passw0rd", "abc123",
    "admin123", "root123", "password1",
    "Password1", "Password123", "P@ssw0rd",
    "P@ssword1", "Passw0rd!", "Welcome1",
    "Welcome123", "Qwerty123", "Admin123",
    "Test123", "Guest123", "User123",
]


def generate_variations(base: str) -> list:
    """Generate password variations from a base word."""
    variations = set()
    base_lower = base.lower()
    base_upper = base.upper()
    base_title = base.title()
    
    # Basic variations
    variations.add(base_lower)
    variations.add(base_upper)
    variations.add(base_title)
    
    # With years
    for year in YEARS:
        variations.add(f"{base_lower}{year}")
        variations.add(f"{base_title}{year}")
        variations.add(f"{base_upper}{year}")
        variations.add(f"{year}{base_lower}")
        
    # With suffixes
    for suffix in COMMON_SUFFIXES:
        variations.add(f"{base_lower}{suffix}")
        variations.add(f"{base_title}{suffix}")
        variations.add(f"{base_upper}{suffix}")
        
    # With seasons + year
    for season in SEASONS:
        for year in YEARS:
            variations.add(f"{base_lower}{season}{year}")
            variations.add(f"{base_title}{season.title()}{year}")
            variations.add(f"{season}{base_lower}{year}")
            variations.add(f"{season.title()}{base_title}{year}")
    
    # With months
    for month in MONTHS:
        for year in YEARS:
            variations.add(f"{base_lower}{month}{year}")
            variations.add(f"{base_title}{month.title()}{year}")
    
    # Leet speak variations (simple)
    leet_base = base_lower
    for char, replacements in LEET_MAP.items():
        if char in leet_base:
            for rep in replacements:
                leet_var = leet_base.replace(char, rep)
                variations.add(leet_var)
                variations.add(leet_var.title())
                for suffix in ["!", "123", "1", "@"]:
                    variations.add(f"{leet_var}{suffix}")
    
    # Keyboard patterns with company
    keyboard_patterns = ["123", "qwerty", "!@#", "321"]
    for pattern in keyboard_patterns:
        variations.add(f"{base_lower}{pattern}")
        variations.add(f"{pattern}{base_lower}")
    
    return list(variations)


def generate_company_passwords(company: str, keywords: list = None) -> list:
    """Generate passwords based on company name."""
    passwords = set()
    
    # Add common passwords first
    passwords.update(COMMON_PASSWORDS)
    
    # Company name variations
    company_clean = company.replace(" ", "").lower()
    company_parts = company.lower().split()
    
    # Full company name
    passwords.update(generate_variations(company_clean))
    
    # Parts of company name
    for part in company_parts:
        if len(part) >= 3:
            passwords.update(generate_variations(part))
    
    # Abbreviation (first letters)
    if len(company_parts) > 1:
        abbrev = "".join(p[0] for p in company_parts)
        passwords.update(generate_variations(abbrev))
    
    # Company + common IT terms
    it_terms = ["admin", "user", "login", "pass", "root", "sys", "net", "web", "db", "dev", "test", "backup", "ftp", "mail", "vpn"]
    for term in it_terms:
        passwords.add(f"{company_clean}{term}")
        passwords.add(f"{term}{company_clean}")
        passwords.add(f"{company_clean.title()}{term.title()}")
        for year in YEARS:
            passwords.add(f"{company_clean}{term}{year}")
    
    # Custom keywords
    if keywords:
        for kw in keywords:
            kw = kw.strip()
            if kw:
                passwords.update(generate_variations(kw))
                # Combine with company
                passwords.add(f"{company_clean}{kw}")
                passwords.add(f"{kw}{company_clean}")
    
    # Domain-style passwords
    passwords.add(f"{company_clean}.com")
    passwords.add(f"{company_clean}@123")
    passwords.add(f"{company_clean}#1")
    
    return sorted(list(passwords))


def main():
    parser = argparse.ArgumentParser(
        description="PassGen - Smart Targeted Password Generator"
    )
    parser.add_argument("-c", "--company", required=True, help="Target company/organization name")
    parser.add_argument("-k", "--keywords", help="Additional keywords (comma-separated)")
    parser.add_argument("-o", "--output", default="generated_wordlist.txt", help="Output file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show generated passwords")
    
    args = parser.parse_args()
    
    keywords = args.keywords.split(",") if args.keywords else []
    
    print(f"\n[*] PassGen v1.0 - Smart Password Generator")
    print(f"[*] Target: {args.company}")
    print(f"[*] Keywords: {keywords if keywords else 'None'}")
    print(f"[*] Output: {args.output}\n")
    
    passwords = generate_company_passwords(args.company, keywords)
    
    # Write to file
    with open(args.output, 'w') as f:
        for pw in passwords:
            f.write(pw + '\n')
    
    print(f"[+] Generated {len(passwords)} password candidates")
    print(f"[+] Saved to: {args.output}")
    
    if args.verbose:
        print(f"\n[*] Sample passwords:")
        for pw in passwords[:20]:
            print(f"    {pw}")
        if len(passwords) > 20:
            print(f"    ... and {len(passwords) - 20} more")
    
    # Show usage hint
    print(f"\n[*] Usage with hydra:")
    print(f"    hydra -l admin -P {args.output} target.com https-post-form")
    print(f"\n[*] Usage with cpanelbrute:")
    print(f"    cpanelbrute -t target.com -u admin -w {args.output}")


if __name__ == "__main__":
    main()
