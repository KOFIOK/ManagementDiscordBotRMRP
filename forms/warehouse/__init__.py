"""
Модули для системы склада
Включает в себя формы запросов, модерацию, редактирование и аудит
"""

# Импорты основных классов для совместимости
from .persistent_views import (
    WarehousePersistentRequestView,
    WarehousePersistentMultiRequestView
)
from .cart import (
    WarehouseRequestCart,
    WarehouseRequestItem,
    get_user_cart,
    clear_user_cart,
    clear_user_cart_safe,
    get_user_cart_message,
    set_user_cart_message
)
from .modals import (
    WarehouseRequestModal,
    WarehouseQuantityModal,
    WarehouseFinalDetailsModal,
    WarehouseCustomItemModal,
    RemoveItemByNumberModal
)
from .views import (
    WarehouseCategorySelect,
    WarehouseItemSelectView,
    WarehousePinMessageView,
    WarehouseCartView,
    ConfirmClearCartView,
    WarehouseSubmittedView
)
from .edit import (
    WarehouseEditSelectView,
    WarehouseEditSelect,
    WarehouseEditActionView,
    WarehouseEditQuantityModal
)
from .status import (
    WarehouseStatusView,
    DeletionConfirmView,
    RejectionReasonModal
)
from .audit import *  # Импорт из warehouse_audit.py

__all__ = [
    # Persistent Views
    'WarehousePersistentRequestView',
    'WarehousePersistentMultiRequestView',
    
    # Cart Management
    'WarehouseRequestCart',
    'WarehouseRequestItem',
    'get_user_cart',
    'clear_user_cart',
    'clear_user_cart_safe',
    'get_user_cart_message',
    'set_user_cart_message',
    
    # Modals
    'WarehouseRequestModal',
    'WarehouseQuantityModal',
    'WarehouseFinalDetailsModal',
    'WarehouseCustomItemModal',
    'RemoveItemByNumberModal',
    
    # Views
    'WarehouseCategorySelect',
    'WarehouseItemSelectView',
    'WarehousePinMessageView',
    'WarehouseCartView',
    'ConfirmClearCartView',
    'WarehouseSubmittedView',
    
    # Edit System
    'WarehouseEditSelectView',
    'WarehouseEditSelect',
    'WarehouseEditActionView',
    'WarehouseEditQuantityModal',
    
    # Status Views
    'WarehouseStatusView',
    'DeletionConfirmView',
    'RejectionReasonModal',
]
