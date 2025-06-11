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
                description=f"Привет, {member.mention}! Добро пожаловать на наш сервер!",
                color=0x00FF00,  # Зеленый цвет
                timestamp=discord.utils.utcnow()
            )
            embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")  # Логотип ВС РФ
            
            # Получаем информацию о настроенном канале получения ролей
            from utils.config_manager import load_config
            config = load_config()
            role_assignment_channel_id = config.get('role_assignment_channel')
            
            # Формируем текст с упоминанием канала если он настроен
            if role_assignment_channel_id:
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
                name="🪖 Хотите служить в ВС РФ?",
                value=(
                    "• Если вы прошли **призыв** или **экскурсию** - получите роль военнослужащего\n"
                    "• Начните со звания **Рядовой** и повышайтесь по службе\n"
                    "• Участвуйте в занятиях и обучении"
                ),
                inline=False
            )
            
            embed.add_field(
                name="👤 Являетесь госслужащим?",
                value=(
                    "• Если вы работник **УВД, ФСБ, ЦГБ** или другого госоргана\n"
                    "• Если вы **поставщик** или представитель организации\n"
                    "• Получите соответствующую роль для доступа к ресурсам"
                ),
                inline=False            )
            
            # Формируем текст для полезных каналов
            if role_assignment_channel_id:
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
            
            # Создаем кнопки для быстрого доступа
            view = WelcomeButtonsView()
            
            # Отправляем приветственное сообщение в ЛС
            try:
                await member.send(embed=embed, view=view)
                print(f"✅ Sent welcome message to {member.display_name} ({member.id})")
                return True
            except discord.Forbidden:
                print(f"❌ Cannot send DM to {member.display_name} - DMs disabled")
                return False
                
        except Exception as e:
            print(f"Error sending welcome message to {member.display_name}: {e}")
            return False


class WelcomeButtonsView(ui.View):
    """Кнопки для приветственного сообщения"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="🪖 Получить роль военнослужащего", 
        style=discord.ButtonStyle.green,
        custom_id="welcome_military_role"
    )
    async def get_military_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка для получения военной роли"""
        # Получаем информацию о канале получения ролей
        from utils.config_manager import load_config
        config = load_config()
        role_assignment_channel_id = config.get('role_assignment_channel')
        
        # Формируем текст с упоминанием канала
        if role_assignment_channel_id:
            role_channel = interaction.guild.get_channel(role_assignment_channel_id)
            if role_channel:
                channel_text = f"1. Перейдите в канал {role_channel.mention}\n"
            else:
                channel_text = "1. Найдите канал **\"Получение ролей\"** на сервере\n"
        else:
            channel_text = "1. Найдите канал **\"Получение ролей\"** на сервере\n"

        await interaction.response.send_message(
            "🎖️ **Отлично! Вы выбрали службу в Вооружённых Силах РФ.**\n\n"
            "📋 **Следующие шаги:**\n"
            f"{channel_text}"
            "2. Нажмите кнопку **\"Призыв / Экскурсия\"**\n"
            "3. Заполните форму с вашими данными\n"
            "4. Дождитесь одобрения инструктора Военного Комиссариата\n\n"
            "💡 **Совет:** Обычно это звание **\"Рядовой\"** для новобранцев.",
            ephemeral=True
        )
    @discord.ui.button(
        label="👤 Получить роль госслужащего", 
        style=discord.ButtonStyle.secondary,
        custom_id="welcome_civilian_role"
    )
    async def get_civilian_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка для получения гражданской роли"""
        # Получаем информацию о канале получения ролей
        from utils.config_manager import load_config
        config = load_config()
        role_assignment_channel_id = config.get('role_assignment_channel')
        
        # Формируем текст с упоминанием канала
        if role_assignment_channel_id:
            role_channel = interaction.guild.get_channel(role_assignment_channel_id)
            if role_channel:
                channel_text = f"1. Перейдите в канал {role_channel.mention}\n"
            else:
                channel_text = "1. Найдите канал **\"Получение ролей\"** на сервере\n"
        else:
            channel_text = "1. Найдите канал **\"Получение ролей\"** на сервере\n"
        
        await interaction.response.send_message(
            "🏛️ **Отлично! Вы представитель госструктуры или организации.**\n\n"
            "📋 **Следующие шаги:**\n"
            f"{channel_text}"
            "2. Нажмите кнопку **\"Я госслужащий\"** или **\"Я поставщик\"**\n"
            "3. Заполните форму с данными о вашей организации\n"
            "4. Приложите доказательства вашего статуса\n"
            "5. Дождитесь одобрения руководства ВС РФ\n\n"
            "💡 **Совет:** Подготовьте ссылку на доказательства заранее.",
            ephemeral=True
        )
    
    @discord.ui.button(
        label="📚 Посмотреть правила", 
        style=discord.ButtonStyle.primary,
        custom_id="welcome_rules"
    )
    async def view_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка для просмотра правил"""
        await interaction.response.send_message(
            "📚 **Правила сервера очень важны!**\n\n"
            "🔍 **Где найти правила:**\n"
            "• Найдите канал <#1250694899049955470> на сервере\n"
            "• Обычно он находится в самом верху списка каналов\n"
            "• Обязательно прочитайте все пункты\n\n"
            "⚠️ **Важно:** Незнание правил не освобождает от ответственности!\n\n"
            "📋 **Основные принципы:**\n"
            "• Уважение к другим участникам\n"
            "• Соблюдение субординации\n"
            "• Запрет на спам и оффтоп\n"
            "• Использование адекватных никнеймов",
            ephemeral=True
        )


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
