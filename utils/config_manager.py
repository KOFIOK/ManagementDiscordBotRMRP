import os
import json

# Configuration file to store channel IDs
CONFIG_FILE = 'data/config.json'

# Default configuration
default_config = {
    'dismissal_channel': None,
    'audit_channel': None,
    'blacklist_channel': None,
    'role_assignment_channel': None,
    'military_role': None,
    'civilian_role': None,
    'additional_military_roles': [],  # Additional roles for military personnel
    'role_assignment_ping_role': None,  # Role to ping when new role assignment submitted
    'excluded_roles': [],
    'ping_settings': {},
    'moderators': {
        'users': [],
        'roles': []
    }
}

# Load configuration
def load_config():
    """Load configuration from JSON file."""
    try:
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Create default config file if it doesn't exist
        save_config(default_config)
        return default_config.copy()

# Save configuration
def save_config(config):
    """Save configuration to JSON file."""
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def is_moderator(user, config):
    """Check if a user has moderator permissions."""
    moderators = config.get('moderators', {'users': [], 'roles': []})
    
    # Check if user is in moderator users list
    if user.id in moderators.get('users', []):
        return True
    
    # Check if user has any of the moderator roles
    user_role_ids = [role.id for role in user.roles]
    moderator_role_ids = moderators.get('roles', [])
    
    if any(role_id in user_role_ids for role_id in moderator_role_ids):
        return True
    
    # Check if user is administrator (admins can always moderate)
    if user.guild_permissions.administrator:
        return True
    
    return False

def can_moderate_user(moderator, target_user, config):
    """
    Check if a moderator can approve/reject a dismissal report from target_user.
    
    Rules:
    1. Moderators cannot approve their own reports
    2. Moderators cannot approve reports from other moderators of the same or higher level
    3. Only moderators with higher roles can approve reports from lower-level moderators
    4. Administrators can approve any reports
    """
    # Self-moderation is not allowed
    if moderator.id == target_user.id:
        return False
    
    # Check if moderator has admin permissions (admins can moderate anyone)
    if moderator.guild_permissions.administrator:
        return True
    
    # Check if moderator has moderator permissions
    if not is_moderator(moderator, config):
        return False
    
    # Check if target user is a moderator
    if not is_moderator(target_user, config):
        # Target is not a moderator, so any moderator can approve
        return True
      # Both are moderators - check hierarchy
    moderators = config.get('moderators', {'users': [], 'roles': []})
    moderator_role_ids = moderators.get('roles', [])
    moderator_user_ids = moderators.get('users', [])
    
    # Check if moderator is a special user-based moderator
    moderator_is_user_based = moderator.id in moderator_user_ids
    target_is_user_based = target_user.id in moderator_user_ids
    
    # Get moderator's highest moderator role position
    moderator_highest_position = -1
    for role in moderator.roles:
        if role.id in moderator_role_ids:
            if role.position > moderator_highest_position:
                moderator_highest_position = role.position
    
    # Get target user's highest moderator role position
    target_highest_position = -1
    for role in target_user.roles:
        if role.id in moderator_role_ids:
            if role.position > target_highest_position:
                target_highest_position = role.position
    
    # Special cases for user-based moderators:
    # 1. If moderator is user-based and target is role-based, user-based can moderate
    # 2. If both are user-based, neither can moderate the other
    # 3. If moderator is role-based and target is user-based, role-based cannot moderate
    if moderator_is_user_based and target_is_user_based:
        # Both are user-based moderators - neither can moderate the other
        return False
    elif moderator_is_user_based and not target_is_user_based:
        # User-based moderator can approve role-based moderator reports
        return True
    elif not moderator_is_user_based and target_is_user_based:
        # Role-based moderator cannot approve user-based moderator reports
        return False
    
    # Both are role-based moderators - check hierarchy by role position
    return moderator_highest_position > target_highest_position
