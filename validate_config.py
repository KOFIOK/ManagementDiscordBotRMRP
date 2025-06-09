#!/usr/bin/env python3
"""
Configuration validator for Army Discord Bot
This script validates the bot configuration before deployment
"""

import json
import os
import sys
from pathlib import Path


def validate_config():
    """Validate bot configuration"""
    print("🔍 Validating bot configuration...")
    
    # Check if config file exists
    config_path = Path("data/config.json")
    if not config_path.exists():
        print("❌ Configuration file not found: data/config.json")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in config file: {e}")
        return False
    
    # Validate required fields
    required_fields = {
        'role_assignment_channel': int,
        'audit_channel': int,
        'military_roles': list,
        'civilian_roles': list
    }
    
    for field, expected_type in required_fields.items():
        if field not in config:
            print(f"⚠️  Warning: Missing optional field '{field}' in config")
        elif not isinstance(config[field], expected_type):
            print(f"❌ Field '{field}' should be {expected_type.__name__}, got {type(config[field]).__name__}")
            return False
    
    print("✅ Configuration file is valid")
    return True


def validate_environment():
    """Validate environment variables"""
    print("🔍 Validating environment...")
    
    # Check for Discord token
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        # Check for token file
        token_file = Path("token.txt")
        env_file = Path(".env")
        
        if token_file.exists():
            print("✅ Discord token found in token.txt")
        elif env_file.exists():
            print("✅ Environment file (.env) found")
        else:
            print("⚠️  Warning: No Discord token found in environment or files")
            print("   Make sure to set DISCORD_TOKEN environment variable")
            print("   or create .env file or token.txt file")
            return False
    else:
        print("✅ Discord token found in environment")
    
    return True


def validate_dependencies():
    """Validate Python dependencies"""
    print("🔍 Validating dependencies...")
    
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print("❌ requirements.txt not found")
        return False
    
    try:
        import discord
        print(f"✅ discord.py version: {discord.__version__}")
    except ImportError:
        print("❌ discord.py not installed")
        return False
    
    return True


def validate_project_structure():
    """Validate project structure"""
    print("🔍 Validating project structure...")
    
    required_files = [
        "app.py",
        "requirements.txt",
        "forms/role_assignment_form.py",
        "utils/config_manager.py",
        "cogs/channel_manager.py"
    ]
    
    required_dirs = [
        "forms",
        "utils", 
        "cogs",
        "data"
    ]
    
    for file_path in required_files:
        if not Path(file_path).exists():
            print(f"❌ Required file missing: {file_path}")
            return False
    
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            print(f"❌ Required directory missing: {dir_path}")
            return False
    
    print("✅ Project structure is valid")
    return True


def main():
    """Main validation function"""
    print("🚀 Army Discord Bot - Configuration Validator")
    print("=" * 50)
    
    all_valid = True
    
    # Run all validations
    validations = [
        validate_project_structure,
        validate_dependencies,
        validate_config,
        validate_environment
    ]
    
    for validation in validations:
        if not validation():
            all_valid = False
        print()
    
    if all_valid:
        print("🎉 All validations passed! Bot is ready for deployment.")
        return 0
    else:
        print("❌ Some validations failed. Please fix the issues before deployment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
