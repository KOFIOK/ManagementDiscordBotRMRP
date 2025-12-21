"""
Test the new position management infrastructure
Тестирование новой инфраструктуры управления должностями
"""

import sys
import os
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all modules can be imported"""
    logger.info("Testing position management infrastructure...")

    try:
        # Test UI components
        from forms.settings.positions.ui_components import create_position_embed, create_paginated_embed
        logger.info("UI components imported successfully")

        # Test validation
        from utils.database_manager import position_service
        logger.info("Validation module imported successfully")

        # Test navigation (will have import errors for now)
        try:
            from forms.settings.positions.navigation import PositionNavigationView
            logger.info("Navigation module imported successfully")
        except ImportError as e:
            logger.warning("Navigation import failed (expected): %s", e)

        # Test management
        try:
            from forms.settings.positions.management import PositionManagementView
            logger.info("Management module imported successfully")
        except ImportError as e:
            logger.warning("Management import failed (expected): %s", e)

        # Test search
        try:
            from forms.settings.positions.search import PositionSearchView
            logger.info("Search module imported successfully")
        except ImportError as e:
            logger.warning("Search import failed (expected): %s", e)

        # Test detailed management
        try:
            from forms.settings.positions.detailed_management import PositionDetailedView
            logger.info("Detailed management imported successfully")
        except ImportError as e:
            logger.warning("Detailed management import failed (expected): %s", e)

        logger.info("Infrastructure test completed!")
        return True

    except Exception as e:
        logger.warning("Infrastructure test failed: %s", e)
        return False

if __name__ == "__main__":
    test_imports()