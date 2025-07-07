"""
Safe Documents System

Система подачи и модерации документов в сейф.
Включает автозаполнение, persistent views, модерацию и редактирование.
"""

from .views import SafeDocumentsPinView, SafeDocumentsApplicationView, SafeDocumentsApprovedView, SafeDocumentsRejectedView
from .modals import SafeDocumentsModal, SafeDocumentsRejectionModal, SafeDocumentsEditModal
from .manager import SafeDocumentsManager, ensure_safe_documents_pin_message, setup_safe_documents_system

__all__ = [
    'SafeDocumentsPinView',
    'SafeDocumentsApplicationView',
    'SafeDocumentsApprovedView', 
    'SafeDocumentsRejectedView',
    'SafeDocumentsModal',
    'SafeDocumentsRejectionModal',
    'SafeDocumentsEditModal',
    'SafeDocumentsManager',
    'ensure_safe_documents_pin_message',
    'setup_safe_documents_system'
]
