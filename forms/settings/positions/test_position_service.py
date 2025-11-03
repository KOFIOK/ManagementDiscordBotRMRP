"""
Test the new PositionService
Тестирование нового сервиса управления должностями
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

def test_position_service():
    """Test position service functionality"""
    print("🧪 Testing PositionService...")

    try:
        from utils.database_manager import position_service

        # Test getting positions for subdivision (should work even if empty)
        positions = position_service.get_positions_for_subdivision(1)
        print(f"✅ get_positions_for_subdivision(1) returned {len(positions)} positions")

        # Test getting all positions with subdivisions
        all_positions = position_service.get_all_positions_with_subdivisions()
        print(f"✅ get_all_positions_with_subdivisions() returned {len(all_positions)} positions")

        # Test validation
        from forms.settings.positions.validation import PositionValidator

        # Test valid name
        is_valid, msg = PositionValidator.validate_position_name("Тестовая должность")
        print(f"✅ Name validation: {is_valid} - {msg}")

        # Test invalid name (empty)
        is_valid, msg = PositionValidator.validate_position_name("")
        print(f"✅ Empty name validation: {not is_valid} - {msg}")

        print("✅ PositionService tests completed successfully!")
        return True

    except Exception as e:
        print(f"❌ PositionService test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_position_service()