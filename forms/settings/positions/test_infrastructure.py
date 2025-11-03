"""
Test the new position management infrastructure
Тестирование новой инфраструктуры управления должностями
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all modules can be imported"""
    print("🧪 Testing position management infrastructure...")

    try:
        # Test UI components
        from forms.settings.positions.ui_components import create_position_embed, create_paginated_embed
        print("✅ UI components imported successfully")

        # Test validation
        from utils.database_manager import position_service
        print("✅ Validation module imported successfully")

        # Test navigation (will have import errors for now)
        try:
            from forms.settings.positions.navigation import PositionNavigationView
            print("✅ Navigation module imported successfully")
        except ImportError as e:
            print(f"⚠️ Navigation import failed (expected): {e}")

        # Test management
        try:
            from forms.settings.positions.management import PositionManagementView
            print("✅ Management module imported successfully")
        except ImportError as e:
            print(f"⚠️ Management import failed (expected): {e}")

        # Test search
        try:
            from forms.settings.positions.search import PositionSearchView
            print("✅ Search module imported successfully")
        except ImportError as e:
            print(f"⚠️ Search import failed (expected): {e}")

        # Test detailed management
        try:
            from forms.settings.positions.detailed_management import PositionDetailedView
            print("✅ Detailed management imported successfully")
        except ImportError as e:
            print(f"⚠️ Detailed management import failed (expected): {e}")

        print("✅ Infrastructure test completed!")
        return True

    except Exception as e:
        print(f"❌ Infrastructure test failed: {e}")
        return False

if __name__ == "__main__":
    test_imports()