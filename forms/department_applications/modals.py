"""
Department Application Forms - Modal forms for department applications
"""
import discord
from discord import ui
from typing import Dict, Any
import logging
from datetime import datetime

from utils.user_database import UserDatabase
from utils.ping_manager import ping_manager

logger = logging.getLogger(__name__)

class DepartmentApplicationModal(ui.Modal):
    """Modal for department applications with auto-filled IC data"""
    
    def __init__(self, department_code: str, application_type: str, user_ic_data: Dict[str, Any]):
        self.department_code = department_code
        self.application_type = application_type  # 'join' or 'transfer'
        self.user_ic_data = user_ic_data
        
        title = f"Заявление в {department_code}"
        if application_type == 'transfer':
            title += " (Перевод)"
        
        super().__init__(title=title, timeout=300)
        
        # Pre-fill IC data
        self._setup_fields()
    
    def _setup_fields(self):
        """Setup form fields with auto-filled IC data"""
        
        # IC Fields (auto-filled, read-only style)
        ic_name = self.user_ic_data.get('name', 'Не указано')
        ic_rank = self.user_ic_data.get('rank', 'Не указано')
        ic_position = self.user_ic_data.get('position', 'Не указано')
        ic_department = self.user_ic_data.get('department', 'Не указано')
        
        # Combine IC info into one field to save space
        ic_info = f"ФИО: {ic_name}\nЗвание: {ic_rank}\nДолжность: {ic_position}"
        if self.application_type == 'transfer':
            ic_info += f"\nТекущее подразделение: {ic_department}"
        
        self.ic_data_field = ui.TextInput(
            label="IC Данные (автозаполнение)",
            default=ic_info,
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True
        )
        self.add_item(self.ic_data_field)
        
        # OOC Fields
        self.ooc_name = ui.TextInput(
            label="OOC Имя",
            placeholder="Ваше имя в Discord",
            max_length=100,
            required=True
        )
        self.add_item(self.ooc_name)
        
        self.ooc_age = ui.TextInput(
            label="Возраст (OOC)",
            placeholder="Ваш возраст",
            max_length=3,
            required=True
        )
        self.add_item(self.ooc_age)
        
        self.motivation = ui.TextInput(
            label="Мотивация",
            placeholder="Почему вы хотите попасть в это подразделение?",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.motivation)
        
        self.additional_info = ui.TextInput(
            label="Дополнительная информация",
            placeholder="Любая дополнительная информация (необязательно)",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        )
        self.add_item(self.additional_info)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Parse IC data from the field
            ic_lines = self.ic_data_field.value.split('\n')
            ic_data = {}
            for line in ic_lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    ic_data[key.strip()] = value.strip()
            
            # Create application data
            application_data = {
                'user_id': interaction.user.id,
                'department_code': self.department_code,
                'application_type': self.application_type,
                'ic_data': ic_data,
                'ooc_data': {
                    'name': self.ooc_name.value,
                    'age': self.ooc_age.value,
                    'motivation': self.motivation.value,
                    'additional_info': self.additional_info.value
                },
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'pending'
            }
            
            # Get department channel
            channel_id = ping_manager.get_department_channel_id(self.department_code)
            if not channel_id:
                await interaction.followup.send(
                    "❌ Канал для заявлений в это подразделение не настроен. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.followup.send(
                    "❌ Канал для заявлений не найден. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Create application embed
            embed = self._create_application_embed(application_data, interaction.user)
            
            # Create application view with moderation buttons
            from .views import DepartmentApplicationView
            view = DepartmentApplicationView(application_data)
            
            # Send application to department channel
            message = await channel.send(embed=embed, view=view)
            
            # Store application data with message ID
            application_data['message_id'] = message.id
            application_data['channel_id'] = channel.id
            
            # Store in config/database (you might want to use a proper database)
            await self._store_application(application_data)
            
            # Get ping roles and send notification
            ping_roles = ping_manager.get_ping_roles_for_context(
                self.department_code, 
                'applications', 
                interaction.guild
            )
            
            if ping_roles:
                ping_mentions = [role.mention for role in ping_roles]
                ping_message = f"📋 Новая заявления в подразделение **{self.department_code}**\n"
                ping_message += f"Пинги: {' '.join(ping_mentions)}"
                
                await channel.send(ping_message, delete_after=30)
            
            # Confirm to user
            await interaction.followup.send(
                f"✅ Ваша заявление в подразделение **{self.department_code}** отправлена!\n"
                f"Она будет рассмотрена модерацией в ближайшее время.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error submitting department application: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при отправке заявления. Попробуйте еще раз.",
                ephemeral=True
            )
    
    def _create_application_embed(self, application_data: Dict, user: discord.Member) -> discord.Embed:
        """Create embed for the application"""
        
        app_type_text = "Заявление на вступление" if application_data['application_type'] == 'join' else "Заявление на перевод"
        
        embed = discord.Embed(
            title=f"{app_type_text} в {application_data['department_code']}",
            color=discord.Color.blue(),
            timestamp=datetime.fromisoformat(application_data['timestamp'])
        )
        
        # User info
        embed.set_author(
            name=f"{user.display_name} ({user.name})",
            icon_url=user.display_avatar.url
        )
        
        # IC Data
        ic_info = ""
        for key, value in application_data['ic_data'].items():
            ic_info += f"**{key}:** {value}\n"
        
        embed.add_field(
            name="📋 IC Данные",
            value=ic_info or "Не указано",
            inline=False
        )
        
        # OOC Data
        ooc_data = application_data['ooc_data']
        ooc_info = f"**OOC Имя:** {ooc_data['name']}\n"
        ooc_info += f"**Возраст:** {ooc_data['age']}\n"
        
        embed.add_field(
            name="👤 OOC Данные",
            value=ooc_info,
            inline=False
        )
        
        # Motivation
        embed.add_field(
            name="💭 Мотивация",
            value=ooc_data['motivation'],
            inline=False
        )
        
        # Additional info
        if ooc_data.get('additional_info'):
            embed.add_field(
                name="ℹ️ Дополнительная информация",
                value=ooc_data['additional_info'],
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
    
    async def _store_application(self, application_data: Dict):
        """Store application data (implement proper storage)"""
        # This is a placeholder - you might want to use a proper database
        # For now, we could store in a JSON file or extend the config system
        pass

class DepartmentApplicationSelectModal(ui.Modal):
    """Simple modal for selecting join/transfer option"""
    
    def __init__(self, department_code: str):
        self.department_code = department_code
        super().__init__(title=f"Заявление в {department_code}", timeout=300)
        
        self.selection = ui.TextInput(
            label="Тип заявления",
            placeholder="Введите 'вступление' или 'перевод'",
            max_length=20,
            required=True
        )
        self.add_item(self.selection)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle selection and proceed to main form"""
        try:
            selection = self.selection.value.lower().strip()
            
            if selection in ['вступление', 'join']:
                app_type = 'join'
            elif selection in ['перевод', 'transfer']:
                app_type = 'transfer'
            else:
                await interaction.response.send_message(
                    "❌ Неверный выбор. Введите 'вступление' или 'перевод'.",
                    ephemeral=True
                )
                return
            
            # Get user IC data
            user_data = await UserDatabase.get_user_info(interaction.user.id)
            if not user_data:
                await interaction.response.send_message(
                    "❌ Ваши данные не найдены в системе. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Create and send main application modal
            modal = DepartmentApplicationModal(self.department_code, app_type, user_data)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in department application select: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка. Попробуйте еще раз.",
                ephemeral=True
            )
