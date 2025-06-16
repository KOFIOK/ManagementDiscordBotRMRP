"""
Personnel management commands for Discord bot
Includes audit, blacklist, and promotion commands
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from utils.config_manager import load_config, is_moderator_or_admin
from utils.google_sheets import sheets_manager
import asyncio
import re


class PersonnelCommands(commands.Cog):
    """Commands for personnel management"""
    
    def __init__(self, bot):
        self.bot = bot
        self._cached_settings = {}
        self._last_cache_update = None
    
    async def _get_settings_data(self):
        """Get settings data from Google Sheets with caching"""
        try:
            current_time = datetime.now()
            
            # Cache for 5 minutes
            if (self._last_cache_update and 
                (current_time - self._last_cache_update).seconds < 300 and
                self._cached_settings):
                return self._cached_settings
            
            if not sheets_manager._ensure_connection():
                return {}
            
            # Get Settings worksheet
            settings_worksheet = None
            for worksheet in sheets_manager.spreadsheet.worksheets():
                if worksheet.title == "Настройки":
                    settings_worksheet = worksheet
                    break
            
            if not settings_worksheet:
                print("Settings worksheet not found")
                return {}
            
            # Get all data from Settings sheet
            all_values = settings_worksheet.get_all_values()
            if not all_values:
                return {}
            
            # Parse data into columns
            settings_data = {
                'actions': [],
                'departments': [],
                'positions': [],
                'ranks': []
            }
            for row in all_values:  # Process all rows (no header)
                if len(row) >= 4:
                    if row[0].strip():  # Column A - ActionsКадровый аудит добавле
                        settings_data['actions'].append(row[0].strip())
                    if row[1].strip():  # Column B - Departments
                        settings_data['departments'].append(row[1].strip())
                    if row[2].strip():  # Column C - Positions
                        settings_data['positions'].append(row[2].strip())
                    if row[3].strip():  # Column D - Ranks
                        settings_data['ranks'].append(row[3].strip())
            
            # Remove duplicates while preserving order
            for key in settings_data:
                settings_data[key] = list(dict.fromkeys(settings_data[key]))
            
            self._cached_settings = settings_data
            self._last_cache_update = current_time
            
            return settings_data
            
        except Exception as e:
            print(f"Error getting settings data: {e}")
            return {}
    
    async def _get_moderator_signed_name(self, discord_id: int):
        """Get moderator's signed name from 'Пользователи' sheet"""
        try:
            if not sheets_manager._ensure_connection():
                return None
            
            # Get the signed name using existing method
            signed_name = await sheets_manager.get_user_info_by_discord_id(discord_id)
            return signed_name
            
        except Exception as e:
            print(f"Error getting moderator signed name: {e}")
            return None
    async def _get_personnel_data(self, discord_id: int):
        """Get personnel data from 'Личный Состав' sheet"""
        try:
            if not sheets_manager._ensure_connection():
                return {}
            
            # Get Personnel worksheet
            personnel_worksheet = None
            for worksheet in sheets_manager.spreadsheet.worksheets():
                if worksheet.title == "Личный Состав":
                    personnel_worksheet = worksheet
                    break
            
            if not personnel_worksheet:
                print("Personnel worksheet not found")
                return {}
            
            # Get all data
            all_values = personnel_worksheet.get_all_values()
            if len(all_values) < 2:
                return {}
            
            # Find user by Discord ID (column G, index 6)
            for row in all_values[1:]:  # Skip header
                if len(row) >= 7 and row[6].strip() == str(discord_id):
                    return {
                        'name': row[0].strip(),  # A
                        'surname': row[1].strip(),  # B
                        'static': row[2].strip(),  # C
                        'rank': row[3].strip(),  # D
                        'department': row[4].strip(),  # E
                        'position': row[5].strip(),  # F
                        'full_name': f"{row[0].strip()} {row[1].strip()}".strip()
                    }
            
            return {}
            
        except Exception as e:
            print(f"Error getting personnel data: {e}")
            return {}
    
    async def _add_to_audit_sheet(self, audit_data):
        """Add record to 'Общий Кадровый' sheet at the top"""
        try:
            if not sheets_manager._ensure_connection():
                return False
            
            # Get audit worksheet
            audit_worksheet = None
            for worksheet in sheets_manager.spreadsheet.worksheets():
                if worksheet.title == "Общий Кадровый":
                    audit_worksheet = worksheet
                    break
            
            if not audit_worksheet:
                print("Audit worksheet not found")
                return False
            
            # Prepare row data (A-L) with Moscow timezone
            moscow_tz = timezone(timedelta(hours=3))
            current_time = datetime.now(moscow_tz)
            
            # Format static for column B (Name | Static)
            static_formatted = audit_data.get('static', '').replace('-', '')
            if len(static_formatted) == 5:
                static_formatted = f"{static_formatted[:2]}-{static_formatted[2:]}"
            elif len(static_formatted) == 6:
                static_formatted = f"{static_formatted[:3]}-{static_formatted[3:]}"
            
            name_with_static = f"{audit_data.get('full_name', '')} | {static_formatted}".strip(' |')
            
            row_data = [
                current_time.strftime("%d.%m.%Y %H:%M:%S"),  # A: Timestamp
                name_with_static,  # B: Name | Static
                audit_data.get('full_name', ''),  # C: Full Name
                audit_data.get('static', ''),  # D: Static
                audit_data.get('action', ''),  # E: Action
                current_time.strftime("%d.%m.%Y"),  # F: Action Date
                audit_data.get('department', ''),  # G: Department
                audit_data.get('position', ''),  # H: Position
                audit_data.get('rank', ''),  # I: Rank
                str(audit_data.get('discord_id', '')),  # J: Discord ID
                audit_data.get('reason', ''),  # K: Dismissal Reason
                audit_data.get('moderator_signed_name', '')  # L: Who wrote audit
            ]
            
            # Insert at row 2 (after header)
            audit_worksheet.insert_row(row_data, 2)
            
            return True
            
        except Exception as e:
            print(f"Error adding to audit sheet: {e}")
            return False
    
    @app_commands.command(name="аудит", description="Добавить запись в кадровый аудит")
    @app_commands.describe(
        сотрудник="Выберите сотрудника",
        действие="Выберите действие",
        подразделение="Подразделение (необязательно)",
        должность="Должность (необязательно)", 
        звание="Звание (необязательно)",
        причина="Причина (для увольнения/приема на службу)"
    )
    async def audit_command(
        self,
        interaction: discord.Interaction,
        сотрудник: discord.Member,
        действие: str,
        подразделение: str = None,
        должность: str = None,
        звание: str = None,
        причина: str = None
    ):
        """Add personnel audit record"""
        
        # Check permissions
        config = load_config()
        if not is_moderator_or_admin(interaction.user, config):
            embed = discord.Embed(
                title="❌ Недостаточно прав",
                description="Эта команда доступна только модераторам и администраторам.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Defer response as this might take time
        await interaction.response.defer()
        
        try:
            # Validate that at least one optional field is provided
            if not any([подразделение, должность, звание]):
                embed = discord.Embed(
                    title="❌ Ошибка заполнения",
                    description="Необходимо заполнить хотя бы одно из полей: подразделение, должность или звание.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Validate reason requirement for specific actions
            if действие in ["Уволен со службы", "Принят на службу"] and not причина:
                embed = discord.Embed(
                    title="❌ Требуется причина",
                    description=f"Для действия '{действие}' необходимо указать причину.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
              # Get moderator's signed name
            moderator_signed_name = await self._get_moderator_signed_name(interaction.user.id)
            if not moderator_signed_name:
                moderator_signed_name = f"{interaction.user.display_name}"
            
            # Get personnel data for autofill
            personnel_data = await self._get_personnel_data(сотрудник.id)
            
            # Prepare audit data with autofill from personnel sheet
            audit_data = {
                'discord_id': сотрудник.id,
                'user_mention': сотрудник.mention,
                'full_name': personnel_data.get('full_name', f"{сотрудник.display_name}"),
                'static': personnel_data.get('static', ''),
                'action': действие,
                'department': подразделение or personnel_data.get('department', ''),
                'position': должность or personnel_data.get('position', ''),
                'rank': звание or personnel_data.get('rank', ''),
                'reason': причина or '',
                'moderator_signed_name': moderator_signed_name
            }
            
            # Add to Google Sheets
            sheets_success = await self._add_to_audit_sheet(audit_data)
              # Send to audit channel
            audit_channel_id = config.get('audit_channel')
            channel_success = False
            
            if audit_channel_id:
                audit_channel = interaction.guild.get_channel(audit_channel_id)
                if audit_channel:
                    # Create audit embed in standard format
                    moscow_tz = timezone(timedelta(hours=3))
                    current_time = datetime.now(moscow_tz)
                    action_date = current_time.strftime('%d-%m-%Y')
                    
                    # Format name with static for display
                    static_formatted = audit_data['static'].replace('-', '') if audit_data['static'] else ''
                    if len(static_formatted) == 5:
                        static_formatted = f"{static_formatted[:2]}-{static_formatted[2:]}"
                    elif len(static_formatted) == 6:
                        static_formatted = f"{static_formatted[:3]}-{static_formatted[3:]}"
                    
                    name_with_static = f"{audit_data['full_name']} | {static_formatted}".strip(' |')
                    
                    embed = discord.Embed(
                        title="Кадровый аудит ВС РФ",
                        color=0x055000,  # Green color as in existing templates
                        timestamp=discord.utils.utcnow()
                    )
                    
                    embed.add_field(name="Кадровую отписал", value=moderator_signed_name, inline=False)
                    embed.add_field(name="Имя Фамилия | 6 цифр статика", value=name_with_static, inline=False)
                    embed.add_field(name="Действие", value=действие, inline=False)
                    
                    # Add reason field only if reason exists
                    if причина:
                        if действие == "Уволен со службы":
                            embed.add_field(name="Причина увольнения", value=причина, inline=False)
                        elif действие == "Принят на службу":
                            embed.add_field(name="Причина принятия", value=причина, inline=False)
                        else:
                            embed.add_field(name="Причина", value=причина, inline=False)
                    
                    embed.add_field(name="Дата Действия", value=action_date, inline=False)
                    embed.add_field(name="Подразделение", value=audit_data['department'] or "Не указано", inline=False)
                    embed.add_field(name="Должность", value=audit_data['position'] or "Не указана", inline=False)
                    embed.add_field(name="Воинское звание", value=audit_data['rank'] or "Не указано", inline=False)
                    
                    embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
                    
                    await audit_channel.send(content=f"<@{сотрудник.id}>", embed=embed)
                    channel_success = True
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Кадровый аудит добавлен",
                color=discord.Color.green()
            )
            
            status_parts = []
            if sheets_success:
                status_parts.append("✅ Записано в таблицу")
            else:
                status_parts.append("❌ Ошибка записи в таблицу")
                
            if channel_success:
                status_parts.append("✅ Отправлено в канал аудита")
            else:
                status_parts.append("❌ Канал аудита не настроен")
            
            embed.description = "\n".join(status_parts)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error in audit command: {e}")
            embed = discord.Embed(
                title="❌ Произошла ошибка",
                description=f"Ошибка при выполнении команды: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Autocomplete functions
    @audit_command.autocomplete('действие')
    async def action_autocomplete(self, interaction: discord.Interaction, current: str):
        settings = await self._get_settings_data()
        actions = settings.get('actions', [])
        
        # Filter actions based on current input
        filtered = [action for action in actions if current.lower() in action.lower()]
        return [app_commands.Choice(name=action, value=action) for action in filtered[:25]]
    
    @audit_command.autocomplete('подразделение')
    async def department_autocomplete(self, interaction: discord.Interaction, current: str):
        settings = await self._get_settings_data()
        departments = settings.get('departments', [])
        
        filtered = [dept for dept in departments if current.lower() in dept.lower()]
        return [app_commands.Choice(name=dept, value=dept) for dept in filtered[:25]]
    
    @audit_command.autocomplete('должность')
    async def position_autocomplete(self, interaction: discord.Interaction, current: str):
        settings = await self._get_settings_data()
        positions = settings.get('positions', [])
        
        filtered = [pos for pos in positions if current.lower() in pos.lower()]
        return [app_commands.Choice(name=pos, value=pos) for pos in filtered[:25]]
    
    @audit_command.autocomplete('звание')
    async def rank_autocomplete(self, interaction: discord.Interaction, current: str):
        settings = await self._get_settings_data()
        ranks = settings.get('ranks', [])
        
        filtered = [rank for rank in ranks if current.lower() in rank.lower()]
        return [app_commands.Choice(name=rank, value=rank) for rank in filtered[:25]]


async def setup(bot):
    await bot.add_cog(PersonnelCommands(bot))
