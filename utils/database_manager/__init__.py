"""
Database Manager Module

Comprehensive database management for PostgreSQL integration.
This module handles personnel records, employee assignments, and role approval workflow.
"""

from .manager import PersonnelManager, personnel_manager
from .department import DepartmentOperations
from .subdivision_mapper import SubdivisionMapper
from .rank_manager import RankManager, rank_manager

__all__ = ['PersonnelManager', 'personnel_manager', 'DepartmentOperations', 'SubdivisionMapper', 'RankManager', 'rank_manager']
