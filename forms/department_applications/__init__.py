"""
Department Applications Module - System for department applications with moderation
"""

from .manager import DepartmentApplicationManager
from .views import DepartmentApplicationView, DepartmentSelectView
from .modals import DepartmentApplicationModal

__all__ = [
    'DepartmentApplicationManager',
    'DepartmentApplicationView', 
    'DepartmentSelectView',
    'DepartmentApplicationModal'
]
