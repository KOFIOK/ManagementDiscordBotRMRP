"""
Role Assignment System - Simplified Interface

This is a simplified interface that imports the modular role assignment system.
The system has been refactored to solve interaction handling issues.
"""

# Import all components from the modular system
from .role_assignment import (
    get_channel_with_fallback,
    RoleAssignmentView,
    ApprovedApplicationView, 
    RejectedApplicationView,
    MilitaryApplicationModal,
    SupplierApplicationModal,
    CivilianApplicationModal,
    MilitaryEditModal,
    CivilianEditModal,
    SupplierEditModal,
    RoleApplicationApprovalView,
    send_role_assignment_message,
    restore_role_assignment_views,
    restore_approval_views
)

# Create alias for backward compatibility
send_role_assignment_button_message = send_role_assignment_message

# Re-export everything for backward compatibility
__all__ = [
    'get_channel_with_fallback',
    'RoleAssignmentView',
    'ApprovedApplicationView', 
    'RejectedApplicationView',
    'MilitaryApplicationModal',
    'SupplierApplicationModal',
    'CivilianApplicationModal',
    'MilitaryEditModal',
    'CivilianEditModal',
    'SupplierEditModal',
    'RoleApplicationApprovalView',
    'send_role_assignment_message',
    'send_role_assignment_button_message',  # Alias for backward compatibility
    'restore_role_assignment_views',
    'restore_approval_views'
]