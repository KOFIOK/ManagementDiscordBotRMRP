import discord
from discord import ui

class WelcomeSystem:
    """Система приветствия новых пользователей на сервере"""
    
    @staticmethod
    async def send_welcome_message(member: discord.Member):
        """Отправить приветственное сообщение новому пользователю"""
        try:
            # Создаем красивое приветственное embed сообщение
            embed = discord.Embed(
                title="🎖️ Добро пожаловать в Вооружённые Силы Российской Федерации!",
                color=0x00FF00,  # Зеленый цвет
                timestamp=discord.utils.utcnow()
            )
            embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")  # Логотип ВС РФ
              # Получаем информацию о настроенном канале получения ролей
            from utils.config_manager import load_config, get_role_assignment_message_link
            config = load_config()
            role_assignment_channel_id = config.get('role_assignment_channel')
            
            # Формируем текст с прямой ссылкой на сообщение с кнопками или упоминанием канала
            message_link = get_role_assignment_message_link(member.guild.id)
            if message_link:
                step_text = f"1. **[🎯 Подать заявку на роль]({message_link})**\n"
            elif role_assignment_channel_id:
                role_channel = member.guild.get_channel(role_assignment_channel_id)
                if role_channel:
                    step_text = f"1. **Получите роль** - перейдите в {role_channel.mention}\n"
                else:
                    step_text = "1. **Получите роль** - перейдите в канал получения ролей\n"
            else:
                step_text = "1. **Получите роль** - перейдите в канал получения ролей\n"
            
            # Добавляем поля с информацией
            embed.add_field(
                name="📋 Что делать дальше?",
                value=(
                    step_text +
                    "2. **Ознакомьтесь с правилами** сервера\n"
                    "3. **Начните службу** или **получите статус госслужащего**"
                ),
                inline=False
            )
            
            embed.add_field(
                name="👤 Являетесь госслужащим?",
                value=(
                    "• Если вы работник **УВД, ФСБ, ЦГБ** или другого госоргана\n"
                    "• Если вы представитель организации и нуждаетесь в **доступе к поставкам**\n"
                    "• Получите соответствующую роль для доступа к каналам"
                ),
                inline=False            )
              # Формируем текст для полезных каналов
            message_link = get_role_assignment_message_link(member.guild.id)
            if message_link:
                channels_text = f"• **[Получение ролей]({message_link})** - основной канал для начала\n"
            elif role_assignment_channel_id:
                role_channel = member.guild.get_channel(role_assignment_channel_id)
                if role_channel:
                    channels_text = f"• {role_channel.mention} - основной канал для начала\n"
                else:
                    channels_text = "• **Получение ролей** - основной канал для начала\n"
            else:
                channels_text = "• **Получение ролей** - основной канал для начала\n"
            
            embed.add_field(
                name="🔗 Полезные каналы",
                value=(
                    channels_text +
                    "• <#1250694899049955470> - обязательно к прочтению\n"
                    "• <#1246119159830679552> - каналы для общения с другими участниками\n"
                    "• <#1246118965810303009> - если нужна помощь"
                ),
                inline=False
            )
            
            embed.set_footer(
                text="Желаем успешной службы! | Руководство ВС РФ",
                icon_url=member.guild.icon.url if member.guild.icon else None
            )
            
            # Отправляем приветственное сообщение в ЛС
            try:
                await member.send(embed=embed)
                print(f"✅ Sent welcome message to {member.display_name} ({member.id})")
                return True
            except discord.Forbidden:
                print(f"❌ Cannot send DM to {member.display_name} - DMs disabled")
                return False
                
        except Exception as e:
            print(f"Error sending welcome message to {member.display_name}: {e}")
            return False


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
