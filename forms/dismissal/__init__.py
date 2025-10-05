"""
Dismissal system - Modular structure

This package contains all dismissal-related functionality split into logical modules:
- modals.py: Modal forms (SimplifiedDismissalModal, StaticRequestModal, RejectionReasonModal)
- views.py: Interactive components (DismissalApprovalView, DismissalReportButton)  
- automatic.py: Automatic dismissal handling
- utils.py: Message utilities and view restoration

All components are re-exported here for backward compatibility.
"""

# Import all modals
from .modals import (
    StaticRequestModal,
    SimplifiedDismissalModal,
    RejectionReasonModal,
    AutomaticDismissalEditModal
)

# Import all views
from .views import (
    DismissalReportButton,
    SimplifiedDismissalApprovalView,
    AutomaticDismissalApprovalView,
    DeletionConfirmationView
)

# Import automatic dismissal functions
from .automatic import (
    create_automatic_dismissal_report,
    should_create_automatic_dismissal
)

# Import utility functions
from .utils import (
    send_dismissal_button_message,
    restore_dismissal_approval_views,
    restore_dismissal_button_views
)

# Export everything for backward compatibility
__all__ = [
    # Modals
    'StaticRequestModal',
    'SimplifiedDismissalModal',
    'RejectionReasonModal',
    'AutomaticDismissalEditModal',
    
    # Views
    'DismissalReportButton',
    'SimplifiedDismissalApprovalView',
    'AutomaticDismissalApprovalView',
    'DeletionConfirmationView',
    
    # Automatic dismissal functions
    'create_automatic_dismissal_report',
    'should_create_automatic_dismissal',
    
    # Utility functions
    'send_dismissal_button_message',
    'restore_dismissal_approval_views',
    'restore_dismissal_button_views'
]
