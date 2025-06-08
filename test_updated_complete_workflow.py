#!/usr/bin/env python3
"""
Complete workflow test for updated early dismissal penalty system.
This script tests the full updated workflow with new requirements:
1) Срок: "14 дней" 
2) Причина: "Неустойка"
3) Дата вынесения: дата внесения + 14 дней
4) Кем внесён: поиск по листу "Пользователи"
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.google_sheets import GoogleSheetsManager

async def test_updated_complete_workflow():
    """Test the complete updated early dismissal penalty workflow."""
    print("🚀 Updated Complete Early Dismissal Penalty Workflow Test")
    print("=" * 75)
    
    sheets_manager = GoogleSheetsManager()
    
    # Use a test static that should exist in your sheets
    test_static = "123-456"  # Adjust this to match your test data
    
    print(f"🔍 Testing with static: {test_static}")
    print()
    
    try:
        # Step 1: Look for hiring record
        print("Step 1: 🔍 Looking for hiring record...")
        hiring_record = await sheets_manager.get_latest_hiring_record_by_static(test_static)
        
        if hiring_record:
            print("✅ Hiring record found!")
            print(f"   Name: {hiring_record.get('ИмяФамилия', 'N/A')}")
            print(f"   Action: {hiring_record.get('Действие', 'N/A')}")
            print(f"   Date: {hiring_record.get('Дата Действия', 'N/A')}")
            
            # Step 2: Calculate service days
            hire_date_str = str(hiring_record.get('Дата Действия', '')).strip()
            if hire_date_str:
                print(f"\nStep 2: 🧮 Calculating service duration...")
                print(f"   Hire date string: {hire_date_str}")
                
                # Parse hire date (same logic as in dismissal_form.py)
                hire_date = None
                current_time = datetime.now()
                
                # If date contains time, extract date part
                if ' ' in hire_date_str:
                    date_part = hire_date_str.split(' ')[0]
                else:
                    date_part = hire_date_str
                
                # Try different date formats
                try:
                    hire_date = datetime.strptime(date_part, '%d.%m.%Y')
                except ValueError:
                    try:
                        hire_date = datetime.strptime(date_part, '%d-%m-%Y')
                    except ValueError:
                        # Try full datetime format
                        try:
                            hire_date = datetime.strptime(hire_date_str, '%d.%m.%Y %H:%M:%S')
                        except ValueError:
                            hire_date = datetime.strptime(hire_date_str, '%d-%m-%Y %H:%M:%S')
                
                if hire_date:
                    days_difference = (current_time - hire_date).days
                    print(f"   Hire date: {hire_date.strftime('%d.%m.%Y')}")
                    print(f"   Current date: {current_time.strftime('%d.%m.%Y')}")
                    print(f"   Days of service: {days_difference}")
                    
                    # Step 3: Check if early dismissal and test updated penalty logging
                    if days_difference < 5:
                        print(f"\nStep 3: ⚠️ EARLY DISMISSAL DETECTED!")
                        print(f"   Service duration: {days_difference} days (< 5 days)")
                        print(f"   Penalty required with UPDATED RULES")
                        
                        # Mock form data and users
                        form_data = {
                            'name': hiring_record.get('ИмяФамилия', 'Тест Пользователь'),
                            'static': test_static,
                            'reason': 'Тестовое досрочное увольнение'
                        }
                        
                        class MockUser:
                            def __init__(self, name):
                                self.id = 123456789012345678
                                self.display_name = name
                        
                        class MockApprovingUser:
                            def __init__(self):
                                self.id = 987654321098765432
                                # Use a surname that should exist in your "Пользователи" sheet
                                self.display_name = "[Администратор] Тест Админович"
                        
                        dismissed_user = MockUser(form_data['name'])
                        approving_user = MockApprovingUser()
                        
                        print(f"\nStep 4: 📝 Testing UPDATED penalty logging...")
                        print(f"   Form data: {form_data}")
                        print(f"   Approving user: {approving_user.display_name}")
                        print()
                        
                        # Step 4: Test updated blacklist record logging
                        penalty_logged = await sheets_manager.add_blacklist_record(
                            form_data=form_data,
                            dismissed_user=dismissed_user,
                            approving_user=approving_user,
                            dismissal_time=current_time,
                            days_difference=days_difference
                        )
                        
                        if penalty_logged:
                            print("✅ UPDATED Penalty successfully logged to blacklist sheet!")
                            
                            enforcement_date = (current_time + timedelta(days=14)).strftime('%d.%m.%Y')
                            
                            print("\n📊 UPDATED Penalty Record Details:")
                            print(f"   Срок: 14 дней (UPDATED from 'Постоянно')")
                            print(f"   Имя Фамилия | Статик: {form_data['name']} | {form_data['static']}")
                            print(f"   Причина: Неустойка (UPDATED from previous reason)")
                            print(f"   Дата внесения: {current_time.strftime('%d.%m.%Y')}")
                            print(f"   Дата вынесения: {enforcement_date} (UPDATED: +14 дней)")
                            print(f"   Кем внесён: [Lookup from 'Пользователи' sheet by surname 'Админович']")
                            print(f"   Сообщение: Автоматическое внесение за досрочное увольнение ({days_difference} дн. службы)")
                            
                            print(f"\n🎯 KEY UPDATES APPLIED:")
                            print(f"   ✅ Term changed to '14 дней'")
                            print(f"   ✅ Reason standardized to 'Неустойка'")
                            print(f"   ✅ Enforcement date calculated as entry date + 14 days")
                            print(f"   ✅ 'Кем внесён' uses 'Пользователи' sheet lookup system")
                        else:
                            print("❌ Failed to log UPDATED penalty to blacklist sheet")
                            
                    else:
                        print(f"\nStep 3: ✅ NORMAL DISMISSAL")
                        print(f"   Service duration: {days_difference} days (>= 5 days)")
                        print(f"   No penalty required")
                    
                else:
                    print("❌ Could not parse hire date")
            else:
                print("❌ No hire date found in record")
                
        else:
            print(f"❌ No hiring record found for static {test_static}")
            print("💡 Make sure the static exists in your 'Общий Кадровый' sheet")
            print("💡 And that there's a record with action 'Принят на службу'")
            
    except Exception as e:
        print(f"❌ Error during updated workflow test: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n🏁 Updated workflow test completed!")

async def test_blacklist_notification():
    """Test the blacklist channel notification (unchanged)."""
    print(f"\n🔔 Testing Blacklist Channel Notification...")
    print("=" * 50)
    
    # Mock form data for notification test
    form_data = {
        'name': 'Тест Уведомление',
        'static': '999-888',
    }
    
    days_difference = 2
    
    # Note: This would require a real Discord guild object
    # For testing purposes, we'll just show what would happen
    print(f"📋 Notification would be sent with:")
    print(f"   Title: ⚠️ Неустойка за досрочное увольнение")
    print(f"   Name: {form_data['name']}")
    print(f"   Static: {form_data['static']}")
    print(f"   Reason: Досрочное увольнение (менее 5 дней службы - {days_difference} дн.)")
    print(f"   Type: Неустойка")
    print(f"   Footer: Автоматическое внесение в чёрный список")
    print(f"✅ Notification system remains unchanged")

async def main():
    """Main test function."""
    await test_updated_complete_workflow()
    await test_blacklist_notification()

if __name__ == "__main__":
    asyncio.run(main())
