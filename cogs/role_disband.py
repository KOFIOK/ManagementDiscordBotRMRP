"""
Role Disband System
Slash command for administrators to mass remove roles from users
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import List
import asyncio
from utils.config_manager import load_config, is_administrator
from utils.message_manager import get_role_reason


class RoleDisbandView(discord.ui.View):
    """View with confirmation button for role disbanding"""
    
    def __init__(self, roles_to_disband: List[discord.Role] = None, admin_user: discord.Member = None, affected_users: List[discord.Member] = None, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.roles_to_disband = roles_to_disband or []
        self.admin_user = admin_user
        self.affected_users = affected_users or []
    
    @discord.ui.button(label="✅ Подтвердить расформирование", style=discord.ButtonStyle.danger, custom_id="confirm_disband")
    async def confirm_disband(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle confirmation of role disbanding"""
        try:
            # Check if the user who clicked is the same admin who initiated the command
            if interaction.user.id != self.admin_user.id:
                await interaction.response.send_message(
                    "❌ Только инициатор команды может подтвердить расформирование.",
                    ephemeral=True
                )
                return
            
            # Disable the button and update the message
            button.disabled = True
            button.label = "⏳ Обрабатывается..."
            button.style = discord.ButtonStyle.secondary
            
            await interaction.response.edit_message(view=self)
            
            # Start the disbanding process
            await self._execute_disband(interaction)
            
        except Exception as e:
            print(f"Error in role disband confirmation: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при подтверждении расформирования.",
                ephemeral=True
            )
    
    async def _execute_disband(self, interaction: discord.Interaction):
        """Execute the role disbanding process"""
        try:
            total_users = len(self.affected_users)
            processed_users = 0
            failed_users = []
            
            # Create progress embed
            progress_embed = discord.Embed(
                title="🔄 Расформирование ролей",
                description=f"Обработка: 0/{total_users} пользователей...",
                color=discord.Color.orange()
            )
            
            await interaction.edit_original_response(embed=progress_embed, view=None)
            
            # Process users in batches to avoid rate limits
            batch_size = 10
            for i in range(0, len(self.affected_users), batch_size):
                batch = self.affected_users[i:i + batch_size]
                batch_tasks = []
                
                for user in batch:
                    batch_tasks.append(self._remove_roles_from_user(user, failed_users))
                
                # Execute batch
                await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                processed_users += len(batch)
                
                # Update progress every batch
                progress_embed.description = f"Обработка: {processed_users}/{total_users} пользователей..."
                await interaction.edit_original_response(embed=progress_embed)
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)
            
            # Create final result embed
            result_embed = discord.Embed(
                title="✅ Расформирование завершено",
                color=discord.Color.green()
            )
            
            role_names = [role.mention for role in self.roles_to_disband]
            result_embed.add_field(
                name="Расформированные роли",
                value=", ".join(role_names),
                inline=False
            )
            
            result_embed.add_field(
                name="Статистика",
                value=f"**Обработано пользователей:** {processed_users}\n**Успешно:** {processed_users - len(failed_users)}\n**Ошибок:** {len(failed_users)}",
                inline=False
            )
            
            if failed_users:
                failed_mentions = [f"<@{user_id}>" for user_id in failed_users[:10]]  # Show max 10
                if len(failed_users) > 10:
                    failed_mentions.append(f"... и ещё {len(failed_users) - 10}")
                
                result_embed.add_field(
                    name="⚠️ Не удалось обработать",
                    value=", ".join(failed_mentions),
                    inline=False
                )
            
            result_embed.set_footer(text=f"Расформировал: {self.admin_user.display_name}")
            result_embed.timestamp = discord.utils.utcnow()
            
            await interaction.edit_original_response(embed=result_embed)
            
            # Send audit log
            await self._send_audit_log(interaction.guild, processed_users - len(failed_users))
            
        except Exception as e:
            print(f"Error executing role disband: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка расформирования",
                description="Произошла критическая ошибка при расформировании ролей.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=error_embed, view=None)
    
    async def _remove_roles_from_user(self, user: discord.Member, failed_users: List[int]):
        """Remove roles from a single user"""
        try:
            roles_to_remove = []
            for role in self.roles_to_disband:
                if role in user.roles:
                    roles_to_remove.append(role)
            
            if roles_to_remove:
                await user.remove_roles(*roles_to_remove, reason=get_role_reason(user.guild.id, "role_removal.administrative", "Административное снятие роли").format(moderator=self.admin_user.mention))
                print(f"✅ Removed {len(roles_to_remove)} roles from {user.display_name}")
            
        except Exception as e:
            print(f"❌ Failed to remove roles from {user.display_name}: {e}")
            failed_users.append(user.id)
    
    async def _send_audit_log(self, guild: discord.Guild, successful_count: int):
        """Send audit log message"""
        try:
            config = load_config()
            audit_channel_id = config.get('audit_channel')
            
            if not audit_channel_id:
                print("No audit channel configured")
                return
            
            audit_channel = guild.get_channel(audit_channel_id)
            if not audit_channel:
                print(f"Audit channel not found: {audit_channel_id}")
                return
            
            # Create audit embed
            audit_embed = discord.Embed(
                title="🔧 Административное действие",
                description=f"{self.admin_user.mention} расформировал роли",
                color=discord.Color.blue()
            )
            
            role_names = [role.mention for role in self.roles_to_disband]
            audit_embed.add_field(
                name="Расформированные роли",
                value=", ".join(role_names),
                inline=False
            )
            
            audit_embed.add_field(
                name="Затронуто пользователей",
                value=str(successful_count),
                inline=True
            )
            
            audit_embed.set_footer(text=f"ID администратора: {self.admin_user.id}")
            audit_embed.timestamp = discord.utils.utcnow()
            
            await audit_channel.send(embed=audit_embed)
            print(f"✅ Sent audit log for role disband by {self.admin_user.display_name}")
            
        except Exception as e:
            print(f"❌ Error sending audit log: {e}")
    
    @discord.ui.button(label="❌ Отменить", style=discord.ButtonStyle.secondary, custom_id="cancel_disband")
    async def cancel_disband(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle cancellation of role disbanding"""
        try:
            # Check if the user who clicked is the same admin who initiated the command
            if interaction.user.id != self.admin_user.id:
                await interaction.response.send_message(
                    "❌ Только инициатор команды может отменить расформирование.",
                    ephemeral=True
                )
                return
            
            # Create cancellation embed
            embed = discord.Embed(
                title="❌ Расформирование отменено",
                description="Операция расформирования ролей была отменена.",
                color=discord.Color.red()
            )
            embed.set_footer(text=f"Отменил: {self.admin_user.display_name}")
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            print(f"Error in role disband cancellation: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при отмене расформирования.",
                ephemeral=True
            )
    
    async def on_timeout(self):
        """Handle view timeout"""
        try:
            embed = discord.Embed(
                title="⏰ Время истекло",
                description="Время ожидания подтверждения расформирования истекло. Операция отменена.",
                color=discord.Color.orange()
            )
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            # Note: We can't edit the message here because we don't have interaction context
            # The timeout will just disable the buttons
            
        except Exception as e:
            print(f"Error handling role disband timeout: {e}")

    # ...existing code...
  
class RoleDisband(commands.Cog):
    """Cog for role disbanding functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        print("🔧 RoleDisband cog initialized")
    
    @app_commands.command(name="расформ", description="Расформировать указанные роли (убрать у всех пользователей)")
    @app_commands.describe(
        роль1="Роль для расформирования",
        роль2="Роль для расформирования (опционально)",
        роль3="Роль для расформирования (опционально)",
        роль4="Роль для расформирования (опционально)",
        роль5="Роль для расформирования (опционально)",
        роль6="Роль для расформирования (опционально)",
        роль7="Роль для расформирования (опционально)",
        роль8="Роль для расформирования (опционально)",
        роль9="Роль для расформирования (опционально)",
        роль10="Роль для расформирования (опционально)"
    )
    async def disband_roles(
        self, 
        interaction: discord.Interaction,
        роль1: discord.Role,
        роль2: discord.Role = None,
        роль3: discord.Role = None,
        роль4: discord.Role = None,
        роль5: discord.Role = None,
        роль6: discord.Role = None,
        роль7: discord.Role = None,
        роль8: discord.Role = None,
        роль9: discord.Role = None,
        роль10: discord.Role = None
    ):
        """Disband specified roles from all users"""
        print(f"🔧 /расформ command called by {interaction.user}")
        try:
            # Check admin permissions - ONLY ADMINISTRATORS can use this command
            config = load_config()
            if not is_administrator(interaction.user, config):
                embed = discord.Embed(
                    title="❌ Недостаточно прав",
                    description="Эта команда доступна только администраторам.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Collect all non-None roles
            all_roles = [роль1, роль2, роль3, роль4, роль5, роль6, роль7, роль8, роль9, роль10]
            roles_to_disband = [role for role in all_roles if role is not None]
            
            # Remove duplicates while preserving order
            seen = set()
            unique_roles = []
            for role in roles_to_disband:
                if role.id not in seen:
                    seen.add(role.id)
                    unique_roles.append(role)
            
            roles_to_disband = unique_roles
            
            print(f"🔧 Roles to disband: {[role.name for role in roles_to_disband]}")
            
            if not roles_to_disband:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Не указано ни одной роли для расформирования.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Filter out protected roles
            protected_roles, allowed_roles = self._filter_protected_roles(roles_to_disband, interaction.guild.me, config)
            
            if not allowed_roles:
                embed = discord.Embed(
                    title="❌ Невозможно расформировать",
                    description="Все указанные роли защищены от расформирования.",
                    color=discord.Color.red()
                )
                
                if protected_roles:
                    protected_names = [role.mention for role in protected_roles]
                    embed.add_field(
                        name="Защищенные роли",
                        value=", ".join(protected_names),
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Find all users with these roles
            affected_users = self._find_affected_users(allowed_roles, interaction.guild)
            
            # Create confirmation embed
            embed = discord.Embed(
                title="⚠️ Подтверждение расформирования",
                description="**ВНИМАНИЕ!** Это действие необратимо!",
                color=discord.Color.orange()
            )
            
            role_names = [role.mention for role in allowed_roles]
            embed.add_field(
                name="Роли для расформирования",
                value=", ".join(role_names),
                inline=False
            )
            
            embed.add_field(
                name="Затронутые пользователи",
                value=str(len(affected_users)),
                inline=True
            )
            
            if protected_roles:
                protected_names = [role.mention for role in protected_roles]
                embed.add_field(
                    name="⚠️ Пропущенные (защищенные) роли",
                    value=", ".join(protected_names),
                    inline=False
                )
            
            embed.set_footer(text="Нажмите 'Подтвердить' для выполнения расформирования")
            
            # Create view with confirmation button
            view = RoleDisbandView(allowed_roles, interaction.user, affected_users)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            print(f"Error in disband_roles command: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке команды.",
                ephemeral=True
            )
    
    def _filter_protected_roles(self, roles: List[discord.Role], bot_member: discord.Member, config: dict) -> tuple[List[discord.Role], List[discord.Role]]:
        """Filter out protected roles that cannot be disbanded"""
        protected_roles = []
        allowed_roles = []
        
        bot_top_role = bot_member.top_role
        
        for role in roles:
            is_protected = False
            
            # Check if role is higher than bot's role
            if role.position >= bot_top_role.position:
                is_protected = True
            
            # Check if role has administrator permissions
            elif role.permissions.administrator:
                is_protected = True
            
            # Check if role is in moderator roles (bot admin roles)
            elif role.id in config.get('moderator_roles', []):
                is_protected = True
            
            # Check if it's @everyone
            elif role.is_default():
                is_protected = True
            
            if is_protected:
                protected_roles.append(role)
            else:
                allowed_roles.append(role)
        
        return protected_roles, allowed_roles
    
    def _find_affected_users(self, roles: List[discord.Role], guild: discord.Guild) -> List[discord.Member]:
        """Find all users who have any of the specified roles"""
        affected_users = set()
        
        for role in roles:
            for member in role.members:
                if not member.bot:  # Skip bots
                    affected_users.add(member)
        
        return list(affected_users)


async def setup(bot):
    """Setup function for the cog"""
    # Add the cog first
    await bot.add_cog(RoleDisband(bot))
    print("Loaded role disband cog successfully")
