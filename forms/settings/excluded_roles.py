"""
Excluded roles configuration forms and views
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal, RoleParser, SectionSettingsView


class ExcludedRolesView(SectionSettingsView):
    """View for managing excluded roles"""
    
    def __init__(self):
        super().__init__(title="🛡️ Управление ролями-исключениями", description="Роли, которые не будут сниматься при одобрении рапорта на увольнение")
    
    @discord.ui.button(label="➕ Добавить роли", style=discord.ButtonStyle.green)
    async def add_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddExcludedRolesModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Удалить роли", style=discord.ButtonStyle.red)
    async def remove_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        excluded_roles_ids = config.get('excluded_roles', [])
        
        if not excluded_roles_ids:
            await self.send_error_message(
                interaction,
                "Нет ролей для удаления",
                "Нет настроенных ролей-исключений для удаления."
            )
            return
        
        modal = RemoveExcludedRolesModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🗑️ Очистить все", style=discord.ButtonStyle.danger)
    async def clear_all_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        config['excluded_roles'] = []
        save_config(config)
        
        await self.send_success_message(
            interaction,
            "Список очищен",
            "Все роли-исключения были удалены. Теперь при увольнении будут сниматься все роли кроме @everyone."
        )


class AddExcludedRolesModal(BaseSettingsModal):
    """Modal for adding excluded roles"""
    
    def __init__(self):
        super().__init__(title="Добавить роли-исключения")
        
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
            roles_text = self.roles_input.value.strip()
            roles = RoleParser.parse_multiple_roles(roles_text, interaction.guild)
            
            if not roles:
                await self.send_error_message(
                    interaction,
                    "Роли не найдены",
                    f"Не удалось найти роли по запросу: `{roles_text}`\n"
                    "Убедитесь, что вы указали правильные упоминания, ID или названия ролей."
                )
                return
            
            # Load current config and add new roles
            config = load_config()
            excluded_roles = set(config.get('excluded_roles', []))
            
            added_roles = []
            for role in roles:
                if role.id not in excluded_roles:
                    excluded_roles.add(role.id)
                    added_roles.append(role.mention)
            
            if not added_roles:
                await self.send_error_message(
                    interaction,
                    "Роли уже добавлены",
                    "Все указанные роли уже находятся в списке исключений."
                )
                return
            
            # Save updated config
            config['excluded_roles'] = list(excluded_roles)
            save_config(config)
            
            await self.send_success_message(
                interaction,
                "Роли добавлены",
                f"Добавлены роли-исключения:\n{chr(10).join(added_roles)}\n\n"
                "Эти роли не будут сниматься при одобрении рапорта на увольнение."
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при добавлении ролей: {str(e)}"
            )


class RemoveExcludedRolesModal(BaseSettingsModal):
    """Modal for removing excluded roles"""
    
    def __init__(self):
        super().__init__(title="Удалить роли-исключения")
        
        self.roles_input = ui.TextInput(
            label="Роли для удаления",
            placeholder="@Роль1, @Роль2, ID1, ID2 или названия ролей через запятую",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=1000,
            required=True
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            roles_text = self.roles_input.value.strip()
            roles = RoleParser.parse_multiple_roles(roles_text, interaction.guild)
            
            if not roles:
                await self.send_error_message(
                    interaction,
                    "Роли не найдены",
                    f"Не удалось найти роли по запросу: `{roles_text}`"
                )
                return
            
            # Load current config and remove roles
            config = load_config()
            excluded_roles = set(config.get('excluded_roles', []))
            
            removed_roles = []
            for role in roles:
                if role.id in excluded_roles:
                    excluded_roles.remove(role.id)
                    removed_roles.append(role.mention)
            
            if not removed_roles:
                await self.send_error_message(
                    interaction,
                    "Роли не найдены в списке",
                    "Указанные роли не находятся в списке исключений."
                )
                return
            
            # Save updated config
            config['excluded_roles'] = list(excluded_roles)
            save_config(config)
            
            await self.send_success_message(
                interaction,
                "Роли удалены",
                f"Удалены роли-исключения:\n{chr(10).join(removed_roles)}\n\n"
                "Теперь эти роли будут сниматься при одобрении рапорта на увольнение."
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при удалении ролей: {str(e)}"
            )