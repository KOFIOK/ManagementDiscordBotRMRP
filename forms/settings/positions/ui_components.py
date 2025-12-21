"""
UI Components for Position Management System
Переиспользуемые компоненты интерфейса
"""

import discord
from typing import List, Dict, Any, Optional

def create_position_embed(title: str, description: str = "", color: discord.Color = discord.Color.blue()) -> discord.Embed:
    """Create a standard position embed"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    return embed

def create_paginated_embed(
    title: str,
    items: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    items_per_page: int = 25
) -> discord.Embed:
    """Create paginated embed for position lists"""
    embed = discord.Embed(
        title=title,
        color=discord.Color.blue()
    )

    # Add pagination info
    start_idx = (page - 1) * items_per_page + 1
    end_idx = min(page * items_per_page, len(items))

    embed.set_footer(text=f"Страница {page}/{total_pages} • Показано {start_idx}-{end_idx} из {len(items)}")

    return embed

def create_navigation_buttons(current_page: int, total_pages: int) -> List[discord.ui.Button]:
    """Create pagination buttons"""
    buttons = []

    # Previous button
    prev_disabled = current_page <= 1
    prev_button = discord.ui.Button(
        label="⬅️",
        style=discord.ButtonStyle.secondary,
        disabled=prev_disabled,
        custom_id=f"page_prev_{current_page}"
    )
    buttons.append(prev_button)

    # Page indicator
    page_button = discord.ui.Button(
        label=f"{current_page}/{total_pages}",
        style=discord.ButtonStyle.secondary,
        disabled=True,
        custom_id="page_indicator"
    )
    buttons.append(page_button)

    # Next button
    next_disabled = current_page >= total_pages
    next_button = discord.ui.Button(
        label="➡️",
        style=discord.ButtonStyle.secondary,
        disabled=next_disabled,
        custom_id=f"page_next_{current_page}"
    )
    buttons.append(next_button)

    return buttons