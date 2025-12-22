"""
Test the new PositionService
Тестирование нового сервиса управления должностями
"""

import sys
import os
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

def test_position_service():
    """Test position service functionality"""
    logger.info("Testing PositionService...")

    try:
        from utils.database_manager import position_service

        # Test getting positions for subdivision (should work even if empty)
        positions = position_service.get_positions_for_subdivision(1)
        logger.info(f"get_positions_for_subdivision(1) returned {len(positions)} positions")

        # Test getting all positions with subdivisions
        all_positions = position_service.get_all_positions_with_subdivisions()
        logger.info(f"get_all_positions_with_subdivisions() returned {len(all_positions)} positions")

        # Test validation
        # Test valid name
        is_valid, msg = position_service.validate_position_name("Тестовая должность")
        logger.info("Name validation: %s - %s", is_valid, msg)

        # Test invalid name (empty)
        is_valid, msg = position_service.validate_position_name("")
        logger.info("Empty name validation: %s - %s", not is_valid, msg)

        logger.info("PositionService tests completed successfully!")
        return True

    except Exception as e:
        logger.warning("PositionService test failed: %s", e)
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_position_service()