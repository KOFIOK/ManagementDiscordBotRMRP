import discord
from discord.ext import commands
from typing import Optional, Dict, Any
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, SectionSettingsView
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class SuppliesSettingsView(SectionSettingsView):
    """Настройки системы поставок"""
    
    def __init__(self):
        super().__init__(title="🚚 Настройки системы поставок", description="Управление военными объектами и уведомлениями о поставках", timeout=300)
        self.create_buttons()
    
    async def get_current_config(self) -> Dict[str, Any]:
        """Получает текущую конфигурацию поставок"""
        config = load_config()
        return config.get('supplies', {})
    
    def create_embed(self) -> discord.Embed:
        """Создает embed с текущими настройками"""
        config = load_config()
        supplies_config = config.get('supplies', {})
        
        # Миграция: если есть старые настройки в часах, конвертируем в минуты
        if 'timer_duration_hours' in supplies_config and 'timer_duration_minutes' not in supplies_config:
            old_hours = supplies_config['timer_duration_hours']
            supplies_config['timer_duration_minutes'] = old_hours * 60
            config['supplies'] = supplies_config
            save_config(config)
            logger.info("Мигрировали настройку таймера: %sч → {old_hours * 60}мин", old_hours)
        
        embed = discord.Embed(
            title="⚙️ Настройки системы поставок",
            description="Управление военными объектами и уведомлениями о поставках",
            color=discord.Color.blue()
        )
        
        # Каналы
        control_channel_id = supplies_config.get('control_channel_id')
        notification_channel_id = supplies_config.get('notification_channel_id') 
        subscription_channel_id = supplies_config.get('subscription_channel_id')
        
        embed.add_field(
            name="📂 Каналы",
            value=(
                f"🎮 **Управление:** {f'<#{control_channel_id}>' if control_channel_id else '❌ Не настроен'}\n"
                f"📢 **Уведомления:** {f'<#{notification_channel_id}>' if notification_channel_id else '❌ Не настроен'}\n"
                f"🔔 **Подписка:** {f'<#{subscription_channel_id}>' if subscription_channel_id else '❌ Не настроен'}"
            ),
            inline=False
        )
        
        # Настройки времени
        timer_duration_minutes = supplies_config.get('timer_duration_minutes', supplies_config.get('timer_duration_hours', 4) * 60)
        warning_minutes = supplies_config.get('warning_minutes', 20)
        
        # Конвертируем минуты в читаемый формат
        hours = timer_duration_minutes // 60
        remaining_minutes = timer_duration_minutes % 60
        
        if hours > 0 and remaining_minutes > 0:
            time_display = f"{hours}ч {remaining_minutes}м"
        elif hours > 0:
            time_display = f"{hours}ч"
        else:
            time_display = f"{remaining_minutes}м"
        
        embed.add_field(
            name="⏰ Настройки времени",
            value=(
                f"⏳ **Длительность таймера:** {timer_duration_minutes} мин ({time_display})\n"
                f"⚠️ **Предупреждение за:** {warning_minutes} минут"
            ),
            inline=True
        )
        
        # Роль подписки
        subscription_role_id = supplies_config.get('subscription_role_id')
        embed.add_field(
            name="🏷️ Роли",
            value=(
                f"🔔 **Подписка на уведомления:** "
                f"{f'<@&{subscription_role_id}>' if subscription_role_id else '❌ Не настроена'}"
            ),
            inline=True
        )
        
        # Военные объекты (статичная информация)
        embed.add_field(
            name="⏰ Настройки времени",
            value=(
                "🏭 **Объект №7** - Промышленный комплекс\n"
                "📦 **Военные Склады** - Складская база\n"
                "📡 **РЛС Орбита** - Радиолокационная станция"
            ),
            inline=False
        )
        
        embed.set_footer(text="Настройте каналы и роли для работы системы поставок")
        return embed
    
    def create_buttons(self):
        """Создает кнопки управления настройками"""
        # Настройка каналов
        self.add_item(ChannelControlButton())
        self.add_item(ChannelNotificationButton())
        self.add_item(ChannelSubscriptionButton())
        
        # Настройка времени
        self.add_item(TimerDurationButton())
        self.add_item(WarningTimeButton())
        
        # Настройка ролей
        self.add_item(SubscriptionRoleButton())


class ChannelControlSelectView(discord.ui.View):
    """View для выбора канала управления"""
    
    def __init__(self):
        super().__init__(timeout=30)
        
        select = discord.ui.ChannelSelect(
            placeholder="Выберите канал управления поставками",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        select.callback = self.channel_select
        self.add_item(select)
    
    async def channel_select(self, interaction: discord.Interaction):
        select = interaction.data['values'][0]
        channel_id = int(select)
        
        config = load_config()
        if 'supplies' not in config:
            config['supplies'] = {}
        config['supplies']['control_channel_id'] = channel_id
        
        if save_config(config):
            await interaction.response.send_message(
                f"✅ Канал управления поставками настроен: <#{channel_id}>",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                " Ошибка сохранения настроек",
                ephemeral=True
            )


class ChannelControlButton(discord.ui.Button):
    """Кнопка настройки канала управления"""
    
    def __init__(self):
        super().__init__(
            label="Канал управления",
            emoji="🎮",
            style=discord.ButtonStyle.primary,
            custom_id="supplies_channel_control"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = ChannelControlSelectView()
        await interaction.response.send_message("Выберите канал:", view=view, ephemeral=True)


class ChannelNotificationSelectView(discord.ui.View):
    """View для выбора канала уведомлений"""
    
    def __init__(self):
        super().__init__(timeout=30)
        
        select = discord.ui.ChannelSelect(
            placeholder="Выберите канал уведомлений о поставках",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        select.callback = self.channel_select
        self.add_item(select)
    
    async def channel_select(self, interaction: discord.Interaction):
        select = interaction.data['values'][0]
        channel_id = int(select)
        
        config = load_config()
        if 'supplies' not in config:
            config['supplies'] = {}
        config['supplies']['notification_channel_id'] = channel_id
        
        if save_config(config):
            await interaction.response.send_message(
                f" Канал уведомлений о поставках настроен: <#{channel_id}>",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                " Ошибка сохранения настроек",
                ephemeral=True
            )


class ChannelNotificationButton(discord.ui.Button):
    """Кнопка настройки канала уведомлений"""
    
    def __init__(self):
        super().__init__(
            label="Канал уведомлений",
            emoji="📢",
            style=discord.ButtonStyle.primary,
            custom_id="supplies_channel_notification"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = ChannelNotificationSelectView()
        await interaction.response.send_message("Выберите канал:", view=view, ephemeral=True)


class ChannelSubscriptionSelectView(discord.ui.View):
    """View для выбора канала подписки"""
    
    def __init__(self):
        super().__init__(timeout=30)
        
        select = discord.ui.ChannelSelect(
            placeholder="Выберите канал подписки на уведомления",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        select.callback = self.channel_select
        self.add_item(select)
    
    async def channel_select(self, interaction: discord.Interaction):
        select = interaction.data['values'][0]
        channel_id = int(select)
        
        config = load_config()
        if 'supplies' not in config:
            config['supplies'] = {}
        config['supplies']['subscription_channel_id'] = channel_id
        
        if save_config(config):
            await interaction.response.send_message(
                f" Канал подписки на поставки настроен: <#{channel_id}>",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                " Ошибка сохранения настроек",
                ephemeral=True
            )


class ChannelSubscriptionButton(discord.ui.Button):
    """Кнопка настройки канала подписки"""
    
    def __init__(self):
        super().__init__(
            label="Канал подписки",
            emoji="🔔",
            style=discord.ButtonStyle.primary,
            custom_id="supplies_channel_subscription"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = ChannelSubscriptionSelectView()
        await interaction.response.send_message("Выберите канал:", view=view, ephemeral=True)


class TimerDurationButton(discord.ui.Button):
    """Кнопка настройки длительности таймера"""
    
    def __init__(self):
        super().__init__(
            label="Длительность таймера",
            emoji="⏳",
            style=discord.ButtonStyle.secondary,
            custom_id="supplies_timer_duration"
        )
    
    async def callback(self, interaction: discord.Interaction):
        modal = TimerDurationModal()
        await interaction.response.send_modal(modal)


class WarningTimeButton(discord.ui.Button):
    """Кнопка настройки времени предупреждения"""
    
    def __init__(self):
        super().__init__(
            label="Время предупреждения",
            emoji="⚠️",
            style=discord.ButtonStyle.secondary,
            custom_id="supplies_warning_time"
        )
    
    async def callback(self, interaction: discord.Interaction):
        modal = WarningTimeModal()
        await interaction.response.send_modal(modal)


class SubscriptionRoleSelectView(discord.ui.View):
    """View для выбора роли подписки"""
    
    def __init__(self):
        super().__init__(timeout=30)
        
        select = discord.ui.RoleSelect(
            placeholder="Выберите роль для подписки на уведомления",
            min_values=1,
            max_values=1
        )
        select.callback = self.role_select
        self.add_item(select)
    
    async def role_select(self, interaction: discord.Interaction):
        select = interaction.data['values'][0]
        role_id = int(select)
        
        config = load_config()
        if 'supplies' not in config:
            config['supplies'] = {}
        config['supplies']['subscription_role_id'] = role_id
        
        if save_config(config):
            await interaction.response.send_message(
                f"✅ Роль подписки на поставки настроена: <@&{role_id}>",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                " Ошибка сохранения настроек",
                ephemeral=True
            )


class SubscriptionRoleButton(discord.ui.Button):
    """Кнопка настройки роли подписки"""
    
    def __init__(self):
        super().__init__(
            label="Роль подписки",
            emoji="👥",
            style=discord.ButtonStyle.success,
            custom_id="supplies_subscription_role"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = SubscriptionRoleSelectView()
        await interaction.response.send_message("Выберите роль:", view=view, ephemeral=True)


class BackToMainButton(discord.ui.Button):
    """Кнопка возврата к главным настройкам"""
    
    def __init__(self):
        super().__init__(
            label="Назад",
            style=discord.ButtonStyle.danger,
            custom_id="supplies_back_to_main"
        )
    
    async def callback(self, interaction: discord.Interaction):
        from .main import SettingsView
        view = SettingsView()
        
        # Создаем embed для главного меню настроек
        embed = discord.Embed(
            title="⚙️ Панель настроек бота",
            description="Добро пожаловать в панель управления настройками бота! Здесь вы можете настроить все основные параметры работы системы.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📝 Доступные категории:",
            value=(
                "• **📂 Настройка каналов** - настроить каналы для различных систем\n"
                "• **🚚 Система поставок** - настроить управление военными объектами\n"
                "• **🛡️ Роли-исключения** - роли, не снимаемые при увольнении\n"
                "• **⚙️ Показать настройки** - просмотр текущих настроек"
            ),
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=view)


class TimerDurationModal(discord.ui.Modal):
    """Модальное окно для настройки длительности таймера"""
    
    def __init__(self):
        super().__init__(title="⏳ Настройка длительности таймера")
        
        self.duration_input = discord.ui.TextInput(
            label="Длительность в минутах",
            placeholder="Введите количество минут (например: 240 для 4ч)",
            min_length=1,
            max_length=4
        )
        self.add_item(self.duration_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.duration_input.value)
            
            if minutes < 1 or minutes > 1440:  # максимум 24 часа = 1440 минут
                await interaction.response.send_message(
                    "❌ Длительность должна быть от 1 до 1440 минут (24 часа)",
                    ephemeral=True
                )
                return
            
            # Конвертируем в читаемый формат для отображения
            hours = minutes // 60
            remaining_minutes = minutes % 60
            
            if hours > 0 and remaining_minutes > 0:
                time_display = f"{hours}ч {remaining_minutes}м"
            elif hours > 0:
                time_display = f"{hours}ч"
            else:
                time_display = f"{remaining_minutes}м"
            
            config = load_config()
            if 'supplies' not in config:
                config['supplies'] = {}
            config['supplies']['timer_duration_minutes'] = minutes
            
            if save_config(config):
                await interaction.response.send_message(
                    f"✅ Длительность таймера установлена: **{minutes} минут** ({time_display})",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Ошибка сохранения настроек",
                    ephemeral=True
                )
                
        except ValueError:
            await interaction.response.send_message(
                " Введите корректное число",
                ephemeral=True
            )


class WarningTimeModal(discord.ui.Modal):
    """Модальное окно для настройки времени предупреждения"""
    
    def __init__(self):
        super().__init__(title="⚠️ Настройка времени предупреждения")
        
        self.warning_input = discord.ui.TextInput(
            label="Предупреждение за (минут)",
            placeholder="Введите количество минут (например: 20)",
            min_length=1,
            max_length=3
        )
        self.add_item(self.warning_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.warning_input.value)
            
            if minutes < 1 or minutes > 240:  # До 4 часов
                await interaction.response.send_message(
                    "❌ Время предупреждения должно быть от 1 до 240 минут",
                    ephemeral=True
                )
                return
            
            config = load_config()
            if 'supplies' not in config:
                config['supplies'] = {}
            config['supplies']['warning_minutes'] = minutes
            
            if save_config(config):
                await interaction.response.send_message(
                    f"✅ Время предупреждения установлено: **{minutes} минут**",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    " Ошибка сохранения настроек",
                    ephemeral=True
                )
                
        except ValueError:
            await interaction.response.send_message(
                " Введите корректное число",
                ephemeral=True
            )