"""
Promotion reports channels configuration
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal, ChannelParser, ConfigDisplayHelper
import os


class PromotionReportsConfigView(BaseSettingsView):
    """View for promotion reports configuration with dropdown selection"""
    
    def __init__(self):
        super().__init__()
        self.add_item(PromotionDepartmentSelect())


class PromotionDepartmentSelect(ui.Select):
    """Select menu for choosing department to configure promotion reports"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Отчёты ВА",
                description="Военная Академия",
                emoji="✈️",
                value="va"
            ),
            discord.SelectOption(
                label="Отчёты ВК",
                description="Военный Комиссариат",
                emoji="🚀",
                value="vk"
            ),
            discord.SelectOption(
                label="Отчёты УВП",
                description="Управление Военной Полиции",
                emoji="👮",
                value="uvp"
            ),
            discord.SelectOption(
                label="Отчёты ССО",
                description="Силы Специальных Операций",
                emoji="🔫",
                value="sso"
            ),
            discord.SelectOption(
                label="Отчёты МР",
                description="Медицинская Рота",
                emoji="⚓",
                value="mr"
            ),
            discord.SelectOption(
                label="Отчёты РОиО",
                description="Рота Охраны и Обеспечения",
                emoji="🛡️",
                value="roio"
            )
        ]
        
        super().__init__(
            placeholder="Выберите подразделение для настройки...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="promotion_department_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_department = self.values[0]
        # Show department configuration with buttons
        department_names = {
            'va': 'ВА (Военная Академия)',
            'vk': 'ВК (Военный Комиссариат)',
            'uvp': 'УВП (Управление Военной Полиции)',
            'sso': 'ССО (Силы Специальных Операций)',
            'mr': 'МР (Медицинская Рота)',
            'roio': 'РОиО (Рота Охраны и Обеспечения)'
        }
        
        department_emojis = {
            'va': '✈️',
            'vk': '🚀',
            'uvp': '👮',
            'sso': '🔫',
            'mr': '⚓',
            'roio': '🛡️'
        }
        
        config = load_config()
        promotion_channels = config.get('promotion_report_channels', {})
        current_channel_id = promotion_channels.get(selected_department)
        
        embed = discord.Embed(
            title=f"{department_emojis.get(selected_department, '📈')} Настройка отчётов {department_names.get(selected_department, selected_department.upper())}",
            description=f"Управление каналом отчётов на повышение для подразделения {department_names.get(selected_department, selected_department.upper())}",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        
        # Show current channel
        if current_channel_id:
            channel = interaction.guild.get_channel(current_channel_id)
            if channel:
                embed.add_field(
                    name="📂 Текущий канал:",
                    value=channel.mention,
                    inline=False
                )
            else:
                embed.add_field(
                    name="❌ Канал не найден",
                    value=f"Канал с ID {current_channel_id} не найден",
                    inline=False
                )
        else:
            embed.add_field(
                name="❌ Канал не настроен",
                value="Установите канал для отчётов на повышение",
                inline=False
            )
        
        # Show notification settings
        notification_settings = config.get('promotion_notifications', {}).get(selected_department, {})
        if notification_settings:
            notification_text = notification_settings.get('text')
            notification_image = notification_settings.get('image')
            notification_enabled = notification_settings.get('enabled', False)
            
            status = "🟢 Включены" if notification_enabled else "🔴 Отключены"
            content_parts = []
            if notification_text:
                content_parts.append("текст")
            if notification_image:
                content_parts.append("изображение")
            content_info = f" ({', '.join(content_parts)})" if content_parts else ""
            
            # Get configured notification time
            schedule_config = config.get('notification_schedule', {'hour': 21, 'minute': 0})
            hour = schedule_config.get('hour', 21)
            minute = schedule_config.get('minute', 0)
            time_str = f"{hour:02d}:{minute:02d}"
            
            embed.add_field(
                name="🔔 Ежедневные уведомления:",
                value=f"{status}{content_info}\n{'*Отправка в ' + time_str + ' МСК*' if notification_enabled else ''}",
                inline=False
            )
        else:
            embed.add_field(
                name="🕐 Ежедневные уведомления:",
                value="❌ Не настроены",
                inline=False
            )
        
        embed.add_field(
            name="🔧 Доступные действия:",
            value=(
                "• **Настроить канал** - установить канал для отчётов\n"
                "• **Задать уведомление** - настроить ежедневные уведомления\n"
                "*Время отправки: `/set_notification_time`*"
            ),
            inline=False
        )
        
        view = PromotionDepartmentConfigView(selected_department)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class PromotionDepartmentConfigView(BaseSettingsView):
    """View for configuring specific department promotion reports"""
    
    def __init__(self, department_code: str):
        super().__init__()
        self.department_code = department_code
    
    @discord.ui.button(label="📂 Настроить канал", style=discord.ButtonStyle.green)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PromotionChannelModal(self.department_code)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔔 Задать уведомление", style=discord.ButtonStyle.secondary)
    async def set_notification(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PromotionNotificationModal(self.department_code)
        await interaction.response.send_modal(modal)


class PromotionChannelModal(BaseSettingsModal):
    """Modal for configuring promotion report channel for specific department"""
    
    def __init__(self, department_code: str):
        self.department_code = department_code
        
        # Короткие названия для заголовков modal (лимит 45 символов)
        department_names = {
            'va': 'ВА',
            'vk': 'ВК', 
            'uvp': 'УВП',
            'sso': 'ССО',
            'mr': 'МР',
            'roio': 'РОиО'
        }
        
        dept_name = department_names.get(department_code, department_code.upper())
        super().__init__(title=f"📈 Настройка канала {dept_name}")
        
        # Полные названия для подсказок
        full_department_names = {
            'va': 'ВА (Военная Академия)',
            'vk': 'ВК (Военный Комиссариат)',
            'uvp': 'УВП (Военная Полиция)',
            'sso': 'ССО (Спецоперации)',
            'mr': 'МР (Медицинская Рота)',
            'roio': 'РОиО (Рота Охраны и Обеспечения)'
        }
        
        full_dept_name = full_department_names.get(department_code, department_code.upper())
        
        self.channel_input = ui.TextInput(
            label=f"Канал для отчётов {dept_name}",
            placeholder=f"Канал для отчётов {full_dept_name}",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse channel input
            channel = ChannelParser.parse_channel_input(self.channel_input.value.strip(), interaction.guild)
            
            if not channel:
                await self.send_error_message(
                    interaction,
                    "Канал не найден",
                    f"Канал '{self.channel_input.value.strip()}' не найден на сервере."
                )
                return
            
            # Save configuration
            config = load_config()
            if 'promotion_report_channels' not in config:
                config['promotion_report_channels'] = {}
            
            config['promotion_report_channels'][self.department_code] = channel.id
            save_config(config)
            
            department_names = {
                'va': 'ВА (Военная Академия)',
                'vk': 'ВК (Военный Комиссариат)',
                'uvp': 'УВП (Военная Полиция)',
                'sso': 'ССО (Спецоперации)',
                'mr': 'МР (Медицинская Рота)',
                'roio': 'РОиО (Рота Охраны и Обеспечения)'
            }
            
            dept_name = department_names.get(self.department_code, self.department_code.upper())
            
            await self.send_success_message(
                interaction,
                "Канал настроен",
                f"Канал для отчётов {dept_name} установлен: {channel.mention}"
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке канала: {str(e)}"
            )


class PromotionNotificationModal(BaseSettingsModal):
    """Modal for configuring promotion report daily notifications"""
    
    def __init__(self, department_code: str):
        self.department_code = department_code
        
        # Короткие названия для заголовков modal
        department_names = {
            'va': 'ВА',
            'vk': 'ВК',
            'uvp': 'УВП', 
            'sso': 'ССО',
            'mr': 'МР',
            'roio': 'РОиО'
        }
        
        dept_name = department_names.get(department_code, department_code.upper())
        super().__init__(title=f"🔔 Уведомления {dept_name}")
        
        # Load current settings
        config = load_config()
        current_notification = config.get('promotion_notifications', {}).get(department_code, {})
        current_text = current_notification.get('text', '')
        current_image = current_notification.get('image', '')
        current_enabled = current_notification.get('enabled', False)
        
        self.text_input = ui.TextInput(
            label="Текст уведомления",
            placeholder="Введите текст для ежедневного уведомления...",
            style=discord.TextStyle.paragraph,
            min_length=0,
            max_length=1000,
            required=False,
            default=current_text
        )
        self.add_item(self.text_input)
        
        self.image_input = ui.TextInput(
            label="Название файла изображения",
            placeholder="Например: report_va.png (файлы в папке files/reports/)",
            min_length=0,
            max_length=100,
            required=False,
            default=current_image
        )
        self.add_item(self.image_input)
        
        self.enabled_input = ui.TextInput(
            label="Включить уведомления? (да/нет)",
            placeholder="да - включить, нет - отключить",
            min_length=2,
            max_length=3,
            required=True,
            default="да" if current_enabled else "нет"
        )
        self.add_item(self.enabled_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            text = self.text_input.value.strip()
            image_filename = self.image_input.value.strip()
            enabled_str = self.enabled_input.value.strip().lower()
            
            # Validate enabled input
            if enabled_str not in ['да', 'нет', 'yes', 'no']:
                await self.send_error_message(
                    interaction,
                    "Неверный ввод",
                    "Введите 'да' для включения или 'нет' для отключения уведомлений."
                )
                return
            
            enabled = enabled_str in ['да', 'yes']
            
            # Validate that at least text or image is provided if enabled
            if enabled and not text and not image_filename:
                await self.send_error_message(
                    interaction,
                    "Необходимо содержимое",
                    "Для включения уведомлений необходимо указать текст или изображение."
                )
                return
            
            # Validate image file if provided
            image_path = None
            if image_filename:
                image_path = os.path.join('files', 'reports', image_filename)
                if not os.path.exists(image_path):
                    await self.send_error_message(
                        interaction,
                        "Файл не найден",
                        f"Файл {image_filename} не найден в папке files/reports/. "
                        f"Убедитесь, что файл существует."
                    )
                    return
            
            # Save configuration
            config = load_config()
            if 'promotion_notifications' not in config:
                config['promotion_notifications'] = {}
            
            if self.department_code not in config['promotion_notifications']:
                config['promotion_notifications'][self.department_code] = {}
            
            config['promotion_notifications'][self.department_code] = {
                'text': text,
                'image': image_filename,
                'enabled': enabled
            }
            
            save_config(config)
            
            # Ensure scheduler is running if notifications are enabled
            if enabled:
                await self._ensure_scheduler_running()
            
            status = "включены" if enabled else "отключены"
            content_parts = []
            if text:
                content_parts.append("текст")
            if image_filename:
                content_parts.append("изображение")
            content_info = f" ({', '.join(content_parts)})" if content_parts else ""
            
            await self.send_success_message(
                interaction,
                "Уведомления настроены",
                f"Ежедневные уведомления для {self.department_code.upper()} {status}{content_info}."
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке уведомлений: {str(e)}"
            )
    
    async def _ensure_scheduler_running(self):
        """Ensure the notification scheduler is running"""
        # This will be implemented when we add the scheduler to the main bot
        pass


async def show_promotion_reports_config(interaction: discord.Interaction):
    """Show promotion reports channels configuration"""
    embed = discord.Embed(
        title="📈 Настройка каналов отчётов на повышение",
        description="Управление каналами для отчётов на повышение по подразделениям.",
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    
    config = load_config()
    helper = ConfigDisplayHelper()
    
    # Show current channels
    promotion_channels = config.get('promotion_report_channels', {})
    department_names = {
        'va': 'ВА (Военная Академия)',
        'vk': 'ВК (Военный Комиссариат)',
        'uvp': 'УВП (Военная Полиция)',
        'sso': 'ССО (Силы Спец. Операций)',
        'mr': 'МР (Медицинская Рота)',
        'roio': 'РОиО (Роты Охраны)'
    }
    
    channels_info = ""
    for dept_code, channel_id in promotion_channels.items():
        dept_name = department_names.get(dept_code, dept_code.upper())
        if channel_id:
            channel = interaction.guild.get_channel(channel_id)
            channel_text = channel.mention if channel else f"❌ Канал не найден (ID: {channel_id})"
        else:
            channel_text = "❌ Не настроен"
        channels_info += f"**{dept_name}**: {channel_text}\n"
    
    embed.add_field(
        name="📊 Настроенные каналы:",
        value=channels_info or "❌ Каналы не настроены",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Описание:",
        value=(
            "Каждый канал предназначен для отчётов на повышение в звании "
            "для соответствующего подразделения. Настройте каналы для "
            "автоматической отправки отчётов в нужные места."
        ),
        inline=False
    )
    
    embed.add_field(
        name="🔧 Доступные действия:",
        value="Выберите подразделение для настройки канала и уведомлений:",
        inline=False
    )
    
    view = PromotionReportsConfigView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
