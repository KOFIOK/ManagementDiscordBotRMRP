"""
Department Application Manager - Manages persistent messages and configuration
"""
import discord
from discord.ext import commands
import logging
from typing import Dict, Optional, List
import json
from datetime import datetime

from utils.config_manager import load_config, save_config
from utils.ping_manager import ping_manager
from .views import DepartmentSelectView

logger = logging.getLogger(__name__)

class DepartmentApplicationManager:
    """Manager for department application system"""
    
    DEPARTMENTS = {
        'УВП': {
            'name': 'Учебно-Воспитательное Подразделение',
            'description': 'Ответственное за обучение и воспитание личного состава',
            'color': 0x3498db,
            'emoji': '🎓'
        },
        'ССО': {
            'name': 'Силы Специальных Операций',
            'description': 'Элитное подразделение для выполнения специальных задач',
            'color': 0x2ecc71,
            'emoji': '🎯'
        },
        'РОиО': {
            'name': 'Разведывательный Отдел и Оборона',
            'description': 'Разведывательная деятельность и оборонительные операции',
            'color': 0x9b59b6,
            'emoji': '🔍'
        },
        'ВК': {
            'name': 'Военная Комендатура',
            'description': 'Поддержание порядка и дисциплины на территории',
            'color': 0xe74c3c,
            'emoji': '🚔'
        },
        'МР': {
            'name': 'Медицинская Рота',
            'description': 'Медицинское обеспечение и помощь личному составу',
            'color': 0xf39c12,
            'emoji': '🏥'
        },
        'ВА': {
            'name': 'Военная Академия',
            'description': 'Высшее военное образование и подготовка офицерского состава',
            'color': 0x1abc9c,
            'emoji': '🎖️'
        }
    }
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def setup_department_channel(self, department_code: str, channel: discord.TextChannel) -> bool:
        """Setup persistent message in department channel"""
        try:
            if department_code not in self.DEPARTMENTS:
                return False
            
            dept_info = self.DEPARTMENTS[department_code]
            
            # Create embed for department info
            embed = discord.Embed(
                title=f"{dept_info['emoji']} {dept_info['name']} ({department_code})",
                description=dept_info['description'],
                color=dept_info['color'],
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="📋 Как подать заявление",
                value="Выберите тип заявления в меню ниже:\n"
                      "• **Вступление** - если вы не состоите в подразделении\n"
                      "• **Перевод** - если хотите перейти из другого подразделения",
                inline=False
            )
            
            embed.add_field(
                name="⚠️ Важная информация",
                value="• Можно подать только одну заявку одновременно\n"
                      "• Заявление рассматривается модерацией\n"
                      "• Ложная информация может привести к отклонению",
                inline=False
            )
            
            embed.set_footer(
                text="Система заявлений в подразделения",
                icon_url=self.bot.user.display_avatar.url if self.bot.user else None
            )
            
            # Create view with select menu
            view = DepartmentSelectView(department_code)
            
            # Send message
            message = await channel.send(embed=embed, view=view)
            
            # Pin the message
            try:
                await message.pin()
            except discord.Forbidden:
                logger.warning(f"Could not pin message in {channel.name} - insufficient permissions")
            
            # Store message info in config
            await self._save_department_message_info(department_code, channel.id, message.id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting up department channel {department_code}: {e}")
            return False
    
    async def _save_department_message_info(self, department_code: str, channel_id: int, message_id: int):
        """Save department message info to config"""
        config = load_config()
        
        if 'departments' not in config:
            config['departments'] = {}
        
        if department_code not in config['departments']:
            config['departments'][department_code] = {}
        
        config['departments'][department_code].update({
            'application_channel_id': channel_id,
            'persistent_message_id': message_id
        })
        
        save_config(config)
    
    async def restore_persistent_views(self):
        """Restore persistent views on bot startup"""
        try:
            config = load_config()
            departments = config.get('departments', {})
            
            for dept_code, dept_config in departments.items():
                channel_id = dept_config.get('application_channel_id')
                message_id = dept_config.get('persistent_message_id')
                
                if channel_id and message_id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        try:
                            message = await channel.fetch_message(message_id)
                            view = DepartmentSelectView(dept_code)
                            self.bot.add_view(view, message_id=message_id)
                            logger.info(f"Restored persistent view for {dept_code} in {channel.name}")
                        except discord.NotFound:
                            logger.warning(f"Persistent message for {dept_code} not found, will recreate")
                            await self.setup_department_channel(dept_code, channel)
                        except Exception as e:
                            logger.error(f"Error restoring view for {dept_code}: {e}")
                    else:
                        logger.warning(f"Channel {channel_id} for {dept_code} not found")
            
            # Also restore application views
            await self._restore_application_views()
            
        except Exception as e:
            logger.error(f"Error restoring persistent views: {e}")
    
    async def _restore_application_views(self):
        """Restore application moderation views"""
        # This would need a proper database to track active applications
        # For now, just log that we should implement this
        logger.info("Application views restoration not implemented - needs database")
    
    def get_department_info(self, department_code: str) -> Optional[Dict]:
        """Get department information"""
        return self.DEPARTMENTS.get(department_code)
    
    def get_all_departments(self) -> Dict:
        """Get all departments"""
        return self.DEPARTMENTS
    
    async def update_department_config(self, department_code: str, **kwargs):
        """Update department configuration"""
        config = load_config()
        
        if 'departments' not in config:
            config['departments'] = {}
        
        if department_code not in config['departments']:
            config['departments'][department_code] = {}
        
        config['departments'][department_code].update(kwargs)
        save_config(config)
    
    async def validate_department_setup(self, department_code: str, guild: discord.Guild) -> tuple[bool, str]:
        """Validate department setup"""
        try:
            dept_info = ping_manager.get_department_info(department_code)
            
            if not dept_info:
                return False, f"Подразделение {department_code} не настроено"
            
            # Check role
            role_id = dept_info.get('role_id')
            if role_id:
                role = guild.get_role(role_id)
                if not role:
                    return False, f"Роль подразделения {department_code} не найдена"
            else:
                return False, f"Роль для подразделения {department_code} не настроена"
            
            # Check channel
            channel_id = dept_info.get('application_channel_id')
            if channel_id:
                channel = guild.get_channel(channel_id)
                if not channel:
                    return False, f"Канал заявлений {department_code} не найден"
            else:
                return False, f"Канал заявлений для подразделения {department_code} не настроен"
            
            # Check ping contexts
            ping_contexts = dept_info.get('ping_contexts', {})
            if 'applications' not in ping_contexts:
                return False, f"Пинги для заявлений в {department_code} не настроены"
            
            return True, f"Подразделение {department_code} настроено корректно"
            
        except Exception as e:
            logger.error(f"Error validating department {department_code}: {e}")
            return False, f"Ошибка при проверке настроек: {e}"
    
    async def get_active_applications(self, user_id: Optional[int] = None, department_code: Optional[str] = None) -> List[Dict]:
        """Get active applications (needs database implementation)"""
        # Placeholder - would need proper database
        logger.info(f"Getting active applications for user {user_id}, department {department_code}")
        return []
    
    async def has_active_application(self, user_id: int) -> bool:
        """Check if user has active application"""
        # Placeholder - would need proper database
        applications = await self.get_active_applications(user_id=user_id)
        return len(applications) > 0
    
    async def create_application_summary_embed(self, guild: discord.Guild) -> discord.Embed:
        """Create summary embed of application system status"""
        embed = discord.Embed(
            title="📋 Система заявлений в подразделения",
            description="Статус настройки подразделений",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        for dept_code in self.DEPARTMENTS.keys():
            is_valid, status = await self.validate_department_setup(dept_code, guild)
            status_emoji = "✅" if is_valid else "❌"
            
            embed.add_field(
                name=f"{status_emoji} {dept_code}",
                value=status,
                inline=False
            )
        
        return embed
