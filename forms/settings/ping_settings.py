"""
Ping settings configuration forms and views
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal, RoleParser


class PingSettingsView(BaseSettingsView):
    """View for managing ping settings"""
    
    @discord.ui.button(label="➕ Добавить настройку", style=discord.ButtonStyle.green)
    async def add_ping_setting(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddPingSettingModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Удалить настройку", style=discord.ButtonStyle.red)
    async def remove_ping_setting(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        ping_settings = config.get('ping_settings', {})
        
        if not ping_settings:
            await self.send_error_message(
                interaction,
                "Нет настроек для удаления",
                "Нет настроенных пингов для удаления."
            )
            return
        
        modal = RemovePingSettingModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🗑️ Очистить все", style=discord.ButtonStyle.danger)
    async def clear_all_pings(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        config['ping_settings'] = {}
        save_config(config)
        
        await self.send_success_message(
            interaction,
            "Настройки пингов очищены",
            "Все настройки пингов были удалены. Теперь при подаче рапортов уведомления отправляться не будут."
        )


class AddPingSettingModal(BaseSettingsModal):
    """Modal for adding ping settings"""
    
    def __init__(self):
        super().__init__(title="Добавить настройку пингов")
        
        self.department_role_input = ui.TextInput(
            label="Роль подразделения",
            placeholder="@Военная полиция, ID роли или название роли",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.department_role_input)
        
        self.ping_roles_input = ui.TextInput(
            label="Роли для пинга",
            placeholder="@Командир ВП, @Зам командира, ID1, ID2 через запятую",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=1000,
            required=True
        )
        self.add_item(self.ping_roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse department role
            department_role = RoleParser.parse_role_input(
                self.department_role_input.value.strip(), 
                interaction.guild
            )
            
            if not department_role:
                await self.send_error_message(
                    interaction,
                    "Роль подразделения не найдена",
                    f"Не удалось найти роль подразделения: `{self.department_role_input.value}`"
                )
                return
            
            # Parse ping roles
            ping_roles = RoleParser.parse_multiple_roles(
                self.ping_roles_input.value.strip(), 
                interaction.guild
            )
            
            if not ping_roles:
                await self.send_error_message(
                    interaction,
                    "Роли для пинга не найдены",
                    f"Не удалось найти роли для пинга: `{self.ping_roles_input.value}`"
                )
                return
            
            # Save to config
            config = load_config()
            ping_settings = config.get('ping_settings', {})
            ping_settings[str(department_role.id)] = [role.id for role in ping_roles]
            config['ping_settings'] = ping_settings
            save_config(config)
            
            ping_roles_mentions = [role.mention for role in ping_roles]
            await self.send_success_message(
                interaction,
                "Настройка пингов добавлена",
                f"Настройка успешно добавлена:\n"
                f"**Подразделение:** {department_role.mention}\n"
                f"**Роли для уведомлений:** {', '.join(ping_roles_mentions)}\n\n"
                f"Теперь при подаче рапорта на увольнение сотрудником {department_role.mention} "
                f"будут уведомлены указанные роли."
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при добавлении настройки: {str(e)}"
            )


class RemovePingSettingModal(BaseSettingsModal):
    """Modal for removing ping settings"""
    
    def __init__(self):
        super().__init__(title="Удалить настройку пингов")
        
        self.department_role_input = ui.TextInput(
            label="Роль подразделения",
            placeholder="@Военная полиция, ID роли или название роли",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.department_role_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse department role
            department_role = RoleParser.parse_role_input(
                self.department_role_input.value.strip(), 
                interaction.guild
            )
            
            if not department_role:
                await self.send_error_message(
                    interaction,
                    "Роль подразделения не найдена",
                    f"Не удалось найти роль подразделения: `{self.department_role_input.value}`"
                )
                return
            
            # Remove from config
            config = load_config()
            ping_settings = config.get('ping_settings', {})
            
            if str(department_role.id) not in ping_settings:
                await self.send_error_message(
                    interaction,
                    "Настройка не найдена",
                    f"Для роли {department_role.mention} не найдено настроек пингов."
                )
                return
            
            del ping_settings[str(department_role.id)]
            config['ping_settings'] = ping_settings
            save_config(config)
            
            await self.send_success_message(
                interaction,
                "Настройка пингов удалена",
                f"Настройка пингов для роли {department_role.mention} успешно удалена."
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при удалении настройки: {str(e)}"
            )
