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
    RoleApplicationApprovalView,
    send_role_assignment_message,
    restore_role_assignment_views,
    restore_approval_views
)

# Re-export everything for backward compatibility
__all__ = [
    'get_channel_with_fallback',
    'RoleAssignmentView',
    'ApprovedApplicationView', 
    'RejectedApplicationView',
    'MilitaryApplicationModal',
    'SupplierApplicationModal',
    'CivilianApplicationModal',
    'RoleApplicationApprovalView',
    'send_role_assignment_message',
    'restore_role_assignment_views',
    'restore_approval_views'
]