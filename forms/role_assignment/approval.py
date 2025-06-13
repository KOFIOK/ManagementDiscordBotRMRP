"""
Application approval system for role assignments

This module handles the approval/rejection workflow with proper interaction handling.
"""

import discord
from discord import ui
import asyncio
from datetime import datetime, timezone
from utils.config_manager import load_config, is_moderator_or_admin
from utils.google_sheets import sheets_manager
from .base import get_channel_with_fallback
from .views import ApprovedApplicationView, RejectedApplicationView, ProcessingApplicationView


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
            await self._request_rejection_reason(interaction)
        except Exception as e:
            print(f"Error in rejection process: {e}")
            await self._send_error_message(interaction, "Произошла ошибка при отклонении заявки.")
    
    async def _check_moderator_permissions(self, interaction):
        """Check if user has moderator permissions"""
        config = load_config()
        return is_moderator_or_admin(interaction.user, config)
    
    async def _process_approval(self, interaction):
        """Process application approval with Google Sheets authorization"""
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
              # Handle moderator authorization first
            signed_by_name = await self._handle_moderator_authorization(interaction, user, guild, config)
            if signed_by_name is None:
                # Authorization failed or modal was shown, processing will continue in callback
                return
            
            # Continue with approval processing if authorization was successful
            await self._continue_approval_process(interaction, user, guild, config, signed_by_name)
                
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
    
    async def _process_rejection(self, interaction, rejection_reason=None):
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
        
        # Add rejection reason if provided
        if rejection_reason:
            embed.add_field(
                name="Причина отказа",
                value=rejection_reason,
                inline=False
            )
        
        # Clear ping content and respond ONCE
        rejected_view = RejectedApplicationView()
        await interaction.response.edit_message(content="", embed=embed, view=rejected_view)
        
        # Send DM to user
        if user:
            if rejection_reason:
                await self._send_rejection_dm_with_reason(user, rejection_reason)
            else:
                await self._send_rejection_dm(user)
    
    async def _request_rejection_reason(self, interaction):
        """Request rejection reason from moderator via modal."""
        try:
            from .modals import RoleRejectionReasonModal
            
            # Store the original message for later reference
            original_message = interaction.message
            
            # Create modal to request rejection reason
            reason_modal = RoleRejectionReasonModal(
                self._finalize_rejection_with_reason,
                original_message
            )
            
            # Send modal
            await interaction.response.send_modal(reason_modal)
            
        except Exception as e:
            print(f"Error in _request_rejection_reason: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Произошла ошибка при запросе причины отказа.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Произошла ошибка при запросе причины отказа.",
                    ephemeral=True
                )

    async def _finalize_rejection_with_reason(self, interaction, rejection_reason, original_message):
        """Finalize the rejection process with the provided reason."""
        try:
            # Respond to the modal interaction first
            await interaction.response.defer()
            
            guild = interaction.guild
            user = guild.get_member(self.application_data["user_id"])
            
            # Update embed with rejection reason
            embed = original_message.embeds[0]
            embed.color = discord.Color.red()
            embed.add_field(
                name="❌ Статус",
                value=f"Отклонено сотрудником {interaction.user.mention}",
                inline=False
            )
            embed.add_field(
                name="Причина отказа",
                value=rejection_reason,
                inline=False
            )
            
            # Update message with rejected view
            rejected_view = RejectedApplicationView()
            await original_message.edit(content="", embed=embed, view=rejected_view)
              # Send DM to user with rejection reason
            if user:
                await self._send_rejection_dm_with_reason(user, rejection_reason)
            
        except Exception as e:
            print(f"Error in _finalize_rejection_with_reason: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при финализации отказа.",
                ephemeral=True
            )
    
    async def _send_rejection_dm_with_reason(self, user, rejection_reason):
        """Send rejection DM to user with specified reason"""
        try:
            app_type = "военную" if self.application_data.get("type") == "military" else "гражданскую"
            
            dm_content = (
                f"## ❌ Ваша заявка на получение ролей была **отклонена**\n"
                f"**Причина отказа:** {rejection_reason}\n\n"
                "Вы можете подать новую заявку, устранив указанные недостатки."
            )
            
            await user.send(dm_content)
        except discord.Forbidden:
            # User has DMs disabled
            pass
        except Exception as e:
            print(f"Error sending rejection DM: {e}")
    
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
            
        except discord.Forbidden as e:            print(f"Warning: No permission to change nickname for {user}")
            # Don't raise the error, just log it
        except Exception as e:
            print(f"Error setting nickname for {user}: {e}")
            # Don't raise the error, just log it
    
    async def _create_approval_embed(self, interaction=None, original_message=None, moderator_info=None):
        """Create approval embed with status"""
        if interaction:
            # Use interaction message and user
            embed = interaction.message.embeds[0]
            moderator_mention = interaction.user.mention
        elif original_message:
            # Use original message and moderator_info
            embed = original_message.embeds[0] if original_message.embeds else None
            if not embed:
                # Fallback: create a basic embed
                embed = discord.Embed(
                    title="✅ Заявка одобрена",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                # Copy existing fields if we have original message
                if original_message and original_message.embeds:
                    original_embed = original_message.embeds[0]
                    for field in original_embed.fields:
                        embed.add_field(name=field.name, value=field.value, inline=field.inline)
            else:
                # Copy the original embed and modify it
                new_embed = discord.Embed(
                    title=embed.title,
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                # Copy existing fields
                for field in embed.fields:
                    new_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                embed = new_embed
            
            moderator_mention = moderator_info if moderator_info else "неизвестным модератором"
        else:
            raise ValueError("Either interaction or original_message must be provided")
        
        embed.color = discord.Color.green()
        
        if self.application_data["type"] == "military":
            if self._should_process_personnel():
                status_message = f"Одобрено инструктором ВК {moderator_mention}"
            else:
                status_message = f"Одобрено инструктором ВК {moderator_mention}\n⚠️ Требуется ручная обработка для звания {self.application_data.get('rank', 'Неизвестно')}"
        else:
            status_message = f"Одобрено руководством бригады ( {moderator_mention} )"
        
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
            if interaction.response.is_done():                # Interaction already responded, use followup
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
    
    async def _handle_moderator_authorization(self, interaction, user, guild, config):
        """Handle moderator authorization flow and return signed_by_name if successful."""
        from utils.moderator_auth import ModeratorAuthHandler
        
        # Use unified authorization handler
        signed_by_name = await ModeratorAuthHandler.handle_moderator_authorization(
            interaction,
            self._continue_approval_with_manual_auth,
            user, guild, config, interaction.message
        )
        
        if signed_by_name:
            # Show processing state with just button change
            processing_view = ProcessingApplicationView()
            if interaction.response.is_done():
                await interaction.edit_original_response(view=processing_view)
            else:
                await interaction.response.edit_message(view=processing_view)
        return signed_by_name
    
    async def _continue_approval_with_manual_auth(self, interaction, moderator_data, user, guild, config, original_message):
        """Continue approval process after manual moderator authorization"""
        try:
            # Extract signed_by_name from moderator_data
            signed_by_name = moderator_data['full_info'] if isinstance(moderator_data, dict) else moderator_data
            await self._continue_approval_process_with_message(original_message, user, guild, config, signed_by_name)
        except Exception as e:
            print(f"Error in manual auth continuation: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при продолжении обработки заявки.",
                ephemeral=True
            )
    async def _continue_approval_process(self, interaction, user, guild, config, signed_by_name):
        """Continue with approval processing after authorization is successful"""
        try:            # First show processing state
            processing_view = ProcessingApplicationView()
            if interaction.response.is_done():
                await interaction.edit_original_response(view=processing_view)
            else:
                await interaction.response.edit_message(view=processing_view)
            
            # Small delay to show processing state
            await asyncio.sleep(0.5)
            
            # Then do all the processing
            try:
                # Assign roles and update nickname if needed
                await self._assign_roles(user, guild, config)
            except Exception as e:
                print(f"Warning: Error in role assignment: {e}")
                # Continue processing even if role assignment fails
                
            # Only do personnel processing for military recruits with rank 'рядовой'
            if self._should_process_personnel():
                try:
                    await self._handle_auto_processing_with_auth(user, guild, config, signed_by_name)
                except Exception as e:
                    print(f"Warning: Error in personnel processing: {e}")
                    # Continue processing even if personnel processing fails
            
            # Send DM to user
            try:
                await self._send_approval_dm(user)
            except Exception as e:
                print(f"Warning: Error sending DM: {e}")
                # Continue even if DM fails
                # # Finally, create final embed and update to approved state
            embed = await self._create_approval_embed(interaction)
            approved_view = ApprovedApplicationView()
            await interaction.edit_original_response(content="", embed=embed, view=approved_view)
                
        except Exception as e:
            print(f"Error in approval process continuation: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ Произошла ошибка при обработке заявки.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ Произошла ошибка при обработке заявки.",
                        ephemeral=True
                    )
            except Exception as followup_error:
                print(f"Failed to send error message: {followup_error}")
    
    async def _handle_auto_processing_with_auth(self, user, guild, config, signed_by_name):
        """Handle automatic processing with pre-authorized moderator"""
        try:
            hiring_time = datetime.now(timezone.utc)
            
            # Log to Google Sheets
            sheets_success = await sheets_manager.add_hiring_record(
                self.application_data,
                user,
                None,  # moderator_user not needed since we have signed_by_name
                hiring_time,
                override_moderator_info=signed_by_name
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
            print(f"Warning: Error in auto processing with auth: {e}")
            # Don't raise exception to prevent approval process from failing
    
    async def _continue_approval_process_with_message(self, original_message, user, guild, config, signed_by_name):
        """Continue with approval processing using original message instead of modal interaction"""
        try:
            # First show processing state
            processing_view = ProcessingApplicationView()
            await original_message.edit(view=processing_view)
            
            # Small delay to show processing state
            await asyncio.sleep(0.5)
            
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
                    await self._handle_auto_processing_with_auth(user, guild, config, signed_by_name)
                except Exception as e:
                    print(f"Warning: Error in personnel processing: {e}")
                    # Continue processing even if personnel processing fails
              # Send DM to user
            try:
                await self._send_approval_dm(user)
            except Exception as e:
                print(f"Warning: Error sending DM: {e}")
                # Continue even if DM fails
            
            # Finally, create final embed and update to approved state
            embed = await self._create_approval_embed(original_message=original_message, moderator_info=signed_by_name)
            approved_view = ApprovedApplicationView()
            await original_message.edit(content="", embed=embed, view=approved_view)
                
        except Exception as e:
            print(f"Error in approval process with message: {e}")
            # Can't send error message to user since we don't have interaction here
            # Error is already logged
