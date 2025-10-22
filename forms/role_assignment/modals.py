"""
Application modals for role assignment system
"""

import discord
import re
from discord import ui
from utils.config_manager import load_config, has_pending_role_application
from utils.message_manager import get_role_assignment_message, get_message_with_params


class MilitaryApplicationModal(ui.Modal):
    """Modal for military service role applications"""
    
    def __init__(self):
        super().__init__(title=get_role_assignment_message(0, 'application.military_modal_title', 'Заявка на получение роли военнослужащего'))
        
        self.first_name_input = ui.TextInput(
            label=get_role_assignment_message(0, 'application.first_name_label', 'Имя'),
            placeholder=get_role_assignment_message(0, 'application.first_name_placeholder', 'Например: Олег'),
            min_length=2,
            max_length=25,
            required=True
        )
        self.add_item(self.first_name_input)
        
        self.last_name_input = ui.TextInput(
            label=get_role_assignment_message(0, 'application.last_name_label', 'Фамилия'),
            placeholder=get_role_assignment_message(0, 'application.last_name_placeholder', 'Например: Дубов'),
            min_length=2,
            max_length=25,
            required=True
        )
        self.add_item(self.last_name_input)
        
        self.static_input = ui.TextInput(
            label=get_role_assignment_message(0, 'application.static_label', 'Статик'),
            placeholder=get_role_assignment_message(0, 'application.static_placeholder', '123-456 (допускается 5-6 цифр)'),
            min_length=5,
            max_length=7,
            required=True
        )
        self.add_item(self.static_input)
        
        # Rank is always "Рядовой" for new military recruits, no need for input field
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process military application submission"""
        # Check for pending applications
        config = load_config()
        role_assignment_channel_id = config.get('role_assignment_channel')
        
        if role_assignment_channel_id:
            has_pending = await has_pending_role_application(interaction.client, interaction.user.id, role_assignment_channel_id)
            if has_pending:
                await interaction.response.send_message(
                    f"{get_role_assignment_message(interaction.guild.id, 'application.error_pending_application', '❌ **У вас уже есть заявка на получение роли, которая находится на рассмотрении.**')}\n\n"
                    "Пожалуйста, дождитесь решения по текущей заявке, прежде чем подавать новую.\n"
                    "Это поможет избежать путаницы и ускорить обработку вашего запроса.",
                    ephemeral=True
                )
                return
        
        # Check if user already has a personnel record
        from utils.postgresql_pool import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT is_dismissal FROM personnel WHERE discord_id = %s
            """, (interaction.user.id,))
            existing_personnel = cursor.fetchone()
            
            if existing_personnel:
                if not existing_personnel['is_dismissal']:
                    # User is already active
                    await interaction.response.send_message(
                        "❌ **Вы уже находитесь на службе в Вооруженных Силах РФ.**\n\n"
                        "Если вам нужно изменить данные или перевестись, обратитесь к командованию.",
                        ephemeral=True
                    )
                    return
                else:
                    # User was dismissed, can reapply
                    pass  # Continue with application
        
        # Check if user has active blacklist entry
        from utils.database_manager import personnel_manager
        blacklist_info = await personnel_manager.check_active_blacklist(interaction.user.id)
        
        if blacklist_info:
            # User is blacklisted, deny application
            start_date_str = blacklist_info['start_date'].strftime('%d.%m.%Y')
            end_date_str = blacklist_info['end_date'].strftime('%d.%m.%Y') if blacklist_info['end_date'] else 'Бессрочно'
            
            await interaction.response.send_message(
                f"❌ **Вам запрещен приём на службу**\n\n"
                f"📋 **{blacklist_info['full_name']} | {blacklist_info['static']} находится в Чёрном списке ВС РФ**\n"
                f"> **Причина:** {blacklist_info['reason']}\n"
                f"> **Период:** {start_date_str} - {end_date_str}\n\n"
                f"*Для снятия с чёрного списка обратитесь к руководству бригады.*",
                ephemeral=True
            )
            return
        
        # Validate first name and last name (must be single words)
        first_name = self.first_name_input.value.strip()
        last_name = self.last_name_input.value.strip()
        
        if ' ' in first_name or '\t' in first_name:
            await interaction.response.send_message(
                get_role_assignment_message(interaction.guild.id, 'application.error_first_name_spaces', "❌ **Имя должно содержать только одно слово.**\nПожалуйста, введите только имя без пробелов."),
                ephemeral=True
            )
            return
        
        if ' ' in last_name or '\t' in last_name:
            await interaction.response.send_message(
                get_role_assignment_message(interaction.guild.id, 'application.error_last_name_spaces', "❌ **Фамилия должна содержать только одно слово.**\nПожалуйста, введите только фамилию без пробелов."),
                ephemeral=True
            )
            return
        
        # Combine first and last name
        full_name = f"{first_name} {last_name}"
        
        # Validate and format static
        static = self.static_input.value.strip()
        formatted_static = self._format_static(static)
        if not formatted_static:
            await interaction.response.send_message(
                f"{get_role_assignment_message(interaction.guild.id, 'application.error_invalid_static_format', '❌ Неверный формат статика. Статик должен содержать 5 или 6 цифр.')}\n"
                "Примеры: 123456, 123-456, 12345, 12-345, 123 456",
                ephemeral=True
            )
            return
        
        # Create application data
        application_data = {
            "type": "military",
            "name": full_name,
            "static": formatted_static,
            "rank": "Рядовой",  # Always set rank as "Рядовой" for new military recruits
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
    
    async def _check_blacklist_status(self, static: str):
        """Check if user is in blacklist using PostgreSQL (stub)"""
        try:
            # TODO: Implement PostgreSQL blacklist check
            print(f"Blacklist check for static {static} - skipped (using PostgreSQL stub)")
            return {"is_blocked": False}
        except Exception as e:
            print(f"Error checking blacklist status: {e}")
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
                else:
                    # Ни одна роль не найдена — логируем для отладки
                    print(f"[WARN] Ни одна роль для пинга не найдена по military_role_assignment_ping_roles: {ping_role_ids}")
            else:
                print("[WARN] military_role_assignment_ping_roles пуст или не задан в config")
            
            # Send to moderation channel
            await moderation_channel.send(content=ping_content, embed=embed, view=approval_view)
            
            await interaction.response.send_message(
                get_message_with_params(interaction.guild.id, "role_assignment.application.success_application_submitted", action="Заявка на получение роли"),
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error sending military application: {e}")
            await interaction.response.send_message(
                get_role_assignment_message(interaction.guild.id, "application.error_submission_failed", "❌ Произошла ошибка при отправке заявки. Попробуйте позже."),
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
            label="Удостоверение (ссылка)",
            placeholder="Ссылка на удостоверение",
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
                    f"{get_role_assignment_message(interaction.guild.id, 'application.error_pending_application', '❌ **У вас уже есть заявка на получение роли, которая находится на рассмотрении.**')}\n\n"
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
                f"{get_role_assignment_message(interaction.guild.id, 'application.error_invalid_static_format', '❌ Неверный формат статика. Статик должен содержать 5 или 6 цифр.')}\n"
                "Примеры: 123456, 123-456, 12345, 12-345, 123 456",
                ephemeral=True
            )
            return
        
        # Validate proof URL
        proof = self.proof_input.value.strip()
        if not self._validate_url(proof):
            await interaction.response.send_message(
                get_role_assignment_message(interaction.guild.id, "application.error_invalid_proof_link", "❌ Пожалуйста, укажите корректную ссылку в поле доказательств."),
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
        """Basic URL validation - accepts various formats"""
        # More permissive URL pattern that accepts:
        # - http/https URLs
        # - URLs without protocol (like discord.gg/...)
        # - Common domain formats including single-letter TLDs
        url_pattern = r'(https?://)?([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{1,}(/[^\s]*)?'
        return bool(re.match(url_pattern, url.strip()))
    
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
            embed.add_field(name="🔗 Удостоверение", value=f"[Ссылка]({application_data['proof']})", inline=False)
            
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
            placeholder="Например: ФСИН, МО РФ, ФСБ",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.faction_input)
        
        self.proof_input = ui.TextInput(
            label="Удостоверение (ссылка)",
            placeholder="Ссылка на удостоверение",
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
                get_role_assignment_message(interaction.guild.id, "application.error_invalid_proof_link", "❌ Пожалуйста, укажите корректную ссылку в поле доказательств."),
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
        """Basic URL validation - accepts various formats"""
        # More permissive URL pattern that accepts:
        # - http/https URLs
        # - URLs without protocol (like discord.gg/...)
        # - Common domain formats including single-letter TLDs
        url_pattern = r'(https?://)?([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{1,}(/[^\s]*)?'
        return bool(re.match(url_pattern, url.strip()))
    
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
            embed.add_field(name="🔗 Удостоверение", value=f"[Ссылка]({application_data['proof']})", inline=False)
            
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



# =============== МОДАЛЬНЫЕ ФОРМЫ ДЛЯ РЕДАКТИРОВАНИЯ ===============

class MilitaryEditModal(ui.Modal):
    """Modal for editing military service role applications"""
    
    def __init__(self, application_data: dict):
        super().__init__(title="✏️ Редактирование военной заявки")
        self.application_data = application_data
        
        # Предзаполняем поля текущими данными
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Например: Олег Дубов",
            min_length=2,
            max_length=50,
            required=True,
            default=application_data.get('name', '')
        )
        self.add_item(self.name_input)
        
        self.static_input = ui.TextInput(
            label="Статик",
            placeholder="123-456 (допускается 5-6 цифр)",
            min_length=5,
            max_length=7,
            required=True,
            default=application_data.get('static', '')
        )
        self.add_item(self.static_input)
        
        # Rank is always "Рядовой" for military personnel, no need for input field
    
    async def on_submit(self, interaction: discord.Interaction):
        """Обработка редактирования военной заявки"""
        try:
            # Валидация и форматирование статика
            static = self.static_input.value.strip()
            formatted_static = self._format_static(static)
            if not formatted_static:
                await interaction.response.send_message(
                    "❌ Неверный формат статика. Статик должен содержать 5 или 6 цифр.\n"
                    "Примеры: 123456, 123-456, 12345, 12-345, 123 456",
                    ephemeral=True
                )
                return
            
            # Собираем новые данные
            updated_data = {
                'name': self.name_input.value.strip(),
                'static': formatted_static,
                'rank': "Рядовой",  # Always set rank as "Рядовой" for military personnel
                # Сохраняем оригинальные данные
                'type': self.application_data['type'],
                'user_id': self.application_data['user_id'],
                'user_mention': self.application_data.get('user_mention', f"<@{self.application_data['user_id']}>"),
                'timestamp': self.application_data.get('timestamp')
            }
            
            await self._handle_edit_update(interaction, updated_data)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Произошла ошибка при редактировании заявки: {str(e)}",
                ephemeral=True
            )
    
    def _format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return ""
    
    async def _handle_edit_update(self, interaction: discord.Interaction, updated_data: dict):
        """Обновление embed с новыми данными"""
        try:
            # Обновляем embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.blue()  # Оставляем синий цвет для военных
            
            # Обновляем поля и удаляем старое поле "Отредактировано" если есть
            fields_to_remove = []
            for i, field in enumerate(embed.fields):
                if field.name == "📝 Имя Фамилия":
                    embed.set_field_at(i, name="📝 Имя Фамилия", value=updated_data['name'], inline=True)
                elif field.name == "🔢 Статик":
                    embed.set_field_at(i, name="🔢 Статик", value=updated_data['static'], inline=True)
                elif field.name == "🎖️ Звание":
                    embed.set_field_at(i, name="🎖️ Звание", value=updated_data['rank'], inline=True)
                elif field.name == "✏️ Отредактировано":
                    fields_to_remove.append(i)
            
            # Удаляем старые поля "Отредактировано" (в обратном порядке, чтобы не сбить индексы)
            for i in reversed(fields_to_remove):
                embed.remove_field(i)
            
            # Добавляем обновленную информацию о редактировании
            embed.add_field(
                name="✏️ Отредактировано",
                value=f"{interaction.user.mention}\n{discord.utils.format_dt(discord.utils.utcnow(), 'f')}",
                inline=True
            )
            
            # Обновляем сообщение
            await interaction.response.edit_message(embed=embed)
            
        except Exception as e:
            print(f"Error updating military application embed: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обновлении заявки.",
                ephemeral=True
            )


class CivilianEditModal(ui.Modal):
    """Modal for editing civilian role applications"""
    
    def __init__(self, application_data: dict):
        super().__init__(title="✏️ Редактирование гражданской заявки")
        self.application_data = application_data
        
        # Предзаполняем поля текущими данными
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Например: Олег Дубов",
            min_length=2,
            max_length=50,
            required=True,
            default=application_data.get('name', '')
        )
        self.add_item(self.name_input)
        
        self.static_input = ui.TextInput(
            label="Статик",
            placeholder="123-456 (допускается 5-6 цифр)",
            min_length=5,
            max_length=7,
            required=True,
            default=application_data.get('static', '')
        )
        self.add_item(self.static_input)
        
        self.faction_input = ui.TextInput(
            label="Фракция, звание, должность",
            placeholder="Например: ФСВНГ, Подполковник, Нач. Упр. Вневедомственной Охраны",
            min_length=1,
            max_length=100,
            required=True,
            default=application_data.get('faction', '')
        )
        self.add_item(self.faction_input)
        
        self.purpose_input = ui.TextInput(
            label="Цель получения роли",
            placeholder="Например: доступ к пропуску (на территорию в/ч)",
            min_length=1,
            max_length=100,
            required=True,
            default=application_data.get('purpose', '')
        )
        self.add_item(self.purpose_input)
        
        self.proof_input = ui.TextInput(
            label="Удостоверение (ссылка)",
            placeholder="Ссылка на удостоверение",
            min_length=5,
            max_length=200,
            required=True,
            default=application_data.get('proof', '')
        )
        self.add_item(self.proof_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Обработка редактирования гражданской заявки"""
        try:
            # Валидация и форматирование статика
            static = self.static_input.value.strip()
            formatted_static = self._format_static(static)
            if not formatted_static:
                await interaction.response.send_message(
                    "❌ Неверный формат статика. Статик должен содержать 5 или 6 цифр.\n"
                    "Примеры: 123456, 123-456, 12345, 12-345, 123 456",
                    ephemeral=True
                )
                return
            
            # Валидация ссылки
            proof = self.proof_input.value.strip()
            if not self._validate_url(proof):
                await interaction.response.send_message(
                    "❌ Пожалуйста, укажите корректную ссылку в поле доказательств.",
                    ephemeral=True
                )
                return
            
            # Собираем новые данные
            updated_data = {
                'name': self.name_input.value.strip(),
                'static': formatted_static,
                'faction': self.faction_input.value.strip(),
                'purpose': self.purpose_input.value.strip(),
                'proof': proof,
                # Сохраняем оригинальные данные
                'type': self.application_data['type'],
                'user_id': self.application_data['user_id'],
                'user_mention': self.application_data.get('user_mention', f"<@{self.application_data['user_id']}>"),
                'timestamp': self.application_data.get('timestamp')
            }
            
            await self._handle_edit_update(interaction, updated_data)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Произошла ошибка при редактировании заявки: {str(e)}",
                ephemeral=True
            )
    
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
        """Basic URL validation - accepts various formats"""
        # More permissive URL pattern that accepts:
        # - http/https URLs
        # - URLs without protocol (like discord.gg/...)
        # - Common domain formats
        url_pattern = r'(https?://)?([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{1,}(/[^\s]*)?'
        return bool(re.match(url_pattern, url.strip()))
    
    async def _handle_edit_update(self, interaction: discord.Interaction, updated_data: dict):
        """Обновление embed с новыми данными"""
        try:
            # Обновляем embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.orange()  # Оставляем оранжевый цвет для гражданских
            
            # Обновляем поля и удаляем старое поле "Отредактировано" если есть
            fields_to_remove = []
            for i, field in enumerate(embed.fields):
                if field.name == "📝 Имя Фамилия":
                    embed.set_field_at(i, name="📝 Имя Фамилия", value=updated_data['name'], inline=True)
                elif field.name == "🔢 Статик":
                    embed.set_field_at(i, name="🔢 Статик", value=updated_data['static'], inline=True)
                elif field.name == "🏛️ Фракция, звание, должность":
                    embed.set_field_at(i, name="🏛️ Фракция, звание, должность", value=updated_data['faction'], inline=False)
                elif field.name == "🎯 Цель получения роли":
                    embed.set_field_at(i, name="🎯 Цель получения роли", value=updated_data['purpose'], inline=False)
                elif field.name == "🔗 Удостоверение":
                    embed.set_field_at(i, name="🔗 Удостоверение", value=f"[Ссылка]({updated_data['proof']})", inline=False)
                elif field.name == "✏️ Отредактировано":
                    fields_to_remove.append(i)
            
            # Удаляем старые поля "Отредактировано" (в обратном порядке, чтобы не сбить индексы)
            for i in reversed(fields_to_remove):
                embed.remove_field(i)
            
            # Добавляем обновленную информацию о редактировании
            embed.add_field(
                name="✏️ Отредактировано",
                value=f"{interaction.user.mention}\n{discord.utils.format_dt(discord.utils.utcnow(), 'f')}",
                inline=True
            )
            
            # Обновляем сообщение
            await interaction.response.edit_message(embed=embed)
            
        except Exception as e:
            print(f"Error updating civilian application embed: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обновлении заявки.",
                ephemeral=True
            )


class SupplierEditModal(ui.Modal):
    """Modal for editing supplier role applications"""
    
    def __init__(self, application_data: dict):
        super().__init__(title="✏️ Редактирование заявки поставщика")
        self.application_data = application_data
        
        # Предзаполняем поля текущими данными
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Например: Олег Дубов",
            min_length=2,
            max_length=50,
            required=True,
            default=application_data.get('name', '')
        )
        self.add_item(self.name_input)
        
        self.static_input = ui.TextInput(
            label="Статик",
            placeholder="123-456 (допускается 5-6 цифр)",
            min_length=5,
            max_length=7,
            required=True,
            default=application_data.get('static', '')
        )
        self.add_item(self.static_input)
        
        self.faction_input = ui.TextInput(
            label="Фракция, звание, должность",
            placeholder="Например: ФСИН, МО РФ, ФСБ",
            min_length=1,
            max_length=100,
            required=True,
            default=application_data.get('faction', '')
        )
        self.add_item(self.faction_input)
        
        self.proof_input = ui.TextInput(
            label="Удостоверение (ссылка)",
            placeholder="Ссылка на удостоверение",
            min_length=5,
            max_length=200,
            required=True,
            default=application_data.get('proof', '')
        )
        self.add_item(self.proof_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Обработка редактирования заявки поставщика"""
        try:
            # Валидация и форматирование статика
            static = self.static_input.value.strip()
            formatted_static = self._format_static(static)
            if not formatted_static:
                await interaction.response.send_message(
                    "❌ Неверный формат статика. Статик должен содержать 5 или 6 цифр.\n"
                    "Примеры: 123456, 123-456, 12345, 12-345, 123 456",
                    ephemeral=True
                )
                return
            
            # Валидация ссылки
            proof = self.proof_input.value.strip()
            if not self._validate_url(proof):
                await interaction.response.send_message(
                    "❌ Пожалуйста, укажите корректную ссылку в поле доказательств.",
                    ephemeral=True
                )
                return
            
            # Собираем новые данные
            updated_data = {
                'name': self.name_input.value.strip(),
                'static': formatted_static,
                'faction': self.faction_input.value.strip(),
                'proof': proof,
                # Сохраняем оригинальные данные
                'type': self.application_data['type'],
                'user_id': self.application_data['user_id'],
                'user_mention': self.application_data.get('user_mention', f"<@{self.application_data['user_id']}>"),
                'timestamp': self.application_data.get('timestamp')
            }
            
            await self._handle_edit_update(interaction, updated_data)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Произошла ошибка при редактировании заявки: {str(e)}",
                ephemeral=True
            )
    
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
        """Basic URL validation - accepts various formats"""
        # More permissive URL pattern that accepts:
        # - http/https URLs
        # - URLs without protocol (like discord.gg/...)
        # - Common domain formats
        url_pattern = r'(https?://)?([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+\.[a-zA-Z]{1,}(/[^\s]*)?'
        return bool(re.match(url_pattern, url.strip()))
    
    async def _handle_edit_update(self, interaction: discord.Interaction, updated_data: dict):
        """Обновление embed с новыми данными"""
        try:
            # Обновляем embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.orange()  # Оставляем оранжевый цвет для поставщиков
            
            # Обновляем поля и удаляем старое поле "Отредактировано" если есть
            fields_to_remove = []
            for i, field in enumerate(embed.fields):
                if field.name == "📝 Имя Фамилия":
                    embed.set_field_at(i, name="📝 Имя Фамилия", value=updated_data['name'], inline=True)
                elif field.name == "🔢 Статик":
                    embed.set_field_at(i, name="🔢 Статик", value=updated_data['static'], inline=True)
                elif field.name == "🏛️ Фракция, звание, должность":
                    embed.set_field_at(i, name="🏛️ Фракция, звание, должность", value=updated_data['faction'], inline=False)
                elif field.name == "🔗 Удостоверение":
                    embed.set_field_at(i, name="🔗 Удостоверение", value=f"[Ссылка]({updated_data['proof']})", inline=False)
                elif field.name == "✏️ Отредактировано":
                    fields_to_remove.append(i)
            
            # Удаляем старые поля "Отредактировано" (в обратном порядке, чтобы не сбить индексы)
            for i in reversed(fields_to_remove):
                embed.remove_field(i)
            
            # Добавляем обновленную информацию о редактировании
            embed.add_field(
                name="✏️ Отредактировано",
                value=f"{interaction.user.mention}\n{discord.utils.format_dt(discord.utils.utcnow(), 'f')}",
                inline=True
            )
            
            # Обновляем сообщение
            await interaction.response.edit_message(embed=embed)
            
        except Exception as e:
            print(f"Error updating supplier application embed: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обновлении заявки.",
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
