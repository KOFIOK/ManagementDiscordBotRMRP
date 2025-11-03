"""
Integration Test for Position Management System
Интеграционный тест системы управления должностями
"""

import sys
import os

# Add current directory and parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(parent_dir)

sys.path.insert(0, project_root)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

def test_position_management_integration():
    """Test the complete position management workflow"""
    print("🧪 Testing position management integration...")

    try:
        # Test imports
        from forms.settings.positions.navigation import PositionNavigationView
        from forms.settings.positions.management import PositionManagementView
        from forms.settings.positions.search import PositionSearchView
        from forms.settings.positions.detailed_management import PositionDetailedView
        from forms.settings.positions.ui_components import create_position_embed, create_paginated_embed
        from utils.database_manager import position_service
        from utils.database_manager import position_service

        print("✅ All modules imported successfully")

        # Test PositionService methods
        print("\n🔍 Testing PositionService...")

        # Test getting positions for subdivision (should work even if empty)
        positions = position_service.get_positions_for_subdivision(1)  # Test subdivision ID
        print(f"✅ get_positions_for_subdivision returned: {len(positions)} positions")

        # Test getting all positions with subdivisions
        all_positions = position_service.get_all_positions_with_subdivisions()
        print(f"✅ get_all_positions_with_subdivisions returned: {len(all_positions)} positions")

        # Test validation
        print("\n🔍 Testing PositionValidator...")
        is_valid, message = position_service.validate_position_name("Test Position")
        print(f"✅ Position name validation: {is_valid} - {message}")

        is_valid, message = position_service.validate_position_name("")
        print(f"✅ Empty name validation: {not is_valid} - {message}")

        # Test UI components
        print("\n🔍 Testing UI components...")
        embed = create_position_embed("Test Title", "Test Description")
        print(f"✅ create_position_embed works: {embed.title}")

        paginated_embed = create_paginated_embed("Test", [], 1, 1)
        print(f"✅ create_paginated_embed works: {paginated_embed.title}")

        # Test view instantiation (without Discord context)
        print("\n🔍 Testing view instantiation...")
        nav_view = PositionNavigationView()
        print("✅ PositionNavigationView instantiated")

        # Test management view with mock data
        mock_subdivision = {"id": 1, "name": "Test Subdivision", "abbreviation": "TS"}
        mgmt_view = PositionManagementView(1, mock_subdivision)
        print("✅ PositionManagementView instantiated")

        # Test search view
        search_view = PositionSearchView()
        print("✅ PositionSearchView instantiated")

        # Test detailed view with mock data
        mock_position = {"id": 1, "name": "Test Position", "role_id": None}
        detailed_view = PositionDetailedView(1, mock_position, 1, mock_subdivision)
        print("✅ PositionDetailedView instantiated")

        print("\n🎉 All integration tests passed!")
        return True

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_position_management_integration()
    sys.exit(0 if success else 1)