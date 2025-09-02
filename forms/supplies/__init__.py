"""
Система управления поставками военных объектов
"""

from .supplies_control_view import SuppliesControlView
from .supplies_subscription_view import SuppliesSubscriptionView
from .supplies_manager import SuppliesManager

__all__ = [
    'SuppliesControlView',
    'SuppliesSubscriptionView', 
    'SuppliesManager'
]
