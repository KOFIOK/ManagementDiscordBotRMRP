"""
Dismissal system views
Contains interactive components (buttons and views) for dismissal reports
"""

import discord
from discord import ui
import asyncio
import re
import discord
from discord import ui
import asyncio
import re
import traceback
from datetime import datetime
from utils.config_manager import load_config, is_moderator_or_admin, can_moderate_user, get_dismissal_message_link
from utils.rank_utils import get_rank_from_roles_postgresql
from utils.nickname_manager import nickname_manager


# Constants for UI elements and messages
class DismissalConstants:
    # UI Labels
    PROCESSING_LABEL = "⏳ Обрабатывается..."
    APPROVED_LABEL = "✅ Одобрено"
    REJECTED_LABEL = "❌ Отказано"
    
    # Error Messages
    NO_PERMISSION_APPROVAL = "❌ У вас нет прав для одобрения рапортов на увольнение. Только модераторы могут выполнять это действие."
    NO_PERMISSION_REJECTION = "❌ У вас нет прав для отказа рапортов на увольнение. Только модераторы могут выполнять это действие."
    AUTHORIZATION_ERROR = "❌ Ошибка проверки авторизации модератора."
    GENERAL_ERROR = "❌ Произошла ошибка при обработке рапорта. Пожалуйста, обратитесь к администратору."
    PROCESSING_ERROR_APPROVAL = "❌ Произошла ошибка при обработке одобрения заявки."
    PROCESSING_ERROR_REJECTION = "❌ Произошла ошибка при обработке отказа"
    AUTH_DATA_ERROR = "❌ Произошла ошибка при обработке данных авторизации."
    DISMISSAL_PROCESSING_ERROR = "❌ Произошла ошибка при обработке увольнения."
    
    # Success Messages
    STATIC_RECEIVED = "✅ Статик получен, продолжаем обработку..."
    
    # Form Field Names
    FIELD_NAME = "Имя Фамилия"
    FIELD_STATIC = "Статик"
    FIELD_DEPARTMENT = "Подразделение"
    FIELD_RANK = "Воинское звание"
    FIELD_REASON = "Причина увольнения"
    
    # Automatic Report Indicators
    AUTO_REPORT_INDICATOR = "🚨 Автоматический рапорт на увольнение"
    STATIC_INPUT_REQUIRED = "Требуется ввод"


class ProcessingApplicationView(discord.ui.View):
    """View that shows processing state - prevents double clicks on approval buttons"""
    
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="🔄 Обрабатывается...",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            custom_id="processing_application"
        ))


def add_dismissal_footer_to_embed(embed, guild_id=None):
    """Add footer with dismissal submission link to embed - TEMPORARILY DISABLED"""
    # TODO: Discord footers don't support clickable links
    # Need to find alternative solution (description, separate message, etc.)
    return embed
    
    # Nickname Prefixes
    DISMISSED_PREFIX = "Уволен | "
    
    # Self-moderation errors
    SELF_APPROVAL_ERROR = "Вы не можете одобрить свой собственный рапорт на увольнение."
    SELF_REJECTION_ERROR = "Вы не можете отклонить свой собственный рапорт на увольнение."
    MODERATOR_HIERARCHY_APPROVAL = "Вы не можете одобрить рапорт модератора того же или более высокого уровня."
    MODERATOR_HIERARCHY_REJECTION = "Вы не можете отклонить рапорт модератора того же или более высокого уровня."
    INSUFFICIENT_PERMISSIONS_APPROVAL = "У вас недостаточно прав для одобрения этого рапорта."
    INSUFFICIENT_PERMISSIONS_REJECTION = "У вас недостаточно прав для отклонения этого рапорта."
    
    # Footer and audit text patterns
    REPORT_SENDER_PREFIX = "Отправлено:"
    AUDIT_NAME_STATIC_FIELD = "Имя Фамилия | 6 цифр статика"
    
    # Default values
    UNKNOWN_VALUE = "Неизвестно"
    
    # Rejection button label
    REJECT_BUTTON_LABEL = "❌ Отказать"


class DismissalReportButton(ui.View):
    """Simplified button view for creating dismissal reports with reason selection"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="ПСЖ", style=discord.ButtonStyle.red, custom_id="dismissal_report_psj", emoji="📋")
    async def dismissal_report_psj(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle PSJ (По собственному желанию) dismissal"""
        from .modals import SimplifiedDismissalModal
        modal = await SimplifiedDismissalModal.create_with_user_data(interaction.user.id, "ПСЖ")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Перевод", style=discord.ButtonStyle.secondary, custom_id="dismissal_report_transfer", emoji="🔄")
    async def dismissal_report_transfer(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle transfer dismissal"""
        from .modals import SimplifiedDismissalModal
        modal = await SimplifiedDismissalModal.create_with_user_data(interaction.user.id, "Перевод")
        await interaction.response.send_modal(modal)


class SimplifiedDismissalApprovalView(ui.View):
    """Simplified approval view for dismissal reports without complex authorization"""
    
    def __init__(self, user_id=None):
        super().__init__(timeout=None)
        self.user_id = user_id
    
    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.green, custom_id="approve_dismissal_simple")
    async def approve_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Simplified dismissal approval"""
        try:
            # Check permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    "❌ У вас нет прав для одобрения рапортов на увольнение.",
                    ephemeral=True
                )
                return
            
            # Get target user
            target_user = interaction.guild.get_member(self.user_id) if self.user_id else None
            if not target_user:
                # User left server - create mock user object
                target_user = type('MockUser', (), {
                    'id': self.user_id,
                    'display_name': 'Покинул сервер',
                    'mention': f'<@{self.user_id}>',
                    '_is_mock': True
                })()
            
            # Check moderator hierarchy - can this moderator approve this user's dismissal?
            if not can_moderate_user(interaction.user, target_user, config):
                await interaction.response.send_message(
                    "❌ Вы не можете одобрить увольнение этого пользователя из-за иерархии модераторов.",
                    ephemeral=True
                )
                return
            
            # Check if user is already dismissed (not in employees table)
            if not getattr(target_user, '_is_mock', False):  # Only check if user is still on server
                try:
                    from utils.database_manager import PersonnelManager
                    pm = PersonnelManager()
                    personnel_data = await pm.get_personnel_summary(target_user.id)
                    
                    if not personnel_data:
                        # User not found in employees table - already dismissed
                        await interaction.response.defer(ephemeral=False)
                        await self._auto_reject_already_dismissed(interaction, target_user)
                        return
                        
                except Exception as e:
                    print(f"❌ Error checking personnel status: {e}")
                    await interaction.response.send_message(
                        "❌ Ошибка проверки статуса пользователя в базе данных.",
                        ephemeral=True
                    )
                    return
            
            # Show processing state to prevent double clicks
            processing_view = ProcessingApplicationView()
            await interaction.response.edit_message(view=processing_view)
            
            # Small delay to ensure UI update
            await asyncio.sleep(0.5)
            
            # Extract form data from embed
            embed = interaction.message.embeds[0]
            form_data = {}
            
            for field in embed.fields:
                if field.name == "Имя Фамилия":
                    form_data['name'] = field.value
                elif field.name == "Статик":
                    form_data['static'] = field.value
                elif field.name == "Причина увольнения":
                    form_data['reason'] = field.value
                elif field.name == "Воинское звание":
                    form_data['rank'] = field.value
                elif field.name == "Подразделение":
                    form_data['department'] = field.value
                elif field.name == "Должность":
                    form_data['position'] = field.value
            
            # Process dismissal through PersonnelManager
            success = await self._process_simplified_dismissal(
                interaction, target_user, form_data, config
            )
            
            if success:
                # Update embed to show approval
                embed.color = discord.Color.green()
                embed.add_field(
                    name="Обработано",
                    value=f"Сотрудник: {interaction.user.mention}\nВремя: {discord.utils.format_dt(discord.utils.utcnow(), 'F')}",
                    inline=False
                )
                
                # Add dismissal footer with link to submit new applications
                embed = add_dismissal_footer_to_embed(embed, interaction.guild.id)
                
                # Create approved view (disabled button)
                approved_view = ui.View(timeout=None)
                approved_button = ui.Button(
                    label="✅ Одобрено",
                    style=discord.ButtonStyle.green,
                    disabled=True
                )
                approved_view.add_item(approved_button)
                
                # Update message - очищаем content от пингов
                await interaction.edit_original_response(
                    content=None,  # Очищаем content
                    embed=embed, 
                    view=approved_view
                )
            
        except Exception as e:
            print(f"❌ Error in simplified dismissal approval: {e}")
            try:
                await interaction.followup.send(
                    "❌ Произошла ошибка при обработке увольнения.",
                    ephemeral=True
                )
            except:
                pass
    
    @discord.ui.button(label="❌ Отказать", style=discord.ButtonStyle.red, custom_id="reject_dismissal_simple")
    async def reject_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Simplified dismissal rejection"""
        try:
            # Check permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    "❌ У вас нет прав для отказа рапортов на увольнение.",
                    ephemeral=True
                )
                return
            
            # Get target user for hierarchy check
            target_user = interaction.guild.get_member(self.user_id) if self.user_id else None
            if not target_user:
                # User left server - create mock user object
                target_user = type('MockUser', (), {
                    'id': self.user_id,
                    'display_name': 'Покинул сервер',
                    'mention': f'<@{self.user_id}>',
                    '_is_mock': True
                })()
            
            # Check moderator hierarchy - can this moderator reject this user's dismissal?
            if not can_moderate_user(interaction.user, target_user, config):
                await interaction.response.send_message(
                    "❌ Вы не можете отклонить увольнение этого пользователя из-за иерархии модераторов.",
                    ephemeral=True
                )
                return
            
            # Show rejection reason input modal
            from .modals import RejectionReasonModal
            rejection_modal = RejectionReasonModal(
                callback_func=self._handle_rejection_callback,
                original_message=interaction.message
            )
            await interaction.response.send_modal(rejection_modal)
            
        except Exception as e:
            print(f"❌ Error in simplified dismissal rejection: {e}")
            try:
                await interaction.response.send_message(
                    "❌ Произошла ошибка при отказе.",
                    ephemeral=True
                )
            except:
                pass
    
    async def _auto_reject_already_dismissed(self, interaction, target_user):
        """Automatically reject dismissal if user is already dismissed"""
        try:
            # Update embed to show automatic rejection
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.add_field(
                name="❌ Причина отклонения",
                value="Пользователь ранее был уволен",
                inline=False
            )
            embed.add_field(
                name="👤 Модератор",
                value=f"🤖 Система",
                inline=False
            )
            embed.add_field(
                name="⏰ Дата обработки",
                value=f"<t:{int(datetime.now().timestamp())}:F>",
                inline=False
            )
            
            # Add dismissal footer with link to submit new applications
            embed = add_dismissal_footer_to_embed(embed, interaction.guild.id)
            
            # Disable all buttons
            view = SimplifiedDismissalApprovalView(user_id=target_user.id)
            view.approve_dismissal.disabled = True
            view.reject_dismissal.disabled = True
            view.approve_dismissal.label = "✅ Автоматически отклонено"
            view.reject_dismissal.label = "❌ Отказано"
            
            # Update message
            await interaction.edit_original_response(
                embed=embed,
                view=view
            )
            
            print(f"🤖 AUTO-REJECT: {target_user.display_name} ({target_user.id}) - already dismissed")
            
        except Exception as e:
            print(f"❌ Error in auto-reject for already dismissed user: {e}")
            await interaction.followup.send(
                "❌ Ошибка при автоматическом отклонении заявки.",
                ephemeral=True
            )
    
    async def _handle_rejection_callback(self, interaction, reason, target_user, original_message):
        """Handle rejection callback from RejectionReasonModal"""
        try:
            # Update embed to show rejection
            embed = original_message.embeds[0]
            embed.color = discord.Color.red()
            embed.add_field(
                name="Отказано",
                value=f"Модератор: {interaction.user.mention}\nПричина: {reason}\nВремя: {discord.utils.format_dt(discord.utils.utcnow(), 'F')}",
                inline=False
            )
            
            # Add dismissal footer with link to submit new applications
            embed = add_dismissal_footer_to_embed(embed, interaction.guild.id)
            
            # Create rejected view (disabled button)
            rejected_view = ui.View(timeout=None)
            rejected_button = ui.Button(
                label="❌ Отказано",
                style=discord.ButtonStyle.red,
                disabled=True
            )
            rejected_view.add_item(rejected_button)
            
            # Update message - очищаем content от пингов
            await original_message.edit(
                content=None,  # Очищаем content
                embed=embed, 
                view=rejected_view
            )
            
            # Notify user if still on server
            if self.user_id:
                target_user = interaction.guild.get_member(self.user_id)
                if target_user:
                    try:
                        await target_user.send(
                            f"❌ **Ваш рапорт на увольнение был отклонен**\n"
                            f"Модератор: {interaction.user.display_name}\n"
                            f"Причина: {reason}"
                        )
                    except:
                        pass
                        
        except Exception as e:
            print(f"❌ Error in rejection callback: {e}")
    
    @discord.ui.button(label="🗑️ Удалить", style=discord.ButtonStyle.grey, custom_id="delete_dismissal_simple")
    async def delete_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Удаление рапорта (только автор или администратор)"""
        try:
            # Check permissions - only author or administrators
            config = load_config()
            is_author = (self.user_id and interaction.user.id == self.user_id)
            is_admin = (interaction.user.guild_permissions.administrator or 
                       any(role.name.lower() in ['администратор', 'admin'] for role in interaction.user.roles))
            
            if not (is_author or is_admin):
                await interaction.response.send_message(
                    "❌ Удалять рапорт может только его автор или администратор.",
                    ephemeral=True
                )
                return
            
            # Delete the message
            await interaction.response.send_message(
                "✅ Рапорт удалён.",
                ephemeral=True
            )
            await interaction.message.delete()
            
        except Exception as e:
            print(f"❌ Error in dismissal deletion: {e}")
            try:
                await interaction.response.send_message(
                    "❌ Произошла ошибка при удалении.",
                    ephemeral=True
                )
            except:
                pass
    
    async def _process_simplified_dismissal(self, interaction, target_user, form_data, config):
        """Process dismissal using PersonnelManager and Discord actions"""
        try:
            user_has_left_server = getattr(target_user, '_is_mock', False)
            
            # 1. Process through PersonnelManager
            if not user_has_left_server:
                try:
                    from utils.database_manager import PersonnelManager
                    pm = PersonnelManager()
                    
                    dismissal_data = {
                        'reason': form_data.get('reason', ''),
                        'static': form_data.get('static', ''),
                        'name': form_data.get('name', target_user.display_name)
                    }
                    
                    success, message = await pm.process_personnel_dismissal(
                        target_user.id,
                        dismissal_data,
                        interaction.user.id,
                        interaction.user.display_name
                    )
                    
                    if not success:
                        print(f"⚠️ PersonnelManager dismissal failed: {message}")
                        await interaction.followup.send(
                            f"⚠️ **Внимание:** {message}",
                            ephemeral=True
                        )
                    else:
                        print(f"✅ PersonnelManager dismissal successful: {message}")
                        
                except Exception as e:
                    print(f"❌ Error in PersonnelManager dismissal: {e}")
            
            # 2. Remove Discord roles (if user still on server)
            if not user_has_left_server:
                excluded_roles_ids = config.get('excluded_roles', [])
                roles_to_remove = []
                
                for role in target_user.roles:
                    if not role.is_default() and role.id not in excluded_roles_ids:
                        roles_to_remove.append(role)
                
                if roles_to_remove:
                    try:
                        await target_user.remove_roles(*roles_to_remove, reason="Рапорт на увольнение одобрен")
                        print(f"✅ Removed {len(roles_to_remove)} roles from {target_user.display_name}")
                    except Exception as e:
                        print(f"❌ Failed to remove roles: {e}")
            
            # 3. Change nickname using nickname_manager (if user still on server)
            if not user_has_left_server:
                try:
                    reason = form_data.get('reason', 'Уволен')
                    provided_name = form_data.get('name', target_user.display_name)
                    
                    print(f"🎆 NICKNAME INTEGRATION: Увольнение {target_user.display_name} -> {provided_name} (причина: {reason})")
                    
                    # Используем nickname_manager для автоматической обработки никнейма
                    new_nickname = await nickname_manager.handle_dismissal(
                        member=target_user,
                        reason=reason,
                        provided_name=provided_name
                    )
                    
                    if new_nickname:
                        await target_user.edit(nick=new_nickname, reason="Рапорт на увольнение одобрен")
                        print(f"✅ NICKNAME MANAGER: Успешно установлен никнейм {target_user} -> {new_nickname}")
                    else:
                        # Fallback к старому методу
                        fallback_nickname = f"Уволен | {provided_name}"
                        await target_user.edit(nick=fallback_nickname, reason="Рапорт на увольнение одобрен")
                        print(f"⚠️ NICKNAME FALLBACK: Использовали fallback никнейм: {fallback_nickname}")
                        
                except Exception as e:
                    print(f"❌ Failed to change nickname: {e}")
            
            # 4. Send audit notification and get URL for blacklist evidence
            audit_message_url = await self._send_audit_notification(interaction, target_user, form_data, config)
            
            # 5. Send DM to user (if still on server)
            if not user_has_left_server:
                try:
                    await target_user.send(
                        f"✅ **Ваш рапорт на увольнение был одобрен**\n"
                        f"Модератор: {interaction.user.display_name}\n"
                        f"С вас были сняты все роли."
                    )
                except:
                    pass  # User has DMs disabled
            
            return True
            
        except Exception as e:
            print(f"❌ Error in simplified dismissal processing: {e}")
            return False
    
    async def _send_audit_notification(self, interaction, target_user, form_data, config):
        """Send notification to audit channel and return message URL for blacklist evidence"""
        try:
            from utils.audit_logger import audit_logger, AuditAction
            from utils.postgresql_pool import get_db_cursor
            
            # Prepare personnel data for audit logger
            personnel_data = {
                'name': form_data.get('name', 'Неизвестно'),
                'static': form_data.get('static', ''),
                'rank': form_data.get('rank', 'Неизвестно'),
                'department': form_data.get('department', 'Неизвестно'),
                'reason': form_data.get('reason', '')
            }
            
            # Send audit notification using centralized logger and get message URL
            audit_message_url = await audit_logger.send_personnel_audit(
                guild=interaction.guild,
                action=await AuditAction.DISMISSAL(),
                target_user=target_user,
                moderator=interaction.user,
                personnel_data=personnel_data,
                config=config
            )
            
            # Get personnel_id for auto-blacklist check
            try:
                with get_db_cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM personnel WHERE discord_id = %s;",
                        (target_user.id,)
                    )
                    result = cursor.fetchone()
                    
                    if result:
                        personnel_id = result['id']
                        
                        # Check and send auto-blacklist if needed (with audit URL as evidence)
                        was_blacklisted = await audit_logger.check_and_send_auto_blacklist(
                            guild=interaction.guild,
                            target_user=target_user,
                            moderator=interaction.user,
                            personnel_id=personnel_id,
                            personnel_data=personnel_data,
                            audit_message_url=audit_message_url,  # Pass audit URL as evidence
                            config=config
                        )
                        
                        if was_blacklisted:
                            print(f"✅ Auto-blacklist triggered for {personnel_data.get('name')}")
                    else:
                        print(f"⚠️ Personnel not found in DB for auto-blacklist check: {target_user.id}")
                        
            except Exception as blacklist_error:
                print(f"⚠️ Error in auto-blacklist check: {blacklist_error}")
                # Don't fail the whole dismissal if blacklist check fails
            
            return audit_message_url
            
        except Exception as e:
            print(f"❌ Error sending audit notification: {e}")
            return None

class DeletionConfirmationView(ui.View):
    """Confirmation view for deletion actions"""
    
    def __init__(self, original_message: discord.Message, user_name: str):
        super().__init__(timeout=60)
        self.original_message = original_message
        self.user_name = user_name
        self.confirmed = None  # None = timeout, True = confirmed, False = cancelled
    
    @discord.ui.button(label="Да, удалить", style=discord.ButtonStyle.red, emoji="🗑️")
    async def confirm_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        try:
            # Delete the original message
            await self.original_message.delete()
            
            # Send ephemeral confirmation
            await interaction.response.send_message(
                f"✅ Рапорт на увольнение пользователя {self.user_name} был удален.",
                ephemeral=True
            )
            
        except discord.NotFound:
            await interaction.response.send_message(
                "❌ Сообщение уже было удалено.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Нет прав для удаления этого сообщения.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Произошла ошибка при удалении: {str(e)}",
                ephemeral=True
            )
        finally:
            self.stop()
    
    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.secondary)
    async def cancel_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        # Просто закрываем диалог без дополнительных сообщений
        await interaction.response.edit_message(view=None)
        self.stop()


class AutomaticDismissalApprovalView(ui.View):
    """
    Special view for automatic dismissal reports with three buttons: Approve, Reject, Edit
    
    This view is persistent (survives bot restarts) due to:
    - timeout=None (never expires)
    - custom_id on all buttons
    - Registration in app.py as persistent view
    """
    
    def __init__(self, user_id=None):
        super().__init__(timeout=None)
        self.user_id = user_id
    
    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.green, custom_id="auto_approve_dismissal")
    async def approve_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle approval of automatic dismissal report"""
        try:
            # Check moderator permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                embed = discord.Embed(
                    title="❌ Недостаточно прав",
                    description="У вас нет прав для рассмотрения автоматических рапортов на увольнение.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Extract target user for hierarchy check
            target_user = await self._extract_target_user_from_embed(interaction)
            if target_user:
                # Check moderator hierarchy
                if not can_moderate_user(interaction.user, target_user, config):
                    await interaction.response.send_message(
                        "❌ Вы не можете одобрить увольнение этого пользователя из-за иерархии модераторов.",
                        ephemeral=True
                    )
                    return
                
                # Check if user is already dismissed (not in employees table)
                if not getattr(target_user, '_is_mock', False):  # Only check if user is still on server
                    try:
                        from utils.database_manager import PersonnelManager
                        pm = PersonnelManager()
                        personnel_data = await pm.get_personnel_summary(target_user.id)
                        
                        if not personnel_data:
                            # User not found in employees table - already dismissed
                            await interaction.response.defer(ephemeral=False)
                            await self._auto_reject_already_dismissed_automatic(interaction, target_user)
                            return
                            
                    except Exception as e:
                        print(f"❌ Error checking personnel status: {e}")
                        await interaction.response.send_message(
                            "❌ Ошибка проверки статуса пользователя в базе данных.",
                            ephemeral=True
                        )
                        return
            
            # Extract and check static before proceeding
            current_data = self._extract_current_data_from_embed(interaction)
            static_value = current_data.get('static', '')
            
            # Check if static is missing or invalid
            if not static_value or static_value.strip() in ['', 'Не найден в реестре']:
                await interaction.response.send_message(
                    "❌ **Невозможно одобрить рапорт без статика!**\n\n"
                    "Пожалуйста, нажмите кнопку **✏️ Изменить** и заполните статик, "
                    "прежде чем одобрять рапорт.",
                    ephemeral=True
                )
                return
            
            # Show processing state to prevent double clicks
            processing_view = ProcessingApplicationView()
            await interaction.response.edit_message(view=processing_view)
            
            # Small delay to ensure UI update
            await asyncio.sleep(0.5)
            
            # Extract user information from embed description
            target_user = await self._extract_target_user_from_embed(interaction)
            
            if not target_user:
                await interaction.followup.send(
                    "❌ Не удалось извлечь информацию о пользователе из рапорта.",
                    ephemeral=True
                )
                return
            
            # Proceed with standard dismissal approval process
            await self._process_automatic_dismissal_approval(interaction, target_user, config)
            
        except Exception as e:
            print(f"Error in automatic dismissal approval: {e}")
            # Try followup first, then response as fallback
            try:
                await interaction.followup.send(
                    "❌ Произошла ошибка при одобрении автоматического рапорта.",
                    ephemeral=True
                )
            except:
                try:
                    await interaction.response.send_message(
                        "❌ Произошла ошибка при одобрении автоматического рапорта.",
                        ephemeral=True
                    )
                except:
                    pass
    
    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.red, custom_id="auto_reject_dismissal")
    async def reject_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle rejection of automatic dismissal report"""
        try:
            # Check moderator permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                embed = discord.Embed(
                    title="❌ Недостаточно прав",
                    description="У вас нет прав для рассмотрения автоматических рапортов на увольнение.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Extract target user for hierarchy check
            target_user = await self._extract_target_user_from_embed(interaction)
            if target_user:
                # Check moderator hierarchy
                if not can_moderate_user(interaction.user, target_user, config):
                    await interaction.response.send_message(
                        "❌ Вы не можете отклонить увольнение этого пользователя из-за иерархии модераторов.",
                        ephemeral=True
                    )
                    return
            
            # Request rejection reason first (before showing processing state)
            from .modals import RejectionReasonModal
            modal = RejectionReasonModal(None, interaction.message, self)  # Pass message and view instead of callback
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"Error in automatic dismissal rejection: {e}")
            # Try response as fallback
            try:
                await interaction.response.send_message(
                    "❌ Произошла ошибка при отклонении автоматического рапорта.",
                    ephemeral=True
                )
            except:
                pass
    
    async def _auto_reject_already_dismissed_automatic(self, interaction, target_user):
        """Automatically reject automatic dismissal if user is already dismissed"""
        try:
            # Update embed to show automatic rejection
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.add_field(
                name="📋 Статус заявки",
                value="❌ **АВТОМАТИЧЕСКИ ОТКЛОНЕНО**",
                inline=False
            )
            embed.add_field(
                name="❌ Причина отклонения",
                value="Пользователь ранее был уволен (не найден в базе данных сотрудников)",
                inline=False
            )
            embed.add_field(
                name="👤 Модератор",
                value=f"🤖 Система (автоматическая проверка)",
                inline=False
            )
            embed.add_field(
                name="⏰ Дата обработки",
                value=f"<t:{int(datetime.now().timestamp())}:F>",
                inline=False
            )
            
            # Add dismissal footer with link to submit new applications
            embed = add_dismissal_footer_to_embed(embed, interaction.guild.id)
            
            # Disable all buttons
            view = AutomaticDismissalApprovalView(user_id=target_user.id)
            view.approve_dismissal.disabled = True
            view.reject_dismissal.disabled = True
            view.edit_dismissal.disabled = True
            view.approve_dismissal.label = "✅ Автоматически отклонено"
            view.reject_dismissal.label = "❌ Отказано"
            view.edit_dismissal.label = "✏️ Изменить (недоступно)"
            
            # Update message
            await interaction.edit_original_response(
                embed=embed,
                view=view
            )
            
            print(f"🤖 AUTO-REJECT AUTOMATIC: {target_user.display_name} ({target_user.id}) - already dismissed")
            
        except Exception as e:
            print(f"❌ Error in auto-reject for already dismissed user (automatic): {e}")
            await interaction.followup.send(
                "❌ Ошибка при автоматическом отклонении заявки.",
                ephemeral=True
            )
    
    @discord.ui.button(label="✏️ Изменить", style=discord.ButtonStyle.secondary, custom_id="auto_edit_dismissal")
    async def edit_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle editing of automatic dismissal report data"""
        try:
            # Check moderator permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                embed = discord.Embed(
                    title="❌ Недостаточно прав",
                    description="У вас нет прав для редактирования автоматических рапортов на увольнение.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Extract current data from embed
            current_data = self._extract_current_data_from_embed(interaction)
            
            # Show edit modal
            from .modals import AutomaticDismissalEditModal
            modal = AutomaticDismissalEditModal(current_data, interaction.message, self)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"Error in automatic dismissal edit: {e}")
            # Try followup first, then response as fallback
            try:
                await interaction.followup.send(
                    "❌ Произошла ошибка при редактировании автоматического рапорта.",
                    ephemeral=True
                )
            except:
                try:
                    await interaction.response.send_message(
                        "❌ Произошла ошибка при редактировании автоматического рапорта.",
                        ephemeral=True
                    )
                except:
                    pass
    
    @discord.ui.button(label="🗑️ Удалить", style=discord.ButtonStyle.grey, custom_id="auto_delete_dismissal")
    async def delete_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete automatic dismissal report (author or admins only)"""
        try:
            # Check deletion permissions (using same method as main class)
            if not await self._check_delete_permissions(interaction):
                error_message = await self._get_delete_permission_error_message(interaction)
                await interaction.response.send_message(error_message, ephemeral=True)
                return
            
            # Extract report information for confirmation
            target_user = await self._extract_target_user_from_embed(interaction)
            current_data = self._extract_current_data_from_embed(interaction)
            
            # Create confirmation embed
            confirmation_embed = discord.Embed(
                title="⚠️ Подтверждение удаления",
                description=(
                    f"Вы действительно хотите **удалить** автоматический рапорт на увольнение?\n\n"
                    f"**Увольняемый:** {target_user.display_name if target_user else 'Неизвестно'}\n"
                    f"**Имя Фамилия:** {current_data.get('name', 'Неизвестно')}\n"
                    f"**Статик:** {current_data.get('static', 'Неизвестно')}\n"
                    f"**Причина:** {current_data.get('reason', 'Неизвестно')}\n\n"
                    f"⚠️ **Это действие нельзя отменить!**"
                ),
                color=discord.Color.orange()
            )
            
            # Add dismissal footer with link to submit new applications
            confirmation_embed = add_dismissal_footer_to_embed(confirmation_embed, interaction.guild.id)
            
            # Create confirmation view
            confirmation_view = DeletionConfirmationView(
                interaction.message, 
                target_user.display_name if target_user else "Неизвестный пользователь"
            )
            await interaction.response.send_message(
                embed=confirmation_embed,
                view=confirmation_view,
                ephemeral=True
            )
            
            # Wait for confirmation
            await confirmation_view.wait()
            
            # Process result based on confirmation state
            if confirmation_view.confirmed is True:
                # Deletion confirmed and already processed in DeletionConfirmationView
                pass  # No additional action needed
            elif confirmation_view.confirmed is False:
                # Deletion cancelled - dialog already closed, no additional message needed
                pass  # No additional action needed
            else:
                # Timeout occurred
                await interaction.edit_original_response(
                    content="⏰ Время ожидания истекло. Удаление отменено.",
                    embed=None,
                    view=None
                )
        
        except Exception as e:
            await self._handle_deletion_error(interaction, e)

    async def _extract_target_user_from_embed(self, interaction):
        """Extract target user from embed description (mention)"""
        try:
            embed = interaction.message.embeds[0]
            description = embed.description
            
            # Extract user ID from mention in description
            import re
            user_mention_pattern = r'<@(\d+)>'
            match = re.search(user_mention_pattern, description)
            if match:
                user_id = int(match.group(1))
                # Try to get member object (may be None if user left)
                target_user = interaction.guild.get_member(user_id)
                
                if not target_user:
                    # Create mock user for users who left
                    class MockUser:
                        def __init__(self, user_id, name):
                            self.id = user_id
                            self.name = name
                            self.display_name = name
                            self.mention = f"<@{user_id}>"
                            self.roles = []
                            self._is_mock = True
                        
                        def __str__(self):
                            return self.display_name
                    
                    target_user = MockUser(user_id, "Покинувший пользователь")
                return target_user
            
            return None
            
        except Exception as e:
            print(f"Error extracting target user: {e}")
            return None
    
    def _extract_current_data_from_embed(self, interaction):
        """Extract current data from embed fields"""
        try:
            embed = interaction.message.embeds[0]
            data = {}
            
            for field in embed.fields:
                if field.name == "Имя Фамилия":
                    data['name'] = field.value
                elif field.name == "Статик":
                    data['static'] = field.value
                elif field.name == "Подразделение":
                    data['department'] = field.value
                elif field.name == "Воинское звание":
                    data['rank'] = field.value
            
            return data            
        except Exception as e:
            print(f"Error extracting current data: {e}")
            return {}
    
    async def _check_delete_permissions(self, interaction: discord.Interaction) -> bool:
        """
        Check if the user has permission to delete the automatic dismissal report.
        Permissions: Discord admins or config admins (no author for automatic reports).
        """
        try:
            # Check if user has Discord admin permissions
            if interaction.user.guild_permissions.administrator:
                return True
            
            # Check if user is in config admins
            try:
                config = load_config()
                admins = config.get('moderators', {}).get('admins', [])
                if interaction.user.id in admins:
                    return True
            except Exception:
                # If config loading fails, fall back to Discord permissions only
                pass
            
            return False
            
        except Exception:
            return False

    async def _get_delete_permission_error_message(self, interaction: discord.Interaction) -> str:
        """Get appropriate error message for delete permission denial"""
        return (
            "❌ У вас нет прав для удаления этого автоматического рапорта.\n"
            "Удалить рапорт может только:\n"
            "• Администратор сервера\n"
            "• Администратор из конфигурации бота"
        )

    async def _handle_deletion_error(self, interaction: discord.Interaction, error: Exception):
        """Handle errors during deletion process"""
        error_message = f"❌ Произошла ошибка при удалении рапорта: {str(error)}"
        
        try:
            if interaction.response.is_done():
                await interaction.edit_original_response(
                    content=error_message,
                    embed=None,
                    view=None
                )
            else:
                await interaction.response.send_message(error_message, ephemeral=True)
        except Exception:
            # If we can't send the error message, at least log it
            print(f"Error in deletion process: {error}")
            import traceback
            traceback.print_exc()
    
    async def _process_automatic_dismissal_approval(self, interaction, target_user, config):
        """Process automatic dismissal approval (similar to standard approval but simplified)"""
        try:
            # Processing state already shown by caller, no need to defer again
            
            # Extract form data from embed
            embed = interaction.message.embeds[0]
            form_data = {}
            
            for field in embed.fields:
                if field.name == "Имя Фамилия":
                    form_data['name'] = field.value
                elif field.name == "Статик":
                    form_data['static'] = field.value
                elif field.name == "Подразделение":
                    form_data['department'] = field.value
                elif field.name == "Воинское звание":
                    form_data['rank'] = field.value
                elif field.name == "Причина увольнения":
                    form_data['reason'] = field.value
            
            # Process standard dismissal approval
            current_time = discord.utils.utcnow()
            ping_settings = config.get('ping_settings', {})
            
            # Get user info for audit - use the same logic as regular dismissals
            # First try to get from embed fields, then from PersonnelManager if user is still on server
            user_rank_for_audit = form_data.get('rank', DismissalConstants.UNKNOWN_VALUE)
            user_unit_for_audit = form_data.get('department', DismissalConstants.UNKNOWN_VALUE)
            user_has_left_server = getattr(target_user, '_is_mock', False)            # Get user position for audit (from PersonnelManager or empty)
            user_position_for_audit = ""
            
            # Always try to get position from PersonnelManager, regardless of server status
            try:
                # Try to get user info from PersonnelManager by Discord ID
                from utils.database_manager import PersonnelManager
                pm = PersonnelManager()
                user_info = await pm.get_personnel_summary(target_user.id)
                if user_info:
                    # Get position if available
                    if user_info.get('position'):
                        user_position_for_audit = user_info.get('position')
                    
                    # Also check if we need to update other missing data (only for users still on server)
                    if not user_has_left_server:
                        if user_rank_for_audit == DismissalConstants.UNKNOWN_VALUE and user_info.get('rank'):
                            user_rank_for_audit = user_info.get('rank')
                        if user_unit_for_audit == DismissalConstants.UNKNOWN_VALUE and user_info.get('department'):
                            user_unit_for_audit = user_info.get('department')
                    
                    print(f"Got user info from PersonnelManager: rank={user_rank_for_audit}, department={user_unit_for_audit}, position={user_position_for_audit}")
                    
                    # Also update form_data with the complete info from PersonnelManager if available
                    if not form_data.get('name') and user_info.get('first_name') and user_info.get('last_name'):
                        form_data['name'] = f"{user_info['first_name']} {user_info['last_name']}"
                    if not form_data.get('static') and user_info.get('static'):
                        form_data['static'] = user_info['static']
            except Exception as e:
                print(f"Error getting user info from PersonnelManager: {e}")
            # If data is still missing and user is still on server, try fallback to roles
            if not user_has_left_server and (user_rank_for_audit == DismissalConstants.UNKNOWN_VALUE or user_unit_for_audit == DismissalConstants.UNKNOWN_VALUE):
                try:
                    if user_rank_for_audit == DismissalConstants.UNKNOWN_VALUE:
                        role_rank = get_rank_from_roles_postgresql(target_user)
                        if role_rank != DismissalConstants.UNKNOWN_VALUE:
                            user_rank_for_audit = role_rank
                    
                    if user_unit_for_audit == DismissalConstants.UNKNOWN_VALUE:
                        from utils.department_manager import DepartmentManager
                        dept_manager = DepartmentManager()
                        role_unit = dept_manager.get_user_department_name(target_user)
                        if role_unit != DismissalConstants.UNKNOWN_VALUE:
                            user_unit_for_audit = role_unit
                    print(f"Fallback to roles: rank={user_rank_for_audit}, department={user_unit_for_audit}")
                except Exception as e:
                    print(f"Error getting data from roles: {e}")            
            # Process dismissal with automatic approval logic
            await self._finalize_automatic_approval(
                interaction, target_user, form_data, user_rank_for_audit, 
                user_unit_for_audit, current_time, config, user_position_for_audit
            )
            
        except Exception as e:
            print(f"Error processing automatic dismissal approval: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке одобрения.",
                ephemeral=True
            )
    
    async def _finalize_automatic_approval(self, interaction, target_user, form_data, 
                                         user_rank_for_audit, user_unit_for_audit, 
                                         current_time, config, user_position_for_audit=""):
        """Finalize automatic dismissal approval"""
        try:
            # Remove user from personnel database using PersonnelManager
            try:
                user_id = getattr(target_user, 'id', None)
                if user_id:
                    from utils.database_manager import PersonnelManager
                    pm = PersonnelManager()
                    
                    # Prepare dismissal data
                    dismissal_data = {
                        'reason': form_data.get('reason', ''),
                        'static': form_data.get('static', ''),
                        'name': form_data.get('name', target_user.display_name)
                    }
                    
                    registry_success, registry_message = await pm.process_personnel_dismissal(
                        user_id,
                        dismissal_data,
                        interaction.user.id,
                        interaction.user.display_name
                    )
                    
                    if not registry_success:
                        print(f"⚠️ Could not remove user from personnel registry: {registry_message}")
                        # Send error notification to moderator
                        try:
                            await interaction.followup.send(
                                f"⚠️ **Внимание:** {registry_message}",
                                ephemeral=True
                            )
                        except:
                            pass  # If followup fails, continue silently
                    else:
                        print(f"✅ Personnel database updated: {registry_message}")
                else:
                    print(f"⚠️ Could not get user ID for {target_user.display_name}")
            except Exception as e:
                print(f"❌ Error updating personnel database: {e}")
                # Send error notification to moderator
                try:
                    await interaction.followup.send(
                        "⚠️ **Внимание:** Ошибка при обновлении базы данных персонала. Обратитесь к руководству бригады.",
                        ephemeral=True
                    )
                except:
                    pass  # If followup fails, continue silently
            
            # Send notification to audit channel
            audit_message_url = None
            try:
                from utils.audit_logger import audit_logger, AuditAction
                from utils.postgresql_pool import get_db_cursor
                
                # Prepare personnel data for audit logger
                personnel_data = {
                    'name': form_data.get('name', DismissalConstants.UNKNOWN_VALUE),
                    'static': form_data.get('static', ''),
                    'rank': user_rank_for_audit,
                    'department': user_unit_for_audit,
                    'position': user_position_for_audit,
                    'reason': form_data.get('reason', '')
                }
                
                # Send audit notification
                audit_message_url = await audit_logger.send_personnel_audit(
                    guild=interaction.guild,
                    action=await AuditAction.DISMISSAL(),
                    target_user=target_user,
                    moderator=interaction.user,
                    personnel_data=personnel_data,
                    config=config
                )
                
                # Get personnel_id for auto-blacklist check
                try:
                    with get_db_cursor() as cursor:
                        cursor.execute(
                            "SELECT id FROM personnel WHERE discord_id = %s;",
                            (target_user.id,)
                        )
                        result = cursor.fetchone()
                        
                        if result:
                            personnel_id = result['id']
                            
                            # Check and send auto-blacklist if needed (with audit URL as evidence)
                            was_blacklisted = await audit_logger.check_and_send_auto_blacklist(
                                guild=interaction.guild,
                                target_user=target_user,
                                moderator=interaction.user,
                                personnel_id=personnel_id,
                                personnel_data=personnel_data,
                                audit_message_url=audit_message_url,  # Pass audit URL as evidence
                                config=config
                            )
                            
                            if was_blacklisted:
                                print(f"✅ Auto-blacklist triggered for {personnel_data.get('name')}")
                        else:
                            print(f"⚠️ Personnel not found in DB for auto-blacklist check: {target_user.id}")
                            
                except Exception as blacklist_error:
                    print(f"⚠️ Error in auto-blacklist check: {blacklist_error}")
                    # Don't fail the whole dismissal if blacklist check fails
                
            except Exception as e:
                print(f"Error sending audit notification: {e}")
            
            # Update embed to show approval
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()            # Add approval status field
            embed.add_field(
                name="✅ Обработано",
                value=f"**Одобрено:** {interaction.user.mention}\n**Время:** {discord.utils.format_dt(current_time, 'F')}",
                inline=False
            )
            
            # Add dismissal footer with link to submit new applications
            embed = add_dismissal_footer_to_embed(embed, interaction.guild.id)
            
            # Create new view with only "Approved" button (disabled)
            approved_view = ui.View(timeout=None)
            approved_button = ui.Button(label=DismissalConstants.APPROVED_LABEL, style=discord.ButtonStyle.green, disabled=True)
            approved_view.add_item(approved_button)
            
            # Update message with approved state
            await interaction.edit_original_response(content='', embed=embed, view=approved_view)

        except Exception as e:
            print(f"Error finalizing automatic approval: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при финализации одобрения.",
                ephemeral=True
            )
    
    async def _finalize_automatic_rejection(self, interaction, rejection_reason, original_message):
        """Finalize automatic dismissal rejection with proper UI state."""
        try:
            # Show processing state first
            processing_view = ui.View(timeout=None)
            processing_button = ui.Button(label=DismissalConstants.PROCESSING_LABEL, style=discord.ButtonStyle.gray, disabled=True)
            processing_view.add_item(processing_button)
            await original_message.edit(view=processing_view)
            
            # Small delay to show processing state
            await asyncio.sleep(0.5)
            
            # Update embed to show rejection
            embed = original_message.embeds[0]
            embed.color = discord.Color.red()
            
            # Add rejection status field
            embed.add_field(
                name="❌ Обработано",
                value=f"**Отклонено:** {interaction.user.mention}\n**Время:** {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n**Причина:** {rejection_reason}",
                inline=False
            )
            
            # Add dismissal footer with link to submit new applications
            embed = add_dismissal_footer_to_embed(embed, interaction.guild.id)
            
            # Create new view with only "Rejected" button (disabled)
            rejected_view = ui.View(timeout=None)
            rejected_button = ui.Button(label=DismissalConstants.REJECTED_LABEL, style=discord.ButtonStyle.red, disabled=True)
            rejected_view.add_item(rejected_button)
            
            # Update message with rejected state
            await original_message.edit(embed=embed, view=rejected_view)
            
        except Exception as e:
            print(f"Error finalizing automatic rejection: {e}")

