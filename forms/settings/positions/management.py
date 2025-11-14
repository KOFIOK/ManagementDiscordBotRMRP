"""
Position Management View
Управление должностями выбранного подразделения с пагинацией
"""

import discord
from discord import ui
from typing import Optional, Dict, Any, List
from utils.database_manager.position_service import position_service
from utils.postgresql_pool import get_db_cursor
from .ui_components import create_position_embed, create_paginated_embed, create_navigation_buttons
from .navigation import create_main_navigation_embed

class PositionManagementView(ui.View):
    """Manage positions for a specific subdivision with pagination"""

    def __init__(self, subdivision_id: int, subdivision_data: Dict[str, Any], page: int = 1):
        super().__init__(timeout=300)
        self.subdivision_id = subdivision_id
        self.subdivision_data = subdivision_data
        self.current_page = page
        self.positions_per_page = 25

    async def update_position_options(self, guild: discord.Guild):
        """Update position select options with pagination"""
        try:
            # Get positions for this subdivision
            positions = self._get_positions_for_subdivision()

            # Calculate pagination
            total_pages = (len(positions) + self.positions_per_page - 1) // self.positions_per_page
            start_idx = (self.current_page - 1) * self.positions_per_page
            end_idx = start_idx + self.positions_per_page

            # Get current page positions
            page_positions = positions[start_idx:end_idx]

            # Create options
            options = []
            for position in page_positions:
                position_name = position.get('name', f'Position {position["id"]}')

                # Check role status
                role_status = "❌"
                if position.get('role_id'):
                    role = guild.get_role(int(position['role_id']))
                    role_status = "✅" if role else "⚠️"

                options.append(discord.SelectOption(
                    label=position_name[:95],  # Discord limit
                    value=str(position['id']),
                    description=f"{role_status} ID: {position['id']}",
                    emoji="📋"
                ))

            if not options:
                options.append(discord.SelectOption(
                    label="Нет должностей",
                    value="none",
                    description="Добавьте должности",
                    emoji="❌"
                ))

            # Update select
            self.position_select.options = options[:25]  # Discord limit

            # Update navigation buttons
            self.clear_items()
            self.add_item(self.position_select)

            # Add pagination buttons if needed
            if total_pages > 1:
                nav_buttons = create_navigation_buttons(self.current_page, total_pages)
                for button in nav_buttons:
                    self.add_item(button)

            # Add action buttons
            self.add_item(self.add_position)
            self.add_item(self.back_to_subdivisions)
            self.add_item(self.refresh)

        except Exception as e:
            print(f"❌ Error updating position options: {e}")

    def _get_positions_for_subdivision(self) -> List[Dict[str, Any]]:
        """Get positions for current subdivision"""
        try:
            # Use new position service
            return position_service.get_positions_for_subdivision(self.subdivision_id)
        except Exception as e:
            print(f"❌ Error getting positions: {e}")
            return []

    @ui.select(
        placeholder="Выберите должность...",
        min_values=1,
        max_values=1,
        options=[],
        custom_id="position_select"
    )
    async def position_select(self, interaction: discord.Interaction, select: ui.Select):
        """Handle position selection"""
        if select.values[0] == "none":
            await interaction.response.send_message("❌ Нет доступных должностей.", ephemeral=True)
            return

        position_id = int(select.values[0])

        # Get position data
        positions = self._get_positions_for_subdivision()
        position_data = next((p for p in positions if p['id'] == position_id), None)

        if not position_data:
            await interaction.response.send_message("❌ Должность не найдена.", ephemeral=True)
            return

        # Show detailed management view
        from .detailed_management import PositionDetailedView
        view = PositionDetailedView(position_id, position_data, self.subdivision_id, self.subdivision_data)

        # Get role information
        role_id = position_data.get('role_id')
        role_display = "Не назначена"
        if role_id:
            role = interaction.guild.get_role(int(role_id))
            if role:
                role_display = f"{role.mention} (ID: {role_id})"
            else:
                role_display = f"⚠️ Роль не найдена (ID: {role_id})"

        embed = create_position_embed(
            title=f"⚙️ Настройка: {position_data.get('name')}",
            description=f"**Подразделение:** {self.subdivision_data.get('name')}\n**Роль Discord:** {role_display}"
        )

        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Добавить должность", style=discord.ButtonStyle.success, emoji="📋")
    async def add_position(self, interaction: discord.Interaction, button: ui.Button):
        """Add new position"""
        modal = AddPositionModal(self.subdivision_id, self.subdivision_data)
        await interaction.response.send_modal(modal)

    @ui.button(label="К подразделениям", style=discord.ButtonStyle.secondary, emoji="◀️")
    async def back_to_subdivisions(self, interaction: discord.Interaction, button: ui.Button):
        """Go back to subdivision selection"""
        from .navigation import PositionNavigationView
        view = PositionNavigationView()
        await view.update_subdivision_options(interaction.guild)
        embed = create_main_navigation_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Обновить", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh(self, interaction: discord.Interaction, button: ui.Button):
        """Refresh the view"""
        await self.update_position_options(interaction.guild)
        embed = create_position_list_embed(self.subdivision_data, self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

def create_position_list_embed(subdivision_data: Dict[str, Any], page: int) -> discord.Embed:
    """Create embed for position list"""
    embed = create_position_embed(
        title=f"📋 Должности: {subdivision_data.get('name')}",
        description="Выберите должность для настройки или добавьте новую."
    )

    return embed

class AddPositionModal(ui.Modal):
    """Add new position modal"""

    def __init__(self, subdivision_id: int, subdivision_data: Dict[str, Any]):
        super().__init__(title=f"Добавить должность в {subdivision_data.get('name')}")
        self.subdivision_id = subdivision_id
        self.subdivision_data = subdivision_data

        self.name_input = ui.TextInput(
            label="Название должности",
            placeholder="Введите название должности...",
            required=True,
            max_length=200
        )

        self.role_input = ui.TextInput(
            label="Discord роль (ID или упоминание)",
            placeholder="Введите ID роли или @роль (необязательно)",
            required=False,
            max_length=50
        )

        self.add_item(self.name_input)
        self.add_item(self.role_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle submission"""
        position_name = self.name_input.value.strip()
        role_input = self.role_input.value.strip() if self.role_input.value else None

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

        # Use new position service
        success, message = position_service.add_position_to_subdivision(
            position_name, self.subdivision_id, role_id
        )

        color = discord.Color.green() if success else discord.Color.red()
        emoji = "✅" if success else "❌"

        embed = discord.Embed(
            title=f"{emoji} {'Должность добавлена' if success else 'Ошибка'}",
            description=message,
            color=color
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditPositionModal(ui.Modal):
    """Edit existing position modal"""

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
            label="Новое подразделение (abbreviation)",
            placeholder="Введите abbreviation подразделения в нижнем регистре...",
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