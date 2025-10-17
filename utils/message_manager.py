"""
Message management system for Army Discord Bot
Handles loading and caching of per-guild messages from YAML files
"""
import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

# Message files configuration
MESSAGES_DIR = 'data/messages'
DEFAULT_MESSAGES_FILE = os.path.join(MESSAGES_DIR, 'messages-default.yml')
BACKUP_DIR = os.path.join(MESSAGES_DIR, 'backups')

# Global cache for loaded messages
_messages_cache: Dict[int, Dict[str, Any]] = {}

def _ensure_messages_directory():
    """Ensure messages directory exists"""
    Path(MESSAGES_DIR).mkdir(parents=True, exist_ok=True)
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)

def _load_yaml_file(file_path: str) -> Dict[str, Any]:
    """Load YAML file and return dictionary"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as e:
        print(f"❌ Error loading YAML file {file_path}: {e}")
        return {}

def _get_guild_messages_file(guild_id: int) -> str:
    """Get path to guild-specific messages file"""
    return os.path.join(MESSAGES_DIR, f'messages-{guild_id}.yml')

def load_default_messages() -> Dict[str, Any]:
    """Load default messages from template file"""
    return _load_yaml_file(DEFAULT_MESSAGES_FILE)

def load_guild_messages(guild_id: int) -> Dict[str, Any]:
    """
    Load messages for specific guild, with fallback to defaults
    Uses caching for performance
    """
    if guild_id in _messages_cache:
        return _messages_cache[guild_id]

    # Load defaults first
    messages = load_default_messages()

    # Load guild-specific overrides
    guild_file = _get_guild_messages_file(guild_id)
    guild_overrides = _load_yaml_file(guild_file)

    # Merge overrides into defaults (deep merge)
    def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    merged_messages = deep_merge(messages, guild_overrides)

    # Cache the result
    _messages_cache[guild_id] = merged_messages

    return merged_messages

def get_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get message by dot-separated key path (e.g., 'dismissal.ui_labels.processing')
    Returns default if key not found
    """
    messages = load_guild_messages(guild_id)

    # Navigate through nested dictionary
    keys = key_path.split('.')
    current = messages

    try:
        for key in keys:
            current = current[key]
        return str(current)
    except (KeyError, TypeError):
        if default:
            return default
        print(f"⚠️ Message key '{key_path}' not found for guild {guild_id}, using fallback")
        return f"[{key_path}]"  # Fallback indicator

def save_guild_messages(guild_id: int, messages: Dict[str, Any]) -> bool:
    """
    Save guild-specific messages to file
    Creates backup before saving
    """
    _ensure_messages_directory()

    file_path = _get_guild_messages_file(guild_id)

    # Create backup if file exists
    if os.path.exists(file_path):
        import shutil
        from datetime import datetime
        backup_name = f"messages-{guild_id}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yml"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        shutil.copy2(file_path, backup_path)

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(messages, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # Clear cache for this guild
        _messages_cache.pop(guild_id, None)

        return True
    except Exception as e:
        print(f"❌ Error saving messages for guild {guild_id}: {e}")
        return False

def clear_messages_cache(guild_id: Optional[int] = None):
    """Clear messages cache for specific guild or all guilds"""
    if guild_id:
        _messages_cache.pop(guild_id, None)
    else:
        _messages_cache.clear()

def get_messages_status() -> Dict[str, Any]:
    """Get status information about messages system"""
    _ensure_messages_directory()

    default_exists = os.path.exists(DEFAULT_MESSAGES_FILE)
    backup_count = len([f for f in os.listdir(BACKUP_DIR) if f.endswith('.yml')]) if os.path.exists(BACKUP_DIR) else 0

    guild_files = [f for f in os.listdir(MESSAGES_DIR) if f.startswith('messages-') and f.endswith('.yml') and not f.startswith('messages-default')]
    guild_count = len(guild_files)

    return {
        'messages_dir_exists': os.path.exists(MESSAGES_DIR),
        'default_messages_exists': default_exists,
        'guild_specific_files': guild_count,
        'backup_count': backup_count,
        'cache_size': len(_messages_cache)
    }

# Initialize on import
_ensure_messages_directory()