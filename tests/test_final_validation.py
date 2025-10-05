#!/usr/bin/env python3
"""
Final validation test for PersonnelManager - only military recruits to DB
"""

import asyncio
import sys
import os

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.database_manager import personnel_manager


async def final_validation():
    print("🎯 FINAL VALIDATION - ONLY MILITARY RECRUITS TO DATABASE")
    print("=" * 60)
    
    # Generate unique test data
    import random
    timestamp = int(random.random() * 10000)
    
    # Test data for military recruit - SHOULD go to database
    military_app = {
        'type': 'military',
        'recruitment_type': 'призыв',
        'name': f'Military User {timestamp}',
        'static': f'{timestamp//100:02d}-{timestamp%100:03d}',
        'rank': 'Рядовой'
    }
    
    # Test data for civilian - should NOT go to database
    civilian_app = {
        'type': 'civilian',
        'name': f'Civilian User {timestamp}',
        'static': f'{(timestamp+10)//100:02d}-{(timestamp+10)%100:03d}',
        'faction': 'Правительство РФ, Госслужащий, Специалист'
    }
    
    # Test data for supplier - should NOT go to database
    supplier_app = {
        'type': 'supplier',
        'name': f'Supplier User {timestamp}',
        'static': f'{(timestamp+20)//100:02d}-{(timestamp+20)%100:03d}'
    }
    
    # Test data for military NON-recruit - should NOT go to database
    military_transfer_app = {
        'type': 'military',
        'recruitment_type': 'перевод',  # NOT призыв/экскурсия
        'name': f'Transfer User {timestamp}',
        'static': f'{(timestamp+30)//100:02d}-{(timestamp+30)%100:03d}',
        'rank': 'Младший сержант'
    }
    
    test_ids = [
        990000001 + timestamp,  # military recruit
        990000002 + timestamp,  # civilian
        990000003 + timestamp,  # supplier
        990000004 + timestamp   # military transfer
    ]
    
    moderator = f'Test Moderator {timestamp}'
    
    # Test 1: Military recruit - should create DB records
    print(f"\n1️⃣ Military recruit (user {test_ids[0]}) - SHOULD create DB records...")
    success1, msg1 = await personnel_manager.process_role_application_approval(
        military_app, test_ids[0], moderator
    )
    print(f"   Result: {'✅ SUCCESS' if success1 else '❌ FAILED'}")
    print(f"   Message: {msg1}")
    
    summary1 = await personnel_manager.get_personnel_summary(test_ids[0])
    if summary1:
        print(f"   ✅ Database record created: {summary1['full_name']} - {summary1['rank']}")
    else:
        print("   ❌ ERROR: No database record found!")
    
    # Test 2: Civilian - should NOT create DB records
    print(f"\n2️⃣ Civilian (user {test_ids[1]}) - should NOT create DB records...")
    success2, msg2 = await personnel_manager.process_role_application_approval(
        civilian_app, test_ids[1], moderator
    )
    print(f"   Result: {'✅ SUCCESS' if success2 else '❌ FAILED'}")
    print(f"   Message: {msg2}")
    
    summary2 = await personnel_manager.get_personnel_summary(test_ids[1])
    if summary2:
        print(f"   ❌ ERROR: Database record found: {summary2['full_name']} (should not exist!)")
    else:
        print("   ✅ Correctly: No database record created")
    
    # Test 3: Supplier - should NOT create DB records
    print(f"\n3️⃣ Supplier (user {test_ids[2]}) - should NOT create DB records...")
    success3, msg3 = await personnel_manager.process_role_application_approval(
        supplier_app, test_ids[2], moderator
    )
    print(f"   Result: {'✅ SUCCESS' if success3 else '❌ FAILED'}")
    print(f"   Message: {msg3}")
    
    summary3 = await personnel_manager.get_personnel_summary(test_ids[2])
    if summary3:
        print(f"   ❌ ERROR: Database record found: {summary3['full_name']} (should not exist!)")
    else:
        print("   ✅ Correctly: No database record created")
    
    # Test 4: Military transfer - should NOT create DB records
    print(f"\n4️⃣ Military transfer (user {test_ids[3]}) - should NOT create DB records...")
    success4, msg4 = await personnel_manager.process_role_application_approval(
        military_transfer_app, test_ids[3], moderator
    )
    print(f"   Result: {'✅ SUCCESS' if success4 else '❌ FAILED'}")
    print(f"   Message: {msg4}")
    
    summary4 = await personnel_manager.get_personnel_summary(test_ids[3])
    if summary4:
        print(f"   ❌ ERROR: Database record found: {summary4['full_name']} (should not exist!)")
    else:
        print("   ✅ Correctly: No database record created")
    
    # Summary
    print(f"\n🎯 VALIDATION SUMMARY:")
    print(f"   Military recruit → DB: {'✅' if summary1 else '❌'}")
    print(f"   Civilian → No DB: {'✅' if not summary2 else '❌'}")
    print(f"   Supplier → No DB: {'✅' if not summary3 else '❌'}")
    print(f"   Military transfer → No DB: {'✅' if not summary4 else '❌'}")
    
    all_correct = summary1 and not summary2 and not summary3 and not summary4
    print(f"\n{'🎉 ALL TESTS PASSED!' if all_correct else '⚠️ SOME TESTS FAILED!'}")


if __name__ == "__main__":
    try:
        asyncio.run(final_validation())
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()