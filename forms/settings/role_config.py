"""
Role configuration forms and views
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal, RoleParser


class RolesConfigView(BaseSettingsView):
    """View for role configuration"""
    
    @discord.ui.button(label="🪖 Роли военнослужащих", style=discord.ButtonStyle.green, custom_id="set_military_roles")
    async def set_military_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SetMultipleRolesModal("military_roles", "🪖 Настройка ролей военнослужащих", "Укажите роли для военнослужащих (через запятую)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👤 Роли гражданских", style=discord.ButtonStyle.secondary, custom_id="set_civilian_roles")
    async def set_civilian_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SetMultipleRolesModal("civilian_roles", "👤 Настройка ролей гражданских", "Укажите роли для гражданских (через запятую)")
        await interaction.response.send_mal(modal)
    
    @discord.ui.button(label="📢 Настроить ping-роли", style=discord.ButtonStyle.primary, custom_id="configure_ping_roles")
    async def configure_ping_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .channels import RolePingConfigView
        view = RolePingConfigView()
        await view.show_ping_config(interaction)


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
            save_config(config)            # Create user-friendly messages
            roles_names = {
                "military_roles": "роли военнослужащих",
                "civilian_roles": "роли гражданских",
                "military_role_assignment_ping_roles": "пинг-роли для военных заявок",
                "civilian_role_assignment_ping_roles": "пинг-роли для гражданских заявок"
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
