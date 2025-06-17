"""
Audit Export Commands for Discord bot
Export all audit channel messages to CSV format
"""

import discord
from discord import app_commands
from discord.ext import commands
import csv
import io
import os
import re
from datetime import datetime, timezone, timedelta
from utils.config_manager import load_config, is_administrator


class AuditExport(commands.Cog):
    """Commands for exporting audit data"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="выгрузить-кадровый", description="Выгрузить все записи кадрового аудита в CSV файл")
    @app_commands.describe(
        начиная_с="Дата начала выгрузки в формате ДД.ММ.ГГГГ (например: 01.01.2025)"
    )
    async def export_audit_command(
        self,
        interaction: discord.Interaction,
        начиная_с: str
    ):
        """Export audit channel messages to CSV file"""
        
        # Check admin permissions
        config = load_config()
        if not is_administrator(interaction.user, config):
            embed = discord.Embed(
                title="❌ Недостаточно прав",
                description="Эта команда доступна только администраторам.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Parse start date
        try:
            start_date = datetime.strptime(начиная_с, "%d.%m.%Y")
            start_date = start_date.replace(tzinfo=timezone.utc)
        except ValueError:
            embed = discord.Embed(
                title="❌ Неверный формат даты",
                description="Используйте формат ДД.ММ.ГГГГ (например: 01.01.2025)",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get audit channel
        audit_channel_id = config.get('audit_channel')
        if not audit_channel_id:
            embed = discord.Embed(
                title="❌ Канал аудита не настроен",
                description="Настройте канал аудита в настройках бота.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        audit_channel = interaction.guild.get_channel(audit_channel_id)
        if not audit_channel:
            embed = discord.Embed(
                title="❌ Канал аудита не найден",
                description="Канал аудита не существует или бот не имеет доступа.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Defer response as this will take time
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Start processing
            embed = discord.Embed(
                title="🔄 Начинаю экспорт кадрового аудита",
                description=f"Обрабатываю сообщения с {начиная_с} по сегодняшний день...",
                color=discord.Color.blue()
            )
            progress_message = await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Read and process messages
            audit_data = await self._process_audit_messages(
                audit_channel, start_date, progress_message
            )
            
            if not audit_data:
                embed = discord.Embed(
                    title="📝 Нет данных для экспорта",
                    description="За указанный период не найдено записей кадрового аудита.",
                    color=discord.Color.yellow()
                )
                await progress_message.edit(embed=embed)
                return
            
            # Create CSV file
            csv_filename = await self._create_csv_file(audit_data, начиная_с)
            
            # Update final status
            embed = discord.Embed(
                title="✅ Экспорт завершен",
                description=f"📊 Обработано записей: **{len(audit_data)}**\n"
                           f"💾 Файл сохранен: `{csv_filename}`\n"
                           f"📅 Период: с {начиная_с} по {datetime.now().strftime('%d.%m.%Y')}",
                color=discord.Color.green()
            )
            await progress_message.edit(embed=embed)
            
        except Exception as e:
            print(f"Error in audit export: {e}")
            embed = discord.Embed(
                title="❌ Произошла ошибка",
                description=f"Ошибка при экспорте: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _process_audit_messages(self, channel, start_date, progress_message):
        """Process all messages in audit channel and extract data"""
        audit_data = []
        processed_count = 0
          # Get messages after start date
        async for message in channel.history(after=start_date, limit=None, oldest_first=True):
            # Only process user messages (not bot or webhook)
            # Skip bot messages and webhook messages, process all user messages
            if message.author.bot or message.webhook_id:
                continue
                
            processed_count += 1
              # Update progress every 100 messages
            if processed_count % 100 == 0:
                embed = discord.Embed(
                    title="🔄 Обрабатываю сообщения",
                    description=f"Обработано: **{processed_count}** сообщений\n"
                               f"Найдено записей: **{len(audit_data)}**\n"
                               f"Последнее сообщение: {message.created_at.strftime('%d.%m.%Y %H:%M')}",
                    color=discord.Color.blue()
                )
                try:
                    await progress_message.edit(embed=embed)
                except:
                    pass  # Ignore if we can't update
              # Parse message content
            records = await self._parse_message_content(message)
            audit_data.extend(records)        
        # Final progress update
        embed = discord.Embed(
            title="🔄 Завершаю обработку",
            description=f"Всего обработано: **{processed_count}** сообщений\n"
                       f"Найдено записей: **{len(audit_data)}**",
            color=discord.Color.blue()
        )
        try:
            await progress_message.edit(embed=embed)
        except:
            pass
        
        return audit_data
    
    async def _parse_message_content(self, message):
        """Parse message content and extract audit records"""
        records = []
        
        # Always try to parse text content first (for old and new formats)
        content = message.content.strip()
        if content:
            text_records = await self._parse_text_format(content, message)
            records.extend(text_records)
        
        # Also check embeds (even though we're focusing on user messages, 
        # some users might use embeds or the message might have both)
        if message.embeds:
            for embed in message.embeds:
                record = await self._parse_embed_format(embed, message)
                if record:
                    records.append(record)
        
        # If no structured data found but message exists, create basic record
        if not records and content:
            # Try to extract any name/static pattern as fallback
            basic_record = await self._parse_fallback_format(content, message)
            if basic_record:
                records.append(basic_record)
        
        return records
    
    async def _parse_embed_format(self, embed, message):
        """Parse new embed format messages"""
        record = {
            'timestamp': message.created_at.strftime('%d.%m.%Y %H:%M:%S'),
            'name_with_static': '',
            'name': '',
            'static': '',
            'action': '',
            'action_date': '',
            'department': '',
            'position': '',
            'rank': '',
            'discord_id': '',
            'dismissal_reason': '',
            'moderator': ''
        }
        
        # Extract data from embed fields
        for field in embed.fields:
            if "Кадровую отписал" in field.name:
                record['moderator'] = field.value
            elif "Имя Фамилия | 6 цифр статика" in field.name or "Имя Фамилия | Статик" in field.name:
                record['name_with_static'] = field.value
                # Parse name and static
                match = re.search(r'^(.+?)\s*\|\s*(\d{2,3}-?\d{3})$', field.value)
                if match:
                    record['name'] = match.group(1).strip()
                    record['static'] = match.group(2).strip()
            elif "Действие" in field.name:
                record['action'] = field.value
            elif "Дата Действия" in field.name:
                record['action_date'] = field.value
            elif "Подразделение" in field.name:
                record['department'] = field.value
            elif "Должность" in field.name:
                record['position'] = field.value
            elif "Воинское звание" in field.name:
                record['rank'] = field.value
            elif "Причина увольнения" in field.name or "Причина" in field.name:
                record['dismissal_reason'] = field.value
        
        # Try to extract Discord ID from mentions in message content
        if message.content:
            discord_id_match = re.search(r'<@(\d+)>', message.content)
            if discord_id_match:
                record['discord_id'] = discord_id_match.group(1)
        
        return record if record['name_with_static'] or record['action'] else None

    async def _parse_text_format(self, content, message):
        """Parse various old text formats with improved regex patterns"""
        records = []
        lines = content.split('\n')
        
        # Improved universal patterns to catch more formats
        patterns = [
            # Pattern 1: Numbered lists "1. Максим Минтело 558-439" (various separators)
            re.compile(r'^\d+\.\s*([А-Яа-яЁё\s]+?)\s*[|/\-\s]\s*(\d{2,3}-?\d{3})'),
            
            # Pattern 2: Direct name + static with separators "Аристарх Громов | 564-269"
            re.compile(r'^([А-Яа-яЁё\s]+?)\s*[|/\-]\s*(\d{2,3}-?\d{3})(?:\s|$)'),
            
            # Pattern 3: Name + static + rank info "Алексея Гаврилова | 252-351 | Сержант - Старший сержант"
            re.compile(r'^([А-Яа-яЁё\s]+?)\s*\|\s*(\d{2,3}-?\d{3})\s*\|\s*(.+?)$'),
            
            # Pattern 4: Name and static with just spaces (careful matching)
            re.compile(r'^([А-Яа-яЁё]+(?:\s+[А-Яа-яЁё]+)+)\s+(\d{2,3}-?\d{3})(?:\s|$)'),
            
            # Pattern 5: Static first, then name with separators
            re.compile(r'^(\d{2,3}-?\d{3})\s*[|/\-]\s*([А-Яа-яЁё\s]+?)(?:\s|$)'),
            
            # Pattern 6: Multiple people on one line "Иван Петров 123-456, Петр Сидоров 789-012"
            re.compile(r'([А-Яа-яЁё]+(?:\s+[А-Яа-яЁё]+)+)\s+(\d{2,3}-?\d{3})'),
            
            # Pattern 7: Any name + static combination (most flexible)
            re.compile(r'([А-Яа-яЁё]+(?:\s+[А-Яа-яЁё]+)+)\s*[|/\-,;\s]\s*(\d{2,3}-?\d{3})'),
            
            # Pattern 8: Static + name (reverse) with any separators
            re.compile(r'(\d{2,3}-?\d{3})\s*[|/\-,;\s]\s*([А-Яа-яЁё]+(?:\s+[А-Яа-яЁё]+)+)'),
        ]
        
        # Collect all people found in this message
        people_found = []
        action_context = ""
        date_context = ""
        
        # First pass: collect all people and context
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('-#'):
                # Check for date in -# format
                date_match = re.search(r'-#\s*(\d{2}\.\d{2}\.\d{4})', line)
                if date_match:
                    date_context = date_match.group(1)
                continue
            
            # Check for action context in headers
            if any(word in line.lower() for word in ["повышен", "уволен", "принят", "переведен", "назначен", "награжден", "понижен"]):
                action_context = line
                continue
            
            # Check for date lines
            date_match = re.match(r'^(\d{2}\.\d{2}\.\d{4})$', line)
            if date_match:
                date_context = date_match.group(1)
                continue
            
            # Try all patterns and collect all matches from the line
            line_matches = []
            
            # Special handling for Pattern 3 (with rank info)
            pattern3_match = patterns[2].match(line)
            if pattern3_match:
                line_matches.append({
                    'name': pattern3_match.group(1).strip(),
                    'static': pattern3_match.group(2).strip(),
                    'rank_info': pattern3_match.group(3).strip()
                })
            else:
                # Try other patterns
                for i, pattern in enumerate(patterns):
                    if i == 2:  # Skip pattern 3, already handled
                        continue
                    
                    if i in [5, 6, 7]:  # Patterns that can find multiple matches
                        matches = pattern.findall(line)
                        for match in matches:
                            # Determine name and static based on pattern
                            if i in [4, 7] and re.match(r'\d', match[0]):  # Static first
                                name, static = match[1].strip(), match[0].strip()
                            else:  # Name first
                                name, static = match[0].strip(), match[1].strip()
                            
                            # Validate name (at least 2 words, reasonable length)
                            if (len(name.split()) >= 2 and 
                                len(name) >= 5 and len(name) <= 50 and
                                re.match(r'^[А-Яа-яЁё\s]+$', name)):
                                line_matches.append({
                                    'name': name,
                                    'static': static,
                                    'rank_info': None
                                })
                    else:  # Patterns that find single match
                        match = pattern.match(line)
                        if match:
                            # Determine name and static
                            if i == 4 and re.match(r'\d', match.group(1)):  # Pattern 5: static first
                                name, static = match.group(2).strip(), match.group(1).strip()
                            else:
                                name, static = match.group(1).strip(), match.group(2).strip()
                            
                            # Validate name
                            if (len(name.split()) >= 2 and 
                                len(name) >= 5 and len(name) <= 50 and
                                re.match(r'^[А-Яа-яЁё\s]+$', name)):
                                line_matches.append({
                                    'name': name,
                                    'static': static,
                                    'rank_info': None
                                })
                            break  # Take first successful match for single-match patterns
            
            # Add all valid matches from this line
            people_found.extend(line_matches)
              # Also check for additional action info for existing people
            if line and people_found and not line_matches:
                if any(word in line.lower() for word in ["уволен", "повышен", "получил звание", "переведен", "награжден", "понижен"]):
                    action_context = line
        
        # Second pass: create records for all found people (with deduplication)
        seen_people = set()
        for person in people_found:
            # Create unique identifier for deduplication
            person_id = f"{person['name'].lower()}|{person['static']}"
            if person_id in seen_people:
                continue  # Skip duplicates
            seen_people.add(person_id)
            
            record = self._create_base_record(message)
            record['name'] = person['name']
            record['static'] = person['static']
            record['name_with_static'] = f"{record['name']} | {record['static']}"
            record['action_date'] = date_context
            
            # Determine action
            if person['rank_info']:
                # Has rank change info
                rank_change = person['rank_info']
                if " - " in rank_change:
                    old_rank, new_rank = rank_change.split(" - ", 1)
                    record['action'] = f"Повышение: {old_rank.strip()} → {new_rank.strip()}"
                    record['rank'] = new_rank.strip()
                else:
                    record['action'] = rank_change
            elif action_context:
                # Use context action
                if "уволен" in action_context.lower():
                    record['action'] = "Уволен со службы"
                    record['dismissal_reason'] = action_context
                elif "повышен" in action_context.lower():
                    record['action'] = action_context
                elif "принят" in action_context.lower():
                    record['action'] = "Принят на службу"
                else:
                    record['action'] = action_context
            else:
                # Fallback
                record['action'] = "Неопределенное действие"
            
            records.append(record)
        
        return records
    
    def _create_base_record(self, message):
        """Create base record structure"""
        return {
            'timestamp': message.created_at.strftime('%d.%m.%Y %H:%M:%S'),
            'name_with_static': '',
            'name': '',
            'static': '',
            'action': '',
            'action_date': '',
            'department': '',
            'position': '',
            'rank': '',
            'discord_id': '',
            'dismissal_reason': '',
            'moderator': message.author.display_name
        }
    
    async def _create_csv_file(self, audit_data, start_date_str):
        """Create CSV file with audit data"""
        # Ensure exports directory exists
        exports_dir = os.path.join("data", "exports")
        os.makedirs(exports_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"audit_export_{start_date_str.replace('.', '-')}_{timestamp}.csv"
        filepath = os.path.join(exports_dir, filename)
        
        # CSV headers
        headers = [
            'Отметка времени',
            'Имя Фамилия | 6 цифр статика',
            'Имя Фамилия',
            'Статик',
            'Действие',
            'Дата Действия',
            'Подразделение',
            'Должность',
            'Звание',
            'Discord ID бойца',
            'Причина увольнения',
            'Кадровую отписал'
        ]
        
        # Write CSV file
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            
            for record in audit_data:
                writer.writerow([
                    record.get('timestamp', ''),
                    record.get('name_with_static', ''),
                    record.get('name', ''),
                    record.get('static', ''),
                    record.get('action', ''),
                    record.get('action_date', ''),
                    record.get('department', ''),
                    record.get('position', ''),
                    record.get('rank', ''),
                    record.get('discord_id', ''),
                    record.get('dismissal_reason', ''),
                    record.get('moderator', '')
                ])
        
        return filename

    async def _parse_fallback_format(self, content, message):
        """Parse any remaining text that might contain personnel data as fallback"""
        # Enhanced patterns for better fallback parsing
        patterns = [
            # Standard separators with Ё support
            r'([А-Яа-яЁё]+(?:\s+[А-Яа-яЁё]+)+)\s*[|/\-]\s*(\d{2,3}-?\d{3})',
            r'([А-Яа-яЁё]+(?:\s+[А-Яа-яЁё]+)+)\s+(\d{2,3}-?\d{3})',
            r'(\d{2,3}-?\d{3})\s*[|/\-]\s*([А-Яа-яЁё]+(?:\s+[А-Яа-яЁё]+)+)',
            r'(\d{2,3}-?\d{3})\s+([А-Яа-яЁё]+(?:\s+[А-Яа-яЁё]+)+)',
            
            # Special punctuation patterns
            r'([А-Яа-яЁё]+\s+[А-Яа-яЁё]+)\s*[:,;]\s*(\d{2,3}-?\d{3})',
            r'(\d{2,3}-?\d{3})\s*[:,;]\s*([А-Яа-яЁё]+\s+[А-Яа-яЁё]+)',
            
            # Parentheses patterns
            r'([А-Яа-яЁё]+\s+[А-Яа-яЁё]+)\s*\(\s*(\d{2,3}-?\d{3})\s*\)',
            r'\(\s*(\d{2,3}-?\d{3})\s*\)\s*([А-Яа-яЁё]+\s+[А-Яа-яЁё]+)',
            
            # Dash patterns (various types)
            r'([А-Яа-яЁё]+\s+[А-Яа-яЁё]+)\s*[—–\-]\s*(\d{2,3}-?\d{3})',
            r'(\d{2,3}-?\d{3})\s*[—–\-]\s*([А-Яа-яЁё]+\s+[А-Яа-яЁё]+)',
            
            # Multiple space patterns
            r'([А-Яа-яЁё]+\s+[А-Яа-яЁё]+)\s{2,}(\d{2,3}-?\d{3})',
            r'(\d{2,3}-?\d{3})\s{2,}([А-Яа-яЁё]+\s+[А-Яа-яЁё]+)',
            
            # Dot patterns
            r'([А-Яа-яЁё]+\s+[А-Яа-яЁё]+)\.\s*(\d{2,3}-?\d{3})',
            r'(\d{2,3}-?\d{3})\.\s*([А-Яа-яЁё]+\s+[А-Яа-яЁё]+)',
        ]
        
        all_matches = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                all_matches.append(match)
        
        if all_matches:
            # Validate and return the best match
            for match in all_matches:
                # Determine which group is name and which is static
                name, static = "", ""
                if re.match(r'\d', match[0]):  # First group starts with digit
                    static = match[0].strip()
                    name = match[1].strip()
                else:
                    name = match[0].strip()
                    static = match[1].strip()
                
                # Enhanced validation
                if (len(name.split()) >= 2 and  # At least first and last name
                    3 <= len(name) <= 50 and  # Reasonable name length
                    re.match(r'^\d{2,3}-?\d{3}$', static) and  # Valid static format
                    re.match(r'^[А-Яа-яЁё\s]+$', name) and  # Only Cyrillic and spaces
                    not re.search(r'\s{3,}', name)):  # No excessive spaces
                    
                    record = self._create_base_record(message)
                    record['name'] = name
                    record['static'] = static
                    record['name_with_static'] = f"{name} | {static}"
                    record['action'] = "Неопределенное действие"
                    
                    return record
        
        return None

async def setup(bot):
    await bot.add_cog(AuditExport(bot))
