"""
Commands settings configuration
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView
from utils.postgresql_pool import get_db_cursor


class CommandsBaseView(BaseSettingsView):
    """Base view for commands settings with display method"""
    
    async def display(self, interaction: discord.Interaction, embed=None):
        """Display the view with embed"""
        if embed is None:
            embed = discord.Embed(
                title="⚙️ Настройки команд",
                description="Настройка команд бота.",
                color=discord.Color.blue()
            )
        await interaction.response.edit_message(embed=embed, view=self)


class CommandsSettingsView(CommandsBaseView):
    """Main commands settings interface"""
    
    def __init__(self):
        super().__init__()
        self.add_item(CommandsSettingsSelect())


class CommandsSettingsSelect(ui.Select):
    """Commands settings dropdown menu"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Настройки команды /аудит",
                description="Настроить доступные действия для команды /аудит",
                emoji="📋",
                value="audit_command"
            )
        ]
        
        super().__init__(
            placeholder="Выберите команду для настройки...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="commands_settings_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_option = self.values[0]
        
        if selected_option == "audit_command":
            await self.show_audit_command_settings(interaction)
    
    async def show_audit_command_settings(self, interaction: discord.Interaction):
        """Show audit command settings"""
        await display_audit_command_settings(interaction)


class AuditCommandSettingsView(CommandsBaseView):
    """Audit command settings interface"""
    
    def __init__(self):
        super().__init__()
        self.actions_select = AuditActionsSelect()
        self.add_item(self.actions_select)
        self.add_item(BackToCommandsButton())
    
    async def setup_options(self):
        """Setup options for the actions select"""
        await self.actions_select.setup_options()
        # Update max_values after setting up options
        if len(self.actions_select.options) > 0:
            self.actions_select.max_values = min(len(self.actions_select.options), 10)


class AuditActionsSelect(ui.Select):
    """Select for enabling/disabling audit actions"""
    
    def __init__(self):
        super().__init__(
            placeholder="Выберите действия для изменения статуса...",
            min_values=1,
            max_values=10,  # Reasonable limit for multiple selection
            custom_id="audit_actions_select"
        )
    
    async def setup_options(self):
        """Setup options from PostgreSQL and current config"""
        try:
            # Get all actions from PostgreSQL
            all_actions = []
            with get_db_cursor() as cursor:
                cursor.execute("SELECT name FROM actions ORDER BY name")
                actions_result = cursor.fetchall()
                all_actions = [row['name'] for row in actions_result] if actions_result else []
            
            # Get current config
            config = load_config()
            disabled_audit_actions = config.get('disabled_audit_actions', [])
            
            # Create options
            options = []
            for action in all_actions:
                is_enabled = action not in disabled_audit_actions
                status_emoji = "✅" if is_enabled else "❌"
                
                options.append(discord.SelectOption(
                    label=f"{status_emoji} {action}",
                    description=f"Статус: {'Включено' if is_enabled else 'Отключено'}",
                    value=action,
                    emoji="🔄"
                ))
            
            # Ensure we have at least one option
            if not options:
                options.append(discord.SelectOption(
                    label="Нет доступных действий",
                    description="Действия не найдены в базе данных",
                    value="no_actions"
                ))
            
            # Discord limit: max 25 options
            self.options = options[:25]
            
            # Adjust max_values based on available options
            actual_max = min(len(self.options), 10)
            if hasattr(self, '_max_values'):
                self._max_values = actual_max
            else:
                # Create new select with correct max_values
                self.max_values = actual_max
            
        except Exception as e:
            print(f"Error setting up audit actions options: {e}")
            self.options = [discord.SelectOption(
                label="Ошибка загрузки",
                description="Не удалось загрузить действия из базы данных",
                value="error"
            )]
    
    async def callback(self, interaction: discord.Interaction):
        if "no_actions" in self.values or "error" in self.values:
            await interaction.response.send_message(
                "❌ Не удалось обработать выбор. Проверьте подключение к базе данных.",
                ephemeral=True
            )
            return
        
        try:
            config = load_config()
            disabled_audit_actions = set(config.get('disabled_audit_actions', []))
            
            # Toggle selected actions
            for action in self.values:
                if action in disabled_audit_actions:
                    disabled_audit_actions.remove(action)
                    status = "включено"
                else:
                    disabled_audit_actions.add(action)
                    status = "отключено"
            
            # Save updated config
            config['disabled_audit_actions'] = list(disabled_audit_actions)
            success = save_config(config)
            
            if success:
                # Create new view with updated options
                view = AuditCommandSettingsView()
                await view.setup_options()
                
                embed = discord.Embed(
                    title="✅ Настройки команды /аудит обновлены",
                    description=f"Изменен статус для {len(self.values)} действий.",
                    color=discord.Color.green()
                )
                
                # Show current status
                enabled_actions = []
                disabled_actions = []
                
                with get_db_cursor() as cursor:
                    cursor.execute("SELECT name FROM actions ORDER BY name")
                    all_actions = [row['name'] for row in cursor.fetchall()]
                
                for action in all_actions:
                    if action in disabled_audit_actions:
                        disabled_actions.append(action)
                    else:
                        enabled_actions.append(action)
                
                if enabled_actions:
                    embed.add_field(
                        name="✅ Включенные действия",
                        value="\n".join(f"• {action}" for action in enabled_actions[:10]),
                        inline=True
                    )
                
                if disabled_actions:
                    embed.add_field(
                        name="❌ Отключенные действия", 
                        value="\n".join(f"• {action}" for action in disabled_actions[:10]),
                        inline=True
                    )
                
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(
                    "❌ Ошибка при сохранении настроек.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"Error updating audit actions: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обновлении настроек.",
                ephemeral=True
            )


class BackToCommandsButton(ui.Button):
    """Button to go back to commands settings"""
    
    def __init__(self):
        super().__init__(
            label="Назад к настройкам команд",
            style=discord.ButtonStyle.secondary,
            emoji="↩️"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = CommandsSettingsView()
        embed = discord.Embed(
            title="⚙️ Настройки команд",
            description="Выберите команду для настройки из списка ниже.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)


async def display_audit_command_settings(interaction: discord.Interaction):
    """Display audit command settings with current status"""
    try:
        config = load_config()
        disabled_audit_actions = config.get('disabled_audit_actions', [])
        
        # Get all actions from PostgreSQL
        all_actions = []
        with get_db_cursor() as cursor:
            cursor.execute("SELECT name FROM actions ORDER BY name")
            actions_result = cursor.fetchall()
            all_actions = [row['name'] for row in actions_result] if actions_result else []
        
        embed = discord.Embed(
            title="📋 Настройки команды /аудит",
            description="Управление доступными действиями для команды /аудит.\n"
                       "Выберите действия ниже для переключения их статуса.",
            color=discord.Color.blue()
        )
        
        # Show current status
        enabled_actions = [action for action in all_actions if action not in disabled_audit_actions]
        disabled_actions = [action for action in all_actions if action in disabled_audit_actions]
        
        if enabled_actions:
            embed.add_field(
                name="✅ Включенные действия",
                value="\n".join(f"• {action}" for action in enabled_actions[:10]) + 
                     (f"\n... и ещё {len(enabled_actions) - 10}" if len(enabled_actions) > 10 else ""),
                inline=True
            )
        
        if disabled_actions:
            embed.add_field(
                name="❌ Отключенные действия",
                value="\n".join(f"• {action}" for action in disabled_actions[:10]) +
                     (f"\n... и ещё {len(disabled_actions) - 10}" if len(disabled_actions) > 10 else ""),
                inline=True
            )
        
        if not enabled_actions and not disabled_actions:
            embed.add_field(
                name="ℹ️ Статус",
                value="Действия не найдены в базе данных",
                inline=False
            )
        
        view = AuditCommandSettingsView()
        await view.setup_options()
        
        await view.display(interaction, embed)
        
    except Exception as e:
        print(f"Error displaying audit command settings: {e}")
        embed = discord.Embed(
            title="❌ Ошибка",
            description="Не удалось загрузить настройки команды /аудит.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed)

