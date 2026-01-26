#!/usr/bin/env python3
"""
Tool Verification Script
========================
Runs key security tools and streams raw output to console to verify:
1. Tools are actually installed and runnable
2. Execution time is realistic
3. Output parsing works correctly

Usage: python3 verify_tools.py [target]
"""

import sys
import time
import json
from datetime import datetime

# Add project root to path
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.executor import get_executor

def print_stream(line: str):
    """Print streaming output directly."""
    print(f"  [RAW] {line}")

def test_tool(name: str, params: dict):
    print(f"\n{'='*60}")
    print(f"Testing Tool: {name}")
    print(f"Params: {params}")
    print(f"{'='*60}\n")
    
    executor = get_executor()
    
    start = time.time()
    result = executor.execute_tool_streaming(
        tool_name=name,
        parameters=params,
        stream_callback=print_stream
    )
    duration = time.time() - start
    
    print(f"\n{'-'*60}")
    print(f"Execution complete in {duration:.2f}s")
    
    if result.get("success"):
        print("✅ SUCCESS")
        print("Parsed Data (Preview):")
        # Try to show parsed data if available, or raw output summary
        if "results" in result and result["results"]:
             # If results is a large string, truncate it
            res = result["results"]
            if isinstance(res, str) and len(res) > 200:
                print(f"{res[:200]}... [truncated]")
            else:
                print(json.dumps(res, indent=2, default=str))
    else:
        print("❌ FAILED")
        print(f"Error: {result.get('error')}")

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "scanme.nmap.org"
    print(f"🔍 Starting Tool Verification for target: {target}")
    
    # 1. Test WHOIS (Simple, usually fast but not instant)
    test_tool("whois_lookup", {"target": target})
    
    # 2. Test Subfinder (Should take a few seconds)
    # Note: Requires 'subfinder' installed
    test_tool("subdomain_discovery", {"domain": target})
    
    # 3. Test DNS Enum (Fast Python implementation or dig)
    test_tool("dns_enum", {"domain": target})
    
    # 4. Test Amass (Mass)
    print("\n[Optional] Testing Amass...")
    test_tool("amass", {"domain": target, "mode": "passive"})

    # 5. Test Nmap Quick (Should take >5 seconds usually)
    # Note: Requires 'nmap' installed
    # Using 'quick_scan' implies specifically checking common ports
    test_tool("nmap_scan", {"target": target, "options": "-F"}) # -F = Fast scan (100 ports)

if __name__ == "__main__":
    main()
