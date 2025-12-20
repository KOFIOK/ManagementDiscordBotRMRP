"""
Настройки системы склада через интерфейс /settings
Включает управление каналами, лимитами по должностям/званиям и режимами работы
"""

import discord
from discord.ext import commands
from typing import Dict, List, Optional, Any
from utils.config_manager import load_config, save_config
from utils.message_manager import get_settings_message
from .base import SectionSettingsView
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class WarehouseSettingsView(SectionSettingsView):
    """Главное меню настроек склада"""
    
    def __init__(self):
        super().__init__(title="📦 Настройки склада", description="Управление системой запросов и выдачи складского имущества", timeout=300)
    
    @discord.ui.button(label="Каналы склада", style=discord.ButtonStyle.primary, emoji="📦")
    async def channels_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Настройка каналов склада"""
        view = WarehouseChannelsView()
        await view.show_settings(interaction)
    
    @discord.ui.button(label="Кулдаун", style=discord.ButtonStyle.secondary, emoji="⏰")
    async def cooldown_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Настройка кулдауна между запросами"""
        modal = WarehouseCooldownModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Режим лимитов", style=discord.ButtonStyle.secondary, emoji="🎛️")
    async def limits_mode_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Настройка режима лимитов"""
        view = WarehouseLimitsModeView()
        await view.show_settings(interaction)

    @discord.ui.button(label="Лимиты должностей", style=discord.ButtonStyle.secondary, emoji="💼")
    async def position_limits_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Настройка лимитов по должностям"""
        view = WarehousePositionLimitsView()
        await view.show_settings(interaction)
    
    @discord.ui.button(label="Лимиты званий", style=discord.ButtonStyle.secondary, emoji="🎖️")
    async def rank_limits_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Настройка лимитов по званиям"""
        view = WarehouseRankLimitsView()
        await view.show_settings(interaction)

    @discord.ui.button(label="Общие лимиты", style=discord.ButtonStyle.secondary, emoji="📊")
    async def general_limits_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Настройка общих лимитов (правило 4.20)"""
        modal = WarehouseGeneralLimitsModal()
        await interaction.response.send_modal(modal)


class WarehouseChannelsView(discord.ui.View):
    """Настройка каналов склада"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Показать настройки каналов"""
        config = load_config()
        
        embed = discord.Embed(
            title="📂 Настройка каналов склада",
            description="Управление каналами системы складского учёта",
            color=discord.Color.blue()
        )
          # Канал запросов
        request_channel_id = config.get('warehouse_request_channel')
        if request_channel_id:
            channel = interaction.guild.get_channel(request_channel_id)
            request_text = channel.mention if channel else f"❌ Канал не найден (ID: {request_channel_id})"
        else:
            request_text = "❌ Не настроен"
        
        embed.add_field(
            name="📂 Канал запросов:",
            value=request_text,
            inline=False
        )
        
        # Канал отправки заявок
        submission_channel_id = config.get('warehouse_submission_channel')
        if submission_channel_id:
            channel = interaction.guild.get_channel(submission_channel_id)
            submission_text = channel.mention if channel else f"❌ Канал не найден (ID: {submission_channel_id})"
        else:
            submission_text = "📦 Используется канал запросов"
        
        embed.add_field(
            name="📂 Канал отправки заявок:",
            value=submission_text,
            inline=False
        )
        
        # Канал аудита
        audit_channel_id = config.get('warehouse_audit_channel')
        if audit_channel_id:
            channel = interaction.guild.get_channel(audit_channel_id)
            audit_text = channel.mention if channel else f"❌ Канал не найден (ID: {audit_channel_id})"
        else:
            audit_text = "❌ Не настроен"
        
        embed.add_field(
            name="📂 Канал аудита:",
            value=audit_text,
            inline=False
        )
        
        # Кураторы аудита
        curators = config.get('warehouse_audit_curators', [])
        if curators:
            curator_mentions = []
            for curator in curators:
                if isinstance(curator, str) and curator.isdigit():
                    curator_mentions.append(f"<@{curator}>")
                elif isinstance(curator, str) and curator.startswith('<@&') and curator.endswith('>'):
                    curator_mentions.append(curator)
                else:
                    curator_mentions.append(str(curator))
            
            curators_text = ", ".join(curator_mentions[:3])  # Показываем первых 3
            if len(curator_mentions) > 3:
                curators_text += f"и еще {len(curator_mentions) - 3}"
        else:
            curators_text = "❌ Не настроены"
        
        embed.add_field(
            name="📦 Канал запросов:",
            value=curators_text,
            inline=False
        )
        
        view = WarehouseChannelsButtonsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class WarehouseChannelsButtonsView(discord.ui.View):
    """Кнопки для настройки каналов склада"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="📂 Канал запросов", style=discord.ButtonStyle.green)
    async def set_request_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WarehouseChannelModal("warehouse_request_channel", "Канал запросов склада")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📤 Канал отправки заявок", style=discord.ButtonStyle.primary)
    async def set_submission_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WarehouseChannelModal("warehouse_submission_channel", "Канал отправки заявок")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📂 Канал аудита", style=discord.ButtonStyle.secondary)
    async def set_audit_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WarehouseChannelModal("warehouse_audit_channel", "Канал аудита склада")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👑 Кураторы аудита", style=discord.ButtonStyle.blurple)
    async def set_audit_curators(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Настройка кураторов для аудита чистки склада"""
        modal = WarehouseAuditCuratorsModal()
        await interaction.response.send_modal(modal)


class WarehouseChannelModal(discord.ui.Modal):
    """Модальное окно для настройки канала склада"""
    
    def __init__(self, config_key: str, title: str):
        super().__init__(title=title)
        self.config_key = config_key
        
        self.channel_input = discord.ui.TextInput(
            label="🆔 ID или упоминание канала",
            placeholder="#канал-склада или 1234567890123456789",
            max_length=100,
            required=True
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_text = self.channel_input.value.strip()
            
            # Используем централизованный парсер каналов
            from .base import ChannelParser
            channel = ChannelParser.parse_channel_input(channel_text, interaction.guild)
            
            if not channel:
                error_msg = get_settings_message(interaction.guild.id, "warehouse.error_channel_not_found", "❌ Канал '{0}' не найден!")
                await interaction.response.send_message(
                    error_msg.format(channel_text), ephemeral=True
                )
                return
            
            # Сохранение конфигурации
            config = load_config()
            config[self.config_key] = channel.id
            save_config(config)
              # Специальная обработка для различных типов каналов
            if self.config_key == "warehouse_request_channel":
                try:
                    from utils.warehouse_utils import send_warehouse_message
                    await send_warehouse_message(channel)
                    message = get_settings_message(interaction.guild.id, "warehouse.success_request_channel_set", "✅ Канал запросов настроен: {0}\n📌 Закрепленное сообщение склада добавлено!").format(channel.mention)
                except Exception as e:
                    logger.error("Ошибка создания сообщения склада: %s", e)
                    message = get_settings_message(interaction.guild.id, "warehouse.success_request_channel_set_error", "✅ Канал запросов настроен: {0}\n❗ Ошибка при добавлении закрепленного сообщения: {1}").format(channel.mention, str(e))
            elif self.config_key == "warehouse_submission_channel":
                message = get_settings_message(interaction.guild.id, "warehouse.success_submission_channel_set", "✅ Канал отправки заявок настроен: {0}\n📤 Все заявки склада будут отправляться в этот канал!").format(channel.mention)
            elif self.config_key == "warehouse_audit_channel":
                message = get_settings_message(interaction.guild.id, "warehouse.success_audit_channel_set", "✅ Канал аудита настроен: {0}").format(channel.mention)
            else:
                message = get_settings_message(interaction.guild.id, "warehouse.success_channel_set", "✅ Канал настроен: {0}").format(channel.mention)
            
            await interaction.response.send_message(message, ephemeral=True)
            
        except Exception as e:
            error_msg = get_settings_message(interaction.guild.id, "warehouse.error_general", "❌ Ошибка: {0}")
            await interaction.response.send_message(
                error_msg.format(str(e)), ephemeral=True
            )


class WarehouseCooldownModal(discord.ui.Modal):
    """Модальное окно для настройки кулдауна"""
    
    def __init__(self):
        super().__init__(title="⏰ Настройка кулдауна")
        
        config = load_config()
        current_cooldown = config.get('warehouse_cooldown_hours', 6)        
        self.cooldown_input = discord.ui.TextInput(
            label="Кулдаун в часах",
            placeholder="Например: 6 или 0.083 (5 мин)",
            default=str(current_cooldown),
            max_length=5,
            required=True
        )
        self.add_item(self.cooldown_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            cooldown_str = self.cooldown_input.value.strip().replace(',', '.')
            
            try:
                cooldown = float(cooldown_str)
            except ValueError:
                await interaction.response.send_message(
                    "❌ Введите корректное число (например: 6 или 0.5)!", ephemeral=True
                )
                return
            
            if cooldown < 0 or cooldown > 168:  # Максимум неделя
                await interaction.response.send_message(
                    "❌ Кулдаун должен быть от 0 до 168 часов!", ephemeral=True
                )
                return
            
            config = load_config()
            config['warehouse_cooldown_hours'] = cooldown
            save_config(config)
            
            # Форматирование вывода
            if cooldown == int(cooldown):
                cooldown_display = str(int(cooldown))
            else:
                cooldown_display = str(cooldown)
            
            await interaction.response.send_message(
                f"✅ Кулдаун установлен: {cooldown_display} часов", ephemeral=True
            )
            
        except Exception as e:
            logger.error("Ошибка в WarehouseCooldownModal: %s", e)
            await interaction.response.send_message(
                f"❌ Ошибка при установке кулдауна: {str(e)}", ephemeral=True
            )


class WarehouseGeneralLimitsModal(discord.ui.Modal):
    """Модальное окно для настройки общих лимитов (правило 4.20)"""

    def __init__(self):
        super().__init__(title="📊 Настройка общих лимитов (4.20)")

        config = load_config()
        limits = config.get('warehouse_general_limits', {
            'weapons_max': 3,
            'materials_max': 2000,
            'armor_max': 20,
            'medkits_max': 25,
            'other_max': 15
        })

        self.weapons_max = discord.ui.TextInput(
            label="Оружие (ед.)",
            placeholder="Например: 3",
            default=str(limits.get('weapons_max', 3)),
            required=True,
            max_length=6
        )
        self.add_item(self.weapons_max)

        self.materials_max = discord.ui.TextInput(
            label="Материалы",
            placeholder="Например: 2000",
            default=str(limits.get('materials_max', 2000)),
            required=True,
            max_length=8
        )
        self.add_item(self.materials_max)

        self.armor_max = discord.ui.TextInput(
            label="Бронежилеты (ед.)",
            placeholder="Например: 20",
            default=str(limits.get('armor_max', 20)),
            required=True,
            max_length=6
        )
        self.add_item(self.armor_max)

        self.medkits_max = discord.ui.TextInput(
            label="Аптечки (ед.)",
            placeholder="Например: 25",
            default=str(limits.get('medkits_max', 25)),
            required=True,
            max_length=6
        )
        self.add_item(self.medkits_max)

        self.other_max = discord.ui.TextInput(
            label="Прочее (ед.)",
            placeholder="Например: 15",
            default=str(limits.get('other_max', 15)),
            required=True,
            max_length=6
        )
        self.add_item(self.other_max)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            def parse_int(value: str, default: int) -> int:
                try:
                    return int(value.strip())
                except Exception:
                    return default

            config = load_config()
            config['warehouse_general_limits'] = {
                'weapons_max': parse_int(self.weapons_max.value, 3),
                'materials_max': parse_int(self.materials_max.value, 2000),
                'armor_max': parse_int(self.armor_max.value, 20),
                'medkits_max': parse_int(self.medkits_max.value, 25),
                'other_max': parse_int(self.other_max.value, 15)
            }
            save_config(config)

            await interaction.response.send_message(
                "✅ Общие лимиты (правило 4.20) обновлены", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при обновлении общих лимитов: {e}", ephemeral=True
            )


class WarehouseLimitsModeView(discord.ui.View):
    """Настройка режима лимитов"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Показать настройки режима лимитов"""
        config = load_config()
        limits_mode = config.get('warehouse_limits_mode', {
            'positions_enabled': True,
            'ranks_enabled': False
        })
        
        embed = discord.Embed(
            title="📦 Режим лимитов склада",
            description="Настройка применения лимитов по должностям и/или званиям",
            color=discord.Color.gold()
        )
        
        pos_status = "🟢 Включен" if limits_mode.get('positions_enabled', True) else "🔴 Отключен"
        rank_status = "🟢 Включен" if limits_mode.get('ranks_enabled', False) else "🔴 Отключен"
        
        embed.add_field(
            name="📤 Канал отправки заявок:",
            value=pos_status,
            inline=True
        )
        
        embed.add_field(
            name="📤 Канал отправки заявок:",
            value=rank_status,
            inline=True
        )
        
        if not limits_mode.get('positions_enabled', True) and not limits_mode.get('ranks_enabled', False):
            embed.add_field(
                name="⚠️ Внимание:",
                value="Все лимиты отключены! Пользователи смогут запрашивать неограниченное количество предметов.",
                inline=False
            )
        
        view = WarehouseLimitsModeButtonsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class WarehouseLimitsModeButtonsView(discord.ui.View):
    """Кнопки для настройки режима лимитов"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="💼 Должности", style=discord.ButtonStyle.green)
    async def toggle_positions(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        limits_mode = config.get('warehouse_limits_mode', {
            'positions_enabled': True,
            'ranks_enabled': False
        })
        
        limits_mode['positions_enabled'] = not limits_mode.get('positions_enabled', True)
        config['warehouse_limits_mode'] = limits_mode
        save_config(config)
        
        status = "включены" if limits_mode['positions_enabled'] else "отключены"
        await interaction.response.send_message(
            f" Лимиты по должностям {status}", ephemeral=True
        )
    
    @discord.ui.button(label="🎖️ Звания", style=discord.ButtonStyle.secondary)
    async def toggle_ranks(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        limits_mode = config.get('warehouse_limits_mode', {
            'positions_enabled': True,
            'ranks_enabled': False
        })
        
        limits_mode['ranks_enabled'] = not limits_mode.get('ranks_enabled', False)
        config['warehouse_limits_mode'] = limits_mode
        save_config(config)
        
        status = "включены" if limits_mode['ranks_enabled'] else "отключены"
        await interaction.response.send_message(
            f" Лимиты по званиям {status}", ephemeral=True
        )


class WarehousePositionLimitsView(discord.ui.View):
    """Настройка лимитов по должностям"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Показать настройки лимитов по должностям"""
        config = load_config()
        position_limits = config.get('warehouse_limits_positions', {})
        
        embed = discord.Embed(
            title="📦 Настройка каналов склада",
            description="Настройка лимитов складского имущества для должностей",
            color=discord.Color.blue()
        )
        
        if position_limits:
            for position, limits in position_limits.items():
                weapon_limit = limits.get('оружие', 3)
                armor_limit = limits.get('бронежилеты', 10)
                medkit_limit = limits.get('аптечки', 20)
                
                embed.add_field(
                    name=f"👤 {position}",
                    value=f"🔫 Оружие: {weapon_limit}\n🛡️ Броня: {armor_limit}\n💊 Аптечки: {medkit_limit}",
                    inline=True
                )
        else:
            embed.add_field(
                name="ℹ️ Информация",
                value="Лимиты по должностям не настроены.\nИспользуются базовые лимиты для всех.",
                inline=False
            )
        
        view = WarehousePositionLimitsButtonsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class WarehousePositionLimitsButtonsView(discord.ui.View):
    """Кнопки для управления лимитами должностей"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="➕ Добавить должность", style=discord.ButtonStyle.green)
    async def add_position(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WarehouseAddPositionModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📊 Канал аудита", style=discord.ButtonStyle.secondary)
    async def edit_position(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        positions = list(config.get('warehouse_limits_positions', {}).keys())
        
        if not positions:
            await interaction.response.send_message(
                " Нет настроенных должностей для редактирования.", ephemeral=True
            )
            return
        
        view = WarehouseSelectPositionView(positions, "edit")
        await interaction.response.send_message(
            "Выберите должность для редактирования:", view=view, ephemeral=True
        )
    
    @discord.ui.button(label="🗑️ Удалить должность", style=discord.ButtonStyle.red)
    async def remove_position(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        positions = list(config.get('warehouse_limits_positions', {}).keys())
        
        if not positions:
            await interaction.response.send_message(
                " Нет настроенных должностей для удаления.", ephemeral=True
            )
            return
        
        view = WarehouseSelectPositionView(positions, "delete")
        await interaction.response.send_message(
            "Выберите должность для удаления:", view=view, ephemeral=True
        )


class WarehouseAddPositionModal(discord.ui.Modal):
    """Модальное окно для добавления должности"""
    
    def __init__(self):
        super().__init__(title="➕ Добавление должности")
        
        self.position_input = discord.ui.TextInput(
            label="Название должности",
            placeholder="Например: Оперативник ССО",
            max_length=100,
            required=True
        )
        self.add_item(self.position_input)
        
        self.weapon_input = discord.ui.TextInput(
            label="Лимит оружия",
            placeholder="3",
            default="3",
            max_length=3,
            required=True
        )
        self.add_item(self.weapon_input)
        
        self.armor_input = discord.ui.TextInput(
            label="Лимит бронежилетов",
            placeholder="10",
            default="10",
            max_length=3,
            required=True
        )
        self.add_item(self.armor_input)
        
        self.medkit_input = discord.ui.TextInput(
            label="Лимит аптечек",
            placeholder="20",
            default="20",
            max_length=3,
            required=True
        )
        self.add_item(self.medkit_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            position = self.position_input.value.strip()
            weapon_limit = int(self.weapon_input.value.strip())
            armor_limit = int(self.armor_input.value.strip())
            medkit_limit = int(self.medkit_input.value.strip())
            
            config = load_config()
            if 'warehouse_limits_positions' not in config:
                config['warehouse_limits_positions'] = {}
            
            config['warehouse_limits_positions'][position] = {
                'оружие': weapon_limit,
                'бронежилеты': armor_limit,
                'аптечки': medkit_limit,
                'обезболивающее': 8,
                'дефибрилляторы': 4,
                'weapon_restrictions': []
            }
            
            save_config(config)
            
            await interaction.response.send_message(
                f"✅ Лимиты для должности **{position}** добавлены:\n"
                f"🔫 Оружие: {weapon_limit}\n"
                f"🛡️ Броня: {armor_limit}\n"
                f"💊 Аптечки: {medkit_limit}",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Лимиты должны быть числами!", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка: {str(e)}", ephemeral=True
            )


class WarehouseSelectPositionView(discord.ui.View):
    """View для выбора должности"""
    
    def __init__(self, positions: List[str], action: str):
        super().__init__(timeout=300)
        self.positions = positions
        self.action = action
        
        # Добавляем селект с должностями
        self.add_item(WarehousePositionSelect(positions, action))


class WarehousePositionSelect(discord.ui.Select):
    """Селект для выбора должности"""
    
    def __init__(self, positions: List[str], action: str):
        self.action = action
        
        options = []
        for position in positions[:25]:  # Discord лимит 25 опций
            options.append(discord.SelectOption(
                label=position,
                value=position
            ))
        
        super().__init__(
            placeholder="Выберите должность...",
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_position = self.values[0]
        
        if self.action == "edit":
            modal = WarehouseEditPositionModal(selected_position)
            await interaction.response.send_modal(modal)
        elif self.action == "delete":
            config = load_config()
            del config['warehouse_limits_positions'][selected_position]
            save_config(config)
            
            await interaction.response.send_message(
                f"✅ Лимиты для должности **{selected_position}** удалены.",
                ephemeral=True
            )


class WarehouseEditPositionModal(discord.ui.Modal):
    """Модальное окно для редактирования должности"""
    
    def __init__(self, position_name: str):
        super().__init__(title=f"📝 Редактирование: {position_name[:30]}")
        self.position_name = position_name
        
        config = load_config()
        current_limits = config.get('warehouse_limits_positions', {}).get(position_name, {})
        
        self.weapon_input = discord.ui.TextInput(
            label="Лимит оружия",
            default=str(current_limits.get('оружие', 3)),
            max_length=3,
            required=True
        )
        self.add_item(self.weapon_input)
        
        self.armor_input = discord.ui.TextInput(
            label="Лимит бронежилетов",
            default=str(current_limits.get('бронежилеты', 10)),
            max_length=3,
            required=True
        )
        self.add_item(self.armor_input)
        
        self.medkit_input = discord.ui.TextInput(
            label="Лимит аптечек",
            default=str(current_limits.get('аптечки', 20)),
            max_length=3,
            required=True
        )
        self.add_item(self.medkit_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            weapon_limit = int(self.weapon_input.value.strip())
            armor_limit = int(self.armor_input.value.strip())
            medkit_limit = int(self.medkit_input.value.strip())
            
            config = load_config()
            if 'warehouse_limits_positions' not in config:
                config['warehouse_limits_positions'] = {}
            
            # Сохраняем существующие ограничения оружия
            current_limits = config['warehouse_limits_positions'].get(self.position_name, {})
            weapon_restrictions = current_limits.get('weapon_restrictions', [])
            
            config['warehouse_limits_positions'][self.position_name] = {
                'оружие': weapon_limit,
                'бронежилеты': armor_limit,
                'аптечки': medkit_limit,
                'обезболивающее': current_limits.get('обезболивающее', 8),
                'дефибрилляторы': current_limits.get('дефибрилляторы', 4),
                'weapon_restrictions': weapon_restrictions
            }
            
            save_config(config)
            
            await interaction.response.send_message(
                f"✅ Лимиты для должности **{self.position_name}** обновлены:\n"
                f" Оружие: {weapon_limit}\n"
                f" Броня: {armor_limit}\n"
                f" Аптечки: {medkit_limit}",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                " Лимиты должны быть числами!", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f" Ошибка: {str(e)}", ephemeral=True
            )


class WarehouseRankLimitsView(discord.ui.View):
    """Настройка лимитов по званиям"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Показать настройки лимитов по званиям"""
        config = load_config()
        rank_limits = config.get('warehouse_limits_ranks', {})
        
        embed = discord.Embed(
            title="📦 Настройка каналов склада",
            description="Настройка лимитов складского имущества для званий",
            color=discord.Color.purple()
        )
        
        if rank_limits:
            for rank, limits in rank_limits.items():
                weapon_limit = limits.get('оружие', 3)
                armor_limit = limits.get('бронежилеты', 10)
                medkit_limit = limits.get('аптечки', 20)
                
                embed.add_field(
                    name=f"🎖️ {rank}",
                    value=f"🔫 Оружие: {weapon_limit}\n🛡️ Броня: {armor_limit}\n💊 Аптечки: {medkit_limit}",
                    inline=True
                )
        else:
            embed.add_field(
                name="ℹ️ Информация",
                value="Лимиты по званиям не настроены.\nИспользуются базовые лимиты для всех.",
                inline=False
            )
        
        view = WarehouseRankLimitsButtonsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class WarehouseRankLimitsButtonsView(discord.ui.View):
    """Кнопки для управления лимитами званий"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="➕ Добавить звание", style=discord.ButtonStyle.green)
    async def add_rank(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WarehouseAddRankModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📊 Канал аудита", style=discord.ButtonStyle.secondary)
    async def edit_rank(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        ranks = list(config.get('warehouse_limits_ranks', {}).keys())
        
        if not ranks:
            await interaction.response.send_message(
                " Нет настроенных званий для редактирования.", ephemeral=True
            )
            return
        
        view = WarehouseSelectRankView(ranks, "edit")
        await interaction.response.send_message(
            "Выберите звание для редактирования:", view=view, ephemeral=True
        )
    
    @discord.ui.button(label="🗑️ Удалить звание", style=discord.ButtonStyle.red)
    async def remove_rank(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        ranks = list(config.get('warehouse_limits_ranks', {}).keys())
        
        if not ranks:
            await interaction.response.send_message(
                " Нет настроенных званий для удаления.", ephemeral=True
            )
            return
        
        view = WarehouseSelectRankView(ranks, "delete")
        await interaction.response.send_message(
            "Выберите звание для удаления:", view=view, ephemeral=True
        )


class WarehouseAddRankModal(discord.ui.Modal):
    """Модальное окно для добавления звания"""
    
    def __init__(self):
        super().__init__(title="➕ Добавление звания")
        
        self.rank_input = discord.ui.TextInput(
            label="Название звания",
            placeholder="Например: Майор",
            max_length=100,
            required=True
        )
        self.add_item(self.rank_input)
        
        self.weapon_input = discord.ui.TextInput(
            label="Лимит оружия",
            placeholder="3",
            default="3",
            max_length=3,
            required=True
        )
        self.add_item(self.weapon_input)
        
        self.armor_input = discord.ui.TextInput(
            label="Лимит бронежилетов",
            placeholder="10",
            default="10",
            max_length=3,
            required=True
        )
        self.add_item(self.armor_input)
        
        self.medkit_input = discord.ui.TextInput(
            label="Лимит аптечек",
            placeholder="20",
            default="20",
            max_length=3,
            required=True
        )
        self.add_item(self.medkit_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            rank = self.rank_input.value.strip()
            weapon_limit = int(self.weapon_input.value.strip())
            armor_limit = int(self.armor_input.value.strip())
            medkit_limit = int(self.medkit_input.value.strip())
            
            config = load_config()
            if 'warehouse_limits_ranks' not in config:
                config['warehouse_limits_ranks'] = {}
            
            config['warehouse_limits_ranks'][rank] = {
                'оружие': weapon_limit,
                'бронежилеты': armor_limit,
                'аптечки': medkit_limit,
                'обезболивающее': 8,
                'дефибрилляторы': 4,
                'weapon_restrictions': []
            }
            
            save_config(config)
            
            await interaction.response.send_message(
                f"✅ Лимиты для звания **{rank}** добавлены:\n"
                f" Оружие: {weapon_limit}\n"
                f" Броня: {armor_limit}\n"
                f" Аптечки: {medkit_limit}",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                " Лимиты должны быть числами!", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f" Ошибка: {str(e)}", ephemeral=True
            )


class WarehouseSelectRankView(discord.ui.View):
    """View для выбора звания"""
    
    def __init__(self, ranks: List[str], action: str):
        super().__init__(timeout=300)
        self.ranks = ranks
        self.action = action
        
        # Добавляем селект со званиями
        self.add_item(WarehouseRankSelect(ranks, action))


class WarehouseRankSelect(discord.ui.Select):
    """Селект для выбора звания"""
    
    def __init__(self, ranks: List[str], action: str):
        self.action = action
        
        options = []
        for rank in ranks[:25]:  # Discord лимит 25 опций
            options.append(discord.SelectOption(
                label=rank,
                value=rank
            ))
        
        super().__init__(
            placeholder="Выберите звание...",
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_rank = self.values[0]
        
        if self.action == "edit":
            modal = WarehouseEditRankModal(selected_rank)
            await interaction.response.send_modal(modal)
        elif self.action == "delete":
            config = load_config()
            del config['warehouse_limits_ranks'][selected_rank]
            save_config(config)
            
            await interaction.response.send_message(
                f"✅ Лимиты для звания **{selected_rank}** удалены.",
                ephemeral=True
            )


class WarehouseEditRankModal(discord.ui.Modal):
    """Модальное окно для редактирования звания"""
    
    def __init__(self, rank_name: str):
        super().__init__(title=f"📝 Редактирование: {rank_name[:30]}")
        self.rank_name = rank_name
        
        config = load_config()
        current_limits = config.get('warehouse_limits_ranks', {}).get(rank_name, {})
        
        self.weapon_input = discord.ui.TextInput(
            label="Лимит оружия",
            default=str(current_limits.get('оружие', 3)),
            max_length=3,
            required=True
        )
        self.add_item(self.weapon_input)
        
        self.armor_input = discord.ui.TextInput(
            label="Лимит бронежилетов",
            default=str(current_limits.get('бронежилеты', 10)),
            max_length=3,
            required=True
        )
        self.add_item(self.armor_input)
        
        self.medkit_input = discord.ui.TextInput(
            label="Лимит аптечек",
            default=str(current_limits.get('аптечки', 20)),
            max_length=3,
            required=True
        )
        self.add_item(self.medkit_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            weapon_limit = int(self.weapon_input.value.strip())
            armor_limit = int(self.armor_input.value.strip())
            medkit_limit = int(self.medkit_input.value.strip())
            
            config = load_config()
            if 'warehouse_limits_ranks' not in config:
                config['warehouse_limits_ranks'] = {}
            
            # Сохраняем существующие ограничения оружия
            current_limits = config['warehouse_limits_ranks'].get(self.rank_name, {})
            weapon_restrictions = current_limits.get('weapon_restrictions', [])
            
            config['warehouse_limits_ranks'][self.rank_name] = {
                'оружие': weapon_limit,
                'бронежилеты': armor_limit,
                'аптечки': medkit_limit,
                'обезболивающее': current_limits.get('обезболивающее', 8),
                'дефибрилляторы': current_limits.get('дефибрилляторы', 4),
                'weapon_restrictions': weapon_restrictions
            }
            
            save_config(config)
            
            await interaction.response.send_message(
                f"✅ Лимиты для звания **{self.rank_name}** обновлены:\n"
                f" Оружие: {weapon_limit}\n"
                f" Броня: {armor_limit}\n"
                f" Аптечки: {medkit_limit}",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                " Лимиты должны быть числами!", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f" Ошибка: {str(e)}", ephemeral=True
            )


class WarehouseAuditCuratorsModal(discord.ui.Modal):
    """Модальное окно для настройки кураторов аудита склада"""
    
    def __init__(self):
        super().__init__(title="👑 Настройка кураторов аудита")
        
        # Загружаем текущие настройки
        config = load_config()
        current_curators = config.get('warehouse_audit_curators', [])
        current_text = ", ".join(str(c) for c in current_curators) if current_curators else ""
        
        self.curators_input = discord.ui.TextInput(
            label="Кураторы Государственных Организаций",
            placeholder="@пользователь1, @роль1, ID1, @пользователь2, ID2...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False,
            default=current_text
        )
        self.add_item(self.curators_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            config = load_config()
            curators_text = self.curators_input.value.strip()
            
            if not curators_text:
                # Очищаем кураторов
                config['warehouse_audit_curators'] = []
                save_config(config)
                
                await interaction.followup.send(
                    "✅ Кураторы аудита склада очищены!", ephemeral=True
                )
                return
            
            # Парсим кураторов
            curators = []
            parts = [part.strip() for part in curators_text.split(',')]
            
            for part in parts:
                if not part:
                    continue
                
                # Проверяем различные форматы
                if part.startswith('<@&') and part.endswith('>'):
                    # Роль
                    role_id = part[3:-1]
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        curators.append(part)
                    else:
                        await interaction.followup.send(
                            f"❌ Роль {part} не найдена!", ephemeral=True
                        )
                        return
                        
                elif part.startswith('<@') and part.endswith('>'):
                    # Пользователь (упоминание)
                    user_id = part[2:-1]
                    if user_id.startswith('!'):
                        user_id = user_id[1:]
                    
                    try:
                        user = await interaction.guild.fetch_member(int(user_id))
                        curators.append(user_id)
                    except (discord.NotFound, discord.HTTPException):
                        await interaction.followup.send(
                            f"❌ Пользователь {part} не найден на сервере!", ephemeral=True
                        )
                        return
                        
                elif part.isdigit():
                    # ID пользователя или роли
                    try:
                        # Проверяем как пользователя
                        user = await interaction.guild.fetch_member(int(part))
                        curators.append(part)
                    except (discord.NotFound, discord.HTTPException):
                        # Проверяем как роль
                        role = interaction.guild.get_role(int(part))
                        if role:
                            curators.append(f"<@&{part}>")
                        else:
                            await interaction.followup.send(
                                f"❌ ID {part} не соответствует пользователю или роли на сервере!", 
                                ephemeral=True
                            )
                            return
                else:
                    # Обычный текст - добавляем как есть
                    curators.append(part)
            
            # Сохраняем настройки
            config['warehouse_audit_curators'] = curators
            save_config(config)
            
            # Формируем сообщение о результате
            result_text = []
            for curator in curators:
                if curator.isdigit():
                    result_text.append(f"<@{curator}>")
                else:
                    result_text.append(curator)
            
            await interaction.followup.send(
                f"✅ Кураторы аудита склада настроены:\n{', '.join(result_text[:5])}"
                + (f"\n и еще {len(result_text) - 5}" if len(result_text) > 5 else ""),
                ephemeral=True
            )
            
        except Exception as e:
            logger.warning("Ошибка при настройке кураторов аудита: %s", e)
            await interaction.followup.send(
                "❌ Произошла ошибка при сохранении настроек!", ephemeral=True
            )