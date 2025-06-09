"""
Role configuration forms and views
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal, RoleParser


class RolesConfigView(BaseSettingsView):
    """View for role configuration"""
    
    @discord.ui.button(label="🪖 Роль военнослужащего", style=discord.ButtonStyle.green, custom_id="set_military_role")
    async def set_military_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SetRoleModal("military_role", "🪖 Настройка роли военнослужащего", "Укажите роль для военнослужащих")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👤 Роль гражданского", style=discord.ButtonStyle.secondary, custom_id="set_civilian_role")
    async def set_civilian_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SetRoleModal("civilian_role", "👤 Настройка роли гражданского", "Укажите роль для гражданских")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⚔️ Дополнительные военные роли", style=discord.ButtonStyle.primary, custom_id="set_additional_military_roles")
    async def set_additional_military_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SetMultipleRolesModal("additional_military_roles", "⚔️ Дополнительные военные роли", "Укажите дополнительные роли для военнослужащих (через запятую)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📢 Ping-роль для заявок", style=discord.ButtonStyle.primary, custom_id="set_ping_role")
    async def set_ping_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SetRoleModal("role_assignment_ping_role", "📢 Ping-роль для заявок", "Укажите роль для уведомлений о новых заявках")
        await interaction.response.send_modal(modal)


class SetRoleModal(BaseSettingsModal):
    """Modal for setting a single role"""
    
    def __init__(self, config_key: str, title: str, description: str):
        super().__init__(title=title)
        self.config_key = config_key
        
        self.role_input = ui.TextInput(
            label="Роль",
            placeholder="@Роль, ID роли или название роли",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.role_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            role = RoleParser.parse_role_input(self.role_input.value.strip(), interaction.guild)
            
            if not role:
                await self.send_error_message(
                    interaction,
                    "Роль не найдена",
                    f"Не удалось найти роль: `{self.role_input.value}`\n"
                    "Убедитесь, что вы указали правильное упоминание, ID или название роли."
                )
                return
            
            # Save to config
            config = load_config()
            config[self.config_key] = role.id
            save_config(config)
            
            # Create user-friendly messages
            role_names = {
                "military_role": "военнослужащего",
                "civilian_role": "гражданского",
                "role_assignment_ping_role": "для уведомлений о заявках"
            }
            
            role_name = role_names.get(self.config_key, self.config_key)
            
            await self.send_success_message(
                interaction,
                "Роль настроена",
                f"Роль {role_name} успешно настроена на {role.mention}!"
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке роли: {str(e)}"
            )


class SetMultipleRolesModal(BaseSettingsModal):
    """Modal for setting multiple roles"""
    
    def __init__(self, config_key: str, title: str, description: str):
        super().__init__(title=title)
        self.config_key = config_key
        
        self.roles_input = ui.TextInput(
            label="Роли",
            placeholder="@Роль1, @Роль2, ID1, ID2 или названия ролей через запятую",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=1000,
            required=True
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            roles = RoleParser.parse_multiple_roles(self.roles_input.value.strip(), interaction.guild)
            
            if not roles:
                await self.send_error_message(
                    interaction,
                    "Роли не найдены",
                    f"Не удалось найти роли: `{self.roles_input.value}`\n"
                    "Убедитесь, что вы указали правильные упоминания, ID или названия ролей."
                )
                return
            
            # Save to config
            config = load_config()
            config[self.config_key] = [role.id for role in roles]
            save_config(config)
            
            # Create user-friendly messages
            roles_names = {
                "additional_military_roles": "дополнительные военные роли"
            }
            
            roles_name = roles_names.get(self.config_key, self.config_key)
            roles_mentions = [role.mention for role in roles]
            
            await self.send_success_message(
                interaction,
                "Роли настроены",
                f"Успешно настроены {roles_name}:\n{chr(10).join(roles_mentions)}"
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке ролей: {str(e)}"
            )
