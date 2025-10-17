#!/usr/bin/env python3
"""
Messages Migration Script
Migrates default messages to per-guild files for existing servers
"""
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
MESSAGES_DIR = 'data/messages'
DEFAULT_FILE = os.path.join(MESSAGES_DIR, 'messages-default.yml')

def migrate_messages():
    """Migrate messages for configured guilds"""
    print("🔄 Starting messages migration...")

    # Load environment explicitly
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
    print(f"📋 Loaded GUILD_ID: {os.getenv('GUILD_ID')}")

    # Ensure messages directory exists
    Path(MESSAGES_DIR).mkdir(parents=True, exist_ok=True)

    if not os.path.exists(DEFAULT_FILE):
        print("❌ Default messages file not found!")
        return False

    # Get guild IDs from environment
    guild_ids = []

    # Primary guild from .env
    primary_guild = os.getenv('GUILD_ID')
    if primary_guild:
        try:
            guild_ids.append(int(primary_guild))
        except ValueError:
            print(f"⚠️ Invalid GUILD_ID in .env: {primary_guild}")

    # TODO: In future, get all guild IDs from database or config
    # For now, just migrate primary guild

    migrated = 0
    for guild_id in guild_ids:
        guild_file = os.path.join(MESSAGES_DIR, f'messages-{guild_id}.yml')

        if os.path.exists(guild_file):
            print(f"ℹ️ Guild {guild_id} already has messages file, skipping")
            continue

        # Copy default to guild-specific
        shutil.copy2(DEFAULT_FILE, guild_file)
        print(f"✅ Migrated messages for guild {guild_id}")
        migrated += 1

    if migrated == 0:
        print("ℹ️ No guilds to migrate (no GUILD_ID in .env or files already exist)")
    else:
        print(f"✅ Migration completed: {migrated} guild(s) migrated")

    return True

if __name__ == "__main__":
    try:
        success = migrate_messages()
        if success:
            print("✅ Messages migration completed successfully")
        else:
            print("❌ Messages migration failed")
            exit(1)
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        exit(1)