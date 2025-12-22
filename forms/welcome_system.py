import discord
from utils.message_service import MessageService
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

class WelcomeSystem:
    """Система приветствия новых пользователей на сервере"""

    @staticmethod
    async def send_welcome_message(member: discord.Member) -> bool:
        """
        Отправить приветственное сообщение новому пользователю

        Args:
            member: Discord member to welcome

        Returns:
            bool: True if message was sent successfully
        """
        return await MessageService.send_welcome_dm(member)

# Функция для регистрации обработчиков событий
def setup_welcome_events(bot):
    """Настройка обработчиков событий для системы приветствия"""
    
    @bot.event
    async def on_member_join(member):
        """Обработчик входа нового пользователя на сервер"""
        logger.info(f"Новый пользователь присоединился: {member.display_name} ({member.id})")
        
        try:
            # Отправляем приветственное сообщение в ЛС
            dm_sent = await WelcomeSystem.send_welcome_message(member)
            
            # Логируем событие
            dm_status = 'OK' if dm_sent else 'FAIL'
            logger.info(f"Welcome process completed for {member.display_name} (DM: {dm_status})")
            
        except Exception as e:
            logger.warning(f"Error in welcome process for {member.display_name}: {e}")
    
    logger.info("Welcome system events registered")
