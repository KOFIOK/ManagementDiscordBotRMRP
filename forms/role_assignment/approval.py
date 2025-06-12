"""
Application approval system for role assignments

This module handles the approval/rejection workflow with proper interaction handling.
"""

import discord
from discord import ui
from datetime import datetime, timezone
from utils.config_manager import load_config, is_moderator_or_admin
from utils.google_sheets import sheets_manager
from .base import get_channel_with_fallback
from .views import ApprovedApplicationView, RejectedApplicationView


class RoleApplicationApprovalView(ui.View):
    """View for approving/rejecting role applications"""
    
    def __init__(self, application_data):
        super().__init__(timeout=None)
        self.application_data = application_data
    
    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.green, custom_id="approve_role_app")
    async def approve_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle application approval"""
        # Check permissions first
        if not await self._check_moderator_permissions(interaction):
            await interaction.response.send_message(
                "❌ У вас нет прав для модерации заявок.",
                ephemeral=True
            )
            return
        
        try:
            await self._process_approval(interaction)
        except Exception as e:
            print(f"Error in approval process: {e}")
            # Use proper error handling based on interaction state
            await self._send_error_message(interaction, "Произошла ошибка при одобрении заявки.")
    
    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.red, custom_id="reject_role_app")
    async def reject_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle application rejection"""
        # Check permissions first  
        if not await self._check_moderator_permissions(interaction):
            await interaction.response.send_message(
                "❌ У вас нет прав для модерации заявок.",
                ephemeral=True
            )
            return
        
        try:
            await self._process_rejection(interaction)
        except Exception as e:
            print(f"Error in rejection process: {e}")
            await self._send_error_message(interaction, "Произошла ошибка при отклонении заявки.")
    
    async def _check_moderator_permissions(self, interaction):
        """Check if user has moderator permissions"""
        config = load_config()
        return is_moderator_or_admin(interaction.user, config)
    
    async def _process_approval(self, interaction):
        """Process application approval with simplified logic"""
        try:
            config = load_config()
            guild = interaction.guild
            user = guild.get_member(self.application_data["user_id"])
            
            if not user:
                await interaction.response.send_message(
                    "❌ Пользователь не найден на сервере.",
                    ephemeral=True
                )
                return
            
            # Create embed first
            embed = await self._create_approval_embed(interaction)
            approved_view = ApprovedApplicationView()
            
            # Respond to interaction immediately to prevent timeout
            await interaction.response.edit_message(embed=embed, view=approved_view)
            
            # Then do all the other processing
            try:
                # Assign roles and update nickname if needed
                await self._assign_roles(user, guild, config)
            except Exception as e:
                print(f"Warning: Error in role assignment: {e}")
                # Continue processing even if role assignment fails
                
            # Only do personnel processing for military recruits with rank 'рядовой'
            if self._should_process_personnel():
                try:
                    await self._handle_auto_processing(interaction, user, guild, config)
                except Exception as e:
                    print(f"Warning: Error in personnel processing: {e}")
                    # Continue processing even if personnel processing fails
            
            # Send DM to user
            try:
                await self._send_approval_dm(user)
            except Exception as e:
                print(f"Warning: Error sending DM: {e}")
                # Continue even if DM fails
                
        except Exception as e:
            print(f"Error in approval process: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Произошла ошибка при обработке заявки.",
                        ephemeral=True
                    )
            except Exception as followup_error:
                print(f"Failed to send error message: {followup_error}")
    
    async def _process_rejection(self, interaction):
        """Process application rejection with simplified logic"""
        guild = interaction.guild
        user = guild.get_member(self.application_data["user_id"])
        
        # Update embed
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(
            name="❌ Статус",
            value=f"Отклонено сотрудником {interaction.user.mention}",
            inline=False
        )
        
        # Clear ping content and respond ONCE
        rejected_view = RejectedApplicationView()
        await interaction.response.edit_message(content="", embed=embed, view=rejected_view)
        
        # Send DM to user
        if user:
            await self._send_rejection_dm(user)
    
    def _should_auto_process(self):
        """Determine if this application should be automatically processed"""
        if self.application_data["type"] == "military":
            rank = self.application_data.get("rank", "").lower()
            return rank == "рядовой"
        else:  # civilian
            return True
    
    def _should_change_nickname(self):
        """Determine if nickname should be changed"""
        if self.application_data["type"] == "military":
            rank = self.application_data.get("rank", "").lower()
            return rank == "рядовой"
        return False  # Never change nickname for civilians
    
    def _should_process_personnel(self):
        """Determine if personnel record should be processed"""
        # Only process personnel records for military recruits with rank 'рядовой'
        if self.application_data["type"] == "military":
            rank = self.application_data.get("rank", "").lower()
            return rank == "рядовой"
        return False  # Never process personnel records for civilians
    
    async def _assign_roles(self, user, guild, config):
        """Assign appropriate roles to user"""
        try:
            if self.application_data["type"] == "military":
                role_ids = config.get('military_roles', [])
                opposite_role_ids = config.get('civilian_roles', [])
                
                # Set nickname for military recruits only
                if self._should_change_nickname():
                    try:
                        await self._set_military_nickname(user)
                    except Exception as e:
                        print(f"Warning: Could not set military nickname: {e}")
                        # Continue processing even if nickname change fails
            else:
                role_ids = config.get('civilian_roles', [])
                opposite_role_ids = config.get('military_roles', [])
            
            # Remove opposite roles
            for role_id in opposite_role_ids:
                role = guild.get_role(role_id)
                if role and role in user.roles:
                    try:
                        await user.remove_roles(role, reason="Переход на другую роль")
                    except discord.Forbidden:
                        print(f"No permission to remove role {role.name}")
                    except Exception as e:
                        print(f"Error removing role {role.name}: {e}")
            
            # Add new roles
            for role_id in role_ids:
                role = guild.get_role(role_id)
                if role:
                    try:
                        await user.add_roles(role, reason="Одобрение заявки на роль")
                    except discord.Forbidden:
                        print(f"No permission to assign role {role.name}")
                    except Exception as e:
                        print(f"Error assigning role {role.name}: {e}")
                        
        except Exception as e:
            print(f"Error in role assignment: {e}")
            raise  # Re-raise the exception to be caught by the caller
    
    async def _set_military_nickname(self, user):
        """Set nickname for military users"""
        try:
            full_name = self.application_data['name']
            full_nickname = f"ВА | {full_name}"
            
            if len(full_nickname) <= 32:
                new_nickname = full_nickname
            else:
                # Shorten if too long
                name_parts = full_name.split()
                if len(name_parts) >= 2:
                    first_initial = name_parts[0][0] if name_parts[0] else "И"
                    last_name = name_parts[-1]
                    new_nickname = f"ВА | {first_initial}. {last_name}"
                else:
                    new_nickname = f"ВА | {full_name[:25]}"
            
            await user.edit(nick=new_nickname, reason="Одобрение заявки на роль военнослужащего")
            print(f"✅ Successfully set nickname for {user} to {new_nickname}")
            
        except discord.Forbidden as e:
            print(f"Warning: No permission to change nickname for {user}")
            # Don't raise the error, just log it
        except Exception as e:
            print(f"Error setting nickname for {user}: {e}")
            # Don't raise the error, just log it
    
    async def _create_approval_embed(self, interaction):
        """Create approval embed with status"""
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        
        if self.application_data["type"] == "military":
            if self._should_process_personnel():
                status_message = f"Одобрено инструктором ВК {interaction.user.mention}"
            else:
                status_message = f"Одобрено инструктором ВК {interaction.user.mention}\n⚠️ Требуется ручная обработка для звания {self.application_data.get('rank', 'Неизвестно')}"
        else:
            status_message = f"Одобрено руководством бригады ( {interaction.user.mention} )"
        
        embed.add_field(
            name="✅ Статус",
            value=status_message,
            inline=False
        )
        
        return embed
    
    async def _handle_auto_processing(self, interaction, user, guild, config):
        """Handle automatic processing (Google Sheets + Audit)"""
        try:
            # Get moderator authorization
            auth_result = await sheets_manager.check_moderator_authorization(interaction.user)
            
            if not auth_result["found"]:
                print(f"Moderator not found in system, skipping auto-processing")
                return
            
            signed_by_name = auth_result["info"]
            hiring_time = datetime.now(timezone.utc)
            
            # Log to Google Sheets
            sheets_success = await sheets_manager.add_hiring_record(
                self.application_data,
                user,
                interaction.user,
                hiring_time,
                override_moderator_info=None
            )
            
            if sheets_success:
                print(f"✅ Successfully logged hiring for {self.application_data.get('name', 'Unknown')}")
            
            # Send audit notification
            audit_channel_id = config.get('audit_channel')
            if audit_channel_id:
                audit_channel = await get_channel_with_fallback(guild, audit_channel_id, "audit channel")
                if audit_channel:
                    await self._send_audit_notification(audit_channel, user, signed_by_name)
            
        except Exception as e:
            print(f"Error in auto-processing: {e}")
    
    async def _send_audit_notification(self, audit_channel, user, signed_by_name):
        """Send notification to audit channel"""
        try:
            audit_embed = discord.Embed(
                title="Кадровый аудит ВС РФ",
                color=0x055000,
                timestamp=discord.utils.utcnow()
            )
            
            action_date = discord.utils.utcnow().strftime('%d-%m-%Y')
            name_with_static = f"{self.application_data.get('name', 'Неизвестно')} | {self.application_data.get('static', '')}"
            
            audit_embed.add_field(name="Кадровую отписал", value=signed_by_name, inline=False)
            audit_embed.add_field(name="Имя Фамилия | 6 цифр статика", value=name_with_static, inline=False)
            audit_embed.add_field(name="Действие", value="Принят на службу", inline=False)
            
            recruitment_type = self.application_data.get("recruitment_type", "")
            if recruitment_type:
                audit_embed.add_field(name="Причина принятия", value=recruitment_type.capitalize(), inline=False)
            
            audit_embed.add_field(name="Дата Действия", value=action_date, inline=False)
            audit_embed.add_field(name="Подразделение", value="Военная Академия", inline=False)
            audit_embed.add_field(name="Воинское звание", value=self.application_data.get("rank", "Рядовой"), inline=False)
            
            audit_embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
            
            await audit_channel.send(content=f"<@{user.id}>", embed=audit_embed)
            print(f"Sent audit notification for hiring of {user.display_name}")
            
        except Exception as e:
            print(f"Error sending audit notification: {e}")
    
    async def _send_approval_dm(self, user):
        """Send approval DM to user"""
        try:
            if self.application_data["type"] == "military":
                instructions = (
                    "## ✅ **Ваша заявка на получение роли военнослужащего была одобрена!**\n\n"
                    "📋 **Полезная информация:**\n"
                    "> • Канал общения:\n> <#1246126422251278597>\n"
                    "> • Расписание занятий (необходимых для повышения):\n> <#1336337899309895722>\n"
                    "> • Следите за оповещениями обучения:\n> <#1337434149274779738>\n"
                    "> • Ознакомьтесь с сайтом Вооружённых Сил РФ:\n> <#1326022450307137659>\n"
                    "> • Следите за последними приказами:\n> <#1251166871064019015>\n"
                    "> • Уже были в ВС РФ? Попробуйте восстановиться:\n> <#1317830537724952626>\n"
                    "> • Решили, что служба не для вас? Напишите рапорт на увольнение:\n> <#1246119825487564981>"
                )
            else:
                instructions = (
                    "## ✅ **Ваша заявка на получение роли госслужащего была одобрена!**\n\n"
                    "📋 **Полезная информация:**\n"
                    "> • Канал общения:\n> <#1246125346152251393>\n"
                    "> • Запросить поставку:\n> <#1246119051726553099>\n"
                    "> • Запросить допуск на территорию ВС РФ:\n> <#1246119269784354888>"
                )
            
            await user.send(instructions)
        except discord.Forbidden:
            pass  # User has DMs disabled
    
    async def _send_rejection_dm(self, user):
        """Send rejection DM to user"""
        try:
            role_type = "военнослужащего" if self.application_data["type"] == "military" else "госслужащего"
            await user.send(
                f"❌ Ваша заявка на получение роли {role_type} была отклонена.\n\n"
                f"Вы можете подать новую заявку позже."
            )
        except discord.Forbidden:
            pass  # User has DMs disabled
    
    async def _send_error_message(self, interaction, message):
        """Send error message with proper interaction handling"""
        try:
            if interaction.response.is_done():
                # Interaction already responded, use followup
                await interaction.followup.send(f"❌ {message}", ephemeral=True)
            else:
                # Interaction not responded yet, use response
                await interaction.response.send_message(f"❌ {message}", ephemeral=True)
        except Exception as e:
            print(f"Failed to send error message: {e}")
            # Last resort - try both methods
            try:
                await interaction.response.send_message(f"❌ {message}", ephemeral=True)
            except:
                try:
                    await interaction.followup.send(f"❌ {message}", ephemeral=True)
                except:
                    pass  # Give up
