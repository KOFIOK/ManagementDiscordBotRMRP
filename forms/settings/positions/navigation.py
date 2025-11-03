"""
Position Navigation System
Иерархическая навигация: Подразделения → Должности с пагинацией
"""

import discord
from discord import ui
from typing import Optional, List, Dict, Any
from utils.postgresql_pool import get_db_cursor
from .ui_components import create_position_embed, create_paginated_embed, create_navigation_buttons

class PositionNavigationView(ui.View):
    """Main navigation view for position management"""

    def __init__(self, current_page: int = 1):
        super().__init__(timeout=300)
        self.current_page = current_page
        self.subdivisions_per_page = 25

    async def update_subdivision_options(self, guild: discord.Guild):
        """Update subdivision select options with pagination"""
        try:
            # Get all subdivisions
            subdivisions = await self._get_all_subdivisions()

            # Calculate pagination
            total_pages = (len(subdivisions) + self.subdivisions_per_page - 1) // self.subdivisions_per_page
            start_idx = (self.current_page - 1) * self.subdivisions_per_page
            end_idx = start_idx + self.subdivisions_per_page

            # Get current page subdivisions
            page_subdivisions = subdivisions[start_idx:end_idx]

            # Create options
            options = []
            for subdivision in page_subdivisions:
                subdivision_name = subdivision.get('name', f'Subdivision {subdivision["id"]}')
                abbreviation = subdivision.get('abbreviation', '')

                # Check if subdivision has positions
                position_count = self._get_position_count_for_subdivision(subdivision['id'])

                label = f"{subdivision_name}"
                if abbreviation:
                    label = f"{abbreviation} - {subdivision_name}"

                description = f"Должностей: {position_count}"

                options.append(discord.SelectOption(
                    label=label[:95],  # Discord limit
                    value=str(subdivision['id']),
                    description=description[:95],
                    emoji="🏢"
                ))

            if not options:
                options.append(discord.SelectOption(
                    label="Нет подразделений",
                    value="none",
                    description="Добавьте подразделения",
                    emoji="❌"
                ))

            # Update select
            self.subdivision_select.options = options[:25]  # Discord limit

            # Update navigation buttons
            self.clear_items()
            self.add_item(self.subdivision_select)

            # Add pagination buttons if needed
            if total_pages > 1:
                nav_buttons = create_navigation_buttons(self.current_page, total_pages)
                for button in nav_buttons:
                    self.add_item(button)

            # Add action buttons
            self.add_item(self.add_subdivision)
            self.add_item(self.search_positions)
            self.add_item(self.refresh)

        except Exception as e:
            print(f"❌ Error updating subdivision options: {e}")

    async def _get_all_subdivisions(self) -> List[Dict[str, Any]]:
        """Get all subdivisions from database"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id, name, abbreviation, role_id FROM subdivisions ORDER BY name")
                result = cursor.fetchall()
                return [dict(row) for row in result] if result else []
        except Exception as e:
            print(f"❌ Error getting subdivisions: {e}")
            return []

    def _get_position_count_for_subdivision(self, subdivision_id: int) -> int:
        """Get position count for subdivision"""
        try:
            # This will be implemented in the position service
            # For now, return placeholder
            return 0
        except Exception:
            return 0

    @ui.select(
        placeholder="Выберите подразделение...",
        min_values=1,
        max_values=1,
        options=[],
        custom_id="subdivision_select"
    )
    async def subdivision_select(self, interaction: discord.Interaction, select: ui.Select):
        """Handle subdivision selection"""
        if select.values[0] == "none":
            await interaction.response.send_message("❌ Нет доступных подразделений.", ephemeral=True)
            return

        subdivision_id = int(select.values[0])

        # Get subdivision data
        subdivisions = await self._get_all_subdivisions()
        subdivision_data = next((s for s in subdivisions if s['id'] == subdivision_id), None)

        if not subdivision_data:
            await interaction.response.send_message("❌ Подразделение не найдено.", ephemeral=True)
            return

        # Navigate to position list for this subdivision
        from .management import PositionManagementView
        view = PositionManagementView(subdivision_id, subdivision_data, page=1)

        embed = create_position_embed(
            title=f"📋 Должности: {subdivision_data.get('name')}",
            description="Выберите должность для настройки или добавьте новую."
        )

        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="➕ Подразделение", style=discord.ButtonStyle.success, emoji="🏢")
    async def add_subdivision(self, interaction: discord.Interaction, button: ui.Button):
        """Add new subdivision"""
        # This will open department management
        await interaction.response.send_message("ℹ️ Управление подразделениями доступно в настройках департаментов.", ephemeral=True)

    @ui.button(label="🔍 Поиск", style=discord.ButtonStyle.primary, emoji="🔍")
    async def search_positions(self, interaction: discord.Interaction, button: ui.Button):
        """Open search interface"""
        from .search import PositionSearchView
        view = PositionSearchView()
        embed = create_position_embed(
            title="🔍 Поиск должностей",
            description="Введите критерии поиска."
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="🔄 Обновить", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh(self, interaction: discord.Interaction, button: ui.Button):
        """Refresh the view"""
        await self.update_subdivision_options(interaction.guild)
        embed = await create_main_navigation_embed()
        await interaction.response.edit_message(embed=embed, view=self)

async def create_main_navigation_embed() -> discord.Embed:
    """Create main navigation embed"""
    embed = create_position_embed(
        title="⚙️ Управление должностями",
        description=(
            "**Иерархическая система:**\n"
            "🏢 Выберите подразделение\n"
            "📋 Просмотрите должности с пагинацией\n"
            "⚙️ Настройте каждую должность\n\n"
            "Выберите подразделение для продолжения."
        )
    )

    return embed