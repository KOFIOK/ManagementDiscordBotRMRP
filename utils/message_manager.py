"""
Message management system for Army Discord Bot
Handles loading and caching of per-guild messages from YAML files
"""
import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
import discord

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
    Supports template references like {templates.permissions.insufficient}
    Returns default if key not found
    """
    messages = load_guild_messages(guild_id)

    # Navigate through nested dictionary
    keys = key_path.split('.')
    current = messages

    try:
        for key in keys:
            current = current[key]

        # Check if the result contains template references
        result = str(current)
        if '{' in result and '}' in result:
            # Resolve template references
            result = _resolve_template_references(result, messages)

        return result
    except (KeyError, TypeError):
        if default:
            return default
        print(f"⚠️ Message key '{key_path}' not found for guild {guild_id}, using fallback")
        return f"[{key_path}]"  # Fallback indicator

def _resolve_template_references(message: str, messages: Dict[str, Any]) -> str:
    """
    Resolve template references in message like {templates.permissions.insufficient}
    Only resolves references that start with known prefixes
    """
    import re

    def replace_template(match):
        template_path = match.group(1)

        # Only resolve references that start with known prefixes
        known_prefixes = ['templates.', 'global.']
        if not any(template_path.startswith(prefix) for prefix in known_prefixes):
            return match.group(0)  # Return original for parameter placeholders

        try:
            # Always resolve from root of messages
            keys = template_path.split('.')
            current = messages
            for key in keys:
                current = current[key]
            return str(current)
        except (KeyError, TypeError):
            print(f"⚠️ Template reference '{template_path}' not found")
            return match.group(0)  # Return original if template not found

    # Replace all {template.path} patterns
    return re.sub(r'\{([^}]+)\}', replace_template, message)

def get_message_with_params(guild_id: int, key_path: str, default: str = None, **params) -> str:
    """
    Get message by key path and format it with parameters
    Example: get_message_with_params(guild_id, "templates.permissions.insufficient", action="для модерации")
    """
    message = get_message(guild_id, key_path, default)
    if params:
        try:
            return message.format(**params)
        except (KeyError, ValueError) as e:
            print(f"⚠️ Error formatting message '{key_path}' with params {params}: {e}")
            return message  # Return unformatted message as fallback
    return message

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

def get_embed_color(guild_id: int, color_key: str) -> discord.Color:
    """
    Get embed color by key, converting HEX string to discord.Color
    Returns default color if key not found or invalid
    """
    import discord
    
    color_hex = get_message(guild_id, f"colors.{color_key}", "#808080")  # Default to gray
    
    try:
        # Remove # if present
        if color_hex.startswith('#'):
            color_hex = color_hex[1:]
        
        # Convert hex to int
        color_int = int(color_hex, 16)
        return discord.Color(color_int)
    except (ValueError, TypeError):
        print(f"⚠️ Invalid color format for '{color_key}': {color_hex}, using default")
        return discord.Color.default()

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

def get_warehouse_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get warehouse message by dot-separated key path (e.g., 'cart.error_no_permissions')
    Returns default if key not found
    """
    return get_message(guild_id, f"warehouse.{key_path}", default)

def get_department_applications_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get department applications message by dot-separated key path (e.g., 'transfer.error_no_permissions')
    Returns default if key not found
    """
    return get_message(guild_id, f"department_applications.{key_path}", default)

def get_leave_requests_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get leave requests message by dot-separated key path (e.g., 'approval.error_insufficient_permissions')
    Returns default if key not found
    """
    return get_message(guild_id, f"leave_requests.{key_path}", default)

def get_role_assignment_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get role assignment message by dot-separated key path (e.g., 'application.error_banned_from_service')
    Returns default if key not found
    """
    return get_message(guild_id, f"role_assignment.{key_path}", default)

def get_safe_documents_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get safe documents message by dot-separated key path (e.g., 'approval.error_not_found')
    Returns default if key not found
    """
    return get_message(guild_id, f"safe_documents.{key_path}", default)

def get_settings_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get settings message by dot-separated key path (e.g., 'warehouse.error_channel_not_found')
    Returns default if key not found
    """
    return get_message(guild_id, f"settings.{key_path}", default)

def get_supplies_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get supplies message by dot-separated key path (e.g., 'control.error_no_permission')
    Returns default if key not found
    """
    return get_message(guild_id, f"supplies.{key_path}", default)

def get_supplies_color(guild_id: int, key_path: str, default_color: str = "#3498DB") -> discord.Color:
    """
    Get supplies embed color by dot-separated key path (e.g., 'colors.main_embed')
    Returns default discord.Color.blue() if key not found or invalid
    """
    try:
        color_hex = get_message(guild_id, f"supplies.{key_path}", default_color)
        if isinstance(color_hex, str) and color_hex.startswith('#'):
            # Convert hex to discord.Color
            color_hex = color_hex.lstrip('#')
            return discord.Color(int(color_hex, 16))
        else:
            # Fallback to default
            return discord.Color.blue()
    except (ValueError, TypeError):
        return discord.Color.blue()

# Initialize on import
_ensure_messages_directory()