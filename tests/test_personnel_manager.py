#!/usr/bin/env python3
"""
Simple test script for PersonnelManager functionality
"""

import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.database_manager import personnel_manager


async def simple_test():
    print("🧪 TESTING PERSONNELMANAGER")
    print("=" * 40)
    
    # Test data for military recruit (should create employee record)
    import random
    random_suffix = random.randint(1000, 9999)
    
    test_military_app = {
        'type': 'military',
        'recruitment_type': 'призыв',  # This should trigger employee creation
        'name': 'Ivan Testov',
        'static': f'{random_suffix//100}-{random_suffix%100:03d}',  # Unique static
        'rank': 'Рядовой'
    }
    
    # Test data for civilian (should NOT create employee record)
    test_civilian_app = {
        'type': 'civilian',
        'name': 'Civilian Test',
        'static': f'{(random_suffix+1)//100}-{(random_suffix+1)%100:03d}',  # Unique static
        'faction': 'Правительство РФ, Госслужащий, Специалист по кадрам'
    }
    
    # Test data for supplier (should NOT create employee record)
    test_supplier_app = {
        'type': 'supplier',
        'name': 'Supplier Test',
        'static': f'{(random_suffix+2)//100}-{(random_suffix+2)%100:03d}'  # Unique static
    }
    
    test_user_id_1 = 999999991
    test_user_id_2 = 999999992  
    test_user_id_3 = 999999993
    moderator = 'Test Moderator'
    
    print("\n1. Testing military recruit processing (should create employee)...")
    success1, message1 = await personnel_manager.process_role_application_approval(
        test_military_app, test_user_id_1, moderator
    )
    
    print(f"Result: {'SUCCESS' if success1 else 'FAILED'}")
    print(f"Message: {message1}")
    
    print("\n2. Testing military recruit personnel summary...")
    summary1 = await personnel_manager.get_personnel_summary(test_user_id_1)
    
    if summary1:
        print("Military personnel data found:")
        print(f"  Name: {summary1['full_name']}")
        print(f"  Rank: {summary1['rank']}")
        print(f"  Department: {summary1['department']}")
        print(f"  Position: {summary1['position']}")
        print(f"  Has Employee: {'YES' if summary1['has_employee_record'] else 'NO'}")
    else:
        print("No military personnel data found")
    
    print("\n3. Testing civilian processing (should NOT touch database)...")
    success2, message2 = await personnel_manager.process_role_application_approval(
        test_civilian_app, test_user_id_2, moderator
    )
    
    print(f"Result: {'SUCCESS' if success2 else 'FAILED'}")
    print(f"Message: {message2}")
    
    print("\n4. Testing civilian personnel summary (should be empty)...")
    summary2 = await personnel_manager.get_personnel_summary(test_user_id_2)
    
    if summary2:
        print("ERROR: Civilian data found in database (should not exist):")
        print(f"  Name: {summary2['full_name']}")
    else:
        print("✅ Correctly: No civilian data in database")
    
    print("\n5. Testing supplier processing (should NOT touch database)...")
    success3, message3 = await personnel_manager.process_role_application_approval(
        test_supplier_app, test_user_id_3, moderator
    )
    
    print(f"Result: {'SUCCESS' if success3 else 'FAILED'}")
    print(f"Message: {message3}")
    
    print("\n6. Testing supplier personnel summary (should be empty)...")
    summary3 = await personnel_manager.get_personnel_summary(test_user_id_3)
    
    if summary3:
        print("ERROR: Supplier data found in database (should not exist):")
        print(f"  Name: {summary3['full_name']}")
    else:
        print("✅ Correctly: No supplier data in database")
    
    print("\n✅ TEST COMPLETED")


if __name__ == "__main__":
    try:
        asyncio.run(simple_test())
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()