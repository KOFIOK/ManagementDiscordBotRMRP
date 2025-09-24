import discord
from utils.config_manager import load_config
from datetime import datetime


class SuppliesControlView(discord.ui.View):
    """Представление с кнопками управления военными объектами"""
    
    def __init__(self):
        super().__init__(timeout=None)
        self._create_dynamic_buttons()
        
    def _create_dynamic_buttons(self):
        """Создает кнопки динамически на основе категорий"""
        try:
            from .supplies_manager import SuppliesManager
            supplies_manager = SuppliesManager()
            categories = supplies_manager.get_categories()
            
            row = 0
            for category_key, category_objects in categories.items():
                if not category_objects:  # Пропускаем пустые категории
                    continue
                    
                for object_key, object_info in category_objects.items():
                    button = discord.ui.Button(
                        label=object_info["name"],
                        emoji=object_info["emoji"],
                        style=discord.ButtonStyle.primary,
                        custom_id=f"supplies_{object_key}",
                        row=row
                    )
                    button.callback = self._create_button_callback(object_key, object_info["name"], object_info["emoji"])
                    self.add_item(button)
                
                row += 1  # Каждая категория в новом ряду
                
            self._update_button_states()
            
        except Exception as e:
            print(f"❌ Ошибка создания динамических кнопок: {e}")
    
    def _create_button_callback(self, object_key: str, object_name: str, emoji: str):
        """Создает callback функцию для кнопки"""
        async def button_callback(interaction: discord.Interaction):
            await self._handle_object_button(interaction, object_key, object_name, emoji)
        return button_callback
        
    def _update_button_states(self):
        """Обновляет состояние кнопок на основе активных таймеров"""
        try:
            from .supplies_manager import SuppliesManager
            supplies_manager = SuppliesManager()
            active_timers = supplies_manager.get_active_timers()
            
            print(f"🔄 Обновление состояния кнопок. Активных таймеров: {len(active_timers)}")
            if active_timers:
                print(f"   Активные объекты: {list(active_timers.keys())}")
            
            # Обновляем состояние каждой кнопки
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.custom_id and item.custom_id.startswith("supplies_"):
                    object_key = item.custom_id.replace("supplies_", "")
                    
                    is_active = object_key in active_timers
                    item.disabled = is_active
                    item.style = discord.ButtonStyle.secondary if is_active else discord.ButtonStyle.primary
                    print(f"   {object_key}: {'заблокирован' if is_active else 'доступен'}")
                    
        except Exception as e:
            print(f"❌ Ошибка обновления состояния кнопок: {e}")
        
    async def _handle_object_button(self, interaction: discord.Interaction, object_key: str, object_name: str, emoji: str):
        """Обработка нажатия на кнопку объекта"""
        try:
            # Проверяем права доступа (модераторы/администраторы или Discord-админы)
            config = load_config()
            moderator_role_ids = config.get('moderators', {}).get('roles', [])
            administrator_role_ids = config.get('administrators', {}).get('roles', [])
            
            user_role_ids = [role.id for role in interaction.user.roles]
            is_bot_moderator_or_admin = any(role_id in user_role_ids for role_id in moderator_role_ids + administrator_role_ids)
            is_discord_admin = interaction.user.guild_permissions.administrator
            
            if not (is_bot_moderator_or_admin or is_discord_admin):
                await interaction.response.send_message(
                    "❌ У вас нет прав для управления поставками.", 
                    ephemeral=True
                )
                return
            
            # Импортируем менеджер поставок
            from .supplies_manager import SuppliesManager
            
            supplies_manager = SuppliesManager(interaction.client)
            
            # Проверяем, есть ли уже активный таймер
            if supplies_manager.is_timer_active(object_key):
                remaining_time = supplies_manager.get_remaining_time(object_key)
                await interaction.response.send_message(
                    f"⏰ {emoji} **{object_name}** уже находится в процессе поставки.\n"
                    f"⏳ Осталось времени: **{remaining_time}**",
                    ephemeral=True
                )
                return
            
            # Запускаем таймер
            success = await supplies_manager.start_timer(object_key, interaction.user)
            
            if success:
                # Получаем настройки таймера
                timer_duration_minutes = config.get('supplies', {}).get('timer_duration_minutes', 
                                                   config.get('supplies', {}).get('timer_duration_hours', 4) * 60)
                
                # Форматируем время для отображения
                hours = timer_duration_minutes // 60
                remaining_minutes = timer_duration_minutes % 60
                
                if hours > 0 and remaining_minutes > 0:
                    time_display = f"{hours}ч {remaining_minutes}м"
                elif hours > 0:
                    time_display = f"{hours}ч"
                else:
                    time_display = f"{remaining_minutes}м"
                
                await interaction.response.send_message(
                    f"✅ {emoji} **{object_name}** - поставка запущена!\n"
                    f"⏰ Длительность: **{time_display}**\n"
                    f"👤 Запустил: {interaction.user.mention}",
                    ephemeral=True
                )
                
                # Обновляем состояние кнопок
                self._update_button_states()
                
                # Обновляем основное сообщение с информацией о таймерах
                await self._update_timer_info(interaction.message)
                
                # Отправляем уведомление в канал оповещений
                await self._send_start_notification(object_key, object_name, emoji, interaction.user)
                
                # Уведомляем планировщик об изменении (для немедленного обновления)
                await self._notify_scheduler_update()
            else:
                await interaction.response.send_message(
                    f"❌ Ошибка при запуске таймера для {object_name}",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Ошибка в обработке кнопки поставок: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.",
                ephemeral=True
            )
    
    async def _update_timer_info(self, message: discord.Message):
        """Обновляет информацию о таймерах во втором embed"""
        try:
            from .supplies_manager import SuppliesManager
            
            supplies_manager = SuppliesManager()
            active_timers = supplies_manager.get_active_timers()
            
            # Создаем embed с информацией о таймерах
            timer_embed = discord.Embed(
                title="📊 Активные поставки",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if not active_timers:
                timer_embed.description = "🟢 Все объекты готовы к поставке"
            else:
                for object_key, timer_info in active_timers.items():
                    object_name = timer_info.get('object_name', object_key)
                    emoji = timer_info.get('emoji', '📦')
                    started_by = timer_info.get('started_by_name', 'Неизвестно')
                    remaining = supplies_manager.get_remaining_time(object_key)
                    
                    timer_embed.add_field(
                        name=f"{emoji} {object_name}",
                        value=f"⏰ Осталось: **{remaining}**\n👤 Запустил: {started_by}",
                        inline=True
                    )
            
            # Обновляем сообщение (добавляем второй embed или обновляем существующий)
            embeds = list(message.embeds) if message.embeds else []
            
            # Если есть только один embed (основной), добавляем второй
            if len(embeds) == 1:
                embeds.append(timer_embed)
            elif len(embeds) >= 2:
                # Обновляем второй embed
                embeds[1] = timer_embed
            else:
                # Если нет embeds, создаем основной и добавляем таймеры
                main_embed = discord.Embed(
                    title="🚚 Управление поставками",
                    description="Выберите военный объект для начала поставки материалов",
                    color=discord.Color.green()
                )
                embeds = [main_embed, timer_embed]
            
            await message.edit(embeds=embeds, view=self)
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении информации о таймерах: {e}")
    
    async def _send_start_notification(self, object_key: str, object_name: str, emoji: str, user):
        """Отправляет уведомление о начале поставки в канал оповещений"""
        try:
            config = load_config()
            notification_channel_id = config.get('supplies', {}).get('notification_channel_id')
            
            if not notification_channel_id:
                print("⚠️ Канал уведомлений не настроен")
                return
            
            # Получаем канал
            channel = user.guild.get_channel(notification_channel_id)
            if not channel:
                print(f"❌ Канал уведомлений не найден: {notification_channel_id}")
                return
            
            # Получаем настройки времени
            timer_duration_minutes = config.get('supplies', {}).get('timer_duration_minutes', 
                                               config.get('supplies', {}).get('timer_duration_hours', 4) * 60)
            warning_minutes = config.get('supplies', {}).get('warning_minutes', 20)
            
            # Получаем текущее оставшееся время вместо изначальной длительности
            from .supplies_manager import SuppliesManager
            supplies_manager = SuppliesManager()
            duration_display = supplies_manager.get_remaining_time(object_key)
            
            # Вычисляем время до предупреждения
            warning_time_minutes = timer_duration_minutes - warning_minutes
            warning_hours = warning_time_minutes // 60
            warning_mins = warning_time_minutes % 60
            
            if warning_hours > 0 and warning_mins > 0:
                warning_display = f"{warning_hours}ч {warning_mins}м"
            elif warning_hours > 0:
                warning_display = f"{warning_hours}ч"
            else:
                warning_display = f"{warning_mins}м"
            
            # Создаем embed
            embed = discord.Embed(
                title=f"{emoji} Поставка **{object_name}** запущена",
                description="",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name=f"⏰ Будет доступно через: **{duration_display}**",
                value="",
                inline=False
            )
            
            embed.add_field(
                name="👤 Запустил",
                value=user.mention,
                inline=True
            )
            
            embed.set_footer(text="Уведомление будет отправлено за несколько минут до конца таймера")
            
            # Отправляем сообщение БЕЗ пинга роли
            message = await channel.send(embed=embed)
            
            # Сохраняем ID сообщения для дальнейшего удаления
            await supplies_manager.save_notification_message(object_key, message.id, 'start')
            
            print(f"✅ Уведомление о начале поставки отправлено для {object_name}")
            
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления о начале поставки: {e}")
    
    async def _notify_scheduler_update(self):
        """Уведомляет планировщик об изменениях для немедленного обновления"""
        try:
            from utils.supplies_scheduler import get_supplies_scheduler
            scheduler = get_supplies_scheduler()
            if scheduler:
                # Принудительно проверяем таймеры при изменении
                await scheduler._check_timers()
        except Exception as e:
            print(f"❌ Ошибка уведомления планировщика: {e}")


async def send_supplies_control_message(channel: discord.TextChannel):
    """Отправляет сообщение с кнопками управления поставками"""
    try:
        # Основной embed
        main_embed = discord.Embed(
            title="🚚 Управление поставками",
            description=(
                "**Военные объекты для поставки материалов**\n\n"
                "⚠️ *Доступно только от Капитана*"
            ),
            color=discord.Color.green()
        )
        main_embed.set_footer(text="Нажмите кнопку для запуска таймера")
        
        # Embed с информацией о таймерах
        from .supplies_manager import SuppliesManager
        supplies_manager = SuppliesManager()
        active_timers = supplies_manager.get_active_timers()
        
        timer_embed = discord.Embed(
            title="📊 Активные поставки",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if not active_timers:
            timer_embed.description = "🟢 Все объекты готовы к поставке"
        else:
            for object_key, timer_info in active_timers.items():
                object_name = timer_info.get('object_name', object_key)
                emoji = timer_info.get('emoji', '📦')
                started_by = timer_info.get('started_by_name', 'Неизвестно')
                remaining = supplies_manager.get_remaining_time(object_key)
                
                timer_embed.add_field(
                    name=f"{emoji} {object_name}",
                    value=f"⏰ Осталось: **{remaining}**\n👤 Запустил: {started_by}",
                    inline=True
                )
        
        view = SuppliesControlView()
        # Обновляем состояние кнопок после создания
        view._update_button_states()
        message = await channel.send(embeds=[main_embed, timer_embed], view=view)
        return message
        
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения управления поставками: {e}")
        return None
