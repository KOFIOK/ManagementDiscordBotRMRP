"""
Dismissal system - Modular structure

This package contains all dismissal-related functionality split into logical modules:
- modals.py: Modal forms (StaticRequestModal, DismissalReportModal)
- views.py: Interactive components (DismissalApprovalView, DismissalReportButton)  
- automatic.py: Automatic dismissal handling
- utils.py: Message utilities and view restoration

All components are re-exported here for backward compatibility.
"""

# Import all modals
from .modals import (
    StaticRequestModal,
    DismissalReportModal
)

# Import all views
from .views import (
    DismissalApprovalView,
    DismissalReportButton,
    AutomaticDismissalApprovalView
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
    'DismissalReportModal',
      # Views
    'DismissalApprovalView', 
    'DismissalReportButton',
    'AutomaticDismissalApprovalView',
    
    # Automatic dismissal functions
    'create_automatic_dismissal_report',
    'should_create_automatic_dismissal',
    
    # Utility functions
    'send_dismissal_button_message',
    'restore_dismissal_approval_views',
    'restore_dismissal_button_views'
]
