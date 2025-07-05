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
from utils.department_manager import DepartmentManager
from .views import DepartmentSelectView

logger = logging.getLogger(__name__)

class DepartmentApplicationManager:
    """Manager for department application system"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.department_manager = DepartmentManager()
    
    async def setup_department_channel(self, department_code: str, channel: discord.TextChannel) -> bool:
        """Setup persistent message in department channel"""
        try:
            # Используем безопасную функцию получения данных подразделения
            dept_info = self.department_manager.get_department_safe(department_code)
            if not dept_info:
                logger.error(f"Department {department_code} not found")
                return False
            
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
    
    async def _save_department_config(self, department_code: str, dept_config: dict):
        """Save department configuration to config file"""
        config = load_config()
        
        if 'departments' not in config:
            config['departments'] = {}
        
        config['departments'][department_code] = dept_config
        save_config(config)
    
    async def restore_persistent_views(self):
        """Restore persistent views on bot startup and ensure messages exist"""
        try:
            config = load_config()
            departments = config.get('departments', {})
            
            print(f"🔄 Found {len(departments)} departments in config")
            
            if not departments:
                logger.info("No departments configured for applications")
                print("ℹ️ No departments configured for applications")
                return
            
            restored_count = 0
            for dept_code, dept_config in departments.items():
                print(f"📋 Processing department: {dept_code}")
                print(f"   Config keys: {list(dept_config.keys())}")
                
                channel_id = dept_config.get('application_channel_id')
                if not channel_id:
                    print(f"   ⚠️ No application_channel_id for {dept_code}")
                    continue
                
                print(f"   🔍 Looking for channel ID: {channel_id}")
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    logger.warning(f"Channel {channel_id} for {dept_code} not found")
                    print(f"   ❌ Channel {channel_id} not found")
                    continue
                
                print(f"   ✅ Found channel: {channel.name}")
                
                # Check for existing pinned message and restore/update it
                persistent_message = await self._find_or_create_persistent_message(
                    dept_code, channel, dept_config
                )
                
                if persistent_message:
                    # Update message with fresh view (important for persistent buttons after restart)
                    await self._update_message_with_fresh_view(persistent_message, dept_code)
                    restored_count += 1
                    logger.info(f"✅ Restored persistent view for {dept_code} in {channel.name}")
                    print(f"   ✅ Restored persistent view for {dept_code}")
                else:
                    logger.warning(f"❌ Failed to restore persistent message for {dept_code}")
                    print(f"   ❌ Failed to restore persistent message for {dept_code}")
            
            # Also restore application moderation views
            await self._restore_application_views()
            
            logger.info(f"Restored {restored_count} department application channels")
            print(f"Department applications: restored {restored_count} views")
            
        except Exception as e:
            logger.error(f"Error restoring persistent views: {e}")
            print(f"❌ Error restoring persistent views: {e}")
            import traceback
            traceback.print_exc()
    
    async def _update_message_with_fresh_view(self, message: discord.Message, dept_code: str):
        """Update existing message with fresh view to make buttons work"""
        try:
            # Create fresh view with proper department code
            view = DepartmentSelectView(dept_code)
            
            # Update the message with new view
            await message.edit(view=view)
            
            # Also register the view with the bot for persistence
            self.bot.add_view(view, message_id=message.id)
            
            logger.info(f"Updated message {message.id} for {dept_code} with fresh view")
            
        except discord.NotFound:
            logger.warning(f"Message {message.id} for {dept_code} not found when updating view")
        except discord.Forbidden:
            logger.warning(f"No permission to update message {message.id} for {dept_code}")
        except Exception as e:
            logger.error(f"Error updating message view for {dept_code}: {e}")
    
    async def _find_or_create_persistent_message(self, dept_code: str, channel: discord.TextChannel, dept_config: Dict) -> Optional[discord.Message]:
        """Find existing persistent message or create new one"""
        try:
            print(f"       🔍 Searching for persistent message for {dept_code}")
            
            # First, check if we have stored message ID
            stored_message_id = dept_config.get('persistent_message_id')
            print(f"       📋 Stored message ID: {stored_message_id}")
            
            if stored_message_id:
                try:
                    message = await channel.fetch_message(stored_message_id)
                    print(f"       ✅ Found stored message {stored_message_id}")
                    
                    # Verify it's our message and still pinned
                    if (message.author == self.bot.user and 
                        message.pinned and 
                        len(message.embeds) > 0 and 
                        dept_code in message.embeds[0].title):
                        logger.info(f"Found existing persistent message for {dept_code}")
                        print(f"       ✅ Message verified as valid persistent message")
                        return message
                    else:
                        print(f"       ⚠️ Message exists but doesn't match criteria:")
                        print(f"           Author is bot: {message.author == self.bot.user}")
                        print(f"           Is pinned: {message.pinned}")
                        print(f"           Has embeds: {len(message.embeds) > 0}")
                        if len(message.embeds) > 0:
                            print(f"           Title contains dept_code: {dept_code in message.embeds[0].title}")
                            print(f"           Actual title: {message.embeds[0].title}")
                except discord.NotFound:
                    logger.info(f"Stored message for {dept_code} not found, will create new")
                    print(f"       ❌ Stored message {stored_message_id} not found")
            
            # Look for pinned messages from bot in channel
            print(f"       🔍 Searching pinned messages in {channel.name}")
            pinned_messages = await channel.pins()
            print(f"       📌 Found {len(pinned_messages)} pinned messages")
            
            for i, message in enumerate(pinned_messages):
                print(f"       📌 Checking pinned message {i+1}: {message.id}")
                print(f"           Author is bot: {message.author == self.bot.user}")
                print(f"           Has embeds: {len(message.embeds) > 0}")
                
                if (message.author == self.bot.user and 
                    len(message.embeds) > 0):
                    print(f"           Embed title: {message.embeds[0].title}")
                    print(f"           Contains dept_code {dept_code}: {dept_code in message.embeds[0].title}")
                    print(f"           Contains 'заявление': {'заявление' in message.embeds[0].title.lower()}")
                    
                    if (dept_code in message.embeds[0].title and
                        "заявление" in message.embeds[0].title.lower()):
                        
                        # Update stored message ID
                        await self._save_department_message_info(dept_code, channel.id, message.id)
                        logger.info(f"Found existing pinned message for {dept_code}")
                        print(f"       ✅ Found matching pinned message!")
                        return message
            
            # No existing message found, create new one
            logger.info(f"Creating new persistent message for {dept_code}")
            print(f"       📝 No existing message found, creating new one")
            success = await self.setup_department_channel(dept_code, channel)
            
            if success:
                print(f"       ✅ Successfully created new message")
                # Get the newly created message
                config = load_config()
                new_message_id = config.get('departments', {}).get(dept_code, {}).get('persistent_message_id')
                if new_message_id:
                    try:
                        return await channel.fetch_message(new_message_id)
                    except discord.NotFound:
                        print(f"       ❌ Could not fetch newly created message {new_message_id}")
            else:
                print(f"       ❌ Failed to create new message")
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding/creating persistent message for {dept_code}: {e}")
            print(f"       ❌ Error in _find_or_create_persistent_message: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _restore_application_views(self):
        """Restore application moderation views"""
        # This would restore views for active application messages
        # For now, just log that this feature could be implemented with a database
        logger.info("Application moderation views restoration - would need database implementation")
    
    def get_department_info(self, department_code: str) -> Optional[Dict]:
        """Get department information"""
        departments = self.department_manager.get_all_departments()
        return departments.get(department_code)
    
    def get_all_departments(self) -> Dict:
        """Get all departments"""
        return self.department_manager.get_all_departments()
    
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
        
        departments = self.department_manager.get_all_departments()
        for dept_code in departments.keys():
            is_valid, status = await self.validate_department_setup(dept_code, guild)
            status_emoji = "✅" if is_valid else "❌"
            
            embed.add_field(
                name=f"{status_emoji} {dept_code}",
                value=status,
                inline=False
            )
        
        return embed
    
    async def setup_all_department_channels(self, guild: discord.Guild) -> Dict[str, str]:
        """Setup/update persistent messages in all configured department channels"""
        results = {}
        config = load_config()
        departments = config.get('departments', {})
        
        for dept_code, dept_config in departments.items():
            channel_id = dept_config.get('application_channel_id')
            if not channel_id:
                results[dept_code] = f"❌ Канал не настроен"
                continue
            
            channel = guild.get_channel(channel_id)
            if not channel:
                results[dept_code] = f"❌ Канал не найден (ID: {channel_id})"
                continue
            
            # Use the same logic as restore_persistent_views
            persistent_message = await self._find_or_create_persistent_message(
                dept_code, channel, dept_config
            )
            
            if persistent_message:
                # Update message with fresh view
                await self._update_message_with_fresh_view(persistent_message, dept_code)
                results[dept_code] = f"✅ Сообщение обновлено"
            else:
                results[dept_code] = f"❌ Ошибка при создании/обновлении"
        
        return results

    async def refresh_department_channel(self, department_code: str, guild: discord.Guild) -> bool:
        """Refresh persistent message for a specific department"""
        try:
            departments = self.department_manager.get_all_departments()
            dept_config = departments.get(department_code)
            if not dept_config:
                return False
            
            channel_id = dept_config.get('application_channel_id')
            if not channel_id:
                return False
            
            channel = guild.get_channel(channel_id)
            if not channel:
                return False
            
            # Delete old message if exists
            existing_message_id = dept_config.get('persistent_message_id')
            if existing_message_id:
                try:
                    existing_message = await channel.fetch_message(existing_message_id)
                    await existing_message.delete()
                except discord.NotFound:
                    pass
            
            # Create new message
            return await self.setup_department_channel(department_code, channel)
            
        except Exception as e:
            logger.error(f"Error refreshing department channel {department_code}: {e}")
            return False
