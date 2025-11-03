"""
Detailed Position Management
Детальное управление отдельной должностью
"""

import discord
from discord import ui
from typing import Dict, Any
from utils.database_manager import position_service
from .ui_components import create_position_embed

class PositionDetailedView(ui.View):
    """Detailed management for individual position"""

    def __init__(self, position_id: int, position_data: Dict[str, Any],
                 subdivision_id: int, subdivision_data: Dict[str, Any]):
        super().__init__(timeout=300)
        self.position_id = position_id
        self.position_data = position_data
        self.subdivision_id = subdivision_id
        self.subdivision_data = subdivision_data

    @ui.button(label="Назначить роль", style=discord.ButtonStyle.primary, emoji="🎭")
    async def assign_role(self, interaction: discord.Interaction, button: ui.Button):
        """Assign Discord role"""
        modal = AssignRoleModal(self.position_id, self.position_data)
        await interaction.response.send_modal(modal)

    @ui.button(label="Удалить роль", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def remove_role(self, interaction: discord.Interaction, button: ui.Button):
        """Remove Discord role"""
        success, message = position_service.update_position_role(
            self.position_id, None, interaction.guild
        )

        color = discord.Color.green() if success else discord.Color.red()
        emoji = "✅" if success else "❌"

        embed = discord.Embed(
            title=f"{emoji} {'Роль удалена' if success else 'Ошибка'}",
            description=message,
            color=color
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="Редактировать", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def edit_position(self, interaction: discord.Interaction, button: ui.Button):
        """Edit position details"""
        modal = EditPositionModal(self.position_id, self.position_data)
        await interaction.response.send_modal(modal)

    @ui.button(label="Удалить должность", style=discord.ButtonStyle.danger, emoji="❌")
    async def delete_position(self, interaction: discord.Interaction, button: ui.Button):
        """Delete position"""
        modal = DeletePositionModal(self.position_id, self.position_data)
        await interaction.response.send_modal(modal)

    @ui.button(label="Назад", style=discord.ButtonStyle.secondary, emoji="◀️")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        """Go back to position list"""
        from .management import PositionManagementView
        view = PositionManagementView(self.subdivision_id, self.subdivision_data)
        await view.update_position_options(interaction.guild)
        embed = await create_position_list_embed(self.subdivision_data)
        await interaction.response.edit_message(embed=embed, view=view)

class AssignRoleModal(ui.Modal):
    """Assign Discord role modal"""

    def __init__(self, position_id: int, position_data: Dict[str, Any]):
        super().__init__(title=f"Назначить роль: {position_data.get('name')}")
        self.position_id = position_id

        self.role_input = ui.TextInput(
            label="Discord роль",
            placeholder="ID роли или @роль...",
            required=True,
            max_length=50
        )

        self.add_item(self.role_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle role assignment"""
        role_input = self.role_input.value.strip()

        # Parse role ID from input
        try:
            role_id = int(role_input)
        except ValueError:
            # Try to find role by mention
            if role_input.startswith('<@&') and role_input.endswith('>'):
                role_id = int(role_input[3:-1])
            else:
                await interaction.response.send_message("❌ Не удалось определить ID роли.", ephemeral=True)
                return

        success, message = position_service.update_position_role(
            self.position_id, role_id, interaction.guild
        )

        color = discord.Color.green() if success else discord.Color.red()
        emoji = "✅" if success else "❌"

        embed = discord.Embed(
            title=f"{emoji} {'Роль назначена' if success else 'Ошибка'}",
            description=message,
            color=color
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

class EditPositionModal(ui.Modal):
    """Edit position details modal"""

    def __init__(self, position_id: int, position_data: Dict[str, Any]):
        super().__init__(title=f"Редактировать: {position_data.get('name')}")
        self.position_id = position_id

        self.name_input = ui.TextInput(
            label="Новое название",
            placeholder="Введите новое название должности...",
            required=True,
            max_length=200,
            default=position_data.get('name', '')
        )

        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle position editing"""
        new_name = self.name_input.value.strip()

        success, message = position_service.update_position_name(self.position_id, new_name)

        color = discord.Color.green() if success else discord.Color.red()
        emoji = "✅" if success else "❌"

        embed = discord.Embed(
            title=f"{emoji} {'Название изменено' if success else 'Ошибка'}",
            description=message,
            color=color
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

class DeletePositionModal(ui.Modal):
    """Delete position confirmation modal"""

    def __init__(self, position_id: int, position_data: Dict[str, Any]):
        super().__init__(title=f"Удалить: {position_data.get('name')}")
        self.position_id = position_id

        self.confirmation = ui.TextInput(
            label="Подтверждение",
            placeholder="Введите 'УДАЛИТЬ' для подтверждения...",
            required=True,
            max_length=10
        )

        self.add_item(self.confirmation)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle position deletion"""
        if self.confirmation.value.upper() != "УДАЛИТЬ":
            await interaction.response.send_message("❌ Неверное подтверждение.", ephemeral=True)
            return

        success, message = position_service.remove_position(self.position_id, force=True)

        color = discord.Color.green() if success else discord.Color.red()
        emoji = "✅" if success else "❌"

        embed = discord.Embed(
            title=f"{emoji} {'Должность удалена' if success else 'Ошибка'}",
            description=message,
            color=color
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def create_position_list_embed(subdivision_data: Dict[str, Any]):
    """Import from management module"""
    from .management import create_position_list_embed
    return await create_position_list_embed(subdivision_data, 1)