"""
Detailed Position Management
Детальное управление отдельной должностью
"""

import discord
from discord import ui
from typing import Dict, Any
from utils.database_manager import position_service
from utils.postgresql_pool import get_db_cursor

class PositionDetailedView(ui.View):
    """Detailed management for individual position"""

    def __init__(self, position_id: int, position_data: Dict[str, Any],
                 subdivision_id: int, subdivision_data: Dict[str, Any]):
        super().__init__(timeout=300)
        self.position_id = position_id
        self.position_data = position_data
        self.subdivision_id = subdivision_id
        self.subdivision_data = subdivision_data

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
        embed = create_position_list_embed(self.subdivision_data)
        await interaction.response.edit_message(embed=embed, view=view)

class EditPositionModal(ui.Modal):
    """Edit position details modal"""

    def __init__(self, position_id: int, position_data: Dict[str, Any]):
        super().__init__(title=f"Редактировать: {position_data.get('name')}")
        self.position_id = position_id
        self.position_data = position_data

        self.name_input = ui.TextInput(
            label="Название должности",
            placeholder="Введите новое название должности...",
            required=True,
            max_length=200,
            default=position_data.get('name', '')
        )

        self.role_input = ui.TextInput(
            label="Discord роль (ID или упоминание)",
            placeholder="Введите ID роли или @роль (необязательно)",
            required=False,
            max_length=50,
            default=str(position_data.get('role_id', ''))
        )

        self.subdivision_input = ui.TextInput(
            label="Новое подразделение (аббревиатура)",
            placeholder="ссо, увп, ва и так далее",
            required=False,
            max_length=50
        )

        self.add_item(self.name_input)
        self.add_item(self.role_input)
        self.add_item(self.subdivision_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle submission"""
        position_name = self.name_input.value.strip()
        role_input = self.role_input.value.strip() if self.role_input.value else None
        subdivision_abbr = self.subdivision_input.value.strip().lower() if self.subdivision_input.value else None

        if not position_name:
            await interaction.response.send_message("❌ Название должности не может быть пустым.", ephemeral=True)
            return

        # Parse role ID from input
        role_id = None
        if role_input:
            try:
                # Try to extract role ID from mention or direct ID
                if role_input.startswith('<@&') and role_input.endswith('>'):
                    role_id = int(role_input[3:-1])
                elif role_input.isdigit():
                    role_id = int(role_input)
                else:
                    # Try to find role by name
                    role = discord.utils.get(interaction.guild.roles, name=role_input)
                    if role:
                        role_id = role.id
                    else:
                        await interaction.response.send_message(
                            f"❌ Роль '{role_input}' не найдена. Укажите ID роли или @роль.",
                            ephemeral=True
                        )
                        return

                # Validate role exists
                role = interaction.guild.get_role(role_id)
                if not role:
                    await interaction.response.send_message(
                        f"❌ Роль с ID {role_id} не найдена на сервере.",
                        ephemeral=True
                    )
                    return

            except ValueError:
                await interaction.response.send_message(
                    "❌ Неверный формат ID роли. Укажите число или @роль.",
                    ephemeral=True
                )
                return

        # Handle subdivision change
        new_subdivision_id = None
        if subdivision_abbr:
            # Find subdivision by abbreviation (case insensitive)
            try:
                with get_db_cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM subdivisions WHERE LOWER(abbreviation) = %s",
                        (subdivision_abbr,)
                    )
                    result = cursor.fetchone()
                    if result:
                        new_subdivision_id = result['id']
                    else:
                        await interaction.response.send_message(
                            f"❌ Подразделение с abbreviation '{subdivision_abbr}' не найдено.",
                            ephemeral=True
                        )
                        return
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ Ошибка при поиске подразделения: {e}",
                    ephemeral=True
                )
                return

        # Update position
        success, message = position_service.update_position(
            self.position_id, position_name, role_id, new_subdivision_id
        )

        color = discord.Color.green() if success else discord.Color.red()
        emoji = "✅" if success else "❌"

        embed = discord.Embed(
            title=f"{emoji} {'Должность обновлена' if success else 'Ошибка'}",
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

def create_position_list_embed(subdivision_data: Dict[str, Any]):
    """Import from management module"""
    from .management import create_position_list_embed
    return create_position_list_embed(subdivision_data, 1)