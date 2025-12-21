"""
Main settings interface
"""
import discord
from discord import ui
from utils.config_manager import load_config
from .base import BaseSettingsView, ConfigDisplayHelper
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class MainSettingsSelect(ui.Select):
    """Main settings dropdown menu"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Настройка каналов",
                description="Настроить каналы для различных систем бота",
                emoji="📂",
                value="channels"
            ),
            discord.SelectOption(
                label="Настройки пингов",
                description="Настроить пинги для уведомлений по подразделениям",
                emoji="📢",
                value="ping_settings"
            ),
            discord.SelectOption(
                label="Управление подразделениями",
                description="Добавить, изменить или удалить подразделения",
                emoji="🏛️",
                value="departments_management"
            ),
            discord.SelectOption(
                label="Роли-исключения",
                description="Настроить роли, которые не снимаются при увольнении",
                emoji="🛡️",
                value="excluded_roles"
            ),
            discord.SelectOption(
                label="Роли званий",
                description="Настроить связывание званий с ролями на сервере",
                emoji="🎖️",
                value="rank_roles"
            ),
            discord.SelectOption(
                label="Роли должностей",
                description="Иерархическая настройка должностей по подразделениям",
                emoji="💼",
                value="position_roles"
            ),
            discord.SelectOption(
                label="Система поставок",
                description="Настроить управление военными объектами и поставками",
                emoji="🚚",
                value="supplies_settings"
            ),
            discord.SelectOption(
                label="Автозамена никнеймов",
                description="Настройка автоматической замены никнеймов при кадровых операциях",
                emoji="🏷️",
                value="nickname_settings"
            ),
            discord.SelectOption(
                label="Электронные заявки",
                description="Настройка системы электронных заявок на вступление/восстановление",
                emoji="📋",
                value="electronic_applications"
            ),
            discord.SelectOption(
                label="Настройки команд",
                description="Настройка доступности действий для различных команд",
                emoji="⚙️",
                value="commands_settings"
            )
        ]
        
        super().__init__(
            placeholder="Выберите категорию настроек...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="main_settings_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_option = self.values[0]
        
        if selected_option == "channels":
            await self.show_channels_menu(interaction)
        elif selected_option == "ping_settings":
            await self.show_ping_settings_menu(interaction)
        elif selected_option == "departments_management":
            await self.show_departments_management_menu(interaction)
        elif selected_option == "excluded_roles":
            await self.show_excluded_roles_config(interaction)
        elif selected_option == "rank_roles":
            await self.show_rank_roles_config(interaction)
        elif selected_option == "position_roles":
            await self.show_position_roles_config(interaction)
        elif selected_option == "warehouse_settings":
            await self.show_warehouse_settings_menu(interaction)
        elif selected_option == "supplies_settings":
            await self.show_supplies_settings_menu(interaction)
        elif selected_option == "electronic_applications":
            await self.show_electronic_applications_menu(interaction)
        elif selected_option == "commands_settings":
            await self.show_commands_settings_menu(interaction)
        elif selected_option == "nickname_settings":
            await self.show_nickname_settings_menu(interaction)
    
    async def show_channels_menu(self, interaction: discord.Interaction):
        """Show submenu for channel configuration"""
        from .channels import ChannelsConfigView
        
        embed = discord.Embed(
            title="📂 Настройка каналов",
            description="Выберите канал для настройки из списка ниже.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Доступные каналы:",
            value=(
                "• **Канал увольнений** - для рапортов на увольнение\n"
                "• **Канал аудита** - для кадрового аудита\n"
                "• **Канал чёрного списка** - для записей чёрного списка\n"
                "• **Канал получения ролей** - для выбора военной/гражданской роли\n"
                "• **Каналы отчётов на повышение** - для отчётов по подразделениям\n"
                "• **Канал отгулов** - для заявок на отгулы\n"
                "• **Сейф документов** - для заявок на безопасное хранение документов"
            ),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Инструкция:",
            value="1. Выберите тип канала из списка\n2. Укажите канал (ID, упоминание или название)\n3. Бот автоматически настроит канал и добавит кнопки",
            inline=False
        )
        
        view = ChannelsConfigView()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    async def show_ping_settings_menu(self, interaction: discord.Interaction):
        """Show modern ping settings configuration menu"""
        from .ping_settings_modern import show_ping_settings_overview
        
        await show_ping_settings_overview(interaction)
    
    async def show_excluded_roles_config(self, interaction: discord.Interaction):
        """Show interface for managing excluded roles"""
        from .excluded_roles import ExcludedRolesView
        
        config = load_config()
        excluded_roles_ids = config.get('excluded_roles', [])
        
        embed = discord.Embed(
            title="🛡️ Управление ролями-исключениями",
            description="Роли, которые не будут сниматься при одобрении рапорта на увольнение.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Show current excluded roles
        if excluded_roles_ids:
            excluded_roles = []
            for role_id in excluded_roles_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    excluded_roles.append(f"• {role.mention}")
                else:
                    excluded_roles.append(f"• ❌ Роль не найдена (ID: {role_id})")
            excluded_text = "\n".join(excluded_roles)
        else:
            excluded_text = "❌ Роли-исключения не настроены"
        
        embed.add_field(name="Текущие роли-исключения:", value=excluded_text, inline=False)
        
        embed.add_field(
            name="ℹ️ Инструкция:",
            value=(
                "• **Добавить роли** - добавить новые роли в список исключений\n"
                "• **Удалить роли** - убрать роли из списка исключений\n"
                "• **Очистить список** - удалить все роли-исключения"
            ),
            inline=False
        )        
        view = ExcludedRolesView()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def show_rank_roles_config(self, interaction: discord.Interaction):
        """Show interface for managing rank roles"""
        from .rank_roles import show_rank_roles_config
        await show_rank_roles_config(interaction)

    async def show_position_roles_config(self, interaction: discord.Interaction):
        """Show interface for managing position roles with hierarchical navigation"""
        try:
            from .positions import PositionNavigationView
            from .positions.navigation import create_main_navigation_embed

            view = PositionNavigationView()
            await view.update_subdivision_options(interaction.guild)
            embed = create_main_navigation_embed()

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.warning("Error in show_position_roles_config: %s", e)
            import traceback
            traceback.print_exc()
            try:
                await interaction.followup.send(f"❌ Ошибка открытия настроек должностей: {str(e)}", ephemeral=True)
            except Exception as e2:
                logger.warning("Failed to send error message: %s", e2)
    
    async def show_electronic_applications_menu(self, interaction: discord.Interaction):
        """Show electronic applications settings menu"""
        from .electronic_applications import show_electronic_applications_menu
        
        await show_electronic_applications_menu(interaction)

    async def show_warehouse_settings_menu(self, interaction: discord.Interaction):
        """Show warehouse settings configuration menu"""
        from .warehouse_settings import WarehouseSettingsView
        
        embed = discord.Embed(
            title="⚙️ Настройки склада",
            description="Управление системой запросов и выдачи складского имущества",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Доступные настройки:",
            value=(
                "• **📍 Каналы склада** - настройка каналов запросов и аудита\n"
                "• **⚙️ Режим лимитов** - переключение между лимитами по должностям/званиям\n"
                "• **📋 Управление лимитами** - настройка лимитов для должностей и званий\n"
                "• **⏰ Кулдаун запросов** - настройка времени между запросами"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📋 Доступные каналы:",
            value=(
                "Система склада позволяет пользователям запрашивать складское имущество "
                "с учетом их должности или звания. Модераторы могут одобрять или отклонять "
                "запросы, а все выдачи автоматически логируются в канал аудита."
            ),
            inline=False
        )
        
        view = WarehouseSettingsView()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def show_supplies_settings_menu(self, interaction: discord.Interaction):
        """Show supplies settings menu"""
        try:
            from .supplies import SuppliesSettingsView
            view = SuppliesSettingsView()
            embed = view.create_embed()
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.warning("Error in show_supplies_settings_menu: %s", e)
            import traceback
            traceback.print_exc()
            
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        f" Ошибка открытия настроек поставок: {str(e)}",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f" Ошибка открытия настроек поставок: {str(e)}",
                        ephemeral=True
                    )
            except:
                pass

    async def show_commands_settings_menu(self, interaction: discord.Interaction):
        """Show commands settings menu"""
        try:
            from .commands_settings import CommandsSettingsView
            view = CommandsSettingsView()
            
            embed = discord.Embed(
                title="⚙️ Настройки команд",
                description="Настройка доступности действий для различных команд бота.",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="📋 Доступные настройки:",
                value=(
                    "• **📋 Команда /аудит** - настроить доступные действия для аудита персонала\n"
                    "• **Больше команд будет добавлено позже**"
                ),
                inline=False
            )
            
            embed.add_field(
                name="ℹ️ Информация:",
                value=(
                    "Здесь можно включать и отключать отдельные действия для различных команд. "
                    "Это позволяет точно настроить функциональность бота под нужды сервера."
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.warning("Error in show_commands_settings_menu: %s", e)
            import traceback
            traceback.print_exc()
            
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        f" Ошибка открытия настроек команд: {str(e)}",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f" Ошибка открытия настроек команд: {str(e)}",
                        ephemeral=True
                    )
            except:
                pass

    async def show_departments_management_menu(self, interaction: discord.Interaction):
        """Show departments management interface"""
        from .departments_management import DepartmentsManagementView
        
        embed = discord.Embed(
            title="🏢 Управление подразделениями",
            description="Добавление, редактирование и удаление подразделений системы",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Доступные действия:",
            value=(
                "• **➕ Добавить подразделение** - создать новое подразделение\n"
                "• **✏️ Редактировать подразделение** - изменить существующее подразделение\n"
                "• ** Удалить подразделение** - удалить подразделение из системы\n"
                "• **📋 Список подразделений** - просмотр всех подразделений"
            ),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Информация:",
            value=(
                "Подразделения используются в системах заявок, уведомлений и каналов. "
                "При удалении подразделения все связанные настройки будут очищены. "
                "Изменения применяются ко всем формам и меню автоматически."
            ),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Инструкция:",
            value=(
                "• Базовые подразделения можно редактировать, но рекомендуется сохранять их\n"
                "• При удалении подразделения все связанные настройки будут удалены\n"
                "• Изменения вступают в силу немедленно"
            ),
            inline=False
        )
        
        view = DepartmentsManagementView()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    async def show_nickname_settings_menu(self, interaction: discord.Interaction):
        """Show nickname auto-replacement settings menu"""
        from .nickname_settings import show_nickname_settings_overview
        
        await show_nickname_settings_overview(interaction)
        

class SettingsView(BaseSettingsView):
    """Main settings view with persistent functionality"""
    
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
        self.add_item(MainSettingsSelect())
    
    async def on_timeout(self):
        # This won't be called for persistent views, but good to have
        for item in self.children:
            item.disabled = True


async def send_settings_message(interaction: discord.Interaction):
    """Send the main settings interface"""
    embed = discord.Embed(
        title="⚙️ Панель настроек бота",
        description="Добро пожаловать в панель управления настройками бота! Здесь вы можете настроить все основные параметры работы системы.",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(
        name="📋 Доступные категории:",
        value=(
            "• **📂 Настройка каналов** - настроить каналы для различных систем\n"
            "• **🛡️ Роли-исключения** - роли, не снимаемые при увольнении\n"
            "• **⚙️ Показать настройки** - просмотр текущих настроек"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📝 Доступные категории:",
        value="1. Выберите категорию из главного меню\n2. Используйте подменю для настройки конкретных параметров\n3. Бот автоматически сохранит изменения",
        inline=False
    )
    
    embed.set_footer(text="Доступно только администраторам")
    
    view = SettingsView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)