"""
Context Menu Commands for Personnel Management
Right-click commands for user management
"""

import discord
from discord import app_commands
from discord.ext import commands
import functools
import traceback

from .modals import PromotionModal, DemotionModal, DismissalModal, PositionModal, RecruitmentModal
from .rank_utils import RankHierarchy
from utils.config_manager import load_config, is_moderator_or_admin
from utils.google_sheets import sheets_manager


def handle_context_errors(func):
    """Decorator to handle errors in context menu commands"""
    @functools.wraps(func)
    async def wrapper(interaction: discord.Interaction, user: discord.Member):
        try:
            print(f"📋 Context menu '{func.__name__}' called by {interaction.user.display_name} for {user.display_name}")
            return await func(interaction, user)
        except Exception as e:
            print(f"❌ Error in {func.__name__}: {e}")
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Произошла ошибка при выполнении команды.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Произошла ошибка при выполнении команды.",
                        ephemeral=True
                    )
            except:
                pass
    return wrapper


# Global context menu commands - cannot be inside a cog class

@app_commands.context_menu(name='Повысить (BETA)')
@handle_context_errors
async def promote_user(interaction: discord.Interaction, user: discord.Member):
    """Context menu command to promote user"""
    # Check permissions
    config = load_config()
    if not is_moderator_or_admin(interaction.user, config):
        await interaction.response.send_message(
            "❌ У вас нет прав для выполнения этой команды. Требуются права модератора или администратора.",
            ephemeral=True
        )
        return
    
    # Check if user exists in personnel database
    personnel_data = await sheets_manager.get_user_info_from_personal_list(user.id)
    if not personnel_data:
        await interaction.response.send_message(
            f"❌ Пользователь {user.display_name} не найден в базе данных персонала.",
            ephemeral=True
        )
        return
    
    # Get current rank and next rank for promotion
    current_rank = personnel_data.get('rank', 'Не указано')
    try:
        next_rank = RankHierarchy.get_next_rank(current_rank)
    except Exception as e:
        print(f"❌ Error getting next rank for '{current_rank}': {e}")
        await interaction.response.send_message(
            f"❌ Ошибка при определении следующего звания для '{current_rank}'",
            ephemeral=True
        )
        return
    
    if not next_rank:
        await interaction.response.send_message(
            f"❌ Пользователь {user.display_name} уже имеет максимальное звание: {current_rank}",
            ephemeral=True
        )
        return
    
    # Open promotion modal
    modal = PromotionModal(user, current_rank, next_rank)
    await interaction.response.send_modal(modal)
    print(f"✅ Promotion modal sent for {user.display_name}")


@app_commands.context_menu(name='Разжаловать (BETA)')
@handle_context_errors
async def demote_user(interaction: discord.Interaction, user: discord.Member):
    """Context menu command to demote user"""
    # Check permissions
    config = load_config()
    if not is_moderator_or_admin(interaction.user, config):
        await interaction.response.send_message(
            "❌ У вас нет прав для выполнения этой команды. Требуются права модератора или администратора.",
            ephemeral=True
        )
        return

    # Check if user exists in personnel database
    personnel_data = await sheets_manager.get_user_info_from_personal_list(user.id)
    if not personnel_data:
        await interaction.response.send_message(
            f"❌ Пользователь {user.display_name} не найден в базе данных персонала.",
            ephemeral=True
        )
        return
    
    # Get current rank and previous rank for demotion
    current_rank = personnel_data.get('rank', 'Не указано')
    try:
        previous_rank = RankHierarchy.get_previous_rank(current_rank)
    except Exception as e:
        print(f"❌ Error getting previous rank for '{current_rank}': {e}")
        await interaction.response.send_message(
            f"❌ Ошибка при определении предыдущего звания для '{current_rank}'",
            ephemeral=True
        )
        return
    
    if not previous_rank:
        await interaction.response.send_message(
            f"❌ Пользователь {user.display_name} имеет минимальное звание: {current_rank}",
            ephemeral=True
        )
        return
    
    # Open demotion modal
    modal = DemotionModal(user, current_rank, previous_rank)
    await interaction.response.send_modal(modal)
    print(f"✅ Demotion modal sent for {user.display_name}")


@app_commands.context_menu(name='Уволить (BETA)')
@handle_context_errors
async def dismiss_user(interaction: discord.Interaction, user: discord.Member):
    """Context menu command to dismiss user"""
    # Check permissions
    config = load_config()
    if not is_moderator_or_admin(interaction.user, config):
        await interaction.response.send_message(
            "❌ У вас нет прав для выполнения этой команды. Требуются права модератора или администратора.",
            ephemeral=True
        )
        return
    
    # Check if user exists in personnel database
    personnel_data = await sheets_manager.get_user_info_from_personal_list(user.id)
    if not personnel_data:
        await interaction.response.send_message(
            f"❌ Пользователь {user.display_name} не найден в базе данных персонала.",
            ephemeral=True
        )
        return
    
    # Open dismissal modal
    modal = DismissalModal(user)
    await interaction.response.send_modal(modal)
    print(f"✅ Dismissal modal sent for {user.display_name}")


@app_commands.context_menu(name='Назначить должность (BETA)')
@handle_context_errors
async def assign_position(interaction: discord.Interaction, user: discord.Member):
    """Context menu command to assign/remove position"""
    # Check permissions
    config = load_config()
    if not is_moderator_or_admin(interaction.user, config):
        await interaction.response.send_message(
            "❌ У вас нет прав для выполнения этой команды. Требуются права модератора или администратора.",
            ephemeral=True
        )
        return
    
    # Check if user exists in personnel database
    personnel_data = await sheets_manager.get_user_info_from_personal_list(user.id)
    if not personnel_data:
        await interaction.response.send_message(
            f"❌ Пользователь {user.display_name} не найден в базе данных персонала.",
            ephemeral=True
        )
        return
    
    # Open position modal
    modal = PositionModal(user)
    await interaction.response.send_modal(modal)
    print(f"✅ Position modal sent for {user.display_name}")


@app_commands.context_menu(name='Принять на службу (BETA)')
@handle_context_errors
async def recruit_user(interaction: discord.Interaction, user: discord.Member):
    """Context menu command to recruit user"""
    # Check permissions
    config = load_config()
    if not is_moderator_or_admin(interaction.user, config):
        await interaction.response.send_message(
            "❌ У вас нет прав для выполнения этой команды. Требуются права модератора или администратора.",
            ephemeral=True
        )
        return
    
    # Open recruitment modal immediately (validation will be done in modal)
    modal = RecruitmentModal(user)
    await interaction.response.send_modal(modal)
    print(f"✅ Recruitment modal sent for {user.display_name}")


def setup_context_commands(bot):
    """Setup context menu commands (avoid duplicates)"""
    # Check if commands are already added to avoid duplicates
    existing_commands = [cmd.name for cmd in bot.tree.get_commands()]
    
    commands_to_add = [
        ('Повысить (BETA)', promote_user),
        ('Разжаловать (BETA)', demote_user), 
        ('Уволить (BETA)', dismiss_user),
        ('Назначить должность (BETA)', assign_position),
        ('Принять на службу (BETA)', recruit_user)
    ]
    
    added_count = 0
    for name, command in commands_to_add:
        if name not in existing_commands:
            bot.tree.add_command(command)
            added_count += 1
    
    if added_count > 0:
        print(f"✅ Personnel context menu commands loaded ({added_count} new commands)")
    else:
        print("ℹ️ Personnel context menu commands already loaded")
