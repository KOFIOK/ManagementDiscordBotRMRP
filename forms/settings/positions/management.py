"""
Position Management View
Управление должностями выбранного подразделения с пагинацией
"""

import discord
from discord import ui
from typing import Optional, Dict, Any, List
from utils.database_manager.position_service import position_service
from .ui_components import create_position_embed, create_paginated_embed, create_navigation_buttons

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

        embed = create_position_embed(
            title=f"⚙️ Настройка: {position_data.get('name')}",
            description=f"**Подразделение:** {self.subdivision_data.get('name')}\n**Роль Discord:** Не назначена"
        )

        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="➕ Должность", style=discord.ButtonStyle.success, emoji="📋")
    async def add_position(self, interaction: discord.Interaction, button: ui.Button):
        """Add new position"""
        modal = AddPositionModal(self.subdivision_id, self.subdivision_data)
        await interaction.response.send_modal(modal)

    @ui.button(label="⬅️ Подразделения", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back_to_subdivisions(self, interaction: discord.Interaction, button: ui.Button):
        """Go back to subdivision selection"""
        from .navigation import PositionNavigationView
        view = PositionNavigationView()
        await view.update_subdivision_options(interaction.guild)
        embed = await create_main_navigation_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="🔄 Обновить", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh(self, interaction: discord.Interaction, button: ui.Button):
        """Refresh the view"""
        await self.update_position_options(interaction.guild)
        embed = await create_position_list_embed(self.subdivision_data, self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

async def create_position_list_embed(subdivision_data: Dict[str, Any], page: int) -> discord.Embed:
    """Create embed for position list"""
    embed = create_position_embed(
        title=f"📋 Должности: {subdivision_data.get('name')}",
        description="Выберите должность для настройки или добавьте новую."
    )

    return embed

async def create_main_navigation_embed():
    """Import from navigation module"""
    from .navigation import create_main_navigation_embed
    return await create_main_navigation_embed()

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

        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle submission"""
        position_name = self.name_input.value.strip()

        if not position_name:
            await interaction.response.send_message("❌ Название должности не может быть пустым.", ephemeral=True)
            return

        # Use new position service
        success, message = position_service.add_position_to_subdivision(
            position_name, self.subdivision_id
        )

        color = discord.Color.green() if success else discord.Color.red()
        emoji = "✅" if success else "❌"

        embed = discord.Embed(
            title=f"{emoji} {'Должность добавлена' if success else 'Ошибка'}",
            description=message,
            color=color
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)