"""
DEPRECATED: utils.ping_adapter has been removed.

Use utils.ping_manager instead.

Examples:
- from utils.ping_manager import ping_manager
- ping_manager.get_user_department_code(user)
- ping_manager.get_ping_roles_for_user(user, 'leave_requests')
"""

raise ImportError(
    "utils.ping_adapter has been removed. Migrate to utils.ping_manager (use ping_manager.get_ping_roles_for_user and related APIs)."
)
