"""
Department Application Forms - Two-stage modal forms for department applications
"""
import discord
from discord import ui
import re
import asyncio
from typing import Dict, Any
import logging
from datetime import datetime, timezone, timedelta

from utils.user_database import UserDatabase
from utils.ping_manager import ping_manager

logger = logging.getLogger(__name__)


class DepartmentApplicationStage1Modal(ui.Modal):
    """Stage 1: IC Information modal for department applications"""
    
    def __init__(self, department_code: str, application_type: str, user_ic_data: Dict[str, Any]):
        self.department_code = department_code
        self.application_type = application_type  # 'join' or 'transfer'
        self.user_ic_data = user_ic_data
        
        title = f"Заявление в {department_code} - IC Информация"
        if application_type == 'transfer':
            title += " (Перевод)"
        
        super().__init__(title=title, timeout=300)
        
        # Pre-fill IC data from Google Sheets
        self._setup_fields()
    
    def _setup_fields(self):
        """Setup form fields with auto-filled IC data"""
        
        # Auto-fill from user database
        ic_first_name = self.user_ic_data.get('first_name', '')
        ic_last_name = self.user_ic_data.get('last_name', '')
        ic_static = self.user_ic_data.get('static', '')
        
        # Full name field
        full_name = f"{ic_first_name} {ic_last_name}".strip()
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Иван Иванов",
            default=full_name,
            max_length=100,
            required=True
        )
        self.add_item(self.name_input)
        
        # Static field with auto-formatting
        self.static_input = ui.TextInput(
            label="Статик",
            placeholder="123456 или 123-456",
            default=ic_static,
            max_length=10,
            required=True
        )
        self.add_item(self.static_input)
        
        # Document copy (link to image)
        self.document_input = ui.TextInput(
            label="Ксерокопия служебного документа",
            placeholder="Ссылка на изображение документа",
            style=discord.TextStyle.short,
            max_length=500,
            required=True
        )
        self.add_item(self.document_input)
        
        # Reason for department choice
        self.reason_input = ui.TextInput(
            label="Причины выбора подразделения",
            placeholder="Опишите, почему вы выбрали именно это подразделение...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.reason_input)
    
    def format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return ""
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle Stage 1 submission"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Validate static
            formatted_static = self.format_static(self.static_input.value)
            if not formatted_static:
                await interaction.followup.send(
                    "❌ **Ошибка валидации статика**\n"
                    "Статик должен содержать ровно 5 или 6 цифр.\n"
                    "**Примеры:** `123456` → `123-456`, `12345` → `12-345`",
                    ephemeral=True
                )
                return
            
            # Validate document link
            document_url = self.document_input.value.strip()
            if not self._validate_url(document_url):
                await interaction.followup.send(
                    "❌ **Ошибка валидации ссылки**\n"
                    "Пожалуйста, укажите корректную ссылку на документ.\n"
                    "Поддерживаются внешние ссылки на изображения.",
                    ephemeral=True
                )
                return
            
            # Store Stage 1 data
            stage1_data = {
                'name': self.name_input.value.strip(),
                'static': formatted_static,
                'document_url': document_url,
                'reason': self.reason_input.value.strip(),
                'department_code': self.department_code,
                'application_type': self.application_type
            }
            
            # Create draft embed
            draft_embed = self._create_draft_embed(stage1_data, interaction.user)
            
            # Create view with continue/cancel buttons
            view = Stage1ReviewView(stage1_data)
            
            await interaction.followup.send(
                "📋 **Черновик заявления - IC Информация**\n"
                "Проверьте данные и выберите действие:",
                embed=draft_embed,
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in Stage 1 application: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка. Попробуйте еще раз.",
                ephemeral=True
            )
    
    def _validate_url(self, url: str) -> bool:
        """Validate if URL is a valid link"""
        if not url:
            return False
        
        # Basic URL validation
        url_lower = url.lower()
        return (
            url.startswith(('http://', 'https://')) or
            url.startswith('https://cdn.discordapp.com/') or
            url.startswith('https://media.discordapp.net/')
        )
    
    def _create_draft_embed(self, stage1_data: Dict, user: discord.Member) -> discord.Embed:
        """Create draft embed for Stage 1 data"""
        app_type_text = "Заявление на вступление" if stage1_data['application_type'] == 'join' else "Заявление на перевод"
        
        embed = discord.Embed(
            title=f"📋 Черновик: {app_type_text} в {stage1_data['department_code']}",
            description="**Этап 1: IC Информация**",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone(timedelta(hours=3)))
        )
        
        embed.set_author(
            name=f"{user.display_name} ({user.name})",
            icon_url=user.display_avatar.url
        )
        
        embed.add_field(
            name="👤 Имя Фамилия",
            value=stage1_data['name'],
            inline=True
        )
        
        embed.add_field(
            name="🏷️ Статик",
            value=stage1_data['static'],
            inline=True
        )
        
        embed.add_field(
            name="📄 Документ",
            value=f"[Ссылка на документ]({stage1_data['document_url']})",
            inline=False
        )
        
        embed.add_field(
            name="💭 Причины выбора подразделения",
            value=stage1_data['reason'],
            inline=False
        )
        
        embed.set_footer(text="Этап 1/2 - IC Информация заполнена")
        
        return embed


class Stage1ReviewView(ui.View):
    """View for reviewing Stage 1 data with continue/cancel options"""
    
    def __init__(self, stage1_data: Dict):
        super().__init__(timeout=300)
        self.stage1_data = stage1_data
    
    @ui.button(label="❌ Отменить", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel the application"""
        await interaction.response.edit_message(
            content="❌ **Заявление отменено**\n"
                   "Вы можете начать заново в любое время.\n\n"
                   "*Это сообщение будет удалено через 5 секунд...*",
            embed=None,
            view=None
        )
        
        # Delete the ephemeral message after a short delay
        await asyncio.sleep(5)
        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass  # Message already deleted
    
    @ui.button(label="➡️ Продолжить", style=discord.ButtonStyle.green)
    async def continue_button(self, interaction: discord.Interaction, button: ui.Button):
        """Continue to Stage 2"""
        try:
            # Create Stage 2 modal
            modal = DepartmentApplicationStage2Modal(self.stage1_data)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error proceeding to Stage 2: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при переходе к следующему этапу.",
                ephemeral=True
            )


class DepartmentApplicationStage2Modal(ui.Modal):
    """Stage 2: OOC Information modal for department applications"""
    
    def __init__(self, stage1_data: Dict):
        self.stage1_data = stage1_data
        
        super().__init__(
            title=f"Заявление в {stage1_data['department_code']} - OOC Информация",
            timeout=300
        )
        
        self._setup_fields()
    
    def _setup_fields(self):
        """Setup OOC fields"""
        
        self.real_name_input = ui.TextInput(
            label="Реальное имя",
            placeholder="Как к вам обращаться в голосовом чате",
            max_length=50,
            required=True
        )
        self.add_item(self.real_name_input)
        
        self.age_input = ui.TextInput(
            label="Возраст",
            placeholder="Ваш возраст (или укажите предпочитаемый диапазон)",
            max_length=20,
            required=True
        )
        self.add_item(self.age_input)
        
        self.timezone_input = ui.TextInput(
            label="Часовой пояс",
            placeholder="UTC+3 (МСК), UTC+5, UTC+7 и т.д.",
            max_length=20,
            required=True
        )
        self.add_item(self.timezone_input)
        
        self.online_hours_input = ui.TextInput(
            label="Онлайн в день",
            placeholder="Примерно сколько часов в день вы играете",
            max_length=50,
            required=True
        )
        self.add_item(self.online_hours_input)
        
        self.prime_time_input = ui.TextInput(
            label="Прайм-тайм",
            placeholder="В какое время вы обычно наиболее активны",
            max_length=100,
            required=True
        )
        self.add_item(self.prime_time_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle Stage 2 submission and create final application"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get age value (no validation)
            age_value = self.age_input.value.strip()
            
            # Combine all data
            complete_application_data = {
                **self.stage1_data,
                'ooc_data': {
                    'real_name': self.real_name_input.value.strip(),
                    'age': age_value,
                    'timezone': self.timezone_input.value.strip(),
                    'online_hours': self.online_hours_input.value.strip(),
                    'prime_time': self.prime_time_input.value.strip()
                },
                'user_id': interaction.user.id,
                'timestamp': datetime.now(timezone(timedelta(hours=3))).isoformat(),
                'status': 'pending'
            }
            
            # Create final draft embed
            final_embed = self._create_final_draft_embed(complete_application_data, interaction.user)
            
            # Create final review view
            view = FinalReviewView(complete_application_data)
            
            await interaction.followup.send(
                "📋 **Финальный черновик заявления**\n"
                "Проверьте все данные перед отправкой:",
                embed=final_embed,
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in Stage 2 application: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка. Попробуйте еще раз.",
                ephemeral=True
            )
    
    def _create_final_draft_embed(self, application_data: Dict, user: discord.Member) -> discord.Embed:
        """Create final draft embed with all data"""
        app_type_text = "Заявление на вступление" if application_data['application_type'] == 'join' else "Заявление на перевод"
        
        embed = discord.Embed(
            title=f"📋 {app_type_text} в {application_data['department_code']}",
            description="**Финальный черновик - готов к отправке**",
            color=discord.Color.blue(),
            timestamp=datetime.fromisoformat(application_data['timestamp']).replace(tzinfo=timezone(timedelta(hours=3)))
        )
        
        embed.set_author(
            name=f"{user.display_name} ({user.name})",
            icon_url=user.display_avatar.url
        )
        
        # IC Data
        embed.add_field(
            name="📋 IC Информация",
            value=f"**Имя:** {application_data['name']}\n"
                  f"**Статик:** {application_data['static']}\n"
                  f"**Документ:** [Ссылка]({application_data['document_url']})",
            inline=False
        )
        
        embed.add_field(
            name="💭 Причины выбора подразделения",
            value=application_data['reason'],
            inline=False
        )
        
        # OOC Data
        ooc_data = application_data['ooc_data']
        embed.add_field(
            name="👤 OOC Информация",
            value=f"**Имя:** {ooc_data['real_name']}\n"
                  f"**Возраст:** {ooc_data['age']}\n"
                  f"**Часовой пояс:** {ooc_data['timezone']}\n"
                  f"**Онлайн в день:** {ooc_data['online_hours']}\n"
                  f"**Прайм-тайм:** {ooc_data['prime_time']}",
            inline=False
        )
        
        embed.set_footer(text="Готов к отправке - проверьте данные")
        
        return embed


class FinalReviewView(ui.View):
    """Final review view with send/cancel options"""
    
    def __init__(self, application_data: Dict):
        super().__init__(timeout=300)
        self.application_data = application_data
    
    @ui.button(label="❌ Отменить", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel the application"""
        await interaction.response.edit_message(
            content="❌ **Заявление отменено**\n"
                   "Вы можете начать заново в любое время.\n\n"
                   "*Это сообщение будет удалено через 5 секунд...*",
            embed=None,
            view=None
        )
        
        # Delete the ephemeral message after a short delay
        await asyncio.sleep(5)
        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass  # Message already deleted
    
    @ui.button(label="📨 Отправить заявление", style=discord.ButtonStyle.green)
    async def send_button(self, interaction: discord.Interaction, button: ui.Button):
        """Send the final application"""
        try:
            await interaction.response.defer()
            
            # Check for duplicate applications before sending
            from .views import check_user_active_applications
            active_check = await check_user_active_applications(
                interaction.guild, 
                interaction.user.id
            )
            
            if active_check['has_active']:
                departments_list = ", ".join(active_check['departments'])
                await interaction.edit_original_response(
                    content=f"❌ **У вас уже есть активное заявление на рассмотрении**\n\n"
                            f"📋 Подразделения: **{departments_list}**\n"
                            f"⏳ Дождитесь рассмотрения текущего заявления перед подачей нового.\n\n"
                            f"💡 Активные заявления можно найти в каналах заявлений соответствующих подразделений.",
                    embed=None,
                    view=None
                )
                return
            
            # Get department channel
            channel_id = ping_manager.get_department_channel_id(self.application_data['department_code'])
            if not channel_id:
                await interaction.edit_original_response(
                    content="❌ Канал для заявлений в это подразделение не настроен. Обратитесь к администратору.",
                    embed=None,
                    view=None
                )
                return
            
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.edit_original_response(
                    content="❌ Канал для заявлений не найден. Обратитесь к администратору.",
                    embed=None,
                    view=None
                )
                return
            
            # Create application embed for moderation
            embed = self._create_moderation_embed(self.application_data, interaction.user)
            
            # Create moderation view
            from .views import DepartmentApplicationView
            view = DepartmentApplicationView(self.application_data)
            
            # Prepare content with pings for target department
            content = self._create_application_content(interaction.user, interaction.guild)
            
            # Send to department channel
            message = await channel.send(content=content, embed=embed, view=view)
            
            # Store application data
            self.application_data['message_id'] = message.id
            self.application_data['channel_id'] = channel.id
            
            # Confirm to user and delete the ephemeral message
            await interaction.edit_original_response(
                content=f"✅ **Заявление отправлено!**\n"
                        f"Ваше заявление в подразделение **{self.application_data['department_code']}** "
                        f"отправлено на рассмотрение модерации.\n\n"
                        f"📍 Канал: {channel.mention}\n"
                        f"⏰ Время обработки: обычно до 24 часов\n\n"
                        f"*Это сообщение будет удалено через 10 секунд...*",
                embed=None,
                view=None
            )
            
            # Delete the ephemeral message after a short delay
            await asyncio.sleep(10)
            try:
                await interaction.delete_original_response()
            except discord.NotFound:
                pass  # Message already deleted
            
        except Exception as e:
            logger.error(f"Error sending application: {e}")
            await interaction.edit_original_response(
                content="❌ Произошла ошибка при отправке заявления. Попробуйте еще раз.",
                embed=None,
                view=None
            )
    
    def _create_moderation_embed(self, application_data: Dict, user: discord.Member) -> discord.Embed:
        """Create embed for moderation"""
        app_type_text = "Заявление на вступление" if application_data['application_type'] == 'join' else "Заявление на перевод"
        
        embed = discord.Embed(
            title=f"{app_type_text} в {application_data['department_code']}",
            color=discord.Color.blue(),
            timestamp=datetime.fromisoformat(application_data['timestamp']).replace(tzinfo=timezone(timedelta(hours=3)))
        )
        
        embed.set_author(
            name=f"{user.display_name} ({user.name})",
            icon_url=user.display_avatar.url
        )
        
        # IC Information
        embed.add_field(
            name="📋 IC Информация",
            value=f"**Имя Фамилия:** {application_data['name']}\n"
                  f"**Статик:** {application_data['static']}\n"
                  f"**Документ:** [Ссылка на документ]({application_data['document_url']})",
            inline=False
        )
        
        embed.add_field(
            name="💭 Причины выбора подразделения",
            value=application_data['reason'],
            inline=False
        )
        
        # OOC Information
        ooc_data = application_data['ooc_data']
        embed.add_field(
            name="👤 OOC Информация",
            value=f"**Имя:** {ooc_data['real_name']}\n"
                  f"**Возраст:** {ooc_data['age']}\n"
                  f"**Часовой пояс:** {ooc_data['timezone']}\n"
                  f"**Онлайн в день:** {ooc_data['online_hours']}\n"
                  f"**Прайм-тайм:** {ooc_data['prime_time']}",
            inline=False
        )
        
        # Status
        embed.add_field(
            name="📊 Статус",
            value="🔄 На рассмотрении",
            inline=True
        )
        
        embed.set_footer(text=f"ID заявления: {application_data['user_id']}")
        
        return embed
    
    def _create_application_content(self, user: discord.Member, guild: discord.Guild) -> str:
        """
        Create content with pings for the application message
        
        For new applications: ping roles for target department  
        For transfers: ping roles for target department + current department
        """
        from utils.ping_manager import PingManager
        ping_manager = PingManager()
        
        content_lines = []
        
        # Get ping roles for target department (where application is being submitted)
        target_ping_roles = ping_manager.get_ping_roles_for_context(
            self.application_data['department_code'], 
            'applications', 
            guild
        )
        
        if target_ping_roles:
            target_mentions = [role.mention for role in target_ping_roles]
            content_lines.append(' '.join(target_mentions))
        
        # Check if this is a transfer (user has current department)
        current_department = ping_manager.get_user_department_code(user)
        if current_department and current_department != self.application_data['department_code']:
            # This is a transfer - add pings for current department on second line
            current_ping_roles = ping_manager.get_ping_roles_for_context(
                current_department,
                'applications',  # или можно использовать 'general'
                guild
            )
            
            if current_ping_roles:
                current_mentions = [role.mention for role in current_ping_roles]
                content_lines.append(' '.join(current_mentions))
        
        return '\n'.join(content_lines) if content_lines else ""
