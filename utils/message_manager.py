"""
Message management system for Army Discord Bot
Handles loading and caching of per-guild messages from YAML files
"""
import os
import yaml
import time
import logging
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import discord

# Message files configuration
MESSAGES_DIR = 'data/messages'
DEFAULT_MESSAGES_FILE = os.path.join(MESSAGES_DIR, 'messages-default.yml')
BACKUP_DIR = os.path.join(MESSAGES_DIR, 'backups')

# Global cache for loaded messages
_messages_cache: Dict[int, Dict[str, Any]] = {}
# Cache for resolved messages (key_path -> resolved_message)
_resolved_messages_cache: Dict[str, str] = {}
# Performance metrics
_cache_hits = 0
_cache_misses = 0
_template_resolution_time = 0.0
_last_cache_cleanup = time.time()

# Setup logging
logger = logging.getLogger('message_manager')

def _ensure_messages_directory():
    """Ensure messages directory exists"""
    Path(MESSAGES_DIR).mkdir(parents=True, exist_ok=True)
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)

def clear_message_cache(guild_id: Optional[int] = None):
    """
    Clear message cache for specific guild or all guilds
    Useful for forcing reload after configuration changes
    """
    global _messages_cache, _resolved_messages_cache, _cache_hits, _cache_misses

    if guild_id is None:
        _messages_cache.clear()
        _resolved_messages_cache.clear()
        _cache_hits = 0
        _cache_misses = 0
        logger.info("🧹 Cleared all message caches")
    else:
        _messages_cache.pop(guild_id, None)
        # Clear resolved messages that might reference this guild
        keys_to_remove = [k for k in _resolved_messages_cache.keys() if str(guild_id) in k]
        for key in keys_to_remove:
            _resolved_messages_cache.pop(key, None)
        logger.info(f"🧹 Cleared message cache for guild {guild_id}")

def get_cache_stats() -> Dict[str, Any]:
    """Get cache performance statistics"""
    total_requests = _cache_hits + _cache_misses
    hit_rate = (_cache_hits / total_requests * 100) if total_requests > 0 else 0

    return {
        'cache_hits': _cache_hits,
        'cache_misses': _cache_misses,
        'hit_rate': f"{hit_rate:.1f}%",
        'cached_guilds': len(_messages_cache),
        'resolved_messages': len(_resolved_messages_cache),
        'template_resolution_time': f"{_template_resolution_time:.4f}s"
    }

def _cleanup_expired_cache():
    """Clean up expired cache entries (run periodically)"""
    global _last_cache_cleanup

    current_time = time.time()
    if current_time - _last_cache_cleanup > 3600:  # Clean up every hour
        # Remove old resolved messages (keep only recent ones)
        if len(_resolved_messages_cache) > 1000:  # Limit cache size
            # Keep only the most recently used 500 entries
            items = list(_resolved_messages_cache.items())
            _resolved_messages_cache.clear()
            _resolved_messages_cache.update(dict(items[-500:]))

        _last_cache_cleanup = current_time
        logger.debug("🧹 Performed cache cleanup")

def _load_yaml_file(file_path: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Load YAML file and return dictionary with error handling
    Returns: (data_dict, error_message)
    """
    try:
        if not os.path.exists(file_path):
            return {}, f"File not found: {file_path}"

        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if data is None:
            return {}, f"Empty or invalid YAML file: {file_path}"

        # Basic validation - check for required structure
        if not isinstance(data, dict):
            return {}, f"Invalid YAML structure (not a dictionary): {file_path}"

        return data, None

    except yaml.YAMLError as e:
        error_msg = f"YAML parsing error in {file_path}: {e}"
        logger.error(f"❌ {error_msg}")
        return {}, error_msg
    except UnicodeDecodeError as e:
        error_msg = f"Encoding error in {file_path}: {e}"
        logger.error(f"❌ {error_msg}")
        return {}, error_msg
    except PermissionError as e:
        error_msg = f"Permission denied reading {file_path}: {e}"
        logger.error(f"❌ {error_msg}")
        return {}, error_msg
    except Exception as e:
        error_msg = f"Unexpected error loading {file_path}: {e}"
        logger.error(f"❌ {error_msg}")
        return {}, error_msg

def _get_guild_messages_file(guild_id: int) -> str:
    """Get path to guild-specific messages file"""
    return os.path.join(MESSAGES_DIR, f'messages-{guild_id}.yml')

def load_default_messages() -> Dict[str, Any]:
    """Load default messages from template file"""
    data, error = _load_yaml_file(DEFAULT_MESSAGES_FILE)
    if error:
        logger.warning(f"⚠️ Failed to load default messages: {error}")
        return {}
    return data

def load_guild_messages(guild_id: int) -> Dict[str, Any]:
    """
    Load messages for specific guild, with fallback to defaults
    Uses caching for performance
    """
    if guild_id in _messages_cache:
        global _cache_hits
        _cache_hits += 1
        return _messages_cache[guild_id]

    global _cache_misses
    _cache_misses += 1

    # Load defaults first
    messages = load_default_messages()

    # Load guild-specific overrides
    guild_file = _get_guild_messages_file(guild_id)
    guild_overrides, error = _load_yaml_file(guild_file)

    if error:
        logger.debug(f"Guild messages file not found or invalid for {guild_id}: {error}")
    else:
        # Merge overrides into defaults (deep merge)
        def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        messages = deep_merge(messages, guild_overrides)

    # Cache the result
    _messages_cache[guild_id] = messages

    # Periodic cache cleanup
    _cleanup_expired_cache()

    return messages

def get_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get message by dot-separated key path (e.g., 'dismissal.ui_labels.processing')
    Supports template references like {templates.permissions.insufficient}
    Returns default if key not found
    """
    # Create cache key
    cache_key = f"{guild_id}:{key_path}"

    # Check resolved messages cache first
    if cache_key in _resolved_messages_cache:
        global _cache_hits
        _cache_hits += 1
        return _resolved_messages_cache[cache_key]

    global _cache_misses
    _cache_misses += 1

    messages = load_guild_messages(guild_id)

    # Navigate through nested dictionary
    keys = key_path.split('.')
    current = messages

    try:
        for key in keys:
            if not isinstance(current, dict):
                raise TypeError(f"Expected dict at '{'.'.join(keys[:keys.index(key)])}', got {type(current)}")
            current = current[key]

        # Check if the result contains template references
        result = str(current)
        if '{' in result and '}' in result:
            # Resolve template references with timing
            start_time = time.time()
            result = _resolve_template_references(result, messages)
            global _template_resolution_time
            _template_resolution_time += time.time() - start_time

        # Cache the resolved result
        _resolved_messages_cache[cache_key] = result
        return result

    except (KeyError, TypeError) as e:
        logger.debug(f"Message key '{key_path}' not found for guild {guild_id}: {e}")

        # Try to find a matching template based on the key path
        template_fallback = _find_template_fallback(key_path)
        if template_fallback:
            logger.info(f"📝 Message key '{key_path}' not found, using template fallback: {template_fallback}")
            return get_message(guild_id, template_fallback, default)

        if default:
            return default

        logger.warning(f"⚠️ Message key '{key_path}' not found for guild {guild_id}, using fallback")
        fallback_result = f"[{key_path}]"  # Fallback indicator

        # Cache the fallback result too
        _resolved_messages_cache[cache_key] = fallback_result
        return fallback_result

def _find_template_fallback(key_path: str) -> str:
    """
    Try to find a matching template for a missing message key.
    Maps common error/status patterns to appropriate templates.
    """
    # Common mappings for error messages
    error_mappings = {
        'error_no_permissions': 'templates.permissions.general',
        'error_insufficient_permissions': 'templates.permissions.insufficient',
        'error_not_found': 'templates.errors.not_found',
        'error_general': 'templates.errors.general',
        'error_processing': 'templates.errors.processing',
        'error_validation': 'templates.errors.validation',
        'permission_denied': 'templates.permissions.general',
    }
    
    # Common mappings for status messages
    status_mappings = {
        'status_processing': 'templates.status.processing',
        'status_approved': 'templates.status.approved',
        'status_rejected': 'templates.status.rejected',
        'processing': 'templates.status.processing',
        'approved': 'templates.status.approved',
        'rejected': 'templates.status.rejected',
        'success': 'templates.status.completed',
        'operation_completed': 'templates.status.completed',
    }
    
    # Extract the last part of the key (the actual message name)
    key_parts = key_path.split('.')
    if not key_parts:
        return None
    
    message_name = key_parts[-1]
    
    # Check error mappings
    if message_name in error_mappings:
        return error_mappings[message_name]
    
    # Check status mappings
    if message_name in status_mappings:
        return status_mappings[message_name]
    
    # Special cases based on keywords
    if 'permission' in message_name.lower() or 'access' in message_name.lower():
        return 'templates.permissions.general'
    if 'error' in message_name.lower():
        return 'templates.errors.general'
    if 'success' in message_name.lower() or 'completed' in message_name.lower():
        return 'templates.status.completed'
    
    return None

def _resolve_template_references(message: str, messages: Dict[str, Any]) -> str:
    """
    Resolve template references in message like {templates.permissions.insufficient}
    Only resolves references that start with known prefixes
    Enhanced with error handling and performance optimizations
    """
    import re

    def replace_template(match):
        template_path = match.group(1)

        # Only resolve references that start with known prefixes
        known_prefixes = ['templates.', 'system.', 'systems.', 'ui.', 'private_messages.', 'global.', 'moderator_notifications.', 'moderator_templates.', 'military.']
        if not any(template_path.startswith(prefix) for prefix in known_prefixes):
            return match.group(0)  # Return original for parameter placeholders

        try:
            # Always resolve from root of messages
            keys = template_path.split('.')
            current = messages

            for key in keys:
                if not isinstance(current, dict):
                    raise TypeError(f"Expected dict at '{'.'.join(keys[:keys.index(key)])}', got {type(current)}")
                if key not in current:
                    raise KeyError(f"Key '{key}' not found in path '{template_path}'")
                current = current[key]

            result = str(current)
            if not result:
                logger.warning(f"⚠️ Template '{template_path}' resolved to empty string")
                return match.group(0)  # Return original if template is empty

            return result

        except (KeyError, TypeError) as e:
            logger.warning(f"⚠️ Template reference '{template_path}' not found: {e}")
            return match.group(0)  # Return original if template not found
        except Exception as e:
            logger.error(f"❌ Unexpected error resolving template '{template_path}': {e}")
            return match.group(0)  # Return original on unexpected errors

    # Replace all {template.path} patterns
    try:
        return re.sub(r'\{([^}]+)\}', replace_template, message)
    except Exception as e:
        logger.error(f"❌ Error in template resolution for message: {e}")
        return message  # Return original message if regex fails

def get_message_with_params(guild_id: int, key_path: str, default: str = None, **params) -> str:
    """
    Get message by key path and format it with parameters
    Example: get_message_with_params(guild_id, "templates.permissions.insufficient", action="для модерации")
    Enhanced with better error handling and validation
    """
    message = get_message(guild_id, key_path, default)

    if not params:
        return message

    try:
        # Validate that message contains the required placeholders
        import re
        placeholders = re.findall(r'\{(\w+)\}', message)
        missing_params = set(placeholders) - set(params.keys())

        if missing_params:
            logger.warning(f"⚠️ Missing parameters for message '{key_path}': {missing_params}")
            # Continue anyway, let format() handle missing placeholders

        return message.format(**params)

    except KeyError as e:
        logger.error(f"❌ Missing required parameter in message '{key_path}': {e}")
        return message  # Return unformatted message as fallback
    except ValueError as e:
        logger.error(f"❌ Invalid format string in message '{key_path}': {e}")
        return message  # Return unformatted message as fallback
    except Exception as e:
        logger.error(f"❌ Unexpected error formatting message '{key_path}' with params {list(params.keys())}: {e}")
        return message  # Return unformatted message as fallback

def save_guild_messages(guild_id: int, messages: Dict[str, Any], create_backup: bool = True) -> bool:
    """
    Save guild-specific messages to file
    Creates backup before saving if create_backup=True
    """
    _ensure_messages_directory()

    file_path = _get_guild_messages_file(guild_id)

    # Create backup if file exists and create_backup is True
    if create_backup and os.path.exists(file_path):
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
    return get_message(guild_id, f"systems.warehouse.{key_path}", default)

def get_department_applications_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get department applications message by dot-separated key path (e.g., 'transfer.error_no_permissions')
    Returns default if key not found
    """
    return get_message(guild_id, f"systems.department_applications.{key_path}", default)

def get_leave_requests_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get leave requests message by dot-separated key path (e.g., 'approval.error_insufficient_permissions')
    Returns default if key not found
    """
    return get_message(guild_id, f"systems.leave_requests.{key_path}", default)

def get_role_assignment_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get role assignment message by dot-separated key path (e.g., 'application.error_banned_from_service')
    Returns default if key not found
    """
    return get_message(guild_id, f"systems.role_assignment.{key_path}", default)

def get_role_reason(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get role assignment reason by dot-separated key path (e.g., 'department_application.approved')
    Returns default if key not found
    """
    return get_message(guild_id, f"role_reasons.{key_path}", default)

def get_safe_documents_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get safe documents message by dot-separated key path (e.g., 'approval.error_not_found')
    Returns default if key not found
    """
    return get_message(guild_id, f"systems.safe_documents.{key_path}", default)

def get_settings_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get settings message by dot-separated key path (e.g., 'warehouse.error_channel_not_found')
    Returns default if key not found
    """
    return get_message(guild_id, f"systems.settings.{key_path}", default)

def get_supplies_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get supplies message by dot-separated key path (e.g., 'control.error_no_permission')
    Returns default if key not found
    """
    return get_message(guild_id, f"systems.supplies.{key_path}", default)

def get_supplies_color(guild_id: int, key_path: str, default_color: str = "#3498DB") -> discord.Color:
    """
    Get supplies color by dot-separated key path (e.g., 'main_embed')
    Returns default color if key not found
    """
    try:
        color_hex = get_message(guild_id, f"systems.supplies.colors.{key_path}")
        if isinstance(color_hex, str) and color_hex.startswith('#'):
            # Convert hex to discord.Color
            color_hex = color_hex.lstrip('#')
            return discord.Color(int(color_hex, 16))
        else:
            # Fallback to default
            return discord.Color.blue()
    except (ValueError, TypeError):
        return discord.Color.blue()

def validate_messages_structure(guild_id: int) -> Tuple[bool, List[str]]:
    """
    Validate the structure of messages for a guild
    Returns: (is_valid, list_of_errors)
    Performs basic validation of critical structures
    """
    errors = []
    messages = load_guild_messages(guild_id)

    def validate_section(section_name: str, section_data: Any, path: str = "", depth: int = 0) -> None:
        # Limit recursion depth to prevent infinite loops
        if depth > 10:
            return

        current_path = f"{path}.{section_name}" if path else section_name

        # Basic type checking - only validate top-level sections
        if depth == 0:
            if not isinstance(section_data, dict):
                errors.append(f"❌ Root section '{section_name}' should be a dictionary")
                return

            # Check for critical sections
            critical_sections = ['templates', 'private_messages', 'moderator_notifications']
            for critical in critical_sections:
                if critical not in section_data:
                    errors.append(f"⚠️ Missing critical section '{critical}'")
                elif not isinstance(section_data[critical], dict):
                    errors.append(f"❌ Critical section '{critical}' should be a dictionary")

        # For deeper validation, just ensure we can navigate the structure
        elif isinstance(section_data, dict):
            # Check a few random keys to ensure structure is navigable
            for key in list(section_data.keys())[:3]:  # Check first 3 keys
                if not isinstance(section_data[key], (dict, str, int, float, bool, list)):
                    errors.append(f"❌ Invalid data type in '{current_path}.{key}': {type(section_data[key])}")

    try:
        if not isinstance(messages, dict):
            return False, ["❌ Messages root should be a dictionary"]

        validate_section("root", messages)

        is_valid = len(errors) == 0

        if is_valid:
            logger.info(f"✅ Messages structure validation passed for guild {guild_id}")
        else:
            logger.warning(f"⚠️ Messages structure validation found {len(errors)} issues for guild {guild_id}")

        return is_valid, errors

    except Exception as e:
        error_msg = f"❌ Unexpected error during validation: {e}"
        logger.error(error_msg)
        return False, [error_msg]

def get_performance_report() -> Dict[str, Any]:
    """
    Get comprehensive performance report for the message system
    """
    stats = get_cache_stats()

    # Additional metrics
    memory_usage = "psutil not available"
    try:
        import psutil  # type: ignore
        process = psutil.Process(os.getpid())
        memory_usage = round(process.memory_info().rss / 1024 / 1024, 2)  # MB
    except Exception:
        pass  # Keep default message

    report = {
        'cache_performance': stats,
        'memory_usage_mb': memory_usage,
        'system_info': {
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            'platform': os.sys.platform,
        },
        'file_info': {
            'default_messages_exists': os.path.exists(DEFAULT_MESSAGES_FILE),
            'default_messages_size_kb': round(os.path.getsize(DEFAULT_MESSAGES_FILE) / 1024, 2) if os.path.exists(DEFAULT_MESSAGES_FILE) else 0,
            'backup_count': len([f for f in os.listdir(BACKUP_DIR) if f.endswith('.yml')]) if os.path.exists(BACKUP_DIR) else 0,
        }
    }

    return report

def get_private_messages(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get private messages by dot-separated key path (e.g., 'welcome.title')
    Returns default if key not found
    """
    return get_message(guild_id, f"private_messages.{key_path}", default)

def get_system_message(guild_id: int, key_path: str, default: str = None) -> str:
    """
    Get system messages by dot-separated key path (e.g., 'personnel.hierarchy_violation')
    Returns default if key not found
    """
    return get_message(guild_id, f"system.{key_path}", default)

def get_systems_message(guild_id: int, system: str, key_path: str, default: str = None) -> str:
    """
    Get system-specific messages by system name and key path
    (e.g., 'dismissal', 'processing_error')
    Returns default if key not found
    """
    return get_message(guild_id, f"systems.{system}.{key_path}", default)

def get_ui_element(guild_id: int, category: str, key: str, default: str = None) -> str:
    """
    Get UI elements by category and key (e.g., 'labels', 'first_name')
    Returns default if key not found
    """
    return get_message(guild_id, f"ui.{category}.{key}", default)

def get_ui_label(guild_id: int, key: str, default: str = None) -> str:
    """
    Get UI label by key (e.g., 'first_name', 'department')
    Returns default if key not found
    """
    return get_ui_element(guild_id, "labels", key, default)

def get_color(guild_id: int, color_name: str, default: str = "#808080") -> str:
    """
    Get color by name (e.g., 'success', 'error')
    Returns default gray if color not found
    """
    return get_message(guild_id, f"colors.{color_name}", default)

def get_military_term(guild_id: int, term_key: str, default: str = None) -> str:
    """
    Get military term by key (e.g., 'faction_name', 'command')
    Returns default if key not found
    """
    return get_message(guild_id, f"military.terms.{term_key}", default)

def get_faction_name(guild_id: int, default: str = "Organization") -> str:
    """
    Get faction/organization name
    Returns default if not found
    """
    return get_message(guild_id, "military.faction_name", default)

def get_military_ranks(guild_id: int, rank_category: str, default: list = None) -> list:
    """
    DEPRECATED: Ranks are now stored in database only.
    This function is kept for backward compatibility but will return empty list.
    Use database rank_manager instead.
    """
    logger.warning("get_military_ranks is deprecated. Use rank_manager from database instead.")
    return default or []

def get_default_recruit_rank(guild_id: int, default: str = "Recruit") -> str:
    """
    DEPRECATED: Default recruit rank should be obtained from database.
    This function is kept for backward compatibility but will return None.
    Use rank_manager from database instead.
    """
    logger.warning("get_default_recruit_rank is deprecated. Use rank_manager from database instead.")
    return None

def get_default_recruit_rank_lower(guild_id: int, default: str = "recruit") -> str:
    """
    DEPRECATED: Default recruit rank should be obtained from database.
    This function is kept for backward compatibility but will return None.
    Use rank_manager from database instead.
    """
    logger.warning("get_default_recruit_rank_lower is deprecated. Use rank_manager from database instead.")
    return None

def get_faction_name(guild_id: int, default: str = "Организация") -> str:
    """
    Get faction/organization name
    Returns default if not found
    """
    return get_message(guild_id, "military.faction_name", default)

def get_ui_button(guild_id: int, button_key: str, default: str = None) -> str:
    """
    Get UI button label by key (e.g., 'approve', 'reject')
    Returns default if key not found
    """
    return get_message(guild_id, f"ui.buttons.{button_key}", default)

def get_ui_status(guild_id: int, status_key: str, default: str = None) -> str:
    """
    Get UI status message by key (e.g., 'success', 'error')
    Returns default if key not found
    """
    return get_message(guild_id, f"ui.status.{status_key}", default)

def get_ui_label(guild_id: int, label_key: str, default: str = None) -> str:
    """
    Get UI label by key (e.g., 'reason', 'description')
    Returns default if key not found
    """
    return get_message(guild_id, f"ui.labels.{label_key}", default)

def get_audit_embed_field(guild_id: int, field_key: str, default: str = None) -> str:
    """
    Get audit embed field name by key (e.g., 'moderator', 'action')
    Returns default if key not found
    """
    return get_message(guild_id, f"audit.embed_fields.{field_key}", default)


# Initialize on import
_ensure_messages_directory()