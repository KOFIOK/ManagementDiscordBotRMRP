"""
Database Manager Module

Comprehensive database management for PostgreSQL integration.
This module handles personnel records, employee assignments, and role approval workflow.
"""

from .manager import PersonnelManager, personnel_manager
from .department import DepartmentOperations
from .rank_manager import RankManager, rank_manager
from .position_manager import PositionManager, position_manager
from .position_service import PositionService, position_service

__all__ = ['PersonnelManager', 'personnel_manager', 'DepartmentOperations', 'RankManager', 'rank_manager', 'PositionManager', 'position_manager', 'PositionService', 'position_service']
