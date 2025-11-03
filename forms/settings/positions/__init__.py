"""
New Position Management System
Иерархическая система управления должностями с пагинацией
"""

from .navigation import PositionNavigationView
from .management import PositionManagementView
from .search import PositionSearchView
from .detailed_management import PositionDetailedView
from .ui_components import create_position_embed, create_paginated_embed
from .validation import PositionValidator

__all__ = [
    'PositionNavigationView',
    'PositionManagementView',
    'PositionSearchView',
    'PositionDetailedView',
    'create_position_embed',
    'create_paginated_embed',
    'PositionValidator'
]