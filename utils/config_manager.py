"""
Enhanced configuration manager with backup and recovery functionality
"""
import os
import json
import shutil
import datetime
from typing import Dict, Any
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

# Configuration file to store channel IDs
CONFIG_FILE = 'data/config.json'
BACKUP_DIR = 'data/backups'
TEMP_CONFIG_FILE = 'data/config.json.tmp'

default_config = {
    'dismissal_channel': None,
    'dismissal_message_id': None,  # ID of the pinned message with dismissal buttons
    'audit_channel': None,
    'blacklist_channel': None,
    'role_assignment_channel': None,
    'role_assignment_message_id': None,  # ID of the pinned message with role assignment buttons
    'moderator_registration_channel': None,  # Channel for moderator registration
    'leave_requests_channel': None,  # Channel for leave requests
    'leave_requests_allowed_roles': [],  # Roles allowed to submit leave requests
    
    # Promotion report channels
    'promotion_report_channels': {
        'va': None,    # Отчёты ВА
        'vk': None,    # Отчёты ВК
        'uvp': None,   # Отчёты УВП
        'sso': None,   # Отчёты ССО
        'mr': None,    # Отчёты МР
        'roio': None   # Отчёты РОиО
    },    # Promotion notifications settings (daily notifications)
    'promotion_notifications': {
        'va': {'text': None, 'image': None, 'enabled': False},
        'vk': {'text': None, 'image': None, 'enabled': False},
        'uvp': {'text': None, 'image': None, 'enabled': False},
        'sso': {'text': None, 'image': None, 'enabled': False},
        'mr': {'text': None, 'image': None, 'enabled': False},
        'roio': {'text': None, 'image': None, 'enabled': False}
    },
    # Notification schedule settings
    'notification_schedule': {
        'hour': 21,     # Hour in MSK (0-23)
        'minute': 0     # Minute (0-59)
    },
    'military_roles': [],  # Military roles (updated to array)
    'supplier_roles': [],  # Supplier roles
    'civilian_roles': [],  # Civilian roles (updated to array)
    'military_role_assignment_ping_roles': [],  # Roles to ping for military applications
    'supplier_role_assignment_ping_roles': [],  # Roles to ping for supplier applications
    'civilian_role_assignment_ping_roles': [],  # Roles to ping for civilian applications
    'excluded_roles': [],
    'ping_settings': {},
    'blacklist_role_mentions': [],  # Ping roles for blacklist channel
    'moderators': {
        'users': [],
        'roles': []
    },
    'administrators': {
        'users': [],
        'roles': []
    },
    'blacklist': {
        'users': [],
        'roles': []
    },    # Warehouse system configuration
    'warehouse_request_channel': None,
    'warehouse_audit_channel': None,
    'warehouse_submission_channel': None,
    'warehouse_cooldown_hours': 6,
    'warehouse_limits_mode': {
        'positions_enabled': True,
        'ranks_enabled': False
    },
    'warehouse_limits_positions': {},  # Will be populated with default limits when first accessed
    'warehouse_limits_ranks': {},  # Will be populated with default limits when first accessed
    
    # Medical registration system configuration
    'medical_registration_channel': None,  # Channel for medical registration forms
    'medical_role_id': None,  # Role to ping for medical requests
    'medical_vvk_allowed_roles': [],  # Roles allowed to submit VVK medical forms
    'medical_lecture_allowed_roles': [],  # Roles allowed to submit lecture medical forms
    
    # Departments configuration (NEW ARCHITECTURE)
    # Note: position_role_ids are now retrieved from PostgreSQL via position_subdivision table
    'departments': {},  # Will be populated with department settings (Discord-specific only)
    
    # Safe documents channel
    'safe_documents_channel': None,
    
    # Nickname auto-replacement settings
    'nickname_auto_replacement': {
        'enabled': True,  # Global enable/disable
        'departments': {
            'УВП': True,
            'ВА': True,
            'ВК': True,
            'РОиО': True,
            'ГШ': True,
            'ССО': True,
            'МР': True
        },  # Per-department settings
        'modules': {
            'dismissal': True,    # Always enabled - dismissal changes nickname regardless
            'department_applications': True,  # Department application operations
            'personnel_commands': True   # Personnel command operations
        },
        'known_positions': [
            'Нач.',
            'Нач. по КР',
            'Зам.', 
            'Зам. Ком.',
            'Ком.',
            'Ком. Бриг',
            'Нач. Штаба',
            'Нач. Отдела',
            'Зам. Нач. Отдела'
        ],  # List of known positions for parsing
        'format_support': {
            'standard_with_subgroup': True,    # Support for "РОиО[ПГ] | ..." format
            'positional_with_subgroup': True,  # Support for "ГШ[АТ] | Зам. Ком. | ..." format
            'auto_detect_positions': True      # Automatically detect positions vs ranks
        },
        'custom_templates': {
            # Template customizations stored here
            # Example structure:
            # 'dismissed': {
            #     'status_text': 'Позорище',
            #     'separator': '|',  # Пробелы добавляются автоматически в коде
            #     'name_chars': 'А-ЯЁа-яёA-Za-z\\-\\.\\s'
            # },
            # 'standard': {
            #     'separator': '-',  # Пробелы добавляются автоматически в коде
            #     'name_chars': 'А-ЯЁа-яёA-Za-z\\-\\.\\s',
            #     'subdivision_chars': 'А-ЯЁA-Zа-яё\\d'
            # }
        }
    },

    # Recruitment settings
    'recruitment': {
        'enabled': True,
        'allow_user_rank_selection': False,
        'default_rank_id': 1,
        'allowed_rank_ids': [],  # empty -> all ranks
        'allow_subdivision_selection': False,
        'default_subdivision_key': 'ВА',
        'allowed_subdivision_keys': []
    },
    
    # Electronic applications system configuration
    'electronic_applications': {
        'enabled': False,
        'channel_id': None,
        'template_path': 'data/electronic_applications.md',
        'discord_tag_pattern': 'Дискорд для связи с вами:\\s*(?:\\(Пример-\\s*)?@?([\\w.#\\d-]+)',
        'success_reaction': '✅',
        'failure_reaction': '❌',
        'templates': {
            'вступление': {
                'path': 'data/electronic_applications.md',
                'type_keyword': 'Заявление на вступление'
            },
            'восстановление': {
                'path': 'data/electronic_applications_restore.md',
                'type_keyword': 'Заявление на восстановление'
            }
        }
    }
}

def create_backup(reason: str = "auto") -> str:
    """Create a backup of current configuration with timestamp and reason."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"config_backup_{timestamp}_{reason}.json"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    # Create backup directory if it doesn't exist
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    try:
        if os.path.exists(CONFIG_FILE):
            shutil.copy2(CONFIG_FILE, backup_path)
            logger.info("Backup created: %s", backup_path)
            
            # Keep only last 10 backups to avoid disk space issues
            cleanup_old_backups()
            
            return backup_path
        else:
            logger.info("No config file to backup")
            return ""
    except Exception as e:
        logger.error("Failed to create backup: %s", e)
        return ""

def cleanup_old_backups(keep_count: int = 10):
    """Keep only the most recent backups, delete older ones."""
    try:
        if not os.path.exists(BACKUP_DIR):
            return
            
        # Get all backup files
        backup_files = [f for f in os.listdir(BACKUP_DIR) if f.startswith('config_backup_') and f.endswith('.json')]
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)), reverse=True)
        
        # Delete old backups if we have more than keep_count
        if len(backup_files) > keep_count:
            for old_backup in backup_files[keep_count:]:
                old_backup_path = os.path.join(BACKUP_DIR, old_backup)
                try:
                    os.remove(old_backup_path)
                    logger.info("Removed old backup: %s", old_backup)
                except Exception as e:
                    logger.error("Failed to remove old backup %s: %s", old_backup, e)
                    
    except Exception as e:
        logger.error("Error during backup cleanup: %s", e)

def list_backups() -> list:
    """List all available backups sorted by date (newest first)."""
    try:
        if not os.path.exists(BACKUP_DIR):
            return []
            
        backup_files = [f for f in os.listdir(BACKUP_DIR) if f.startswith('config_backup_') and f.endswith('.json')]
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)), reverse=True)
        
        return backup_files
    except Exception as e:
        logger.error("Error listing backups: %s", e)
        return []

def restore_from_backup(backup_filename: str) -> bool:
    """Restore configuration from a specific backup file."""
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    if not os.path.exists(backup_path):
        logger.info("Backup file not found: %s", backup_path)
        return False
    
    try:
        # Create a backup of current config before restoring
        create_backup("before_restore")
        
        # Test if backup file is valid JSON
        with open(backup_path, 'r', encoding='utf-8') as f:
            test_config = json.load(f)
        
        # Copy backup to main config
        shutil.copy2(backup_path, CONFIG_FILE)
        logger.info("Configuration restored from: %s", backup_filename)
        return True
        
    except json.JSONDecodeError as e:
        logger.info("Invalid JSON in backup file: %s", e)
        return False
    except Exception as e:
        logger.error("Failed to restore from backup: %s", e)
        return False

def safe_save_config(config: Dict[Any, Any]) -> bool:
    """Safely save configuration with atomic write and backup."""
    try:
        # Create backup before saving
        create_backup("before_save")
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        
        # Write to temporary file first (atomic write)
        with open(TEMP_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        
        # Test if the temporary file is valid JSON
        with open(TEMP_CONFIG_FILE, 'r', encoding='utf-8') as f:
            json.load(f)  # This will raise an exception if JSON is invalid
        
        # If we got here, the file is valid - move it to the final location
        if os.path.exists(CONFIG_FILE):
            # Create backup of old config with specific reason
            create_backup("replaced")
        
        shutil.move(TEMP_CONFIG_FILE, CONFIG_FILE)
        logger.info("Configuration saved successfully")
        return True
        
    except Exception as e:
        logger.error("Failed to save configuration: %s", e)
        
        # Clean up temporary file if it exists
        if os.path.exists(TEMP_CONFIG_FILE):
            try:
                os.remove(TEMP_CONFIG_FILE)
            except:
                pass
        
        return False

def load_config() -> Dict[Any, Any]:
    """Load configuration from JSON file with recovery capabilities."""
    try:
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        
        if not os.path.exists(CONFIG_FILE):
            logger.info("Config file doesn't exist, creating default configuration")
            safe_save_config(default_config)
            return default_config.copy()
        
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Apply migrations
        if migrate_config(config):
            logger.info("Configuration migrated to new format")
            safe_save_config(config)
        return config
        
    except json.JSONDecodeError as e:
        logger.info("Config file is corrupted: %s", e)
        return attempt_recovery()
    except Exception as e:
        logger.error("Error loading config: %s", e)
        return attempt_recovery()

def attempt_recovery() -> Dict[Any, Any]:
    """Attempt to recover configuration from backups."""
    logger.info("Attempting configuration recovery...")
    
    backups = list_backups()
    
    if not backups:
        logger.info("No backups found, using default configuration")
        safe_save_config(default_config)
        return default_config.copy()
    
    logger.info(f"Found {len(backups)} backup(s), trying to restore...")
    
    for backup_file in backups:
        logger.info("Trying backup: %s", backup_file)
        backup_path = os.path.join(BACKUP_DIR, backup_file)
        
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                recovered_config = json.load(f)
            
            # Backup seems valid, restore it
            shutil.copy2(backup_path, CONFIG_FILE)
            logger.info("Successfully recovered from backup: %s", backup_file)
            return recovered_config
            
        except Exception as e:
            logger.info("Backup %s is also corrupted: %s", backup_file, e)
            continue
    
    logger.info("All backups are corrupted, using default configuration")
    safe_save_config(default_config)
    return default_config.copy()

# Replace the original save_config function
def save_config(config: Dict[Any, Any]) -> bool:
    """Save configuration (wrapper for safe_save_config for backward compatibility)."""
    return safe_save_config(config)

def is_moderator(user, config):
    """Check if a user has moderator permissions (excludes administrators to maintain separation)."""
    # First check if user is blacklisted - blacklisted users lose ALL moderator privileges
    blacklist_check = is_blacklisted_user(user, config)
    if blacklist_check['blacklisted']:
        return False
    
    moderators = config.get('moderators', {'users': [], 'roles': []})
    
    # Check if user is in moderator users list
    if user.id in moderators.get('users', []):
        return True
    
    # Check if user has any of the moderator roles (only if user has roles attribute)
    if hasattr(user, 'roles') and user.roles:
        user_role_ids = [role.id for role in user.roles]
        moderator_role_ids = moderators.get('roles', [])
        
        if any(role_id in user_role_ids for role_id in moderator_role_ids):
            return True
    
    # Discord administrators have moderator privileges but are handled separately (only if user has guild_permissions)
    if hasattr(user, 'guild_permissions') and user.guild_permissions and user.guild_permissions.administrator:
        return True
    
    return False

def can_moderate_user(moderator, target_user, config):
    """
    Check if a moderator can approve/reject a dismissal report from target_user.
    
    Rules:
    1. Administrators can approve ANY reports (including their own)
    2. Regular moderators cannot approve their own reports
    3. Regular moderators cannot approve reports from other moderators of the same or higher level
    4. Only moderators with higher roles can approve reports from lower-level moderators
    """
    # Check if moderator is a custom administrator (custom administrators can moderate anyone, including themselves)
    if is_administrator(moderator, config):
        return True
    
    # Check if moderator has Discord admin permissions (Discord admins can moderate anyone, including themselves)
    if hasattr(moderator, 'guild_permissions') and moderator.guild_permissions.administrator:
        return True
    
    # Self-moderation is not allowed for regular moderators (but allowed for administrators above)
    if moderator.id == target_user.id:
        return False
    
    # Check if moderator has moderator permissions
    if not is_moderator(moderator, config):
        return False
    
    # Regular moderators cannot moderate administrators
    if is_administrator(target_user, config):
        return False
    
    # Check if target user is a moderator
    if not is_moderator(target_user, config):
        # Target is not a moderator, so any moderator can approve
        return True
    
    # Both are moderators - check hierarchy
    moderator_roles = []
    target_roles = []
    
    # Get moderator roles only if user has roles attribute
    if hasattr(moderator, 'roles') and moderator.roles:
        moderator_roles = [role for role in moderator.roles if role.id in config.get('moderators', {}).get('roles', [])]
    
    # Get target user roles only if user has roles attribute
    if hasattr(target_user, 'roles') and target_user.roles:
        target_roles = [role for role in target_user.roles if role.id in config.get('moderators', {}).get('roles', [])]
    
    if not moderator_roles:
        # Moderator is individual user, not role-based
        # Individual moderators cannot moderate role-based moderators
        return not target_roles
    
    if not target_roles:
        # Target is individual moderator, role-based moderators can moderate them
        return True
    
    # Both have moderator roles - check hierarchy
    max_moderator_position = max(role.position for role in moderator_roles)
    max_target_position = max(role.position for role in target_roles)
    
    return max_moderator_position > max_target_position

def migrate_config(config):
    """Migrate old configuration format to new format."""
    migrated = False
    
    # Migrate old single ping role to new multiple ping roles format
    # Handle legacy 'role_assignment_ping_role' key (used for both military and civilian)
    if 'role_assignment_ping_role' in config:
        old_role = config.get('role_assignment_ping_role')
        if old_role is not None:
            # Migrate to both military and civilian ping roles
            config['military_role_assignment_ping_roles'] = [old_role]
            config['civilian_role_assignment_ping_roles'] = [old_role]
            migrated = True
        del config['role_assignment_ping_role']
    
    # Migrate old separate ping roles to new multiple ping roles format
    if 'military_role_assignment_ping_role' in config:
        old_role = config.get('military_role_assignment_ping_role')
        if old_role is not None:
            config['military_role_assignment_ping_roles'] = [old_role]
            migrated = True
        del config['military_role_assignment_ping_role']
    
    if 'civilian_role_assignment_ping_role' in config:
        old_role = config.get('civilian_role_assignment_ping_role')
        if old_role is not None:
            config['civilian_role_assignment_ping_roles'] = [old_role]
            migrated = True
        del config['civilian_role_assignment_ping_role']
    
    # Migrate old single roles to new multiple roles format
    if 'military_role' in config:
        old_role = config.get('military_role')
        if old_role is not None:
            config['military_roles'] = [old_role]
            migrated = True
        del config['military_role']
    
    if 'civilian_role' in config:
        old_role = config.get('civilian_role')
        if old_role is not None:
            config['civilian_roles'] = [old_role]
            migrated = True
        del config['civilian_role']
    
    # Ensure all new keys exist with proper defaults (including nested structures)
    def merge_defaults(config_dict, default_dict):
        """Recursively merge default values into config"""
        local_migrated = False
        for key, default_value in default_dict.items():
            if key not in config_dict:
                config_dict[key] = default_value
                local_migrated = True
            elif isinstance(default_value, dict) and isinstance(config_dict[key], dict):
                # Recursively merge nested dictionaries
                nested_migrated = merge_defaults(config_dict[key], default_value)
                local_migrated = local_migrated or nested_migrated
        return local_migrated
    
    if merge_defaults(config, default_config):
        migrated = True
    
    return migrated


# ============================================================================
# Recruitment configuration helpers
# ============================================================================


def get_recruitment_config(guild_id: int | None = None) -> Dict[str, Any]:
    """Возвращает настройки приёма с мерджем дефолтов и безопасной очисткой списков."""
    config = load_config()
    defaults = default_config.get('recruitment', {})
    user_cfg = config.get('recruitment', {}) or {}

    merged = defaults.copy()
    merged.update(user_cfg)

    # Безопасно приводим типы
    try:
        merged['default_rank_id'] = int(merged['default_rank_id']) if merged.get('default_rank_id') is not None else None
    except Exception:
        merged['default_rank_id'] = None

    allowed_rank_ids = []
    for rid in merged.get('allowed_rank_ids', []) or []:
        try:
            allowed_rank_ids.append(int(rid))
        except Exception:
            continue
    merged['allowed_rank_ids'] = allowed_rank_ids

    # Заглушки для подразделений
    merged['allow_subdivision_selection'] = False
    merged['default_subdivision_key'] = merged.get('default_subdivision_key', 'ВА') or 'ВА'
    merged['allowed_subdivision_keys'] = merged.get('allowed_subdivision_keys', []) or []

    return merged


async def get_recruitment_ranks(limit: int = 25) -> list[Dict[str, Any]]:
    """Возвращает список рангов для приёма с учётом whitelist и лимита."""
    from utils.database_manager.rank_manager import RankManager

    cfg = get_recruitment_config()
    allowed_ids = cfg.get('allowed_rank_ids') or []

    rank_manager = RankManager()
    ranks = await rank_manager.get_all_active_ranks()

    if allowed_ids:
        ranks = [r for r in ranks if r.get('id') in allowed_ids]

    # Отсортируем по rank_level, затем обрежем лимит
    ranks = sorted(ranks, key=lambda x: x.get('rank_level', 0))[:limit]
    return ranks

def export_config(export_path: str) -> bool:
    """Export current configuration to a specified path."""
    try:
        config = load_config()
        
        # Add metadata to export
        export_data = {
            'exported_at': datetime.datetime.now().isoformat(),
            'version': '1.0',
            'config': config
        }
        
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=4, ensure_ascii=False)
        
        logger.info("Configuration exported to: %s", export_path)
        return True
        
    except Exception as e:
        logger.error("Failed to export configuration: %s", e)
        return False

def import_config(import_path: str) -> bool:
    """Import configuration from a specified path."""
    try:
        with open(import_path, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
        
        # Check if it's an export file with metadata
        if 'config' in import_data and 'exported_at' in import_data:
            config = import_data['config']
            logger.info(f"Importing configuration exported at: {import_data['exported_at']}")
        else:
            # Assume it's a raw config file
            config = import_data
        
        # Create backup before importing
        create_backup("before_import")
        
        # Validate and save the imported config
        return safe_save_config(config)
        
    except Exception as e:
        logger.error("Failed to import configuration: %s", e)
        return False

def get_config_status() -> Dict[str, Any]:
    """Get detailed status of configuration system."""
    status = {
        'config_exists': os.path.exists(CONFIG_FILE),
        'config_size': 0,
        'backup_count': 0,
        'last_backup': None,
        'config_valid': False
    }
    
    try:
        if status['config_exists']:
            status['config_size'] = os.path.getsize(CONFIG_FILE)
            
            # Test if config is valid
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                json.load(f)
            status['config_valid'] = True
        
        backups = list_backups()
        status['backup_count'] = len(backups)
        
        if backups:
            latest_backup = backups[0]
            backup_path = os.path.join(BACKUP_DIR, latest_backup)
            status['last_backup'] = datetime.datetime.fromtimestamp(
                os.path.getmtime(backup_path)
            ).isoformat()
    
    except Exception as e:
        logger.error("Error getting config status: %s", e)
    
    return status

def is_administrator(user, config):
    """Check if a user has administrator permissions."""
    
    administrators = config.get('administrators', {'users': [], 'roles': []})
    
    # Check if user is in administrator users list
    if user.id in administrators.get('users', []):
        return True
    
    # Check if user has any of the administrator roles (only if user has roles attribute)
    if hasattr(user, 'roles') and user.roles:
        user_role_ids = [role.id for role in user.roles]
        administrator_role_ids = administrators.get('roles', [])
        
        if any(role_id in user_role_ids for role_id in administrator_role_ids):
            return True
    
    # Discord administrators are always considered administrators (only if user has guild_permissions)
    if hasattr(user, 'guild_permissions') and user.guild_permissions and user.guild_permissions.administrator:
        return True
    
    return False

def is_moderator_or_admin(user, config):
    """Check if a user has moderator or administrator permissions."""
    # Administrators have all moderator privileges plus more
    if is_administrator(user, config):
        return True
    
    # Check regular moderator permissions
    return is_moderator(user, config)

def is_blacklisted_user(user, config, module=None):
    """
    Check if user is blacklisted.
    
    Args:
        user: Discord user object
        config: Bot configuration
        module: (deprecated) - ignored for backward compatibility
    
    Returns:
        dict: {
            'blacklisted': bool,
            'reason': str or None
        }
    """
    blacklist = config.get('blacklist', {'users': [], 'roles': []})
    
    # Check if user is in blacklist
    user_blacklisted = user.id in blacklist.get('users', [])
    
    # Check if user has blacklisted role
    role_blacklisted = False
    if hasattr(user, 'roles') and user.roles:
        user_role_ids = [role.id for role in user.roles]
        blacklisted_role_ids = blacklist.get('roles', [])
        role_blacklisted = any(role_id in user_role_ids for role_id in blacklisted_role_ids)
    
    is_blacklisted = user_blacklisted or role_blacklisted
    
    result = {
        'blacklisted': is_blacklisted,
        'reason': None
    }
    
    if not is_blacklisted:
        return result
    
    # Determine reason
    if user_blacklisted:
        result['reason'] = f"Пользователь {user.display_name} в чёрном списке"
    elif role_blacklisted:
        blacklisted_roles = [role for role in user.roles if role.id in blacklisted_role_ids]
        result['reason'] = f"Роль '{blacklisted_roles[0].name}' в чёрном списке"
    
    return result

async def has_pending_dismissal_report(bot, user_id, dismissal_channel_id):
    """
    Проверка наличия у пользователя незавершённого (pending) рапорта на увольнение.
    Совместима с новым форматом сообщений (embed title/description) и старым контентом.
    Возвращает True, если рапорт найден и он ещё не обработан; иначе False.
    """
    if not dismissal_channel_id:
        return False
    
    try:
        channel = bot.get_channel(dismissal_channel_id)
        if not channel:
            return False
        
        # Проверяем последние 100 сообщений в канале
        async for message in channel.history(limit=100):
            if message.author != bot.user:
                continue
            
            has_embeds = bool(message.embeds)
            embed = message.embeds[0] if has_embeds else None
            content = message.content or ""
            
            # Определяем, что сообщение — рапорт на увольнение
            is_dismissal_report = False
            if embed:
                title = (embed.title or "")
                desc = (embed.description or "")
                if "Рапорт на увольнение" in title:
                    is_dismissal_report = True
                elif ("подал рапорт на увольнение!" in desc) or ("Отправитель" in desc):
                    is_dismissal_report = True
            
            # Fallback: старый формат — фраза в content
            if not is_dismissal_report and content:
                if "Новый рапорт на увольнение" in content:
                    is_dismissal_report = True
            
            if not is_dismissal_report:
                continue
            
            # Проверяем, что этот рапорт принадлежит конкретному пользователю
            user_mention = f"<@{user_id}>"
            mention_in_embed = bool(embed and embed.description and user_mention in embed.description)
            mention_in_content = user_mention in content
            if not (mention_in_embed or mention_in_content):
                continue
            
            # Определяем, обработан ли рапорт
            status_pending = True
            if embed and embed.fields:
                for field in embed.fields:
                    name = (field.name or "")
                    # Считаем обработанным, если есть поле "Обработано" или "Отказано"
                    if (
                        "Обработано" in name or
                        "✅ Обработано" in name or
                        "Отказано" in name or
                        "❌ Отказано" in name or
                        "Approved" in name or
                        "Rejected" in name
                    ):
                        status_pending = False
                        break
            
            if status_pending:
                return True
        
        return False
    except Exception as e:
        logger.error("Error checking pending dismissal reports: %s", e)
        return False

async def has_pending_role_application(bot, user_id, role_assignment_channel_id):
    """
    Check if user has a pending role application (not yet processed).
    Returns True if user has pending application, False otherwise.
    """
    if not role_assignment_channel_id:
        return False
        
    try:
        channel = bot.get_channel(role_assignment_channel_id)
        if not channel:
            return False
            
        # Search through recent messages (last 100)
        async for message in channel.history(limit=100):
            # Check if message is from bot and has role application embed
            if (message.author == bot.user and 
                message.embeds and
                len(message.embeds) > 0):
                
                embed = message.embeds[0]
                if not embed.title or "Заявка на получение роли" not in embed.title:
                    continue
                
                # Check if this application is from the specific user
                user_mention = f"<@{user_id}>"
                for field in embed.fields:
                    if field.name == "👤 Заявитель" and user_mention in field.value:
                        # Check if application is still pending (no status field)
                        status_pending = True
                        for status_field in embed.fields:
                            if status_field.name in ["✅ Статус", "❌ Статус"]:
                                status_pending = False
                                break
                        
                        if status_pending:
                            return True
                            
        return False
        
    except Exception as e:
        logger.error("Error checking pending role applications: %s", e)
        return False

def save_role_assignment_message_id(message_id: int):
    """Save the ID of the role assignment message with buttons"""
    try:
        config = load_config()
        config['role_assignment_message_id'] = message_id
        save_config(config)
        logger.info("Saved role assignment message ID: %s", message_id)
        return True
    except Exception as e:
        logger.error("Error saving role assignment message ID: %s", e)
        return False

def get_role_assignment_message_link(guild_id: int):
    """Get the direct link to the role assignment message"""
    try:
        config = load_config()
        message_id = config.get('role_assignment_message_id')
        channel_id = config.get('role_assignment_channel')
        
        if message_id and channel_id:
            return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
        return None
    except Exception as e:
        logger.error("Error getting role assignment message link: %s", e)
        return None

def save_dismissal_message_id(message_id: int):
    """Save the ID of the dismissal message with buttons"""
    try:
        config = load_config()
        config['dismissal_message_id'] = message_id
        save_config(config)
        logger.info("Saved dismissal message ID: %s", message_id)
        return True
    except Exception as e:
        logger.error("Error saving dismissal message ID: %s", e)
        return False

def get_dismissal_message_link(guild_id: int):
    """Get the direct link to the dismissal message"""
    try:
        config = load_config()
        message_id = config.get('dismissal_message_id')
        channel_id = config.get('dismissal_channel')
        
        if message_id and channel_id:
            return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
        return None
    except Exception as e:
        logger.error("Error getting dismissal message link: %s", e)
        return None

def get_default_warehouse_limits():
    """Получить лимиты по умолчанию на основе приказа № 256"""
    return {
        # Силы Специальных Операций
        "Оперативник ССО": {
            "оружие": 3,
            "бронежилеты": 15,
            "аптечки": 20,
            "обезболивающее": 8,
            "дефибрилляторы": 4,
            "weapon_restrictions": []
        },
        
        # Рота Охраны и Обеспечения
        "Старший сотрудник охраны": {
            "оружие": 3,
            "бронежилеты": 15,
            "аптечки": 20,
            "обезболивающее": 8,
            "дефибрилляторы": 0,
            "weapon_restrictions": []
        },
        "Сотрудник охраны": {
            "оружие": 3,
            "бронежилеты": 15,
            "аптечки": 10,
            "обезболивающее": 6,
            "дефибрилляторы": 0,
            "weapon_restrictions": ["Кольт М16", "Кольт 416 Канада", "ФН СКАР-Т", "Штейр АУГ-А3", "Таурус Бешеный бык"]
        },
        "Младший сотрудник охраны": {
            "оружие": 3,
            "бронежилеты": 5,
            "аптечки": 5,
            "обезболивающее": 4,
            "дефибрилляторы": 0,
            "weapon_restrictions": ["Кольт М16", "Кольт 416 Канада", "ФН СКАР-Т", "Штейр АУГ-А3", "Таурус Бешеный бык"]
        },
        
        # Медицинская рота
        "Военный врач": {
            "оружие": 2,
            "бронежилеты": 15,
            "аптечки": 20,
            "обезболивающее": 8,
            "дефибрилляторы": 4,
            "weapon_restrictions": []
        },
        "Помощник врача": {
            "оружие": 3,
            "бронежилеты": 5,
            "аптечки": 20,
            "обезболивающее": 8,
            "дефибрилляторы": 3,
            "weapon_restrictions": ["Кольт М16", "Кольт 416 Канада", "ФН СКАР-Т", "Штейр АУГ-А3", "Таурус Бешеный бык"]
        },
        
        # Военная полиция
        "Старший инспектор ВП": {
            "оружие": 2,
            "бронежилеты": 15,
            "аптечки": 20,
            "обезболивающее": 6,
            "дефибрилляторы": 2,
            "weapon_restrictions": []
        },
        "Дознаватель ВП": {
            "оружие": 2,
            "бронежилеты": 15,
            "аптечки": 10,
            "обезболивающее": 4,
            "дефибрилляторы": 2,
            "weapon_restrictions": ["Кольт М16", "Кольт 416 Канада", "ФН СКАР-Т", "Штейр АУГ-А3", "Таурус Бешеный бык"]
        },
        "Инспектор ВП": {
            "оружие": 2,
            "бронежилеты": 5,
            "аптечки": 10,
            "обезболивающее": 4,
            "дефибрилляторы": 1,
            "weapon_restrictions": ["Кольт М16", "Кольт 416 Канада", "ФН СКАР-Т", "Штейр АУГ-А3", "Таурус Бешеный бык"]
        },
        
        # Военный Комиссариат
        "Старший инструктор": {
            "оружие": 2,
            "бронежилеты": 5,
            "аптечки": 10,
            "обезболивающее": 4,
            "дефибрилляторы": 0,
            "weapon_restrictions": ["Кольт М16", "Кольт 416 Канада", "ФН СКАР-Т", "Штейр АУГ-А3", "Таурус Бешеный бык"]
        }
    }


def get_default_warehouse_ranks_limits():
    """Получить базовые лимиты по званиям с актуальными названиями из БД"""
    try:
        # Попробуем получить актуальные названия рангов из БД
        from utils.postgresql_pool import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute("SELECT name FROM ranks ORDER BY rank_level;")
            db_ranks = [row['name'] for row in cursor.fetchall()]
    except Exception:
        # Если БД недоступна, используем стандартные названия
        db_ranks = []

    # Базовые лимиты - используем названия из БД если доступны
    limits = {}

    # Рядовой состав
    if "Рядовой" in db_ranks or not db_ranks:
        limits["Рядовой"] = {
            "оружие": 2,
            "бронежилеты": 5,
            "аптечки": 10,
            "обезболивающее": 4,
            "дефибрилляторы": 0,
            "weapon_restrictions": ["Кольт М16", "АК-74М"]
        }

    if "Ефрейтор" in db_ranks or not db_ranks:
        limits["Ефрейтор"] = {
            "оружие": 2,
            "бронежилеты": 5,
            "аптечки": 10,
            "обезболивающее": 4,
            "дефибрилляторы": 0,
            "weapon_restrictions": ["Кольт М16", "АК-74М", "Кольт 416 Канада"]
        }

    # Сержантский состав
    if "Мл. Сержант" in db_ranks or not db_ranks:
        limits["Мл. Сержант"] = {
            "оружие": 3,
            "бронежилеты": 8,
            "аптечки": 15,
            "обезболивающее": 6,
            "дефибрилляторы": 1,
            "weapon_restrictions": []
        }

    if "Сержант" in db_ranks or not db_ranks:
        limits["Сержант"] = {
            "оружие": 3,
            "бронежилеты": 8,
            "аптечки": 15,
            "обезболивающее": 6,
            "дефибрилляторы": 1,
            "weapon_restrictions": []
        }

    if "Ст. Сержант" in db_ranks or not db_ranks:
        limits["Ст. Сержант"] = {
            "оружие": 3,
            "бронежилеты": 15,
            "аптечки": 20,
            "обезболивающее": 8,
            "дефибрилляторы": 2,
            "weapon_restrictions": []
        }

    if "Старшина" in db_ranks or not db_ranks:
        limits["Старшина"] = {
            "оружие": 3,
            "бронежилеты": 15,
            "аптечки": 20,
            "обезболивающее": 8,
            "дефибрилляторы": 2,
            "weapon_restrictions": []
        }

    # Прапорщики
    if "Прапорщик" in db_ranks or not db_ranks:
        limits["Прапорщик"] = {
            "оружие": 3,
            "бронежилеты": 15,
            "аптечки": 20,
            "обезболивающее": 8,
            "дефибрилляторы": 3,
            "weapon_restrictions": []
        }

    if "Ст. Прапорщик" in db_ranks or not db_ranks:
        limits["Ст. Прапорщик"] = {
            "оружие": 3,
            "бронежилеты": 15,
            "аптечки": 20,
            "обезболивающее": 8,
            "дефибрилляторы": 3,
            "weapon_restrictions": []
        }

    # Офицерский состав - используем базовые лимиты для всех
    officer_ranks = ["Мл. Лейтенант", "Лейтенант", "Ст. Лейтенант", "Капитан", "Майор", "Подполковник", "Полковник", "Генерал-майор", "Генерал-лейтенант", "Генерал-полковник", "Генерал Армии"]
    for rank in officer_ranks:
        if rank in db_ranks or not db_ranks:
            limits[rank] = {
                "оружие": 3,
                "бронежилеты": 15,
                "аптечки": 20,
                "обезболивающее": 8,
                "дефибрилляторы": 4,
                "weapon_restrictions": []
            }

    return limits


def initialize_warehouse_limits():
    """Инициализировать лимиты склада при первом использовании"""
    config = load_config()

    # Инициализировать лимиты по должностям, если они пусты
    if not config.get('warehouse_limits_positions'):
        config['warehouse_limits_positions'] = get_default_warehouse_limits()
        logger.info("Инициализированы лимиты склада по должностям")

    # Инициализировать лимиты по званиям, если они пусты
    if not config.get('warehouse_limits_ranks'):
        config['warehouse_limits_ranks'] = get_default_warehouse_ranks_limits()
        logger.info("Инициализированы лимиты склада по званиям")

    save_config(config)
    return config


def ensure_warehouse_config():
    """Убедиться что конфигурация склада полная"""
    config = load_config()
    updated = False
      # Проверить наличие всех необходимых полей
    if 'warehouse_request_channel' not in config:
        config['warehouse_request_channel'] = None
        updated = True
    
    if 'warehouse_audit_channel' not in config:
        config['warehouse_audit_channel'] = None
        updated = True
    
    if 'warehouse_submission_channel' not in config:
        config['warehouse_submission_channel'] = None
        updated = True
    
    if 'warehouse_cooldown_hours' not in config:
        config['warehouse_cooldown_hours'] = 6
        updated = True
    
    if 'warehouse_limits_mode' not in config:
        config['warehouse_limits_mode'] = {
            'positions_enabled': True,
            'ranks_enabled': False
        }
        updated = True
    
    if 'warehouse_limits_positions' not in config:
        config['warehouse_limits_positions'] = {}
        updated = True

    if 'warehouse_limits_ranks' not in config:
        config['warehouse_limits_ranks'] = {}
        updated = True
    
    if updated:
        save_config(config)
        logger.info("Конфигурация склада обновлена")
    
    return config

# Messages system integration
def get_messages_status() -> Dict[str, Any]:
    """Get status of messages system (wrapper for message_manager)"""
    try:
        from utils.message_manager import get_messages_status
        return get_messages_status()
    except ImportError:
        return {
            'messages_dir_exists': False,
            'default_messages_exists': False,
            'guild_specific_files': 0,
            'backup_count': 0,
            'cache_size': 0,
            'error': 'message_manager not available'
        }
    except Exception as e:
        return {
            'messages_dir_exists': False,
            'default_messages_exists': False,
            'guild_specific_files': 0,
            'backup_count': 0,
            'cache_size': 0,
            'error': str(e)
        }