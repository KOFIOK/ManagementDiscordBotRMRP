"""
Application modals for role assignment system
"""

import discord
import re
from datetime import datetime, timezone, timedelta
from discord import ui
from utils.config_manager import load_config, has_pending_role_application
from utils.google_sheets import sheets_manager, retry_on_google_error


class MilitaryApplicationModal(ui.Modal):
    """Modal for military service role applications"""
    
    def __init__(self):
        super().__init__(title="Заявка на получение роли военнослужащего")
        
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Например: Иван Иванов",
            min_length=2,
            max_length=50,
            required=True
        )
        self.add_item(self.name_input)
        
        self.static_input = ui.TextInput(
            label="Статик",
            placeholder="123-456 (допускается 5-6 цифр)",
            min_length=5,
            max_length=7,
            required=True
        )
        self.add_item(self.static_input)
        
        self.rank_input = ui.TextInput(
            label="Звание",
            placeholder="Обычно: Рядовой",
            min_length=1,
            max_length=30,
            required=True,
            default="Рядовой"
        )
        self.add_item(self.rank_input)
        
        self.recruitment_type_input = ui.TextInput(
            label="Порядок набора",
            placeholder="Экскурсия или Призыв",
            min_length=1,
            max_length=20,
            required=True
        )
        self.add_item(self.recruitment_type_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process military application submission"""
        # Check for pending applications
        config = load_config()
        role_assignment_channel_id = config.get('role_assignment_channel')
        
        if role_assignment_channel_id:
            has_pending = await has_pending_role_application(interaction.client, interaction.user.id, role_assignment_channel_id)
            if has_pending:
                await interaction.response.send_message(
                    "❌ **У вас уже есть заявка на получение роли, которая находится на рассмотрении.**\n\n"
                    "Пожалуйста, дождитесь решения по текущей заявке, прежде чем подавать новую.\n"
                    "Это поможет избежать путаницы и ускорить обработку вашего запроса.",
                    ephemeral=True
                )
                return
        
        # Validate and format static
        static = self.static_input.value.strip()
        formatted_static = self._format_static(static)
        if not formatted_static:
            await interaction.response.send_message(
                "❌ Неверный формат статика. Статик должен содержать 5 или 6 цифр.\n"
                "Примеры: 123456, 123-456, 12345, 12-345, 123 456",
                ephemeral=True
            )
            return
          # Validate recruitment type
        recruitment_type = self.recruitment_type_input.value.strip().lower()
        if recruitment_type not in ["экскурсия", "призыв"]:
            await interaction.response.send_message(
                "❌ Порядок набора должен быть: 'Экскурсия' или 'Призыв'.",
                ephemeral=True
            )
            return
        
        # Check blacklist status for military applications
        blacklist_check = await self._check_blacklist_status(formatted_static)
        if blacklist_check["is_blocked"]:
            await interaction.response.send_message(
                f"### ❌ **Доступ к подаче заявки временно ограничен — Вы в Чёрном Списке!**\n\n"
                f"> **Причина:** {blacklist_check['reason']}\n"
                f"> **Чёрный Список выдал:** {blacklist_check['officer']}\n"
                f"> **Ограничение по (включительно):** {blacklist_check['end_date']}",
                ephemeral=True
            )
            return
        
        # Create application data
        application_data = {
            "type": "military",
            "name": self.name_input.value.strip(),
            "static": formatted_static,
            "rank": self.rank_input.value.strip(),
            "recruitment_type": recruitment_type,
            "user_id": interaction.user.id,
            "user_mention": interaction.user.mention
        }
        
        # Send for approval
        await self._send_application_for_approval(interaction, application_data)
    
    def _format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return ""
    
    @retry_on_google_error(retries=3, delay=1)
    async def _check_blacklist_status(self, static_formatted):
        """Check if user is blacklisted based on static number"""
        try:
            # Check if Google Sheets manager is available
            if not sheets_manager:
                print("Google Sheets manager not available")
                return {"is_blocked": False}
            
            # Ensure connection
            if not sheets_manager._ensure_connection():
                print("No Google Sheets connection for blacklist check")
                return {"is_blocked": False}
            
            # Get the 'Отправлено (НЕ РЕДАКТИРОВАТЬ)' worksheet
            blacklist_worksheet = None
            for worksheet in sheets_manager.spreadsheet.worksheets():
                if worksheet.title == "Отправлено (НЕ РЕДАКТИРОВАТЬ)":
                    blacklist_worksheet = worksheet
                    break
            
            if not blacklist_worksheet:
                print("'Отправлено (НЕ РЕДАКТИРОВАТЬ)' sheet not found")
                return {"is_blocked": False}
            
            # Get all values from the sheet
            sheet_data = blacklist_worksheet.get_all_values()
            if not sheet_data:
                print("No data found in blacklist sheet")
                return {"is_blocked": False}
            
            # Find records with matching static
            found_records = []
            for row_index, row_data in enumerate(sheet_data):
                # Skip header row and empty rows
                if row_index == 0 or len(row_data) < 6:
                    continue
                
                # Check if column B ends with " | {static_formatted}"
                column_b = str(row_data[1]) if len(row_data) > 1 else ""
                if column_b.endswith(f" | {static_formatted}"):
                    found_records.append((row_index, row_data))
            
            if not found_records:
                return {"is_blocked": False}
            
            # Get the most recent record (smallest row index = closest to top)
            latest_record = min(found_records, key=lambda x: x[0])
            row_data = latest_record[1]
            
            # Parse end date from column E (format: DD.MM.YYYY)
            end_date_str = str(row_data[4]) if len(row_data) > 4 else ""
            if not end_date_str or end_date_str.strip() == "":
                return {"is_blocked": False}
            
            try:
                end_date = datetime.strptime(end_date_str.strip(), "%d.%m.%Y").date()
            except ValueError:
                print(f"Invalid date format in blacklist: {end_date_str}")
                return {"is_blocked": False}
            
            # Get current date in Moscow timezone (UTC+3)
            moscow_tz = timezone(timedelta(hours=3))
            current_date = datetime.now(moscow_tz).date()
            
            if end_date >= current_date:
                # Punishment is still active
                reason = str(row_data[2]) if len(row_data) > 2 else "Не указана"
                officer = str(row_data[5]) if len(row_data) > 5 else "Не указан"
                
                return {
                    "is_blocked": True,
                    "reason": reason,
                    "officer": officer,
                    "end_date": end_date_str
                }
            else:
                # Punishment has expired
                return {"is_blocked": False}
                
        except Exception as e:
            print(f"Error checking blacklist status: {e}")
            # Fail-safe: allow application submission if there's an error
            return {"is_blocked": False}
    
    async def _send_application_for_approval(self, interaction, application_data):
        """Send application to moderation channel"""
        try:
            config = load_config()
            moderation_channel_id = config.get('role_assignment_channel')
            
            if not moderation_channel_id:
                await interaction.response.send_message(
                    "❌ Канал модерации не настроен. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            moderation_channel = interaction.guild.get_channel(moderation_channel_id)
            if not moderation_channel:
                await interaction.response.send_message(
                    "❌ Канал модерации не найден. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Create embed
            embed = discord.Embed(
                title="📋 Заявка на получение роли военнослужащего",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="👤 Заявитель", value=application_data["user_mention"], inline=False)
            embed.add_field(name="📝 Имя Фамилия", value=application_data["name"], inline=True)
            embed.add_field(name="🔢 Статик", value=application_data["static"], inline=True)
            embed.add_field(name="🎖️ Звание", value=application_data["rank"], inline=True)
            embed.add_field(name="📋 Порядок набора", value=application_data["recruitment_type"].title(), inline=True)
            
            # Create approval view
            from .base import create_approval_view
            approval_view = create_approval_view(application_data)
            
            # Get ping roles
            ping_role_ids = config.get('military_role_assignment_ping_roles', [])
            ping_content = ""
            if ping_role_ids:
                ping_mentions = []
                for ping_role_id in ping_role_ids:
                    ping_role = moderation_channel.guild.get_role(ping_role_id)
                    if ping_role:
                        ping_mentions.append(ping_role.mention)
                if ping_mentions:
                    ping_content = f"-# {' '.join(ping_mentions)}"
            
            # Send to moderation channel
            await moderation_channel.send(content=ping_content, embed=embed, view=approval_view)
            
            await interaction.response.send_message(
                "✅ Ваша заявка отправлена на рассмотрение военнослужащим. Ожидайте решения.",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error sending military application: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при отправке заявки. Попробуйте позже.",
                ephemeral=True
            )


class CivilianApplicationModal(ui.Modal):
    """Modal for civilian role applications"""
    
    def __init__(self):
        super().__init__(title="Заявка на получение роли госслужащего")
        
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Например: Иван Иванов",
            min_length=2,
            max_length=50,
            required=True
        )
        self.add_item(self.name_input)
        
        self.static_input = ui.TextInput(
            label="Статик",
            placeholder="123-456 (допускается 5-6 цифр)",
            min_length=5,
            max_length=7,
            required=True
        )
        self.add_item(self.static_input)
        
        self.faction_input = ui.TextInput(
            label="Фракция, звание, должность",
            placeholder="Например: ФСВНГ, Подполковник, Нач. Упр. Вневедомственной Охраны",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.faction_input)
        
        self.purpose_input = ui.TextInput(
            label="Цель получения роли",
            placeholder="Например: доступ к пропуску (на территорию в/ч)",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.purpose_input)
        
        self.proof_input = ui.TextInput(
            label="Доказательства (ссылка)",
            placeholder="Ссылка на доказательства",
            min_length=5,
            max_length=200,
            required=True
        )
        self.add_item(self.proof_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process civilian application submission"""
        # Check for pending applications
        config = load_config()
        role_assignment_channel_id = config.get('role_assignment_channel')
        
        if role_assignment_channel_id:
            has_pending = await has_pending_role_application(interaction.client, interaction.user.id, role_assignment_channel_id)
            if has_pending:
                await interaction.response.send_message(
                    "❌ **У вас уже есть заявка на получение роли, которая находится на рассмотрении.**\n\n"
                    "Пожалуйста, дождитесь решения по текущей заявке, прежде чем подавать новую.\n"
                    "Это поможет избежать путаницы и ускорить обработку вашего запроса.",
                    ephemeral=True
                )
                return
        
        # Validate and format static
        static = self.static_input.value.strip()
        formatted_static = self._format_static(static)
        if not formatted_static:
            await interaction.response.send_message(
                "❌ Неверный формат статика. Статик должен содержать 5 или 6 цифр.\n"
                "Примеры: 123456, 123-456, 12345, 12-345, 123 456",
                ephemeral=True
            )
            return
        
        # Validate proof URL
        proof = self.proof_input.value.strip()
        if not self._validate_url(proof):
            await interaction.response.send_message(
                "❌ Пожалуйста, укажите корректную ссылку в поле доказательств.",
                ephemeral=True
            )
            return
        
        # Create application data
        application_data = {
            "type": "civilian",
            "name": self.name_input.value.strip(),
            "static": formatted_static,
            "faction": self.faction_input.value.strip(),
            "purpose": self.purpose_input.value.strip(),
            "proof": proof,
            "user_id": interaction.user.id,
            "user_mention": interaction.user.mention
        }
        
        # Send for approval
        await self._send_application_for_approval(interaction, application_data)
    
    def _format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return ""
    
    def _validate_url(self, url):
        """Basic URL validation"""
        url_pattern = r'https?://[^\s/$.?#].[^\s]*'
        return bool(re.match(url_pattern, url))
    
    async def _send_application_for_approval(self, interaction, application_data):
        """Send application to moderation channel"""
        try:
            config = load_config()
            moderation_channel_id = config.get('role_assignment_channel')
            
            if not moderation_channel_id:
                await interaction.response.send_message(
                    "❌ Канал модерации не настроен. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            moderation_channel = interaction.guild.get_channel(moderation_channel_id)
            if not moderation_channel:
                await interaction.response.send_message(
                    "❌ Канал модерации не найден. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Create embed
            embed = discord.Embed(
                title="📋 Заявка на получение роли госслужащего",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="👤 Заявитель", value=application_data["user_mention"], inline=False)
            embed.add_field(name="📝 Имя Фамилия", value=application_data["name"], inline=True)
            embed.add_field(name="🔢 Статик", value=application_data["static"], inline=True)
            embed.add_field(name="🏛️ Фракция, звание, должность", value=application_data["faction"], inline=False)
            embed.add_field(name="🎯 Цель получения роли", value=application_data["purpose"], inline=False)
            embed.add_field(name="🔗 Доказательства", value=f"[Ссылка]({application_data['proof']})", inline=False)
            
            # Create approval view
            from .base import create_approval_view
            approval_view = create_approval_view(application_data)
            
            # Get ping roles
            ping_role_ids = config.get('civilian_role_assignment_ping_roles', [])
            ping_content = ""
            if ping_role_ids:
                ping_mentions = []
                for ping_role_id in ping_role_ids:
                    ping_role = moderation_channel.guild.get_role(ping_role_id)
                    if ping_role:
                        ping_mentions.append(ping_role.mention)
                if ping_mentions:
                    ping_content = f"-# {' '.join(ping_mentions)}"
            
            # Send to moderation channel
            await moderation_channel.send(content=ping_content, embed=embed, view=approval_view)
            
            await interaction.response.send_message(
                "✅ Ваша заявка отправлена на рассмотрение военнослужащим. Ожидайте решения.",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error sending civilian application: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при отправке заявки. Попробуйте позже.",
                ephemeral=True
            )


class SupplierApplicationModal(ui.Modal):
    """Modal for supplier role applications"""
    
    def __init__(self):
        super().__init__(title="Заявка на получение роли доступа к поставкам")
        
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Например: Иван Иванов",
            min_length=2,
            max_length=50,
            required=True
        )
        self.add_item(self.name_input)
        
        self.static_input = ui.TextInput(
            label="Статик",
            placeholder="123-456 (допускается 5-6 цифр)",
            min_length=5,
            max_length=7,
            required=True
        )
        self.add_item(self.static_input)
        
        self.faction_input = ui.TextInput(
            label="Фракция, звание, должность",
            placeholder="Например: ФСВНГ, Подполковник",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.faction_input)
        
        self.proof_input = ui.TextInput(
            label="Доказательства (ссылка)",
            placeholder="Ссылка на доказательства",
            min_length=5,
            max_length=200,
            required=True
        )
        self.add_item(self.proof_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process supplier application submission"""
        # Check for pending applications
        config = load_config()
        role_assignment_channel_id = config.get('role_assignment_channel')
        
        if role_assignment_channel_id:
            has_pending = await has_pending_role_application(interaction.client, interaction.user.id, role_assignment_channel_id)
            if has_pending:
                await interaction.response.send_message(
                    "❌ **У вас уже есть заявка на получение роли, которая находится на рассмотрении.**\n\n"
                    "Пожалуйста, дождитесь решения по текущей заявке, прежде чем подавать новую.\n"
                    "Это поможет избежать путаницы и ускорить обработку вашего запроса.",
                    ephemeral=True
                )
                return
        
        # Validate and format static
        static = self.static_input.value.strip()
        formatted_static = self._format_static(static)
        if not formatted_static:
            await interaction.response.send_message(
                "❌ Неверный формат статика. Статик должен содержать 5 или 6 цифр.\n"
                "Примеры: 123456, 123-456, 12345, 12-345, 123 456",
                ephemeral=True
            )
            return
        
        # Validate proof URL
        proof = self.proof_input.value.strip()
        if not self._validate_url(proof):
            await interaction.response.send_message(
                "❌ Пожалуйста, укажите корректную ссылку в поле доказательств.",
                ephemeral=True
            )
            return
        
        # Create application data
        application_data = {
            "type": "supplier",
            "name": self.name_input.value.strip(),
            "static": formatted_static,
            "faction": self.faction_input.value.strip(),
            "proof": proof,
            "user_id": interaction.user.id,
            "user_mention": interaction.user.mention
        }
        
        # Send for approval
        await self._send_application_for_approval(interaction, application_data)
    
    def _format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return ""
    
    def _validate_url(self, url):
        """Basic URL validation"""
        url_pattern = r'https?://[^\s/$.?#].[^\s]*'
        return bool(re.match(url_pattern, url))
    
    async def _send_application_for_approval(self, interaction, application_data):
        """Send application to moderation channel"""
        try:
            config = load_config()
            moderation_channel_id = config.get('role_assignment_channel')
            
            if not moderation_channel_id:
                await interaction.response.send_message(
                    "❌ Канал модерации не настроен. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            moderation_channel = interaction.guild.get_channel(moderation_channel_id)
            if not moderation_channel:
                await interaction.response.send_message(
                    "❌ Канал модерации не найден. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Create embed
            embed = discord.Embed(
                title="📦 Заявка на получение роли доступа к поставкам",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="👤 Заявитель", value=application_data["user_mention"], inline=False)
            embed.add_field(name="📝 Имя Фамилия", value=application_data["name"], inline=True)
            embed.add_field(name="🔢 Статик", value=application_data["static"], inline=True)
            embed.add_field(name="🏛️ Фракция, звание, должность", value=application_data["faction"], inline=False)
            embed.add_field(name="🔗 Доказательства", value=f"[Ссылка]({application_data['proof']})", inline=False)
            
            # Create approval view
            from .base import create_approval_view
            approval_view = create_approval_view(application_data)
            
            # Get ping roles
            ping_role_ids = config.get('supplier_role_assignment_ping_roles', [])
            ping_content = ""
            if ping_role_ids:
                ping_mentions = []
                for ping_role_id in ping_role_ids:
                    ping_role = moderation_channel.guild.get_role(ping_role_id)
                    if ping_role:
                        ping_mentions.append(ping_role.mention)
                if ping_mentions:
                    ping_content = f"-# {' '.join(ping_mentions)}"
            
            # Send to moderation channel
            await moderation_channel.send(content=ping_content, embed=embed, view=approval_view)
            
            await interaction.response.send_message(
                "✅ Ваша заявка отправлена на рассмотрение военнослужащим. Ожидайте решения.",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error sending supplier application: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при отправке заявки. Попробуйте позже.",
                ephemeral=True
            )


class RoleRejectionReasonModal(ui.Modal, title="Причина отказа"):
    """Modal for requesting rejection reason when rejecting role applications"""
    
    reason_input = ui.TextInput(
        label="Введите причину отказа:",
        placeholder="Укажите причину отказа заявки на получение роли",
        style=discord.TextStyle.paragraph,        min_length=0,
        max_length=500,
        required=True
    )
    
    def __init__(self, callback_func, *args, **kwargs):
        super().__init__()
        self.callback_func = callback_func
        self.callback_args = args
        self.callback_kwargs = kwargs
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            reason = self.reason_input.value.strip()
            
            # Call the callback function with rejection reason
            if self.callback_func:
                await self.callback_func(interaction, reason, *self.callback_args, **self.callback_kwargs)
                
        except Exception as e:
            print(f"Error in RoleRejectionReasonModal: {e}")
            # Check if we already responded to avoid errors
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Произошла ошибка при обработке причины отказа.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Произошла ошибка при обработке причины отказа.",
                    ephemeral=True
                )
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"RoleRejectionReasonModal error: {error}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Произошла ошибка при обработке причины отказа. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "Произошла ошибка при обработке причины отказа. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
                    ephemeral=True
                )
        except Exception as follow_error:
            print(f"Failed to send error message in RoleRejectionReasonModal.on_error: {follow_error}")
