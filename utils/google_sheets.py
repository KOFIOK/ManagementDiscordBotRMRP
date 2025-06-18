import gspread
import os
from datetime import datetime
import discord
import re
import asyncio
import functools
from datetime import datetime

# Google Sheets configuration
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def retry_on_google_error(retries=3, delay=1):
    """Decorator for retrying Google Sheets operations on failure"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    error_msg = str(e)
                    
                    # Check if it's a Google API error
                    if "APIError" in str(type(e)) or "503" in error_msg or "500" in error_msg:
                        if attempt < retries - 1:  # Don't sleep on the last attempt
                            wait_time = delay * (attempt + 1)  # Exponential backoff
                            print(f"⚠️ Google Sheets error, retrying in {wait_time}s: {e}")
                            await asyncio.sleep(wait_time)
                            continue
                    else:
                        # If it's not a Google API error, don't retry
                        raise e
                    
            print(f"❌ All retry attempts failed: {last_error}")
            raise last_error
        return wrapper
    return decorator

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
    
    def get_worksheet(self, worksheet_name):
        """
        Get a specific worksheet by name.
        
        Args:
            worksheet_name (str): Name of the worksheet to get
            
        Returns:
            gspread.Worksheet or None: The worksheet object if found, None otherwise
        """
        try:
            if not self.client:
                self.client = gspread.service_account(filename=self.credentials_path)
            
            if not self.spreadsheet:
                self.spreadsheet = self.client.open(self.spreadsheet_name)
            
            return self.spreadsheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            print(f"❌ Worksheet '{worksheet_name}' not found in spreadsheet")
            return None
        except Exception as e:
            print(f"❌ Error getting worksheet '{worksheet_name}': {e}")
            return None
    
    def get_rank_from_roles(self, member):
        """Extract rank from user's Discord roles."""
        # Check if this is a MockUser (users who left the server)
        if getattr(member, '_is_mock', False):
            return "Неизвестно"
            
        # Check if member has roles attribute (additional safety check)
        if not hasattr(member, 'roles') or member.roles is None:
            return "Неизвестно"
            
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
        # Check if this is a MockUser (users who left the server)
        if getattr(member, '_is_mock', False):
            return "Неизвестно"
            
        # Check if member has a guild (additional safety check)
        if not hasattr(member, 'guild') or member.guild is None:
            return "Неизвестно"
            
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
    @retry_on_google_error(retries=3, delay=1)
    async def get_user_info_by_discord_id(self, discord_id):
        """Search for user by Discord ID in 'Пользователи' sheet and return full name with static from column J."""
        try:
            print(f"📋 SHEET SEARCH: Looking for Discord ID '{discord_id}' in 'Пользователи' sheet")
            
            # Ensure connection
            if not self._ensure_connection():
                print("❌ SHEET SEARCH: Failed to establish Google Sheets connection")
                return None
            
            # Get the 'Пользователи' worksheet
            users_worksheet = None
            all_worksheets = self.spreadsheet.worksheets()
            worksheet_names = [ws.title for ws in all_worksheets]
            print(f"📋 SHEET SEARCH: Available worksheets: {worksheet_names}")
            
            for worksheet in all_worksheets:
                if worksheet.title == "Пользователи":
                    users_worksheet = worksheet
                    break
            
            if not users_worksheet:
                print("❌ SHEET SEARCH: 'Пользователи' sheet not found")
                return None
            
            print("✅ SHEET SEARCH: Found 'Пользователи' worksheet")
            
            # Get all values with retry mechanism
            try:
                all_values = users_worksheet.get_all_values()
                print(f"📋 SHEET SEARCH: Retrieved {len(all_values)} rows from sheet")
            except Exception as e:
                print(f"❌ Error getting values from sheet: {e}")
                raise  # Let the retry decorator handle it
            
            # Skip header row (row 0) and search in data rows
            discord_id_str = str(discord_id)
            
            for i, row in enumerate(all_values[1:], start=1):  # Start from row 1 (skip header)
                if len(row) > 5:  # Ensure row has at least column F (Discord ID)
                    cell_discord_id = row[5] if len(row) > 5 else ""  # Column F (index 5)
                    if cell_discord_id and cell_discord_id.strip() == discord_id_str:
                        print(f"✅ SHEET SEARCH: MATCH FOUND in row {i+1} for Discord ID: '{discord_id}'")
                        
                        # Found match, return corresponding value from column J if exists
                        if len(row) > 9 and row[9]:  # Column J exists and has value
                            print(f"✅ SHEET SEARCH: Returning column J value: '{row[9]}'")
                            return row[9]
                        else:
                            # If column J is empty, construct from B and C
                            name_value = row[1] if len(row) > 1 else ""  # Column B
                            static_value = row[2] if len(row) > 2 else ""  # Column C
                            if name_value and static_value:
                                result = f"{name_value} | {static_value}"
                                print(f"✅ SHEET SEARCH: Column J empty, constructed: '{result}'")
                                return result
                            elif name_value:
                                print(f"✅ SHEET SEARCH: No static found, returning name only: '{name_value}'")
                                return name_value
                            else:
                                print(f"⚠️ SHEET SEARCH: Found Discord ID but no name data")
                                return None
                                                        
            print(f"❌ SHEET SEARCH: No match found for Discord ID '{discord_id}'")
            return None
            
        except Exception as e:
            print(f"Error searching in 'Пользователи' sheet: {e}")
            raise  # Let the retry decorator handle it

    @retry_on_google_error(retries=3, delay=1)
    async def check_moderator_authorization(self, approving_user):
        """
        Check if moderator is authorized in 'Пользователи' sheet by Discord ID.
        Returns dict with authorization status and info.
        """
        try:
            print(f"🔍 AUTHORIZATION CHECK: User '{approving_user.display_name}' (ID: {approving_user.id})")
            
            try:
                # Search in 'Пользователи' sheet by Discord ID
                full_user_info = await self.get_user_info_by_discord_id(approving_user.id)
                print(f"🔍 AUTHORIZATION CHECK: Search result: {full_user_info}")
                
                if full_user_info:
                    print(f"✅ AUTHORIZATION CHECK: Moderator FOUND in system!")
                    return {
                        "found": True,
                        "info": full_user_info,
                        "clean_name": approving_user.display_name,
                        "requires_manual_input": False
                    }
                else:
                    print(f"❌ AUTHORIZATION CHECK: Moderator NOT FOUND in system!")
                    return {
                        "found": False,  # Moderator not found - need manual registration
                        "info": None,
                        "clean_name": approving_user.display_name,
                        "requires_manual_input": True
                    }
            except Exception as e:
                print(f"⚠️ AUTHORIZATION CHECK: Sheet search failed: {e}")
                # Fall back to requiring manual auth if Google Sheets fails
                print(f"ℹ️ AUTHORIZATION CHECK: Using fallback mode - requiring manual auth")
                return {
                    "found": False,  # Require manual auth in fallback mode
                    "info": None,
                    "clean_name": approving_user.display_name,
                    "requires_manual_input": True
                }
                
        except Exception as e:
            print(f"❌ AUTHORIZATION CHECK: Error in check_moderator_authorization: {e}")
            # In case of any error, require manual auth for safety
            return {
                "found": False,  # Require manual auth in case of problems
                "info": None,
                "clean_name": approving_user.display_name,
                "requires_manual_input": False
            }
    
    async def add_dismissal_record(self, form_data, dismissed_user, approving_user, dismissal_time, ping_settings, override_moderator_info=None):
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
              # Handle MockUser case or when user has left server - use form data instead of roles
            if getattr(dismissed_user, '_is_mock', False):
                # For MockUser, get data from form instead of roles
                rank = form_data.get('rank', 'Неизвестно')
                department = form_data.get('department', 'Неизвестно')
                print(f"Using form data for MockUser: rank={rank}, department={department}")
            else:
                # For real users, try to get from roles first, then fallback to form data
                rank = self.get_rank_from_roles(dismissed_user)
                department = self.get_department_from_roles(dismissed_user, ping_settings)
                
                # If rank or department not found from roles (user may have left server), use form data
                if rank == 'Неизвестно' and form_data.get('rank'):
                    rank = form_data.get('rank', 'Неизвестно')
                    print(f"Using form data for rank: {rank}")
                
                if department == 'Неизвестно' and form_data.get('department'):
                    department = form_data.get('department', 'Неизвестно')
                    print(f"Using form data for department: {department}")
            
            # Log the data sources for debugging
            print(f"📊 DISMISSAL LOGGING DEBUG:")
            print(f"   User: {dismissed_user.display_name} (ID: {dismissed_user.id})")
            print(f"   Is MockUser: {getattr(dismissed_user, '_is_mock', False)}")
            print(f"   Form data: {form_data}")
            print(f"   Final rank: {rank}")
            print(f"   Final department: {department}")
            
            # Get approved by info - use override if provided, otherwise use centralized method
            if override_moderator_info:
                approved_by_info = override_moderator_info
            else:
                # Use centralized authorization check
                auth_result = await self.check_moderator_authorization(approving_user)
                approved_by_info = auth_result["info"] or auth_result["clean_name"]
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
    async def send_to_blacklist(self, guild, form_data, days_difference, audit_message_url=None, approving_user=None, override_moderator_info=None):
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
            
            # Get approving user info - use override if provided, otherwise use centralized method
            approving_user_name = "Система"
            if approving_user:
                if override_moderator_info:
                    approving_user_name = override_moderator_info
                else:
                    # Use centralized authorization check
                    auth_result = await self.check_moderator_authorization(approving_user)
                    approving_user_name = auth_result["info"] or auth_result["clean_name"]
            
            name = form_data.get('name', 'Неизвестно')
            static = form_data.get('static', 'Неизвестно')
            
            # Format dates (current date + 14 days)
            from datetime import datetime, timedelta
            current_date = datetime.now()
            enforcement_date = current_date + timedelta(days=14)
            
            def format_date(date):
                return date.strftime('%d.%m.%Y')
            
            # Create embed fields in the required format
            fields = [
                {"name": "1. Кто выдаёт", "value": approving_user_name, "inline": False},
                {"name": "2. Кому", "value": f"{name} | {static}", "inline": False},
                {"name": "3. Причина", "value": "Неустойка", "inline": False},
                {"name": "4. Дата начала", "value": format_date(current_date), "inline": True},
                {"name": "5. Дата окончания", "value": format_date(enforcement_date), "inline": True},
                {"name": "6. Доказательства", "value": audit_message_url if audit_message_url else "—", "inline": False}
            ]
            
            # Create blacklist embed
            embed = discord.Embed(
                title="📋 Новое дело",
                color=0xe74c3c,  # Red color (15158332 in decimal)
                timestamp=discord.utils.utcnow()
            )
            
            # Add fields to embed
            for field in fields:
                embed.add_field(
                    name=field["name"], 
                    value=field["value"], 
                    inline=field["inline"]
                )
            
            # Set thumbnail
            embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
            
            # Send message with role pings
            # Note: You may need to configure these role IDs in your config
            role_mentions = config.get('blacklist_role_mentions', [])
            content = ""
            if role_mentions:
                mentions = [f"<@&{role_id}>" for role_id in role_mentions]
                content = f"-# {' '.join(mentions)}"
            
            await blacklist_channel.send(content=content, embed=embed)
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
    async def add_blacklist_record(self, form_data, dismissed_user, approving_user, dismissal_time, days_difference, override_moderator_info=None):
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
            
            # Get approving user info - use override if provided, otherwise use centralized method
            if override_moderator_info:
                approved_by_info = override_moderator_info
            else:
                # Use centralized authorization check
                auth_result = await self.check_moderator_authorization(approving_user)
                approved_by_info = auth_result["info"] or auth_result["clean_name"]
            
            # Format dates
            from datetime import timedelta
            current_date = dismissal_time.strftime('%d.%m.%Y')
            # Calculate enforcement date (current date + 14 days)
            enforcement_date = (dismissal_time + timedelta(days=14)).strftime('%d.%m.%Y')
            # Prepare row data according to blacklist sheet structure:
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
                approved_by_info,  # Кем внесён
                ""  # Сообщение
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
    
    
    async def add_hiring_record(self, application_data, approved_user, approving_user, hiring_time, override_moderator_info=None):
        """Add a hiring record to the Google Sheets for new recruits with rank 'Рядовой'."""
        try:
            # Ensure connection
            if not self._ensure_connection():
                print("Failed to establish Google Sheets connection")
                return False
            
            # Extract data from application
            name_from_form = application_data.get('name', '')
            static_from_form = application_data.get('static', '')
            rank = application_data.get('rank', 'Рядовой')
            recruitment_type = application_data.get('recruitment_type', '')
            
            # Only create record for "Рядовой" rank
            if rank.lower() != 'рядовой':
                print(f"Skipping hiring record - rank is '{rank}', not 'Рядовой'")
                return True  # Not an error, just not applicable
            
            discord_id = str(approved_user.id)
            
            # Get approved by info - use override if provided, otherwise use centralized method
            if override_moderator_info:
                approved_by_info = override_moderator_info
            else:
                # Use centralized authorization check
                auth_result = await self.check_moderator_authorization(approving_user)
                approved_by_info = auth_result["info"] or auth_result["clean_name"]
            
            # Prepare row data according to table structure:
            # Column 1: Отметка времени  
            # Column 2: Имя Фамилия | 6 цифр статика
            # Column 3: ИмяФамилия
            # Column 4: Статик
            # Column 5: Действие (для найма будет "Принят на службу")
            # Column 6: Дата Действия
            # Column 7: Подразделение (для новых - "Военная Академия")
            # Column 8: Должность (можно оставить пустым)
            # Column 9: Звание ("Рядовой")
            # Column 10: Discord ID бойца
            # Column 11: Причина увольнения (для найма - порядок набора: Экскурсия/Призыв)
            # Column 12: Кадровую отписал
            # Column 13: Ссылка на сообщение Discord (можно оставить пустым)
            row_data = [
                str(hiring_time.strftime('%d.%m.%Y %H:%M')),  # Отметка времени
                f"{name_from_form} | {static_from_form}" if static_from_form else str(name_from_form),  # Имя Фамилия | статик
                str(name_from_form),  # ИмяФамилия
                str(static_from_form) if static_from_form else "",  # Статик
                "Принят на службу",  # Действие
                str(hiring_time.strftime('%d.%m.%Y')),  # Дата Действия
                "Военная Академия",  # Подразделение
                "",  # Должность (пустое)
                "Рядовой",  # Звание
                str(discord_id),  # Discord ID бойца
                str(recruitment_type).capitalize(),  # Порядок набора (Экскурсия/Призыв)
                str(approved_by_info),  # Кадровую отписал
                ""  # Ссылка на сообщение Discord (пустое)
            ]
            
            # Insert record at the beginning (after headers)
            result = self.worksheet.insert_row(row_data, index=2)
            
            # Check if insert was successful
            if result:
                print(f"✅ Successfully added hiring record for {name_from_form} (Рядовой)")
                return True
            else:
                print(f"❌ Failed to add hiring record for {name_from_form}")
                return False
                
        except Exception as e:
            print(f"❌ Error adding hiring record to Google Sheets: {e}")
            # Print more detailed error information
            if hasattr(e, 'response'):
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            return False
    
    
    async def register_moderator(self, moderator_data, discord_user):
        """
        Register a new moderator in the 'Пользователи' sheet.
        
        Args:
            moderator_data: Dict containing moderator information
                - email: Moderator's email address
                - name: Moderator's full name (Имя Фамилия)
                - static: Moderator's static number (formatted)
                - position: Moderator's position/rank
            discord_user: Discord user object for access management
            
        Returns:
            bool: True if registration successful, False otherwise
        """
        try:
            # Extract data from moderator_data dict
            email = moderator_data['email']
            name = moderator_data['name']
            static = moderator_data['static']
            position = moderator_data['position']
            # Ensure connection
            if not self._ensure_connection():
                print("Failed to establish Google Sheets connection for moderator registration")
                return False
            
            # Get the 'Пользователи' worksheet
            users_worksheet = None
            for worksheet in self.spreadsheet.worksheets():
                if worksheet.title == "Пользователи":
                    users_worksheet = worksheet
                    break
            
            if not users_worksheet:
                print("'Пользователи' sheet not found")
                return False
            # Check if moderator already exists (by Discord ID, email, or name+static)
            try:
                # Use get_all_values instead of get_all_records to avoid header issues
                all_values = users_worksheet.get_all_values()
                
                # Skip header row and check existing data
                for row in all_values[1:]:  # Skip first row (headers)
                    if len(row) > 0:
                        # Check by Discord ID (column F, index 5) - primary check
                        if len(row) > 5 and row[5].strip() == str(discord_user.id):
                            print(f"Moderator with Discord ID {discord_user.id} already exists")
                            return True  # Already registered, consider it success
                        
                        # Check by email (column A, index 0)
                        if len(row) > 0 and row[0].strip().lower() == email.lower():
                            print(f"Moderator with email {email} already exists")
                            return True  # Already registered, consider it success
                        
                        # Check by name + static combination (columns B and C, indices 1 and 2)
                        if len(row) > 2:
                            existing_name = row[1].strip() if len(row) > 1 else ""
                            existing_static = row[2].strip() if len(row) > 2 else ""
                            if existing_name == name and existing_static == static:
                                print(f"Moderator {name} | {static} already exists")
                                return True  # Already registered, consider it success
            except Exception as e:
                print(f"Warning: Could not check existing moderators: {e}")
                # Continue with registration anyway
                # # Format registration date
            registration_date = datetime.now().strftime('%d.%m.%Y %H:%M')
              # Prepare row data for 'Пользователи' sheet (columns A-F):
            # Column A: Email
            # Column B: Имя Фамилия  
            # Column C: Статик
            # Column D: Должность
            # Column E: Дата регистрации
            # Column F: Discord ID
            # Note: Column J with "Имя Фамилия | Статик" is auto-generated by table formula
            row_data = [
                email,              # Column A: Email
                name,               # Column B: Имя Фамилия
                static,             # Column C: Статик
                position,           # Column D: Должность
                registration_date,  # Column E: Дата регистрации
                str(discord_user.id)  # Column F: Discord ID
            ]# Find the next empty row safely (avoiding formula conflicts)
            all_data = users_worksheet.get_all_values()
              # Find the last row with actual data in columns A-F
            last_data_row = 0
            for i, row in enumerate(all_data):
                if any(cell.strip() for cell in row[:6] if cell):  # Check if first 6 columns have data
                    last_data_row = i + 1
            
            # Add new data after the last data row (not at the very end to avoid formula conflicts)
            next_row = last_data_row + 1
            
            # Safety check: ensure we don't overwrite existing data
            while next_row <= len(all_data):
                if next_row > len(all_data) or not any(cell.strip() for cell in all_data[next_row-1][:6] if cell):
                    break
                next_row += 1
            
            # Use batch update with exact range to avoid formula interference
            range_name = f"A{next_row}:F{next_row}"
            print(f"📝 Registering moderator in range {range_name}")
            
            # Use batch update instead of single cell updates
            result = users_worksheet.update(
                values=[row_data], 
                range_name=range_name,
                value_input_option='RAW'  # Use RAW to prevent formula interpretation
            )            # Check if append was successful
            if result:
                print(f"✅ Successfully registered moderator: {name} | {static} ({email}) [Discord ID: {discord_user.id}]")
                # Automatically add moderator as editor to spreadsheet
                print(f"🔑 Attempting to add editor access to spreadsheet...")
                
                # First check if they already have access
                has_access = await self.check_editor_access(email)
                if has_access:
                    print(f"📋 {email} already has access to spreadsheet")
                else:
                    # Try to add editor access
                    access_granted = await self.add_editor_to_spreadsheet(email)
                    if access_granted:
                        print(f"✅ Successfully granted spreadsheet access to {email}")
                    else:
                        print(f"⚠️  Could not automatically grant spreadsheet access to {email}")
                
                return True
            else:
                print(f"❌ Failed to register moderator: {name} | {static}")
                return False
                
        except Exception as e:
            print(f"❌ Error registering moderator in Google Sheets: {e}")
            # Print more detailed error information
            if hasattr(e, 'response'):
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            return False
    async def add_editor_to_spreadsheet(self, email):
        """
        Add a new editor to the Google Spreadsheet.
        
        Args:
            email: Email address of the user to add as editor
            
        Returns:
            bool: True if access granted successfully, False otherwise
        """
        try:
            # Ensure connection
            if not self._ensure_connection():
                print("Failed to establish Google Sheets connection for adding editor")
                return False
            
            print(f"📧 Adding editor access for: {email}")
            
            # Share the spreadsheet with the email address
            # 'writer' role gives edit access to the spreadsheet
            self.spreadsheet.share(
                email, 
                perm_type='user', 
                role='writer',
                notify=True,  # Send notification email
                email_message=f"Вам предоставлен доступ к кадровому аудиту ВС РФ. Вы можете редактировать таблицу."
            )
            
            print(f"✅ Successfully added {email} as editor to spreadsheet")
            return True
            
        except Exception as e:
            print(f"❌ Error adding editor to spreadsheet: {e}")
            # Check if error is due to invalid email or permission issues
            if "Invalid email" in str(e).lower():
                print(f"   Invalid email address: {email}")
            elif "permission" in str(e).lower():
                print(f"   Permission denied - check service account rights")
            else:
                print(f"   Unexpected error: {type(e).__name__}: {e}")
            
            return False
    
    async def check_editor_access(self, email):
        """
        Check if an email already has editor access to the spreadsheet.
        
        Args:
            email: Email address to check
            
        Returns:
            bool: True if user already has access, False otherwise
        """
        try:
            # Get list of permissions for the spreadsheet
            permissions = self.spreadsheet.list_permissions()
            
            # Check if email already has access
            for permission in permissions:
                if permission.get('emailAddress', '').lower() == email.lower():
                    role = permission.get('role', '')
                    print(f"📋 {email} already has {role} access")
                    return True
            return False
            
        except Exception as e:
            print(f"❌ Error checking editor access: {e}")
            return False
    

# Global instance
sheets_manager = GoogleSheetsManager()
