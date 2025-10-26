"""
Department Application Views - Persistent views for department applications
"""
import discord
from discord import ui
from typing import Dict, Any, List
import logging
from datetime import datetime, timezone, timedelta

from utils.config_manager import load_config
from utils.message_manager import get_department_applications_message, get_private_messages, get_ui_button, get_military_term, get_ui_label, get_role_reason, get_moderator_display_name
from utils.ping_manager import ping_manager
from utils.nickname_manager import nickname_manager
from utils import get_safe_personnel_name
# Импорты для работы с PostgreSQL будут добавлены по мере необходимости

logger = logging.getLogger(__name__)

class DepartmentApplicationView(ui.View):
    """View with moderation buttons for department applications"""
    
    def __init__(self, application_data: Dict[str, Any]):
        super().__init__(timeout=None)  # Persistent view
        self.application_data = application_data
        
        # Initialize transfer approval state for transfer applications
        self.transfer_state = {
            'approved': False,
            'permission_given': False,
            'approved_by': None,
            'permission_by': None
        } if application_data.get('application_type') == 'transfer' else None
        
        self.is_transfer = application_data.get('application_type') == 'transfer'
    
    def _setup_permission_button_visibility(self):
        """Show/hide permission button based on application type"""
        # Find and remove permission button for join applications
        if not self.is_transfer:
            # For join applications, remove the permission button entirely
            for i, item in enumerate(self.children):
                if hasattr(item, 'custom_id') and item.custom_id == "dept_app_permission_static":
                    self.remove_item(item)
                    break
        # For transfer applications, the button stays as is (enabled and visible)
    
    async def _permission_button_callback(self, interaction: discord.Interaction):
        """Handle permission button click for transfers"""
        await self.give_permission_callback(interaction)
    
    def setup_buttons(self):
        """Setup buttons after initialization - called after __init__"""
        # Setup permission button visibility based on application type
        self._setup_permission_button_visibility()
        
        # Set STATIC custom_id for persistence (важно для восстановления после рестарта)
        # Only set if the button attributes exist (they are created by @ui.button decorators)
        if hasattr(self, 'approve_button'):
            self.approve_button.custom_id = "dept_app_approve_static"
        if hasattr(self, 'reject_button'):
            self.reject_button.custom_id = "dept_app_reject_static"
        if hasattr(self, 'delete_button'):
            self.delete_button.custom_id = "dept_app_delete_static"
        
        # Set custom_id for permission button is now set in the decorator
    
    def _extract_application_data_from_embed(self, embed: discord.Embed) -> Dict[str, Any]:
        """Извлекает данные заявления из embed для статических views"""
        try:
            data = {
                'user_id': None,
                'department_code': None,
                'name': None,
                'static': None,
                'application_type': 'join'
            }
            
            # Извлекаем user_id из footer
            if embed.footer and embed.footer.text and "ID заявления:" in embed.footer.text:
                try:
                    data['user_id'] = int(embed.footer.text.split("ID заявления:")[-1].strip())
                except (ValueError, IndexError):
                    pass
            
            # Извлекаем department_code из description (новый формат)
            if embed.description:
                # Ищем в description после "в " и до " от"
                if " в " in embed.description and " от" in embed.description:
                    dept_part = embed.description.split(" в ")[-1].split(" от")[0]
                    # Убираем лишние слова
                    data['department_code'] = dept_part.strip()
                    
                # Определяем тип заявления
                if "перевод" in embed.description.lower():
                    data['application_type'] = 'transfer'
            # Fallback: извлекаем department_code из title (старый формат)
            elif embed.title:
                # Ищем в title после "в "
                if " в " in embed.title:
                    dept_part = embed.title.split(" в ")[-1]
                    # Убираем лишние слова
                    data['department_code'] = dept_part.strip()
                    
                # Определяем тип заявления
                if "перевод" in embed.title.lower():
                    data['application_type'] = 'transfer'
            
            # Извлекаем данные из полей
            for field in embed.fields:
                field_name = field.name.lower()
                field_value = field.value
                
                # Для отдельных полей (старый формат)
                if "имя фамилия" in field_name:
                    data['name'] = field_value
                elif "статик" in field_name:
                    data['static'] = field_value
                # Для нового формата, где данные внутри "📋 IC Информация"
                elif "ic информация" in field_name:
                    # Парсим строку вида:
                    # **Имя Фамилия:** Марко Толедо
                    # **Статик:** 135-583
                    # **Документ:** [Ссылка на документ](url)
                    lines = field_value.split('\n')
                    for line in lines:
                        if '**Имя Фамилия:**' in line:
                            data['name'] = line.split('**Имя Фамилия:**')[-1].strip()
                        elif '**Статик:**' in line:
                            data['static'] = line.split('**Статик:**')[-1].strip()
            
            return data
            
        except Exception as e:
            logger.error(f"Error extracting application data from embed: {e}")
            return self.application_data  # Fallback to original data
    
    def _extract_transfer_state_from_embed(self, embed: discord.Embed) -> Dict[str, Any]:
        """Extract transfer approval state from embed status field"""
        state = {
            'approved': False,
            'permission_given': False,
            'approved_by': None,
            'permission_by': None
        }
        
        try:
            # Look for status field
            for field in embed.fields:
                if field.name == "📊 Статус":
                    status_value = field.value
                    
                    # Check for approval status
                    if "✅ Одобрено" in status_value:
                        state['approved'] = True
                        # Extract who approved (format: "✅ Одобрено @username")
                        if "<@" in status_value:
                            import re
                            match = re.search(r'<@!?(\d+)>', status_value)
                            if match:
                                state['approved_by'] = int(match.group(1))
                    
                    # Check for permission status
                    if "🔒 Разрешение дано" in status_value:
                        state['permission_given'] = True
                        # Extract who gave permission (format: "🔒 Разрешение дано @username")
                        if "<@" in status_value:
                            import re
                            matches = re.findall(r'<@!?(\d+)>', status_value)
                            if len(matches) >= 2:  # Second mention is permission giver
                                state['permission_by'] = int(matches[1])
                            elif len(matches) == 1 and not state['approved']:  # Only permission given
                                state['permission_by'] = int(matches[0])
                    
                    break
                    
        except Exception as e:
            logger.error(f"Error extracting transfer state from embed: {e}")
        
        return state
    
    def _update_transfer_status_in_embed(self, embed: discord.Embed, state: Dict[str, Any], guild: discord.Guild) -> discord.Embed:
        """Update the transfer status field in the embed based on current state"""
        try:
            # Create status text based on current state
            status_parts = []
            
            if state['approved']:
                approved_user = guild.get_member(state['approved_by'])
                if approved_user:
                    status_parts.append(f"✅ Одобрено {approved_user.mention}")
                else:
                    status_parts.append(f"✅ Одобрено <@{state['approved_by']}>")
            
            if state['permission_given']:
                permission_user = guild.get_member(state['permission_by'])
                if permission_user:
                    status_parts.append(f"🔒 Разрешение дано {permission_user.mention}")
                else:
                    status_parts.append(f"🔒 Разрешение дано <@{state['permission_by']}>")
            
            # If neither is done, show waiting status
            if not status_parts:
                status_text = "⏳ Ожидает рассмотрения"
            else:
                status_text = "\n".join(status_parts)
            
            # Update the status field
            for i, field in enumerate(embed.fields):
                if field.name == "📊 Статус":
                    embed.set_field_at(
                        i,
                        name="📊 Статус",
                        value=status_text,
                        inline=True
                    )
                    break
            
            return embed
            
        except Exception as e:
            logger.error(f"Error updating transfer status in embed: {e}")
            return embed
    
    def _create_transfer_buttons_view(self, state: Dict[str, Any]) -> ui.View:
        """Create a new view with buttons in the correct state for transfers"""
        view = ui.View(timeout=None)
        
        # Approve button
        approve_disabled = state['approved']
        approve_style = discord.ButtonStyle.grey if approve_disabled else discord.ButtonStyle.green
        approve_label = get_ui_button(0, "approved") if approve_disabled else get_ui_button(0, "approve")
        
        approve_btn = ui.Button(
            label=approve_label,
            style=approve_style,
            disabled=approve_disabled,
            custom_id="dept_app_approve_static",
            row=0
        )
        approve_btn.callback = self.approve_button.callback
        view.add_item(approve_btn)
        
        # Permission button - only for transfers
        permission_disabled = state['permission_given']
        permission_style = discord.ButtonStyle.grey if permission_disabled else discord.ButtonStyle.green
        permission_label = "🔒 Разрешение дано" if permission_disabled else "🔒 Дать разрешение"
        
        permission_btn = ui.Button(
            label=permission_label,
            style=permission_style,
            disabled=permission_disabled,
            custom_id="dept_app_permission_static",
            row=0
        )
        permission_btn.callback = self._permission_button_callback
        view.add_item(permission_btn)
        
        # Reject button (always enabled until fully approved)
        if not (state['approved'] and state['permission_given']):
            reject_btn = ui.Button(
                label="❌ Отклонить",
                style=discord.ButtonStyle.red,
                custom_id="dept_app_reject_static",
                row=0
            )
            reject_btn.callback = self.reject_button.callback
            view.add_item(reject_btn)
        
        # Delete button (always enabled for admin/author)
        delete_btn = ui.Button(
            label="🗑️ Удалить",
            style=discord.ButtonStyle.grey,
            custom_id="dept_app_delete_static",
            row=0
        )
        delete_btn.callback = self.delete_button.callback
        view.add_item(delete_btn)
        
        return view
    
    async def give_permission_callback(self, interaction: discord.Interaction):
        """Handle permission button click"""
        try:
            # Extract current data from embed (for static views)
            if interaction.message and interaction.message.embeds:
                self.application_data = self._extract_application_data_from_embed(interaction.message.embeds[0])
            
            # Check if this is a transfer application first
            if self.application_data.get('application_type') != 'transfer':
                error_msg = get_department_applications_message(interaction.guild.id, "transfer.error_not_transfer_application", "❌ Эта кнопка доступна только для заявлений на перевод.")
                await interaction.response.send_message(
                    error_msg,
                    ephemeral=True
                )
                return
            
            # First check if user is a moderator at all
            config = load_config()
            administrators = config.get('administrators', {})
            moderators = config.get('moderators', {})
            user_role_ids = [role.id for role in interaction.user.roles]
            
            is_admin = (
                interaction.user.id in administrators.get('users', []) or
                any(role_id in user_role_ids for role_id in administrators.get('roles', []))
            )
            
            is_moderator = (
                interaction.user.id in moderators.get('users', []) or
                any(role_id in user_role_ids for role_id in moderators.get('roles', []))
            )
            
            # If not admin and not moderator, show basic access denied message
            if not (is_admin or is_moderator):
                error_msg = get_department_applications_message(interaction.guild.id, "transfer_permission_denied", "❌ У вас нет прав для выдачи разрешения на перевод. Это действие доступно только модераторам.")
                await interaction.response.send_message(
                    error_msg,
                    ephemeral=True
                )
                return
            
            # Check specific permissions for moderators with roles from second line
            if not await self._check_permission_permissions(interaction):
                error_message = self._get_permission_error_message(interaction)
                await interaction.response.send_message(error_message, ephemeral=True)
                return
            
            # Extract current transfer state from embed
            current_state = self._extract_transfer_state_from_embed(interaction.message.embeds[0])
            
            # Check if permission already given
            if current_state['permission_given']:
                error_msg = get_department_applications_message(interaction.guild.id, "transfer.error_already_permitted", "❌ Разрешение уже было дано для этого перевода.")
                await interaction.response.send_message(
                    error_msg,
                    ephemeral=True
                )
                return
            
            await interaction.response.defer()
            
            # Update state
            current_state['permission_given'] = True
            current_state['permission_by'] = interaction.user.id
            
            # Update embed
            embed = interaction.message.embeds[0].copy()
            embed = self._update_transfer_status_in_embed(embed, current_state, interaction.guild)
            
            # Check if both approvals are done
            if current_state['approved'] and current_state['permission_given']:
                # Both approvals complete - process final approval
                await self._process_final_transfer_approval(interaction, embed, current_state)
            else:
                # Update view with disabled permission button
                new_view = self._create_transfer_buttons_view(current_state)
                await interaction.edit_original_response(embed=embed, view=new_view)
                
                # Send feedback message
                await interaction.followup.send(
                    get_department_applications_message(interaction.guild.id, "transfer.success_permission_granted", "✅ Разрешение на перевод выдано! Ожидаем одобрения руководства нового подразделения."),
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"Error giving permission for department transfer: {e}")
            await interaction.followup.send(
                get_department_applications_message(interaction.guild.id, "transfer.error_general", "❌ Произошла ошибка при выдаче разрешения."),
                ephemeral=True
            )
    
    async def _process_final_transfer_approval(self, interaction: discord.Interaction, embed: discord.Embed, state: Dict[str, Any]):
        """Process final approval when both approve and permission buttons are pressed"""
        try:
            # Show "Processing..." state immediately to prevent double-clicks and show progress
            processing_embed = embed.copy()
            
            # Update status field to show processing
            for i, field in enumerate(processing_embed.fields):
                if field.name == "📊 Статус":
                    processing_embed.set_field_at(
                        i,
                        name="📊 Статус", 
                        value="⏳ Обрабатывается...",
                        inline=True
                    )
                    break
            
            # Replace all buttons with single disabled "Processing" button
            processing_view = ui.View(timeout=None)
            processing_button = ui.Button(
                label="⏳ Обрабатывается...",
                style=discord.ButtonStyle.grey,
                disabled=True
            )
            processing_view.add_item(processing_button)
            
            # Update message with processing state
            await interaction.edit_original_response(embed=processing_embed, view=processing_view)
            
            # Get target user
            target_user = interaction.guild.get_member(self.application_data['user_id'])
            if not target_user:
                # Restore state view if user not found
                restored_view = self._create_transfer_buttons_view(state)
                await interaction.edit_original_response(embed=embed, view=restored_view)
                await interaction.followup.send(
                    get_department_applications_message(interaction.guild.id, "transfer.error_user_not_found", "❌ Пользователь не найден на сервере."),
                    ephemeral=True
                )
                return
            
            # Process approval (assign roles, update nickname, log to sheets)
            success = await self._process_approval(interaction, target_user)
            
            if success:
                # Clear user's cache since status changed
                _clear_user_cache(target_user.id)
                
                # Update embed for final approval
                embed.color = discord.Color.green()
                
                # Update status field to show final approval with both moderators
                for i, field in enumerate(embed.fields):
                    if field.name == "📊 Статус":
                        # Create final status with both moderators mentioned
                        status_parts = []
                        
                        # Add who approved
                        if state['approved_by']:
                            approved_user = interaction.guild.get_member(state['approved_by'])
                            if approved_user:
                                status_parts.append(f"✅ Одобрено {approved_user.mention}")
                            else:
                                status_parts.append(f"✅ Одобрено <@{state['approved_by']}>")
                        
                        # Add who gave permission
                        if state['permission_by']:
                            permission_user = interaction.guild.get_member(state['permission_by'])
                            if permission_user:
                                status_parts.append(f"🔒 Разрешение дано {permission_user.mention}")
                            else:
                                status_parts.append(f"🔒 Разрешение дано <@{state['permission_by']}>")
                        
                        # Add completion status
                        status_parts.append("**Перевод выполнен**")
                        
                        final_status = "\n".join(status_parts)
                        
                        embed.set_field_at(
                            i,
                            name="📊 Статус",
                            value=final_status,
                            inline=True
                        )
                        break
                
                embed.add_field(
                    name="⏰ Время обработки",
                    value=f"<t:{int((datetime.now(timezone(timedelta(hours=3)))).timestamp())}:R>",
                    inline=True
                )
                
                # Create final view with single disabled "Completed" button
                final_view = ui.View(timeout=None)
                approved_button = ui.Button(
                    label="✅ Одобрено",
                    style=discord.ButtonStyle.green,
                    disabled=True
                )
                final_view.add_item(approved_button)
                
                await interaction.edit_original_response(embed=embed, view=final_view)
                
                # Send success message
                await interaction.followup.send(
                    get_department_applications_message(interaction.guild.id, "transfer.success_transfer_completed", "✅ Перевод пользователя выполнен! Роли подразделения и должности назначены автоматически.").replace("пользователя", f"пользователя {target_user.mention}"),
                    ephemeral=True
                )
                
                # Send DM to user
                try:
                    dm_embed = discord.Embed(
                        title=get_private_messages(interaction.guild.id, 'department_applications.transfer_approval.title'),
                        description=get_private_messages(interaction.guild.id, 'department_applications.transfer_approval.description').format(
                            department_code=self.application_data['department_code']
                        ),
                        color=discord.Color.green(),
                        timestamp=datetime.now(timezone(timedelta(hours=3)))
                    )
                    await target_user.send(embed=dm_embed)
                except discord.Forbidden:
                    logger.warning(f"Could not send DM to {target_user} about approved transfer")
            else:
                # Restore state view if approval failed
                restored_view = self._create_transfer_buttons_view(state)
                await interaction.edit_original_response(embed=embed, view=restored_view)
                
        except Exception as e:
            logger.error(f"Error processing final transfer approval: {e}")
            await interaction.followup.send(
                get_department_applications_message(interaction.guild.id, "transfer.error_transfer_failed", "❌ Произошла ошибка при выполнении перевода."),
                ephemeral=True
            )
    
    @ui.button(label=get_ui_button(0, "approve"), style=discord.ButtonStyle.green, row=0)
    async def approve_button(self, interaction: discord.Interaction, button: ui.Button):
        """Approve the application"""
        try:
            # Извлекаем актуальные данные из embed (для статических views)
            if interaction.message and interaction.message.embeds:
                self.application_data = self._extract_application_data_from_embed(interaction.message.embeds[0])
            
            # Check permissions - for approve, only first line roles can approve
            if not await self._check_approve_permissions(interaction):
                error_message = self._get_approve_permission_error_message(interaction)
                await interaction.response.send_message(error_message, ephemeral=True)
                return
            
            # Handle transfer applications differently
            if self.application_data.get('application_type') == 'transfer':
                await self._handle_transfer_approval(interaction)
                return
            
            await interaction.response.defer()
            
            # Regular join application logic (unchanged)
            # Show "Processing..." state immediately to prevent double-clicks
            processing_embed = interaction.message.embeds[0].copy()
            
            # Update status field to show processing
            for i, field in enumerate(processing_embed.fields):
                if field.name == "📊 Статус":
                    processing_embed.set_field_at(
                        i,
                        name="📊 Статус", 
                        value="⏳ Обрабатывается...",
                        inline=True
                    )
                    break
            
            # Replace all buttons with single disabled "Processing" button
            processing_view = ui.View(timeout=None)
            processing_button = ui.Button(
                label="⏳ Обрабатывается...",
                style=discord.ButtonStyle.grey,
                disabled=True
            )
            processing_view.add_item(processing_button)
            
            # Update message with processing state
            await interaction.edit_original_response(content="", embed=processing_embed, view=processing_view)
            
            # Get target user
            target_user = interaction.guild.get_member(self.application_data['user_id'])
            if not target_user:
                # Restore original buttons on error
                await self._restore_original_buttons(interaction)
                await interaction.followup.send(
                    "❌ Пользователь не найден на сервере.",
                    ephemeral=True
                )
                return
            
            # Check if user already has department role
            dept_role_id = ping_manager.get_department_role_id(self.application_data['department_code'])
            if dept_role_id:
                dept_role = interaction.guild.get_role(dept_role_id)
                if dept_role and dept_role in target_user.roles:
                    # Restore original buttons on error
                    await self._restore_original_buttons(interaction)
                    await interaction.followup.send(
                        f"❌ Пользователь уже состоит в подразделении {self.application_data['department_code']}.",
                        ephemeral=True
                    )
                    return
            
            # Process approval
            success = await self._process_approval(interaction, target_user)
            
            if success:
                # Clear user's cache since status changed
                _clear_user_cache(target_user.id)
                
                # Update embed
                embed = interaction.message.embeds[0]
                embed.color = discord.Color.green()
                
                # Update status field
                for i, field in enumerate(embed.fields):
                    if field.name == "📊 Статус":
                        embed.set_field_at(
                            i,
                            name="📊 Статус",
                            value=f"✅ Одобрено {interaction.user.mention}",
                            inline=True
                        )
                        break
                
                embed.add_field(
                    name="⏰ Время обработки",
                    value=f"<t:{int((datetime.now(timezone(timedelta(hours=3)))).timestamp())}:R>",
                    inline=True
                )
                
                # Disable all buttons and replace with single status button
                self.clear_items()
                
                # Add single disabled "Approved" button
                approved_button = ui.Button(
                    label="✅ Одобрено",
                    style=discord.ButtonStyle.green,
                    disabled=True
                )
                self.add_item(approved_button)
                
                await interaction.edit_original_response(content="", embed=embed, view=self)
                
                # Send success message
                await interaction.followup.send(
                    get_department_applications_message(interaction.guild.id, "success.approved", "✅ Заявление пользователя {user} одобрено! Роли подразделения и должности назначены автоматически.").format(user=target_user.mention),
                    ephemeral=True
                )
                
                # Send DM to user
                try:
                    dm_embed = discord.Embed(
                        title=get_private_messages(interaction.guild.id, 'department_applications.approval.title'),
                        description=get_private_messages(interaction.guild.id, 'department_applications.approval.description').format(
                            department_code=self.application_data['department_code']
                        ),
                        color=discord.Color.green(),
                        timestamp=datetime.now(timezone(timedelta(hours=3)))
                    )
                    await target_user.send(embed=dm_embed)
                except discord.Forbidden:
                    logger.warning(f"Could not send DM to {target_user} about approved application")
            else:
                # Restore original buttons if approval failed
                await self._restore_original_buttons(interaction)
            
        except Exception as e:
            logger.error(f"Error approving department application: {e}")
            # Restore original buttons on error
            await self._restore_original_buttons(interaction)
            await interaction.followup.send(
                "❌ Произошла ошибка при одобрении заявления.",
                ephemeral=True
            )

    @ui.button(label="🔒 Дать разрешение", style=discord.ButtonStyle.green, row=0, custom_id="dept_app_permission_static")
    async def permission_button(self, interaction: discord.Interaction, button: ui.Button):
        """Give permission for transfer application"""
        await self._permission_button_callback(interaction)

    async def _handle_transfer_approval(self, interaction: discord.Interaction):
        """Handle approval button click for transfer applications"""
        try:
            # Extract current transfer state from embed
            current_state = self._extract_transfer_state_from_embed(interaction.message.embeds[0])
            
            # Check if already approved
            if current_state['approved']:
                await interaction.response.send_message(
                    "❌ Этот перевод уже был одобрен.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer()
            
            # Update state
            current_state['approved'] = True
            current_state['approved_by'] = interaction.user.id
            
            # Update embed
            embed = interaction.message.embeds[0].copy()
            embed = self._update_transfer_status_in_embed(embed, current_state, interaction.guild)
            
            # Check if both approvals are done
            if current_state['approved'] and current_state['permission_given']:
                # Both approvals complete - process final approval
                await self._process_final_transfer_approval(interaction, embed, current_state)
            else:
                # Update view with disabled approve button
                new_view = self._create_transfer_buttons_view(current_state)
                await interaction.edit_original_response(embed=embed, view=new_view)
                
                # Send feedback message
                await interaction.followup.send(
                    "✅ Перевод одобрен! Ожидаем подтверждения бывшего руководства сотрудника.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error handling transfer approval: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при одобрении перевода.",
                ephemeral=True
            )

    @ui.button(label="❌ Отклонить", style=discord.ButtonStyle.red, row=0)
    async def reject_button(self, interaction: discord.Interaction, button: ui.Button):
        """Reject the application with reason"""
        try:
            # Извлекаем актуальные данные из embed (для статических views)
            if interaction.message and interaction.message.embeds:
                self.application_data = self._extract_application_data_from_embed(interaction.message.embeds[0])
            
            # Check permissions - for reject, any role from all lines can reject
            if not await self._check_reject_permissions(interaction):
                error_message = self._get_reject_permission_error_message(interaction)
                await interaction.response.send_message(error_message, ephemeral=True)
                return
            
            # Show rejection reason modal
            modal = RejectionReasonModal(self.application_data)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error rejecting department application: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при отклонении заявления.",
                ephemeral=True
            )
    
    @ui.button(label="🗑️ Удалить", style=discord.ButtonStyle.grey, row=0)  
    async def delete_button(self, interaction: discord.Interaction, button: ui.Button):
        """Delete the application (admin or author only)"""
        try:
            # Извлекаем актуальные данные из embed (для статических views)
            if interaction.message and interaction.message.embeds:
                self.application_data = self._extract_application_data_from_embed(interaction.message.embeds[0])
            
            # Check if user is admin or application author
            is_admin = await self._check_admin_permissions(interaction)
            is_author = interaction.user.id == self.application_data['user_id']
            
            if not (is_admin or is_author):
                await interaction.response.send_message(
                    "❌ Только администратор или автор заявления может удалить его.",
                    ephemeral=True
                )
                return
            
            # Confirm deletion
            confirm_view = ConfirmDeletionView()
            await interaction.response.send_message(
                get_department_applications_message(interaction.guild.id, "confirmations.delete_warning", "⚠️ Вы уверены, что хотите удалить это заявление? Это действие нельзя отменить."),
                view=confirm_view,
                ephemeral=True
            )
            
            # Wait for confirmation
            await confirm_view.wait()
            
            if confirm_view.confirmed:
                await interaction.delete_original_response()
                await interaction.message.delete()
            else:
                await interaction.edit_original_response(
                    content="❌ Удаление отменено.",
                    view=None
                )
            
        except Exception as e:
            logger.error(f"Error deleting department application: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при удалении заявления.",
                ephemeral=True
            )
    
    async def _check_moderator_permissions(self, interaction: discord.Interaction) -> bool:
        """
        Check if user has moderator permissions with proper hierarchy
        - Admin can moderate ANYTHING (including their own applications)
        - Moderator cannot moderate their own applications
        - Higher hierarchy moderator can moderate lower hierarchy moderator applications
        """
        user_id = interaction.user.id
        application_user_id = self.application_data['user_id']
        
        config = load_config()
        administrators = config.get('administrators', {})
        moderators = config.get('moderators', {})
        user_role_ids = [role.id for role in interaction.user.roles]
        
        # Check if user is administrator FIRST (can moderate anything including own applications)
        is_admin = (
            user_id in administrators.get('users', []) or
            any(role_id in user_role_ids for role_id in administrators.get('roles', []))
        )
        
        if is_admin:
            return True  # Admins can moderate everything
        
        # Check if user is moderator
        is_moderator_by_user = user_id in moderators.get('users', [])
        moderator_roles = [role for role in interaction.user.roles if role.id in moderators.get('roles', [])]
        is_moderator_by_role = len(moderator_roles) > 0
        
        if not (is_moderator_by_user or is_moderator_by_role):
            return False  # Not admin, not moderator
        
        # Moderators have restrictions:
        # 1. Cannot moderate own application
        if user_id == application_user_id:
            return False
        
        # 2. Moderator hierarchy check: cannot moderate other moderators/admins
        application_user = interaction.guild.get_member(application_user_id)
        if application_user:
            app_user_role_ids = [role.id for role in application_user.roles]
            
            # Check if application author is admin
            app_user_is_admin = (
                application_user_id in administrators.get('users', []) or
                any(role_id in app_user_role_ids for role_id in administrators.get('roles', []))
            )
            
            if app_user_is_admin:
                return False  # Moderator cannot moderate admin applications
            
            # Check if application author is also moderator
            app_is_moderator_by_user = application_user_id in moderators.get('users', [])
            app_moderator_roles = [role for role in application_user.roles if role.id in moderators.get('roles', [])]
            app_is_moderator_by_role = len(app_moderator_roles) > 0
            
            if not (app_is_moderator_by_user or app_is_moderator_by_role):
                return True  # Moderator can moderate regular user applications
            
            # Both are moderators - check hierarchy
            if is_moderator_by_role and app_is_moderator_by_role:
                # Find highest moderator role position for current user
                user_highest_mod_role_position = max(role.position for role in moderator_roles)
                
                # Find highest moderator role position for application author
                app_highest_mod_role_position = max(role.position for role in app_moderator_roles)
                
                # Higher role can moderate lower role
                return user_highest_mod_role_position > app_highest_mod_role_position
            
            # If one is moderator by user and other by role
            if is_moderator_by_user and app_is_moderator_by_role:
                return False  # User moderator cannot moderate role moderator
            
            if is_moderator_by_role and app_is_moderator_by_user:
                return True  # Role moderator can moderate user moderator
            
            # Both are user moderators - deny moderation
            if is_moderator_by_user and app_is_moderator_by_user:
                return False
        
        return True  # Moderator can moderate regular user applications
    
    async def _check_admin_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions"""
        config = load_config()
        administrators = config.get('administrators', {})
        
        # Check admin users
        if interaction.user.id in administrators.get('users', []):
            return True
        
        # Check admin roles
        user_role_ids = [role.id for role in interaction.user.roles]
        admin_role_ids = administrators.get('roles', [])
        
        return any(role_id in user_role_ids for role_id in admin_role_ids)
    
    async def _restore_original_buttons(self, interaction: discord.Interaction):
        """Restore original buttons after error"""
        try:
            # Get the original embed (should already be set)
            original_embed = interaction.message.embeds[0].copy()
            
            # For transfer applications, restore state-based view
            if self.application_data.get('application_type') == 'transfer':
                # Extract current state and restore appropriate view
                current_state = self._extract_transfer_state_from_embed(original_embed)
                
                # Reset processing status if needed
                for i, field in enumerate(original_embed.fields):
                    if field.name == "📊 Статус" and "Обрабатывается" in field.value:
                        original_embed = self._update_transfer_status_in_embed(original_embed, current_state, interaction.guild)
                        break
                
                # Create state-based view
                restored_view = self._create_transfer_buttons_view(current_state)
            else:
                # Regular join application - restore original status
                for i, field in enumerate(original_embed.fields):
                    if field.name == "📊 Статус" and "Обрабатывается" in field.value:
                        original_embed.set_field_at(
                            i,
                            name="📊 Статус",
                            value="⏳ Ожидает рассмотрения",
                            inline=True
                        )
                        break
                
                # Create new view with original buttons
                restored_view = DepartmentApplicationView(self.application_data)
                restored_view.setup_buttons()
            
            # Update message back to original state
            await interaction.edit_original_response(content="", embed=original_embed, view=restored_view)
            
        except Exception as e:
            logger.error(f"Error restoring original buttons: {e}")
    
    async def _process_approval(self, interaction: discord.Interaction, target_user: discord.Member) -> bool:
        """Process application approval - assign roles and update nickname"""
        try:
            dept_code = self.application_data['department_code']
            
            # Get department role
            dept_role_id = ping_manager.get_department_role_id(dept_code)
            if not dept_role_id:
                await interaction.followup.send(
                    f"❌ Роль для подразделения {dept_code} не настроена.",
                    ephemeral=True
                )
                return False
            
            dept_role = interaction.guild.get_role(dept_role_id)
            if not dept_role:
                await interaction.followup.send(
                    f"❌ Роль подразделения {dept_code} не найдена.",
                    ephemeral=True
                )
                return False
            
            # Step 1: Remove ALL department roles (regardless of transfer/join)
            await self._remove_all_department_roles(target_user)
            
            # Step 2: Remove ALL position roles (regardless of transfer/join)
            await self._remove_all_position_roles(target_user)
            
            # Step 3: Assign new department role
            # Get department name for the reason message
            dept_info = ping_manager.get_department_info(dept_code)
            dept_name = dept_info.get('name', dept_code) if dept_info else dept_code
            reason = get_role_reason(interaction.guild.id, "department_application.approved", "Заявка в подразделение: одобрена").format(department_name=dept_name, moderator=interaction.user.mention)
            await target_user.add_roles(dept_role, reason=reason)
            
            # Step 4: Assign assignable position roles for this department
            await self._assign_department_position_roles(target_user, dept_code, interaction.user)
            
            # Step 5: Update nickname with department abbreviation
            await self._update_user_nickname(target_user, dept_code)
            
            # Step 6: Process in database using PersonnelManager
            await self._process_database_operation(interaction, target_user, dept_code)
            
            return True
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Боту не хватает прав для назначения роли или изменения никнейма.",
                ephemeral=True
            )
            return False
        except Exception as e:
            logger.error(f"Error processing application approval: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке заявления.",
                ephemeral=True
            )
            return False
    
    async def _remove_all_department_roles(self, user: discord.Member):
        """Remove ALL department roles from user"""
        all_dept_role_ids = ping_manager.get_all_department_role_ids()
        
        for role_id in all_dept_role_ids:
            role = user.guild.get_role(role_id)
            if role and role in user.roles:
                try:
                    await user.remove_roles(role, reason=get_role_reason(user.guild.id, "role_removal.department_change", "Смена подразделения: снята роль").format(moderator="система"))
                except discord.Forbidden:
                    logger.warning(f"Could not remove department role {role.name} from {user} - insufficient permissions")
                except Exception as e:
                    logger.error(f"Error removing department role {role.name} from {user}: {e}")
    
    async def _remove_all_position_roles(self, user: discord.Member):
        """Remove ALL position roles from user"""
        all_position_role_ids = ping_manager.get_all_position_role_ids()
        
        for role_id in all_position_role_ids:
            role = user.guild.get_role(role_id)
            if role and role in user.roles:
                try:
                    await user.remove_roles(role, reason=get_role_reason(user.guild.id, "role_removal.position_change", "Смена должности: снята роль").format(moderator="система"))
                except discord.Forbidden:
                    logger.warning(f"Could not remove position role {role.name} from {user} - insufficient permissions")
                except Exception as e:
                    logger.error(f"Error removing position role {role.name} from {user}: {e}")
    
    async def _assign_department_position_roles(self, user: discord.Member, dept_code: str, moderator: discord.Member):
        """Assign assignable position roles for the department"""
        # Get moderator display name for audit reasons
        moderator_display = await get_moderator_display_name(moderator)
        
        assignable_role_ids = ping_manager.get_department_assignable_position_roles(dept_code)
        
        logger.info(f"Attempting to assign position roles for {dept_code} to {user.display_name}")
        logger.info(f"Assignable role IDs: {assignable_role_ids}")
        
        if not assignable_role_ids:
            logger.warning(f"No assignable position roles configured for department {dept_code}")
            return
        
        assigned_roles = []
        failed_roles = []
        
        for role_id in assignable_role_ids:
            role = user.guild.get_role(role_id)
            if not role:
                logger.error(f"Role with ID {role_id} not found on server for department {dept_code}")
                failed_roles.append(f"ID:{role_id}")
                continue
                
            logger.info(f"Attempting to assign role {role.name} (ID: {role_id}) to {user.display_name}")
            
            try:
                reason = get_role_reason(user.guild.id, "position_assignment.assigned", "Назначение должности").format(position=role.name, moderator=moderator_display)
                await user.add_roles(role, reason=reason)
                assigned_roles.append(role.name)
                logger.info(f"Successfully assigned role {role.name} to {user.display_name}")
            except discord.Forbidden:
                logger.warning(f"Could not assign position role {role.name} to {user} - insufficient permissions")
                failed_roles.append(role.name)
            except Exception as e:
                logger.error(f"Error assigning position role {role.name} to {user}: {e}")
                failed_roles.append(role.name)
        
        # Log results
        if assigned_roles:
            logger.info(f"Assigned position roles to {user}: {', '.join(assigned_roles)}")
        if failed_roles:
            logger.warning(f"Failed to assign position roles to {user}: {', '.join(failed_roles)}")
        
        logger.info(f"Position role assignment complete for {user.display_name}: {len(assigned_roles)} assigned, {len(failed_roles)} failed")
    
    async def _remove_old_department_roles(self, user: discord.Member, new_dept_code: str):
        """Legacy method - now calls the new comprehensive role removal"""
        await self._remove_all_department_roles(user)
    
    async def _update_user_nickname(self, user: discord.Member, dept_code: str):
        """Update user nickname with department abbreviation using nickname_manager"""
        try:
            # Проверяем настройки автозамены никнеймов
            if not self._should_update_nickname_for_dept(dept_code):
                print(f"🚫 DEPT NICKNAME: Автозамена отключена для {dept_code}")
                return
            
            # Определяем тип операции
            application_type = self.application_data.get('application_type', 'join')
            
            # Получаем данные о сотруднике из БД
            try:
                from utils.database_manager import PersonnelManager
                pm = PersonnelManager()
                personnel_data = await pm.get_personnel_summary(user.id)
            except Exception as e:
                print(f"⚠️ Не удалось получить данные из БД: {e}")
                personnel_data = None
            
            if application_type == 'transfer' or personnel_data:
                # Перевод в подразделение (есть данные в БД)
                print(f"🎆 DEPT APPLICATION: Перевод {user.display_name} в {dept_code}")
                
                current_rank = personnel_data.get('rank', 'Рядовой') if personnel_data else 'Рядовой'
                
                # Используем dept_code напрямую как subdivision_key для nickname_manager
                # nickname_manager сам разберется с маппингом через SubdivisionMapper
                new_nickname = await nickname_manager.handle_transfer(
                    member=user,
                    subdivision_key=dept_code,
                    rank_name=current_rank
                )
                
                if new_nickname:
                    await user.edit(nick=new_nickname, reason=get_role_reason(user.guild.id, "nickname_change.department_transfer", "Перевод в подразделение: изменён никнейм").format(moderator="система"))
                    print(f"✅ DEPT NICKNAME: Никнейм обновлён: {new_nickname}")
                else:
                    # Fallback к улучшенному методу
                    await self._update_nickname_smart_fallback(user, dept_code)
                    print(f"⚠️ DEPT FALLBACK: Использовали smart fallback метод")
            
            else:
                # Приём в подразделение (новобранец)
                print(f"🎆 DEPT APPLICATION: Приём в {dept_code} {user.display_name}")
                
                # Для новобранцев попробуем handle_hiring, если не получится - smart fallback
                try:
                    # Извлекаем имя из текущего никнейма для handle_hiring
                    parsed_nickname = nickname_manager.parse_nickname(user.display_name)
                    name_from_nick = parsed_nickname.get('name', user.display_name)
                    
                    if name_from_nick and ' ' in name_from_nick:
                        first_name, last_name = nickname_manager.extract_name_parts(name_from_nick)
                        
                        new_nickname = await nickname_manager.handle_hiring(
                            member=user,
                            rank_name='Рядовой',  # Новобранец получает базовое звание
                            first_name=first_name,
                            last_name=last_name
                        )
                        
                        if new_nickname:
                            await user.edit(nick=new_nickname, reason=get_role_reason(user.guild.id, "nickname_change.department_join", "Приём в подразделение: изменён никнейм").format(moderator="система"))
                            print(f"✅ DEPT HIRING: Никнейм обновлён через handle_hiring: {new_nickname}")
                            return
                    
                except Exception as e:
                    print(f"⚠️ handle_hiring не сработал: {e}")
                
                # Если handle_hiring не сработал, используем smart fallback
                await self._update_nickname_smart_fallback(user, dept_code)
                print(f"✅ DEPT JOIN: Никнейм обновлён для новобранца через smart fallback")
                
        except discord.Forbidden:
            logger.warning(f"Could not update nickname for {user} - insufficient permissions")
        except Exception as e:
            logger.error(f"Error updating nickname for {user}: {e}")
            # Fallback к улучшенному методу при ошибках
            try:
                await self._update_nickname_smart_fallback(user, dept_code)
            except Exception as fallback_error:
                logger.error(f"Even smart fallback nickname update failed: {fallback_error}")

    def _should_update_nickname_for_dept(self, dept_code: str) -> bool:
        """Проверяет, включена ли автозамена никнеймов для подразделения"""
        try:
            from utils.config_manager import load_config
            config = load_config()
            nickname_settings = config.get('nickname_auto_replacement', {})
            
            # Проверяем глобальную настройку
            if not nickname_settings.get('enabled', True):
                return False
            
            # Проверяем настройку для подразделения
            department_settings = nickname_settings.get('departments', {})
            return department_settings.get(dept_code, True)  # По умолчанию включена
            
        except Exception as e:
            logger.error(f"Ошибка при проверке настроек автозамены для {dept_code}: {e}")
            return True  # При ошибке разрешаем
    
    async def _update_nickname_smart_fallback(self, user: discord.Member, dept_code: str):
        """Улучшенный fallback метод для обновления никнейма с анализом текущего никнейма"""
        try:
            from utils.config_manager import load_config
            config = load_config()
            
            # Получаем аббревиатуру подразделения из config
            dept_config = config.get('departments', {}).get(dept_code, {})
            abbreviation = dept_config.get('abbreviation', dept_code)
            
            # Анализируем текущий никнейм пользователя
            current_nickname = user.display_name
            parsed_nickname = nickname_manager.parse_nickname(current_nickname)
            
            # Извлекаем имя из текущего никнейма
            name_to_use = None
            
            if parsed_nickname.get('name'):
                # Используем имя из текущего никнейма
                name_to_use = parsed_nickname['name']
            else:
                # Fallback к оригинальному имени пользователя
                name_to_use = user.name
            
            # Формируем новый никнейм в формате "ABBREVIATION | Name"
            new_nickname = f"{abbreviation} | {name_to_use}"
            
            # Обрезаем до лимита Discord (32 символа)
            if len(new_nickname) > 32:
                # Сначала пробуем сократить имя
                available_for_name = 32 - len(f"{abbreviation} | ")
                if available_for_name > 0:
                    truncated_name = name_to_use[:available_for_name]
                    new_nickname = f"{abbreviation} | {truncated_name}"
                else:
                    # В крайнем случае используем только аббревиатуру
                    new_nickname = abbreviation[:32]
            
            await user.edit(nick=new_nickname, reason=get_role_reason(user.guild.id, "nickname_change.department_join", "Приём в подразделение: изменён никнейм").format(moderator="система"))
            logger.info(f"Applied smart fallback nickname: {user} -> {new_nickname}")
            
        except discord.Forbidden:
            logger.warning(f"No permission to change nickname for {user}")
        except Exception as e:
            logger.error(f"Smart fallback nickname update failed: {e}")
            raise
    
    async def _update_nickname_fallback(self, user: discord.Member, dept_code: str):
        """Fallback method for updating nickname with simple department prefix"""
        try:
            from utils.config_manager import load_config
            config = load_config()
            
            # Get department abbreviation from config
            dept_config = config.get('departments', {}).get(dept_code, {})
            abbreviation = dept_config.get('abbreviation', dept_code)
            
            # Create simple nickname format: "ABBREVIATION | Username"
            fallback_nickname = f"{abbreviation} | {user.name}"
            
            # Trim to Discord's 32 character limit
            if len(fallback_nickname) > 32:
                fallback_nickname = fallback_nickname[:32]
            
            await user.edit(nick=fallback_nickname, reason=get_role_reason(user.guild.id, "nickname_change.department_join", "Приём в подразделение: изменён никнейм").format(moderator="система"))
            logger.info(f"Applied fallback nickname: {user} -> {fallback_nickname}")
            
        except discord.Forbidden:
            logger.warning(f"No permission to change nickname for {user}")
        except Exception as e:
            logger.error(f"Fallback nickname update failed: {e}")
            raise
    
    async def _process_database_operation(self, interaction: discord.Interaction, target_user: discord.Member, dept_code: str):
        """Process department application in PostgreSQL database"""
        try:
            from utils.database_manager import PersonnelManager, SubdivisionMapper
            from utils.audit_logger import audit_logger, AuditAction
            from utils.config_manager import load_config
            
            # Initialize managers
            pm = PersonnelManager()
            subdivision_mapper = SubdivisionMapper()
            config = load_config()
            
            # Get department name from config
            dept_config = config.get('departments', {}).get(dept_code, {})
            dept_name = dept_config.get('name', dept_code)
            
            # Prepare application data for PersonnelManager
            application_data = {
                'target_department': dept_name,
                'reason': self.application_data.get('reason', 'Заявка в подразделение'),
                'application_type': self.application_data.get('application_type', 'join')
            }
            
            # Determine moderator info
            moderator_info = f"{interaction.user.display_name} ({interaction.user.id})"
            
            # Process based on application type
            if self.application_data.get('application_type') == 'transfer':
                # Department transfer
                success, message = await pm.process_department_transfer(
                    application_data=application_data,
                    user_discord_id=target_user.id,
                    moderator_discord_id=interaction.user.id,
                    moderator_info=moderator_info
                )
            else:
                # Department join
                success, message = await pm.process_department_join(
                    application_data=application_data,
                    user_discord_id=target_user.id,
                    moderator_discord_id=interaction.user.id,
                    moderator_info=moderator_info
                )
            
            # Get personnel data for audit
            personnel_data_summary = await pm.get_personnel_summary(target_user.id)
            if not personnel_data_summary:
                # Fallback personnel data if not found in DB
                personnel_data = {
                    'name': target_user.display_name,
                    'static': 'Неизвестно',
                    'rank': 'Неизвестно',
                    'department': dept_name,
                    'position': 'Неизвестно'
                }
            else:
                # Format personnel data correctly for audit
                personnel_data = {
                    'name': get_safe_personnel_name(personnel_data_summary, target_user.display_name),
                    'static': personnel_data_summary.get('static', ''),
                    'rank': personnel_data_summary.get('rank', 'Неизвестно'),
                    'department': dept_name,
                    'position': personnel_data_summary.get('position', 'Неизвестно')
                }
            
            # Send audit notification (without custom_fields to maintain standard audit format)
            if self.application_data.get('application_type') == 'transfer':
                action = await AuditAction.DEPARTMENT_TRANSFER()
            else:
                action = await AuditAction.DEPARTMENT_JOIN()
            
            audit_url = await audit_logger.send_personnel_audit(
                guild=interaction.guild,
                action=action,
                target_user=target_user,
                moderator=interaction.user,
                personnel_data=personnel_data,
                config=config
            )
            
            # Additional audit for position assignment if assignable positions were granted
            assignable_role_ids = ping_manager.get_department_assignable_position_roles(dept_code)
            if assignable_role_ids:
                # Get the names of assigned position roles and update database
                assigned_position_names = []
                for role_id in assignable_role_ids:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        assigned_position_names.append(role.name)
                        # Update position_subdivision_id in database
                        from utils.database_manager.position_manager import position_manager
                        await position_manager.update_position_subdivision_by_role_id(
                            target_user.id, role_id, dept_code, interaction.user.id
                        )
                
                if assigned_position_names:
                    # Create updated personnel data for position assignment audit
                    position_personnel_data = personnel_data.copy()
                    position_personnel_data['position'] = ', '.join(assigned_position_names)
                    
                    # Send position assignment audit
                    position_action = await AuditAction.POSITION_ASSIGNMENT()
                    await audit_logger.send_personnel_audit(
                        guild=interaction.guild,
                        action=position_action,
                        target_user=target_user,
                        moderator=interaction.user,
                        personnel_data=position_personnel_data,
                        config=config
                    )
            
            if success:
                logger.info(f"Successfully processed department application: {message}")
            else:
                logger.warning(f"Database operation completed with issues: {message}")
                
        except Exception as e:
            logger.error(f"Error processing database operation: {e}")
            # Don't fail the whole application if database logging fails
    
    # PostgreSQL Migration: Google Sheets logging methods removed
    # All logging now handled by PostgreSQL backend through sheets_manager
    
    def _extract_role_mentions_from_content(self, content: str) -> List[List[int]]:
        """
        Extract role IDs from content lines
        Returns list of lists - each inner list contains role IDs from one line
        """
        import re
        
        lines = content.strip().split('\n') if content else []
        role_lines = []
        
        for line in lines:
            # Find all role mentions in format <@&role_id>
            role_pattern = r'<@&(\d+)>'
            role_ids = [int(match) for match in re.findall(role_pattern, line)]
            role_lines.append(role_ids)
        
        return role_lines
    
    async def _check_approve_permissions(self, interaction: discord.Interaction) -> bool:
        """
        Check if user has permission to approve applications
        - Admins can approve anything
        - Moderators can only approve if they have at least one role from FIRST LINE of content
        """

        config = load_config()
        administrators = config.get('administrators', {})
        moderators = config.get('moderators', {})
        user_role_ids = [role.id for role in interaction.user.roles]

        # Check if user is administrator (can approve anything)
        is_admin = (
            interaction.user.id in administrators.get('users', []) or
            any(role_id in user_role_ids for role_id in administrators.get('roles', []))
        )

        print(f"DEBUG: Является ли пользователь администратором: {is_admin}")

        if is_admin:
            return True
        
        # Check if user is moderator
        is_moderator = (
            interaction.user.id in moderators.get('users', []) or
            any(role_id in user_role_ids for role_id in moderators.get('roles', []))
        )
        print(f"DEBUG: Является ли пользователь модератором: {is_moderator}")
        if not is_moderator:
            return False

        # Extract roles from first line of content
        content = interaction.message.content if interaction.message else ""
        role_lines = self._extract_role_mentions_from_content(content)
        
        if not role_lines or not role_lines[0]:
            # No roles in content or empty first line - fallback to old logic
            return await self._eck_moderator_permissions(interaction)
        
        first_line_role_ids = role_lines[0]
        print(f"DEBUG: Требуемые роли из первой строки сообщения (ID): {first_line_role_ids}")

        # Check if moderator has at least one role from first line
        has_required_role = any(role_id in user_role_ids for role_id in first_line_role_ids)

        return has_required_role
    
    async def _check_reject_permissions(self, interaction: discord.Interaction) -> bool:
        """
        Check if user has permission to reject applications
        - Admins can reject anything
        - Moderators can reject if they have at least one role from ANY LINE of content
        """
        config = load_config()
        administrators = config.get('administrators', {})
        moderators = config.get('moderators', {})
        user_role_ids = [role.id for role in interaction.user.roles]
        
        # Check if user is administrator (can reject anything)
        is_admin = (
            interaction.user.id in administrators.get('users', []) or
            any(role_id in user_role_ids for role_id in administrators.get('roles', []))
        )
        
        if is_admin:
            return True
        
        # Check if user is moderator
        is_moderator = (
            interaction.user.id in moderators.get('users', []) or
            any(role_id in user_role_ids for role_id in moderators.get('roles', []))
        )
        
        if not is_moderator:
            return False
        
        # Extract roles from all lines of content
        content = interaction.message.content if interaction.message else ""
        role_lines = self._extract_role_mentions_from_content(content)
        
        if not role_lines:
            # No roles in content - fallback to old logic
            return await self._check_moderator_permissions(interaction)
        
        # Collect all role IDs from all lines
        all_role_ids = []
        for line_roles in role_lines:
            all_role_ids.extend(line_roles)
        
        if not all_role_ids:
            # No roles found - fallback to old logic
            return await self._check_moderator_permissions(interaction)
        
        # Check if moderator has at least one role from any line
        has_required_role = any(role_id in user_role_ids for role_id in all_role_ids)
        
        return has_required_role
    
    async def _check_permission_permissions(self, interaction: discord.Interaction) -> bool:
        """
        Check if user has permission to give permission for transfers
        - Admins can give permission for anything
        - Moderators can give permission if they have at least one role from SECOND LINE of content
        """
        config = load_config()
        administrators = config.get('administrators', {})
        moderators = config.get('moderators', {})
        user_role_ids = [role.id for role in interaction.user.roles]
        
        # Check if user is administrator (can give permission for anything)
        is_admin = (
            interaction.user.id in administrators.get('users', []) or
            any(role_id in user_role_ids for role_id in administrators.get('roles', []))
        )
        
        if is_admin:
            return True
        
        # Check if user is moderator
        is_moderator = (
            interaction.user.id in moderators.get('users', []) or
            any(role_id in user_role_ids for role_id in moderators.get('roles', []))
        )
        
        if not is_moderator:
            return False
        
        # Extract roles from second line of content
        content = interaction.message.content if interaction.message else ""
        role_lines = self._extract_role_mentions_from_content(content)
        
        if not role_lines or len(role_lines) < 2 or not role_lines[1]:
            # No roles in content or no second line - fallback to old logic
            return await self._check_moderator_permissions(interaction)
        
        second_line_role_ids = role_lines[1]
        
        # Check if moderator has at least one role from second line
        has_required_role = any(role_id in user_role_ids for role_id in second_line_role_ids)
        
        return has_required_role
    
    def _get_approve_permission_error_message(self, interaction: discord.Interaction) -> str:
        """Get error message for approve permission denial"""
        content = interaction.message.content if interaction.message else ""
        role_lines = self._extract_role_mentions_from_content(content)
        
        if role_lines and role_lines[0]:
            first_line_roles = [interaction.guild.get_role(role_id) for role_id in role_lines[0]]
            valid_roles = [role for role in first_line_roles if role is not None]
            
            if valid_roles:
                role_names = [role.name for role in valid_roles]
                return f"❌ Вы не можете одобрить это заявление.\n\n" \
                       f"**Для одобрения требуется одна из ролей:**\n" \
                       f"• {chr(10).join(f'`{name}`' for name in role_names)}"
        
        return "❌ У вас нет прав для одобрения этого заявления."
    
    def _get_reject_permission_error_message(self, interaction: discord.Interaction) -> str:
        """Get error message for reject permission denial"""
        content = interaction.message.content if interaction.message else ""
        role_lines = self._extract_role_mentions_from_content(content)
        
        all_role_ids = []
        for line_roles in role_lines:
            all_role_ids.extend(line_roles)
        
        if all_role_ids:
            all_roles = [interaction.guild.get_role(role_id) for role_id in all_role_ids]
            valid_roles = list(set([role for role in all_roles if role is not None]))  # Remove duplicates
            
            if valid_roles:
                role_names = [role.name for role in valid_roles]
                return f"❌ Вы не можете отклонить это заявление.\n\n" \
                       f"**Для отклонения требуется одна из ролей:**\n" \
                       f"• {chr(10).join(f'`{name}`' for name in role_names)}"
        
        return "❌ У вас нет прав для отклонения этого заявления."
    
    def _get_permission_error_message(self, interaction: discord.Interaction) -> str:
        """Get error message for permission denial"""
        content = interaction.message.content if interaction.message else ""
        role_lines = self._extract_role_mentions_from_content(content)
        
        if role_lines and len(role_lines) >= 2 and role_lines[1]:
            second_line_roles = [interaction.guild.get_role(role_id) for role_id in role_lines[1]]
            valid_roles = [role for role in second_line_roles if role is not None]
            
            if valid_roles:
                role_names = [role.name for role in valid_roles]
                return f"❌ Вы не можете дать разрешение на этот перевод.\n\n" \
                       f"**Для выдачи разрешения требуется одна из ролей:**\n" \
                       f"• {chr(10).join(f'`{name}`' for name in role_names)}"
        
        return "❌ У вас нет прав для выдачи разрешения на этот перевод."

class RejectionReasonModal(ui.Modal):
    """Modal for entering rejection reason"""
    
    def __init__(self, application_data: Dict[str, Any]):
        super().__init__(title="Причина отклонения", timeout=300)
        self.application_data = application_data
        
        self.reason = ui.TextInput(
            label="Причина отклонения",
            placeholder="Укажите причину отклонения заявления...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle rejection with reason"""
        try:
            await interaction.response.defer()
            
            # Get target user
            target_user = interaction.guild.get_member(self.application_data['user_id'])
            
            # Update embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            
            # Update status field
            for i, field in enumerate(embed.fields):
                if field.name == "📊 Статус":
                    embed.set_field_at(
                        i,
                        name="📊 Статус",
                        value=f"❌ Отклонено {interaction.user.mention}",
                        inline=True
                    )
                    break
            
            # Add rejection reason
            embed.add_field(
                name="📝 Причина отклонения",
                value=self.reason.value,
                inline=False
            )
            
            embed.add_field(
                name="⏰ Время обработки",
                value=f"<t:{int((datetime.now(timezone(timedelta(hours=3)))).timestamp())}:R>",
                inline=True
            )
            
            # Clear all buttons and add single disabled "Rejected" button
            view = DepartmentApplicationView(self.application_data)
            view.setup_buttons()
            view.clear_items()
            
            # Clear user's cache since status changed
            _clear_user_cache(self.application_data['user_id'])
            
            rejected_button = ui.Button(
                label="❌ Отклонено",
                style=discord.ButtonStyle.red,
                disabled=True
            )
            view.add_item(rejected_button)
            
            await interaction.edit_original_response(content="", embed=embed, view=view)
            
            # Send success message
            await interaction.followup.send(
                f"❌ Заявление пользователя {target_user.mention if target_user else 'неизвестного пользователя'} отклонено.",
                ephemeral=True
            )
            
            # Send DM to user if possible
            if target_user:
                try:
                    dm_embed = discord.Embed(
                        title=get_private_messages(interaction.guild.id, 'department_applications.rejection.title'),
                        description=get_private_messages(interaction.guild.id, 'department_applications.rejection.description').format(
                            department_code=self.application_data['department_code']
                        ),
                        color=discord.Color.red(),
                        timestamp=datetime.now(timezone(timedelta(hours=3)))
                    )
                    dm_embed.add_field(
                        name=get_private_messages(interaction.guild.id, 'department_applications.rejection.reason_field'),
                        value=self.reason.value,
                        inline=False
                    )
                    await target_user.send(embed=dm_embed)
                except discord.Forbidden:
                    logger.warning(f"Could not send DM to {target_user} about rejected application")
            
        except Exception as e:
            logger.error(f"Error processing application rejection: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при отклонении заявления.",
                ephemeral=True
            )

class ConfirmDeletionView(ui.View):
    """Confirmation view for deletion"""
    
    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed = False
    
    @ui.button(label="✅ Да, удалить", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = True
        self.stop()
    
    @ui.button(label="❌ Отмена", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = False
        self.stop()

class DepartmentSelectView(ui.View):
    """Button view for choosing department application type"""
    
    def __init__(self, department_code: str):
        super().__init__(timeout=None)  # Persistent view
        self.department_code = department_code
        
        # Set custom_id for persistence - ВАЖНО!
        self.custom_id = f"dept_select_{department_code}"
        
        # Update button custom_ids to be unique per department
        self.join_button.custom_id = f"dept_app_join_{department_code}"
        self.transfer_button.custom_id = f"dept_app_transfer_{department_code}"
    
    @ui.button(label=get_ui_label(0, "join_department"), style=discord.ButtonStyle.green, emoji="➕")
    async def join_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle department join application"""
        await self._handle_application_type(interaction, "join")
    
    @ui.button(label="Перевод из другого подразделения", style=discord.ButtonStyle.blurple, emoji="🔄")
    async def transfer_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle department transfer application"""
        await self._handle_application_type(interaction, "transfer")
    
    async def _handle_application_type(self, interaction: discord.Interaction, app_type: str):
        """Handle department application type selection"""
        try:
            # Get department code from view's custom_id: dept_select_{department_code}
            if hasattr(self, 'custom_id') and self.custom_id.startswith('dept_select_'):
                department_code = self.custom_id.replace('dept_select_', '')
            else:
                # Fallback to instance variable
                department_code = getattr(self, 'department_code', 'ВВ')
            
            # Update instance variables for compatibility
            self.department_code = department_code
            
            # БЫСТРАЯ ОТПРАВКА МОДАЛЬНОГО ОКНА - отвечаем в течение 1 секунды
            from .modals import DepartmentApplicationStage1Modal
            modal = DepartmentApplicationStage1Modal(department_code, app_type, interaction.user.id, skip_data_loading=True)
            await interaction.response.send_modal(modal)
            
            # ПРОВЕРКА АКТИВНЫХ ЗАЯВЛЕНИЙ В ФОНЕ (асинхронно)
            # Если найдем активные заявления - закроем модальное окно через followup
            try:
                active_check = await check_user_active_applications(
                    interaction.guild, 
                    interaction.user.id
                )
                
                if active_check['has_active']:
                    # Модальное окно уже открыто, но мы можем отправить уведомление
                    # Discord автоматически закроет модальное окно при отправке followup
                    departments_list = ", ".join(active_check['departments'])
                    await interaction.followup.send(
                        f"❌ **У вас уже есть активное заявление на рассмотрении**\n\n"
                        f"📋 Подразделения: **{departments_list}**\n"
                        f"⏳ Дождитесь рассмотрения текущего заявления перед подачей нового.\n\n"
                        f"💡 Активные заявления можно найти в каналах заявлений соответствующих подразделений.",
                        ephemeral=True
                    )
                    # Пользователь увидит это сообщение, если попытается отправить заявление
                    
            except Exception as bg_error:
                logger.warning(f"Background check for active applications failed: {bg_error}")
                # Не останавливаем процесс - пользователь может продолжить подачу заявления
            
        except Exception as e:
            logger.error(f"Error in department application: {e}")
            try:
                await interaction.response.send_message(
                    "❌ Произошла ошибка. Попробуйте еще раз.",
                    ephemeral=True
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    "❌ Произошла ошибка. Попробуйте еще раз.",
                    ephemeral=True
                )

# Active applications cache for performance optimization
_active_applications_cache = {}
_cache_expiry = {}

def _is_cache_valid(user_id: int) -> bool:
    """Check if cache for user is still valid"""
    if user_id not in _cache_expiry:
        return False
    
    from datetime import datetime, timedelta
    return datetime.now() < _cache_expiry[user_id]

def _cache_user_active_status(user_id: int, has_active: bool, departments: list):
    """Cache user's active application status for 30 seconds"""
    from datetime import datetime, timedelta
    
    _active_applications_cache[user_id] = {
        'has_active': has_active,
        'departments': departments
    }
    _cache_expiry[user_id] = datetime.now() + timedelta(seconds=30)

def _get_cached_active_status(user_id: int) -> Dict:
    """Get cached active status if available and valid"""
    if _is_cache_valid(user_id):
        cached = _active_applications_cache.get(user_id, {})
        return {
            'has_active': cached.get('has_active', False),
            'applications': [],  # Don't cache message objects
            'departments': cached.get('departments', [])
        }
    return None

def _clear_user_cache(user_id: int):
    """Clear cache for user (call when application is submitted/processed)"""
    _active_applications_cache.pop(user_id, None)
    _cache_expiry.pop(user_id, None)

async def check_user_active_applications(guild: discord.Guild, user_id: int, department_code: str = None) -> Dict:
    """
   
    Check if user has any active (pending) applications - OPTIMIZED WITH CACHE
    
    Args:
        guild: Discord guild to search in
        user_id: User ID to check applications for
        department_code: Optional - check for specific department only
        
    Returns:
        dict: {
            'has_active': bool,
            'applications': [list of active application messages],
            'departments': [list of department codes with active applications]
        }
    """
    # Try cache first (30 second expiry)
    cached_result = _get_cached_active_status(user_id)
    if cached_result is not None:
        logger.info(f"⚡ Using cached active applications status for user {user_id}")
        return cached_result
    
    result = {
        'has_active': False,
        'applications': [],
        'departments': []
    }
    
    try:
        config = load_config()
        departments = config.get('departments', {})
        
        # Check each department or specific department
        depts_to_check = [department_code] if department_code else departments.keys()
        
        # OPTIMIZATION: Limit search and use timeout
        max_messages_per_channel = 50  # Reduced from 100
        search_timeout = 2.0  # Maximum 2 seconds per channel
        
        for dept_code in depts_to_check:
            dept_config = departments.get(dept_code, {})
            channel_id = dept_config.get('application_channel_id')
            
            if not channel_id:
                continue
                
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            
            try:
                # Use asyncio.timeout for faster failure
                import asyncio
                
                async def check_channel_for_user():
                    # Check recent messages for user's applications
                    async for message in channel.history(limit=max_messages_per_channel):
                        if not message.embeds:
                            continue
                            
                        embed = message.embeds[0]
                        
                        # Quick check if this is a department application
                        if not embed.footer or not embed.footer.text:
                            continue
                            
                        if f"ID заявления: {user_id}" in embed.footer.text:
                            # Quick check if application is still pending (has view with enabled buttons)
                            if message.components:
                                # Check if buttons are not disabled
                                for action_row in message.components:
                                    for component in action_row.children:
                                        if hasattr(component, 'disabled') and not component.disabled:
                                            # Found active application
                                            result['has_active'] = True
                                            result['applications'].append(message)
                                            if dept_code not in result['departments']:
                                                result['departments'].append(dept_code)
                                            return True  # Early exit when found
                            break  # Only check the most recent application per user per department
                    return False
                
                # Apply timeout to channel check
                found_active = await asyncio.wait_for(check_channel_for_user(), timeout=search_timeout)
                
                # If found active application, we can stop checking other departments
                if found_active and not department_code:
                    break
                    
            except asyncio.TimeoutError:
                logger.warning(f"Timeout checking active applications in department {dept_code} - skipping")
                continue
            except Exception as channel_error:
                logger.error(f"Error checking applications in department {dept_code}: {channel_error}")
                continue
        
        # Cache the result for 30 seconds
        _cache_user_active_status(user_id, result['has_active'], result['departments'])
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking user active applications: {e}")
        return result
