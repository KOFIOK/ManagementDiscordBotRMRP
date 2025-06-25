"""
User Database Management System

This module manages the current personnel database in Google Sheets.
Unlike the audit log which tracks all actions, this maintains only the latest
active personnel information.

Sheet structure (columns A-G):
A: Имя (First Name)
B: Фамилия (Last Name) 
C: Статик (Static ID)
D: Воинское Звание (Military Rank)
E: Подразделение (Department)
F: Должность (Position)
G: Discord ID (Primary Key)
"""

import asyncio
from datetime import datetime, timezone
from utils.google_sheets import sheets_manager


class UserDatabase:
    """Manages personnel database operations"""
    
    WORKSHEET_NAME = "Личный Состав"
    HEADERS = ["Имя", "Фамилия", "Статик", "Воинское Звание", "Подразделение", "Должность", "Discord ID"]
    
    # Column indices (0-based)
    COL_FIRST_NAME = 0
    COL_LAST_NAME = 1
    COL_STATIC = 2
    COL_RANK = 3
    COL_DEPARTMENT = 4
    COL_POSITION = 5
    COL_DISCORD_ID = 6
    
    @classmethod
    async def add_or_update_user(cls, application_data, user_discord_id):
        """
        Add or update user in personnel database
        
        Args:
            application_data: Dict containing user application data
            user_discord_id: Discord user ID (primary key)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Parse name from application
            full_name = application_data.get("name", "").strip()
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else ""
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            
            # Extract data from application
            static_id = application_data.get("static", "").strip()
            
            # Constants for new recruits
            rank = "Рядовой"
            department = "Военная Академия"
            position = ""  # Empty position
            
            # Prepare row data
            user_data = [
                first_name,
                last_name,
                static_id,
                rank,
                department,
                position,
                str(user_discord_id)
            ]
            
            print(f"📊 Adding/updating user in database: {first_name} {last_name} (ID: {user_discord_id})")
            
            # Check if user already exists
            existing_row = await cls._find_user_row(user_discord_id)
            
            if existing_row:
                # Update existing user (delete old, add new at top)
                print(f"🔄 Updating existing user record at row {existing_row}")
                await cls._delete_user_row(existing_row)
            
            # Add new record at the top (row 2, after headers)
            success = await cls._insert_user_at_top(user_data)
            
            if success:
                print(f"✅ Successfully {'updated' if existing_row else 'added'} user {first_name} {last_name} in personnel database")
                return True
            else:
                print(f"❌ Failed to add user {first_name} {last_name} to personnel database")
                return False
                
        except Exception as e:
            print(f"❌ Error managing user database for {user_discord_id}: {e}")
            return False
    
    @classmethod
    async def remove_user(cls, user_discord_id):
        """
        Remove user from personnel database (e.g., when dismissed)
        
        Args:
            user_discord_id: Discord user ID to remove
            
        Returns:
            bool: True if successful (user found and removed), False otherwise
        """
        try:
            print(f"🗑️ Removing user from personnel database: ID {user_discord_id}")
            
            # Find user in database
            existing_row = await cls._find_user_row(user_discord_id)
            
            if existing_row:                # Remove the user
                success = await cls._delete_user_row(existing_row)
                if success:
                    print(f"✅ Successfully removed user {user_discord_id} from personnel database")
                    return True
                else:
                    print(f"❌ Failed to remove user {user_discord_id} from personnel database")
                    return False
            else:
                print(f"⚠️ User {user_discord_id} not found in personnel database")
                return False
                
        except Exception as e:
            print(f"❌ Error removing user {user_discord_id} from database: {e}")
            return False
    
    @classmethod
    async def get_user_info(cls, user_discord_id):
        """
        Get user information from personnel database by Discord ID with caching
        
        Args:
            user_discord_id: Discord user ID to search for
            
        Returns:
            dict: User data if found, None otherwise
            Format: {
                'first_name': str,
                'last_name': str, 
                'full_name': str,
                'static': str,
                'rank': str,
                'department': str,
                'position': str,
                'discord_id': str
            }
        """
        try:
            # Используем внутреннюю функцию кэша для избежания рекурсии
            from utils.user_cache import _global_cache
            
            cached_data = await _global_cache._get_user_info_internal(user_discord_id)
            if cached_data is not None:
                print(f"📋 UNIVERSAL CACHE HIT: {user_discord_id}")
                return cached_data
            
            # Если нет в кэше - загружаем оригинальным способом
            print(f"🔄 UNIVERSAL CACHE MISS: {user_discord_id}")
            return await cls._get_user_info_original(user_discord_id)
            
        except Exception as e:
            print(f"❌ CACHE ERROR, fallback для {user_discord_id}: {e}")
            # Fallback на оригинальный метод
            return await cls._get_user_info_original(user_discord_id)
    
    @classmethod
    async def _get_user_info_original(cls, user_discord_id):
        """
        Original get_user_info method without caching
        
        Args:
            user_discord_id: Discord user ID to search for
            
        Returns:
            dict: User data if found, None otherwise
        """
        try:
            worksheet = sheets_manager.get_worksheet(cls.WORKSHEET_NAME)
            if not worksheet:
                print(f"❌ Worksheet '{cls.WORKSHEET_NAME}' not found")
                return None
            
            # Get all values in Discord ID column (column G)
            discord_id_column = worksheet.col_values(cls.COL_DISCORD_ID + 1)  # gspread uses 1-based indexing
            
            # Search for Discord ID (skip header row)
            for i, cell_value in enumerate(discord_id_column[1:], start=2):  # Start from row 2
                if str(cell_value).strip() == str(user_discord_id).strip():
                    # Found user, get all data from this row
                    row_data = worksheet.row_values(i)
                    
                    # Ensure we have all columns (pad with empty strings if needed)
                    while len(row_data) < len(cls.HEADERS):
                        row_data.append("")
                    
                    user_info = {
                        'first_name': row_data[cls.COL_FIRST_NAME].strip() if cls.COL_FIRST_NAME < len(row_data) else "",
                        'last_name': row_data[cls.COL_LAST_NAME].strip() if cls.COL_LAST_NAME < len(row_data) else "",
                        'static': row_data[cls.COL_STATIC].strip() if cls.COL_STATIC < len(row_data) else "",
                        'rank': row_data[cls.COL_RANK].strip() if cls.COL_RANK < len(row_data) else "",
                        'department': row_data[cls.COL_DEPARTMENT].strip() if cls.COL_DEPARTMENT < len(row_data) else "",
                        'position': row_data[cls.COL_POSITION].strip() if cls.COL_POSITION < len(row_data) else "",
                        'discord_id': str(user_discord_id)
                    }
                    
                    # Create full name
                    user_info['full_name'] = f"{user_info['first_name']} {user_info['last_name']}".strip()
                    
                    print(f"✅ Found user data for {user_discord_id}: {user_info['full_name']} ({user_info['static']})")
                    return user_info
            
            print(f"⚠️ User {user_discord_id} not found in personnel database")
            return None
            
        except Exception as e:
            print(f"❌ Error getting user info for {user_discord_id}: {e}")
            return None
    
    @classmethod
    async def _find_user_row(cls, discord_id):
        """
        Find row number of user by Discord ID
        
        Args:
            discord_id: Discord user ID to search for
            
        Returns:
            int: Row number if found, None otherwise
        """
        try:
            worksheet = sheets_manager.get_worksheet(cls.WORKSHEET_NAME)
            if not worksheet:
                print(f"❌ Worksheet '{cls.WORKSHEET_NAME}' not found")
                return None
            
            # Get all values in Discord ID column (column G)
            discord_id_column = worksheet.col_values(cls.COL_DISCORD_ID + 1)  # gspread uses 1-based indexing
            
            # Search for Discord ID (skip header row)
            for i, cell_value in enumerate(discord_id_column[1:], start=2):  # Start from row 2
                if str(cell_value).strip() == str(discord_id).strip():
                    return i
            
            return None
            
        except Exception as e:
            print(f"❌ Error searching for user {discord_id}: {e}")
            return None
    
    @classmethod
    async def _delete_user_row(cls, row_number):
        """
        Delete user row from database
          Args:
            row_number: Row number to delete
        """
        try:
            worksheet = sheets_manager.get_worksheet(cls.WORKSHEET_NAME)
            if not worksheet:
                return False
            
            # Delete the row
            worksheet.delete_rows(row_number)
            print(f"🗑️ Deleted user record from row {row_number}")
            return True
            
        except Exception as e:
            print(f"❌ Error deleting row {row_number}: {e}")
            return False
    
    @classmethod
    async def _insert_user_at_top(cls, user_data):
        """
        Insert user data at the top of the database (row 2)
        
        Args:
            user_data: List of user data to insert
              Returns:
            bool: True if successful, False otherwise
        """
        try:
            worksheet = sheets_manager.get_worksheet(cls.WORKSHEET_NAME)
            if not worksheet:
                return False
            
            # Insert row at position 2 (after headers)
            worksheet.insert_row(user_data, 2)
            print(f"📝 Inserted user record at row 2")
            return True
            
        except Exception as e:
            print(f"❌ Error inserting user data: {e}")
            return False
    
    @classmethod
    async def verify_worksheet_exists(cls):
        """
        Verify that the personnel worksheet exists and has proper headers
          Returns:
            bool: True if worksheet is ready, False otherwise
        """
        try:
            worksheet = sheets_manager.get_worksheet(cls.WORKSHEET_NAME)
            if not worksheet:
                print(f"❌ Worksheet '{cls.WORKSHEET_NAME}' not found")
                return False
            
            # Check if headers exist
            first_row = worksheet.row_values(1)
            if not first_row or len(first_row) < len(cls.HEADERS):
                print(f"⚠️ Headers missing or incomplete in '{cls.WORKSHEET_NAME}'")
                # Could auto-create headers here if needed
                return False
            
            print(f"✅ Worksheet '{cls.WORKSHEET_NAME}' verified")
            return True
            
        except Exception as e:
            print(f"❌ Error verifying worksheet: {e}")
            return False


# Create global instance
user_database = UserDatabase()
