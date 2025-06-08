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
                "Уволен со службы",  # Действиея
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
        
    async def send_to_blacklist(self, guild, form_data, days_difference):
        """Send a message to blacklist channel about early dismissal penalty."""
        try:
            from utils.config_manager import load_config
            
            config = load_config()
            blacklist_channel_id = config.get('blacklist_channel')
            
            if not blacklist_channel_id:
                print("Blacklist channel not configured")
                return False
            
            blacklist_channel = guild.get_channel(blacklist_channel_id)
            if not blacklist_channel:
                print(f"Blacklist channel not found: {blacklist_channel_id}")
                return False
            
            # Create blacklist embed
            embed = discord.Embed(
                title="⚠️ Неустойка за досрочное увольнение",
                color=0xFF0000,  # Red color
                timestamp=discord.utils.utcnow()
            )
            
            name = form_data.get('name', 'Неизвестно')
            static = form_data.get('static', 'Неизвестно')
            
            embed.add_field(name="Имя Фамилия", value=name, inline=False)
            embed.add_field(name="Статик", value=static, inline=False)
            embed.add_field(name="Причина внесения в чёрный список", 
                          value=f"Досрочное увольнение (менее 5 дней службы - {days_difference} дн.)", 
                          inline=False)
            embed.add_field(name="Тип нарушения", value="Неустойка", inline=False)
            
            embed.set_footer(text="Автоматическое внесение в чёрный список")
            
            await blacklist_channel.send(embed=embed)
            print(f"Successfully sent blacklist message for {name} ({static})")
            return True
        
        except Exception as e:
            print(f"Error sending message to blacklist: {e}")
            return False

    async def get_latest_hiring_record_by_static(self, static):
        """Search for the latest 'Принят на службу' record by static in 'Общий Кадровый' sheet."""
        try:
            # Ensure connection
            if not self._ensure_connection():
                return None
            
            # Get all records from the worksheet
            all_records = self.worksheet.get_all_records()
              # Filter records by static and action
            hiring_records = []
            for record in all_records:
                # Check if static matches (column 4 - Статик)
                record_static = str(record.get('Статик', '')).strip()
                # Check if action is "Принят на службу" (column 5 - Действие)
                record_action = str(record.get('Действие', '')).strip()
                
                if record_static == static and record_action == "Принят на службу":
                    hiring_records.append(record)
            
            if not hiring_records:
                return None
                
            # Find the latest record by date (column 6 - Дата Действия)
            latest_record = None
            latest_date = None
            
            for record in hiring_records:
                date_str = str(record.get('Дата Действия', '')).strip()
                if date_str:
                    try:
                        # Parse date - handle both with and without time
                        record_date = None
                        
                        # If date contains time, extract date part
                        if ' ' in date_str:
                            date_part = date_str.split(' ')[0]
                        else:
                            date_part = date_str
                        
                        # Try different date formats
                        try:
                            record_date = datetime.strptime(date_part, '%d.%m.%Y')
                        except ValueError:
                            try:
                                record_date = datetime.strptime(date_part, '%d-%m-%Y')
                            except ValueError:
                                # Try full datetime format
                                try:
                                    record_date = datetime.strptime(date_str, '%d.%m.%Y %H:%M:%S')
                                except ValueError:
                                    record_date = datetime.strptime(date_str, '%d-%m-%Y %H:%M:%S')
                        
                        if record_date and (latest_date is None or record_date > latest_date):
                            latest_date = record_date
                            latest_record = record
                            
                    except ValueError:
                        print(f"Could not parse date: {date_str}")
                        continue
            
            return latest_record
        
        except Exception as e:
            print(f"Error searching for hiring record by static: {e}")
            return None

    async def add_blacklist_record(self, form_data, dismissed_user, approving_user, dismissal_time, days_difference):
        """Add a blacklist penalty record to the 'Отправлено (НЕ РЕДАКТИРОВАТЬ)' sheet."""
        try:
            # Ensure connection
            if not self._ensure_connection():
                print("Failed to establish Google Sheets connection for blacklist record")
                return False
            
            # Get the 'Отправлено (НЕ РЕДАКТИРОВАТЬ)' worksheet
            blacklist_worksheet = None
            for worksheet in self.spreadsheet.worksheets():
                if worksheet.title == "Отправлено (НЕ РЕДАКТИРОВАТЬ)":
                    blacklist_worksheet = worksheet
                    break
            
            if not blacklist_worksheet:
                print("'Отправлено (НЕ РЕДАКТИРОВАТЬ)' sheet not found")
                return False
            
            # Extract data
            name_from_form = form_data.get('name', '')
            static_from_form = form_data.get('static', '')
            
            # Use name from form as primary
            real_name = name_from_form or self.extract_name_from_nickname(dismissed_user.display_name)
            
            # Get approving user info for "Кем внесён" field using the same system as dismissal records
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
            
            # Format dates
            from datetime import timedelta
            current_date = dismissal_time.strftime('%d.%m.%Y')
            # Calculate enforcement date (current date + 14 days)
            enforcement_date = (dismissal_time + timedelta(days=14)).strftime('%d.%m.%Y')            # Prepare row data according to blacklist sheet structure:
            # Column A: Срок (продолжительность неустойки)
            # Column B: Имя Фамилия | Статик
            # Column C: Причина
            # Column D: Дата внесения 
            # Column E: Дата вынесения
            # Column F: Кем внесён
            # Column G: Сообщение
            row_data = [
                "14 дней",  # Срок - 14 дней неустойки
                f"{real_name} | {static_from_form}" if static_from_form else str(real_name),  # Имя Фамилия | Статик
                "Неустойка",  # Причина - всегда "Неустойка"
                current_date,  # Дата внесения
                enforcement_date,  # Дата вынесения (дата внесения + 14 дней)
                approved_by_info,  # Кем внесён - из листа "Пользователи"
                '="1. " & B3 & СИМВОЛ(10) & "2. " & C3 & СИМВОЛ(10) & "3. " & ТЕКСТ(D3;"dd.mm.yyyy") & СИМВОЛ(10) & "4. " & ТЕКСТ(E3;"dd.mm.yyyy") & СИМВОЛ(10) & "5. " & F3 & СИМВОЛ(10)'  # Сообщение
            ]
            
            # Insert record at the beginning (after headers)
            result = blacklist_worksheet.insert_row(row_data, index=2)
            
            # Check if insert was successful
            if result:
                print(f"✅ Successfully added blacklist penalty record for {real_name}")
                return True
            else:
                print(f"❌ Failed to add blacklist penalty record for {real_name}")
                return False
                
        except Exception as e:
            print(f"❌ Error adding blacklist penalty record to Google Sheets: {e}")
            # Print more detailed error information
            if hasattr(e, 'response'):
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            return False

# Global instance
sheets_manager = GoogleSheetsManager()
