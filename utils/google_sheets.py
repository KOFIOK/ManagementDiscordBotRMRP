# filepath: g:\GitHub\repos\army discord bot\utils\google_sheets.py
import gspread
from google.oauth2.service_account import Credentials
import json
import os
from datetime import datetime
import discord
import re

# Google Sheets configuration
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

class GoogleSheetsManager:
    def __init__(self):
        self.credentials_path = 'credentials.json'
        self.spreadsheet_name = 'ВС РФ | Общий Кадровый Аудит'
        self.dismissal_sheet_name = 'Общий Кадровый'
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        
    def initialize(self):
        """Initialize the Google Sheets connection."""
        try:
            # Check if credentials file exists
            if not os.path.exists(self.credentials_path):
                print(f"❌ Credentials file not found: {self.credentials_path}")
                return False
            
            # Connect to Google Sheets
            print(f"📁 Loading credentials from: {self.credentials_path}")
            self.client = gspread.service_account(filename=self.credentials_path)
            
            print(f"📊 Opening spreadsheet: {self.spreadsheet_name}")
            self.spreadsheet = self.client.open(self.spreadsheet_name)
            
            print(f"📋 Opening worksheet: {self.dismissal_sheet_name}")
            self.worksheet = self.spreadsheet.worksheet(self.dismissal_sheet_name)
            
            print("✅ Google Sheets successfully initialized!")
            return True
        except gspread.SpreadsheetNotFound:
            print(f"❌ Spreadsheet '{self.spreadsheet_name}' not found or no access")
            return False
        except gspread.WorksheetNotFound:
            print(f"❌ Worksheet '{self.dismissal_sheet_name}' not found in spreadsheet")
            return False
        except Exception as e:
            print(f"❌ Failed to initialize Google Sheets: {type(e).__name__}: {e}")
            if hasattr(e, 'response'):
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            return False
    
    async def async_initialize(self):
        """Async wrapper for initialize method."""
        return self.initialize()
    
    def _ensure_connection(self):
        """Ensure we have a valid connection to Google Sheets."""
        if not self.client or not self.spreadsheet or not self.worksheet:
            try:
                self.client = gspread.service_account(filename=self.credentials_path)
                self.spreadsheet = self.client.open(self.spreadsheet_name)
                self.worksheet = self.spreadsheet.worksheet(self.dismissal_sheet_name)
                return True
            except Exception as e:
                print(f"Error establishing Google Sheets connection: {e}")
                return False
        return True
        
    def get_rank_from_roles(self, member):
        """Extract rank from user's Discord roles."""
        # Full rank names
        ranks = [
            "Генерал Армии", "Генерал-Полковник", "Генерал-Лейтенант", "Генерал-Майор",
            "Полковник", "Подполковник", "Майор", "Капитан", "Старший Лейтенант",
            "Лейтенант", "Младший Лейтенант", "Старший Прапорщик", "Прапорщик",
            "Старшина", "Старший Сержант", "Сержант", "Младший Сержант", "Ефрейтор", "Рядовой"
        ]
        
        # Abbreviated rank names mapping to full names
        rank_abbreviations = {
            "Мл. Лейтенант": "Младший Лейтенант",
            "Ст. Лейтенант": "Старший Лейтенант", 
            "Ст. Прапорщик": "Старший Прапорщик",
            "Ст. Сержант": "Старший Сержант",
            "Мл. Сержант": "Младший Сержант",
            "Ген. Армии": "Генерал Армии",
            "Ген. Полковник": "Генерал-Полковник",
            "Ген. Лейтенант": "Генерал-Лейтенант",
            "Ген. Майор": "Генерал-Майор"
        }
        
        for role in member.roles:
            # Check full rank names first
            if role.name in ranks:
                return role.name
            # Check abbreviated rank names
            elif role.name in rank_abbreviations:
                return rank_abbreviations[role.name]
        
        return "Неизвестно"
    
    def get_department_from_roles(self, member, ping_settings):
        """Extract department from user's Discord roles based on ping settings."""
        if not ping_settings:
            return "Неизвестно"
        
        # Find user's highest department role (by position in hierarchy)
        user_department = None
        highest_position = -1
        
        for department_role_id in ping_settings.keys():
            department_role = member.guild.get_role(int(department_role_id))
            if department_role and department_role in member.roles:
                # Check if this role is higher in hierarchy than current highest
                if department_role.position > highest_position:
                    highest_position = department_role.position
                    user_department = department_role
        
        return user_department.name if user_department else "Неизвестно"

    def extract_name_from_nickname(self, display_name):
        """Extract clean name from Discord nickname, removing department/position prefixes."""
        # Format 1: "{Подразделение} | Имя Фамилия"
        if " | " in display_name:
            return display_name.split(" | ", 1)[1]
        
        # Format 2: "[Должность] Имя Фамилия" or "!![Должность] Имя Фамилия" or "![Должность] Имя Фамилия"
        elif "]" in display_name:
            # Find the last occurrence of "]" to handle nested brackets
            bracket_end = display_name.rfind("]")
            if bracket_end != -1:
                # Extract everything after "]", removing leading exclamation marks and spaces
                after_bracket = display_name[bracket_end + 1:]
                # Remove leading exclamation marks and spaces
                clean_name = re.sub(r'^[!\s]+', '', after_bracket).strip()
                if clean_name:
                    return clean_name
        
        # If no specific format found, return as is
        return display_name
    
    async def get_user_info_from_users_sheet(self, surname):
        """Search for user by surname in 'Пользователи' sheet and return full name with static from column J."""
        try:
            # Ensure connection
            if not self._ensure_connection():
                return None
            
            # Get the 'Пользователи' worksheet
            users_worksheet = None
            for worksheet in self.spreadsheet.worksheets():
                if worksheet.title == "Пользователи":
                    users_worksheet = worksheet
                    break
            
            if not users_worksheet:
                print("'Пользователи' sheet not found")
                return None
            
            # Get all values from column B (full names) and column J (full info)
            names_column = users_worksheet.col_values(2)  # Column B
            full_info_column = users_worksheet.col_values(10)  # Column J
            
            # Search for matching surname (case-insensitive)
            surname_lower = surname.lower().strip()
            for i, cell_name in enumerate(names_column):
                if cell_name and cell_name.strip():
                    # Extract surname from "Имя Фамилия" (last word)
                    name_parts = cell_name.strip().split()
                    if len(name_parts) >= 2:
                        cell_surname = name_parts[-1].lower().strip()
                        if cell_surname == surname_lower:
                            # Found match, return corresponding value from column J
                            if i < len(full_info_column) and full_info_column[i]:
                                return full_info_column[i]
            
            return None
        
        except Exception as e:
            print(f"Error searching in 'Пользователи' sheet: {e}")
            return None
    
    async def add_dismissal_record(self, form_data, dismissed_user, approving_user, dismissal_time, ping_settings):
        """Add a dismissal record to the Google Sheets."""
        try:
            # Ensure connection
            if not self._ensure_connection():
                print("Failed to establish Google Sheets connection")
                return False
              # Extract name from form data (use form name as primary source)
            name_from_form = form_data.get('name', '')
            static_from_form = form_data.get('static', '')
            
            # Use name from form as primary, fallback to extracted from nickname
            real_name = name_from_form or self.extract_name_from_nickname(dismissed_user.display_name)
            discord_id = str(dismissed_user.id)
            rank = self.get_rank_from_roles(dismissed_user)
            department = self.get_department_from_roles(dismissed_user, ping_settings)
            
            # Get approved by info - extract surname and lookup
            approved_by_clean_name = self.extract_name_from_nickname(approving_user.display_name)
            approved_by_info = approving_user.display_name  # Default fallback
            
            if approved_by_clean_name:
                # Extract surname (last word)
                name_parts = approved_by_clean_name.strip().split()
                if len(name_parts) >= 2:
                    surname = name_parts[-1]  # Last word as surname
                    # Search in 'Пользователи' sheet
                    full_user_info = await self.get_user_info_from_users_sheet(surname)
                    if full_user_info:
                        approved_by_info = full_user_info
                    else:
                        approved_by_info = approved_by_clean_name
              # Prepare row data according to table structure:
            # Column 1: Отметка времени  
            # Column 2: Имя Фамилия | 6 цифр статика
            # Column 3: ИмяФамилия
            # Column 4: Статик
            # Column 5: Действие (для увольнений будет "Увольнение")
            # Column 6: Дата Действия
            # Column 7: Подразделение
            # Column 8: Должность (можно оставить пустым или использовать роль)
            # Column 9: Звание
            # Column 10: Discord ID бойца
            # Column 11: Причина увольнения
            # Column 12: Кадровую отписал
            # Column 13: Ссылка на сообщение Discord (можно оставить пустым)
            row_data = [
                str(dismissal_time.strftime('%d.%m.%Y %H:%M')),  # Отметка времени
                f"{real_name} | {static_from_form}" if static_from_form else str(real_name),  # Имя Фамилия | статик
                str(real_name),  # ИмяФамилия
                str(static_from_form) if static_from_form else "",  # Статик
                "Увольнение",  # Действие
                str(dismissal_time.strftime('%d.%m.%Y')),  # Дата Действия
                str(department),  # Подразделение
                "",  # Должность (пустое)
                str(rank),  # Звание
                str(discord_id),  # Discord ID бойца
                str(form_data.get('reason', '')),  # Причина увольнения
                str(approved_by_info),  # Кадровую отписал
                ""  # Ссылка на сообщение Discord (пустое)
            ]
            
            # Insert record at the beginning (after headers)
            result = self.worksheet.insert_row(row_data, index=2)
            
            # Check if insert was successful
            if result:
                print(f"✅ Successfully added dismissal record for {real_name}")
                return True
            else:
                print(f"❌ Failed to add dismissal record for {real_name}")
                return False
            
        except Exception as e:
            print(f"❌ Error adding dismissal record to Google Sheets: {e}")
            # Print more detailed error information
            if hasattr(e, 'response'):
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            return False

# Global instance
sheets_manager = GoogleSheetsManager()
