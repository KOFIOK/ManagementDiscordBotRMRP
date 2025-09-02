"""
Personnel Context Menu System
Context menu commands for personnel management (right-click on users)
"""

from .commands import setup_context_commands
from .rank_utils import RankHierarchy

__all__ = ['setup_context_commands', 'RankHierarchy']
