#!/usr/bin/env python3
"""
Initialize Firestarter Database Schema.
This script creates necessary tables in PostgreSQL if they don't exist.
"""

import os
import sys
from pathlib import Path

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def init_db():
    """Initialize database tables."""
    print("🚀 Initializing Firestarter Database...")
    
    # Check config
    host = os.getenv("POSTGRES_HOST")
    db = os.getenv("POSTGRES_DATABASE")
    user = os.getenv("POSTGRES_USER")
    
    if not all([host, db, user]):
        print("❌ Error: Missing PostgreSQL configuration in .env")
        print("Please ensure POSTGRES_HOST, POSTGRES_DATABASE, and POSTGRES_USER are set.")
        sys.exit(1)
        
    print(f"📦 Connecting to {db} at {host} as {user}...")
    
    try:
        from memory.conversation_store import ConversationStore
        store = ConversationStore()
        # The __init__ method calls create_tables() automatically
        print("✅ Database schema initialized successfully.")
        print("   - Created tables: conversations, conversation_messages, tool_results, findings")
        print("   - Created indexes for performance")
        
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_db()
