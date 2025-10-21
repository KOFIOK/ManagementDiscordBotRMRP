import discord
from utils.message_service import MessageService

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
        print(f"👋 New member joined: {member.display_name} ({member.id})")
        
        try:
            # Отправляем приветственное сообщение в ЛС
            dm_sent = await WelcomeSystem.send_welcome_message(member)
            
            # Логируем событие
            print(f"✅ Welcome process completed for {member.display_name} (DM: {'✅' if dm_sent else '❌'})")
            
        except Exception as e:
            print(f"❌ Error in welcome process for {member.display_name}: {e}")
    
    print("✅ Welcome system events registered")
