"""
Role Assignment System Module

This module provides a complete role assignment system for Discord bots,
including military and civilian role applications with moderation workflow.
"""

from .base import get_channel_with_fallback, create_approval_view
from .views import RoleAssignmentView, ApprovedApplicationView, RejectedApplicationView
from .modals import MilitaryApplicationModal, CivilianApplicationModal, SupplierApplicationModal
from .approval import RoleApplicationApprovalView
from .utils import send_role_assignment_message, restore_role_assignment_views, restore_approval_views

__all__ = [
    'get_channel_with_fallback',
    'create_approval_view',
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
