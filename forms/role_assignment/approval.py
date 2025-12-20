"""
Application approval system for role assignments

This module handles the approval/rejection workflow with proper interaction handling.
"""

import discord
from discord import ui
import asyncio
from utils.config_manager import load_config, is_moderator_or_admin, is_blacklisted_user, is_administrator
from utils.config_manager import is_administrator, load_config, is_moderator_or_admin
from utils.message_manager import get_private_messages, get_role_reason, get_moderator_display_name
from utils.message_service import MessageService
# PostgreSQL integration with enhanced personnel management
from utils.database_manager import personnel_manager
from utils.database_manager.rank_manager import rank_manager
from utils.nickname_manager import nickname_manager
from utils.audit_logger import audit_logger
from .base import get_channel_with_fallback
from .views import ApprovedApplicationView, RejectedApplicationView, ProcessingApplicationView
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class RoleApplicationApprovalView(ui.View):
    """View for approving/rejecting role applications"""
    
    def __init__(self, application_data):
        super().__init__(timeout=None)
        self.application_data = application_data
    
    def _extract_application_data_from_embed(self, embed: discord.Embed) -> dict:
        """Извлечение актуальных данных заявки из embed сообщения"""
        try:
            application_data = {}
            
            # Извлекаем данные из полей embed
            for field in embed.fields:
                # Заявитель
                if field.name == "👤 Заявитель":
                    user_mention = field.value
                    import re
                    match = re.search(r'<@!?(\d+)>', user_mention)
                    if match:
                        application_data['user_id'] = int(match.group(1))
                        application_data['user_mention'] = user_mention
                # Имя/Фамилия (военные и поставщики)
                elif field.name == "📝 Имя Фамилия":
                    application_data['name'] = field.value
                # Статик (разные эмодзи в формах)
                elif field.name in ("🔢 Статик", "🆔 Статик"):
                    application_data['static'] = field.value
                # Звание (военные)
                elif field.name == "🎖️ Звание":
                    application_data['rank'] = field.value
                # Фракция/должность (гос/поставки)
                elif "Фракция" in field.name:
                    application_data['faction'] = field.value
                # Цель получения роли (гос)
                elif field.name == "🎯 Цель получения роли":
                    application_data['purpose'] = field.value
                # Удостоверение/доказательства (ссылка)
                elif "Удостоверение" in field.name:
                    import re
                    link_match = re.search(r'\[.*?\]\((.*?)\)', field.value)
                    application_data['proof'] = link_match.group(1) if link_match else field.value
            
            # Определяем тип заявки из заголовка embed
            if embed.title:
                if "военнослужащего" in embed.title.lower():
                    application_data['type'] = 'military'
                elif "доступа к поставкам" in embed.title.lower():
                    application_data['type'] = 'supplier'
                elif "госслужащего" in embed.title.lower():
                    application_data['type'] = 'civilian'
            
            # Добавляем timestamp
            if embed.timestamp:
                application_data['timestamp'] = embed.timestamp.isoformat()
            
            # Сохраняем оригинальные данные из self.application_data для совместимости
            application_data['original_user_id'] = self.application_data.get('user_id')
            
            return application_data
            
        except Exception as e:
            logger.error("Error extracting application data from embed: %s", e)
            return {}
    
    def _get_current_application_data(self, interaction: discord.Interaction) -> dict:
        """Получение актуальных (текущих) данных заявки из embed"""
        # Всегда извлекаем данные из embed, чтобы получить актуальные значения
        if interaction.message and interaction.message.embeds:
            return self._extract_application_data_from_embed(interaction.message.embeds[0])
        
        # Если embed недоступен, используем оригинальные данные как fallback
        return self.application_data

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
        
        # Get current application data (including applicant user_id)
        current_data = self._get_current_application_data(interaction)
        applicant_user_id = current_data.get('user_id')
        
        if not applicant_user_id:
            await interaction.response.send_message(
                "❌ Не удалось определить ID заявителя из заявки.",
                ephemeral=True
            )
            return
        
        # Check if APPLICANT has active blacklist entry
        from utils.database_manager import personnel_manager
        
        # Предпочитаем статик из заявки; если его нет, падаем обратно на discord_id
        blacklist_lookup = self.application_data.get('static') or applicant_user_id
        blacklist_info = await personnel_manager.check_active_blacklist(blacklist_lookup)
        
        if blacklist_info:
            # Applicant is blacklisted, deny application
            start_date_str = blacklist_info['start_date'].strftime('%d.%m.%Y')
            end_date_str = blacklist_info['end_date'].strftime('%d.%m.%Y') if blacklist_info['end_date'] else 'Бессрочно'
            
            await interaction.response.send_message(
                f"❌ **Вы не можете одобрить заявку этого человека**\n\n"
                f"📋 **Заявитель находится в Чёрном списке ВС РФ**\n"
                f"> **Причина:** {blacklist_info['reason']}\n"
                f"> **Период:** {start_date_str} - {end_date_str}\n\n"
                f"*Обратитесь к руководству бригады для снятия с чёрного списка.*",
                ephemeral=True
            )
            return
        
        # Check for static duplication (only for military applications with static)
        if self.application_data.get('type') == 'military' and self.application_data.get('static'):
            from utils.postgresql_pool import get_db_cursor
            try:
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        SELECT discord_id, first_name, last_name, static, is_dismissal, dismissal_date
                        FROM personnel
                        WHERE static = %s AND discord_id != %s
                        LIMIT 1;
                    """, (self.application_data['static'], applicant_user_id))
                    
                    existing_record = cursor.fetchone()
                    
                    if existing_record:
                        # Static already exists for another user - show warning
                        await self._show_static_conflict_warning(
                            interaction,
                            existing_record,
                            applicant_user_id
                        )
                        return
            except Exception as db_error:
                logger.error("Error checking static duplication: %s", db_error)
                # Continue with approval if DB check fails
        
        try:
            await self._process_approval(interaction)
        except Exception as e:
            logger.error("Error in approval process: %s", e)
            # Use proper error handling based on interaction state
            MessageService.send_error(interaction, "Произошла ошибка при одобрении заявки.")
    
    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.red, custom_id="reject_role_app")
    async def reject_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle application rejection"""
        # Check permissions first
        if not await self._check_moderator_permissions(interaction):
            MessageService.send_error(interaction, "У вас нет прав для модерации заявок.")
            return
        
        try:
            await self._request_rejection_reason(interaction)
        except Exception as e:
            logger.error("Error in rejection process: %s", e)
            MessageService.send_error(interaction, "Произошла ошибка при отклонении заявки.")
    
    @discord.ui.button(label="Изменить", style=discord.ButtonStyle.secondary, custom_id="role_assignment:edit_pending", emoji="✏️")
    async def edit_pending_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Редактирование заявки на рассмотрении (только автор или администраторы)"""
        try:
            # Получаем актуальные данные из embed (не оригинальные!)
            current_application_data = self._get_current_application_data(interaction)
            if not current_application_data:
                await interaction.response.send_message(
                    "❌ Не удалось получить данные заявки!",
                    ephemeral=True
                )
                return
            
            config = load_config()
            # Проверяем права на редактирование: автор заявки или администратор
            can_edit = (
                interaction.user.id == current_application_data.get('user_id') or  # Автор заявки
                is_moderator_or_admin(interaction.user, config)  # Администратор
            )
            
            if not can_edit:
                await interaction.response.send_message(
                    " У вас нет прав для редактирования этой заявки!",
                    ephemeral=True
                )
                return
            
            # Показываем модальное окно для редактирования в зависимости от типа заявки
            application_type = current_application_data.get('type')
            if application_type == 'military':
                from .modals import MilitaryEditModal
                modal = MilitaryEditModal(current_application_data)
            elif application_type == 'civilian':
                from .modals import CivilianEditModal
                modal = CivilianEditModal(current_application_data)
            elif application_type == 'supplier':
                from .modals import SupplierEditModal
                modal = SupplierEditModal(current_application_data)
            else:
                await interaction.response.send_message(
                    "❌ Неизвестный тип заявки!",
                    ephemeral=True
                )
                return
            
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            await interaction.response.send_message(
                f" Произошла ошибка при редактировании заявки: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="Удалить", style=discord.ButtonStyle.secondary, custom_id="role_assignment:delete_pending", emoji="🗑️")
    async def delete_pending_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Удаление заявки на рассмотрении (только автор или администраторы)"""
        try:
            # Получаем актуальные данные из embed
            current_application_data = self._get_current_application_data(interaction)
            if not current_application_data:
                MessageService.send_error(interaction, "Не удалось получить данные заявки!")
                return
            
            config = load_config()
            # Проверяем права на удаление: автор заявки или администратор
            can_delete = (
                interaction.user.id == current_application_data.get('user_id') or  # Автор заявки
                is_administrator(interaction.user, config)  # Администратор
            )
            
            if not can_delete:
                await interaction.response.send_message(
                    " У вас нет прав для удаления этой заявки!",
                    ephemeral=True
                )
                return
            
            # Показываем подтверждение удаления
            confirmation_view = DeleteConfirmationView(interaction.message)
            embed = discord.Embed(
                title="🗑️ Подтверждение удаления",
                description="Вы уверены, что хотите удалить эту заявку?\n\n**Это действие нельзя отменить!**",
                color=discord.Color.orange()
            )
            
            await interaction.response.send_message(
                embed=embed,
                view=confirmation_view,
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.response.send_message(
                f" Произошла ошибка при удалении заявки: {str(e)}",
                ephemeral=True
            )

    async def _show_static_conflict_warning(self, interaction, existing_record, new_user_id):
        """Show warning about static conflict and ask for confirmation"""
        try:
            old_discord_id = existing_record['discord_id']
            old_first_name = existing_record['first_name']
            old_last_name = existing_record['last_name']
            old_static = existing_record['static']
            is_dismissed = existing_record['is_dismissal']
            dismissal_date = existing_record['dismissal_date']
            
            # Format dismissal status
            if is_dismissed and dismissal_date:
                dismissal_status = f"Уволен {dismissal_date.strftime('%d.%m.%Y')}"
            elif is_dismissed:
                dismissal_status = "Уволен (дата неизвестна)"
            else:
                dismissal_status = "Состоит во фракции"
            
            # Create warning embed
            warning_embed = discord.Embed(
                title="⚠️ Аккуратно! Конфликт данных",
                description=(
                    "Вы пытаетесь одобрить заявку, информация о которой различается с тем, что уже есть в базе данных.\n\n"
                    "**Существующая запись:**"
                ),
                color=discord.Color.orange()
            )
            
            warning_embed.add_field(
                name="Дискорд",
                value=f"<@{old_discord_id}> (`{old_discord_id}`)",
                inline=False
            )
            warning_embed.add_field(name="Имя", value=old_first_name or "—", inline=True)
            warning_embed.add_field(name="Фамилия", value=old_last_name or "—", inline=True)
            warning_embed.add_field(name="Статик", value=old_static, inline=True)
            warning_embed.add_field(
                name="Статус службы",
                value=dismissal_status,
                inline=False
            )
            
            warning_embed.add_field(
                name="⚠️ Действие",
                value=(
                    f"Изучите дело <@{old_discord_id}>, перед тем как одобрять заявку <@{new_user_id}>.\n\n"
                    "**Подтвердить** — заменить старую запись на новую (старые данные будут потеряны)\n"
                    "**Отклонить** — отклонить заявку с автоматической причиной"
                ),
                inline=False
            )
            
            # Create confirmation view
            conflict_view = StaticConflictConfirmationView(
                self.application_data,
                old_discord_id,
                new_user_id,
                interaction.message
            )
            
            await interaction.response.send_message(
                embed=warning_embed,
                view=conflict_view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error("Error showing static conflict warning: %s", e)
            await interaction.response.send_message(
                "❌ Произошла ошибка при проверке данных.",
                ephemeral=True
            )
    
    async def _check_moderator_permissions(self, interaction):
        """Check if user has moderator permissions"""
        config = load_config()
        return is_moderator_or_admin(interaction.user, config)
    
    async def _process_approval(self, interaction):
        """Process application approval"""
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
              # Direct processing without authorization modal
            signed_by_name = interaction.user.display_name
            
            # Continue with approval processing
            await self._continue_approval_process(interaction, user, guild, config, signed_by_name)
                
        except Exception as e:
            logger.error("Error in approval process: %s", e)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Произошла ошибка при обработке заявки.",
                        ephemeral=True
                    )
            except Exception as followup_error:
                logger.error("Failed to send error message: %s", followup_error)
    
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
            role_type = "военнослужащего" if self.application_data["type"] == "military" else "госслужащего"
            await MessageService.send_rejection_dm(
                user=user,
                guild_id=interaction.guild.id,
                rejection_reason=rejection_reason,
                role_type=role_type
            )
    
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
            logger.error("Error in _request_rejection_reason: %s", e)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Произошла ошибка при запросе причины отказа.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    " Произошла ошибка при запросе причины отказа.",
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
                role_type = "военнослужащего" if self.application_data["type"] == "military" else "госслужащего"
                await MessageService.send_rejection_dm(
                    user=user,
                    guild_id=interaction.guild.id,
                    rejection_reason=rejection_reason,
                    role_type=role_type
                )
                
        except Exception as e:
            logger.error("Error in _finalize_rejection_with_reason: %s", e)
            await interaction.followup.send(
                "❌ Произошла ошибка при финализации отказа.",
                ephemeral=True
            )
    
    def _should_auto_process(self):
        """Determine if this application should be automatically processed"""
        if self.application_data["type"] == "military":
            rank = self.application_data.get("rank", "").lower()
            default_rank = rank_manager.get_default_recruit_rank_sync()
            return default_rank and rank == default_rank.lower()
        elif self.application_data["type"] == "supplier":
            return True  # Auto-process supplier applications
        else:  # civilian
            return True
    
    def _should_change_nickname(self):
        """Determine if nickname should be changed"""
        if self.application_data["type"] == "military":
            rank = self.application_data.get("rank", "").lower()
            default_rank = rank_manager.get_default_recruit_rank_sync()
            return default_rank and rank == default_rank.lower()
        return False  # Never change nickname for suppliers or civilians
    
    def _should_process_personnel(self):
        """Determine if personnel record should be processed"""
        # Process personnel records for all military recruits
        if self.application_data["type"] == "military":
            return True
        return False  # Never process personnel records for suppliers or civilians
    
    async def _assign_roles(self, user, guild, config, moderator):
        """Assign appropriate roles to user with proper cleanup"""
        try:
            from utils.role_utils import role_utils
            
            logger.info(f" ROLE ASSIGNMENT: Начинаем обработку ролей для {user.display_name} (тип: {self.application_data['type']})")
            
            # Шаг 1: Очистить роли подразделений и должностей (для чистоты)
            # Базовые роли (военные/гражданские/поставщики) не должны иметь ролей подразделений
            removed_dept = await role_utils.clear_all_department_roles(
                user, 
                reason="role_removal.role_assignment_cleanup"
            )
            removed_pos = await role_utils.clear_all_position_roles(
                user, 
                reason="role_removal.role_assignment_cleanup"
            )
            removed_ranks = await role_utils.clear_all_rank_roles(
                user,
                reason="role_removal.role_assignment_cleanup"
            )
            
            if removed_dept:
                logger.info(f" Очищены роли подразделений: {', '.join(removed_dept)}")
            if removed_pos:
                logger.info(f" Очищены роли должностей: {', '.join(removed_pos)}")
            if removed_ranks:
                logger.info(f" Очищены роли рангов: {', '.join(removed_ranks)}")
            
            # Шаг 2: Назначить соответствующие роли в зависимости от типа
            assigned_roles = []
            
            if self.application_data["type"] == "military":
                # Назначить военные роли
                assigned_roles = await role_utils.assign_military_roles(user, self.application_data, moderator)
                
                # Set nickname for military recruits only
                if self._should_change_nickname():
                    try:
                        await self._set_military_nickname(user)
                    except Exception as e:
                        logger.warning("Warning: Could not set military nickname: %s", e)
                        # Continue processing even if nickname change fails
                        
            elif self.application_data["type"] == "supplier":
                # Назначить роли поставщика
                assigned_roles = await role_utils.assign_supplier_roles(user, self.application_data, moderator)
                
            else:  # civilian
                # Назначить роли госслужащего
                assigned_roles = await role_utils.assign_civilian_roles(user, self.application_data, moderator)
            
            if assigned_roles:
                logger.info(f"Назначены роли: {', '.join(assigned_roles)}")
            else:
                logger.info(f" Не удалось назначить роли для типа {self.application_data['type']}")
                        
        except Exception as e:
            logger.warning("Error in role assignment: %s", e)
            raise  # Re-raise the exception to be caught by the caller
    
    async def _set_military_nickname(self, user):
        """Set nickname for military users using nickname_manager"""
        try:
            # Извлекаем имя и фамилию из заявки
            full_name = self.application_data['name']
            name_parts = full_name.split()
            
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])
            else:
                first_name = full_name
                last_name = ''
            
            # Получаем звание из заявки
            rank_name = self.application_data.get('rank', rank_manager.get_default_recruit_rank_sync())
            
            # Получаем статик из заявки
            static = self.application_data.get('static', '')
            
            logger.info("NICKNAME INTEGRATION: Приём на службу {user.display_name} -> %s %s (звание: %s)", first_name, last_name, rank_name)
            
            # Используем nickname_manager для автоматической обработки никнейма
            new_nickname = await nickname_manager.handle_hiring(
                member=user,
                rank_name=rank_name,
                first_name=first_name,
                last_name=last_name,
                static=static
            )
            
            if new_nickname:
                await user.edit(nick=new_nickname, reason=get_role_reason(user.guild.id, "nickname_change.personnel_acceptance", "Приём в организацию: изменён никнейм").format(moderator="система"))
                logger.info("NICKNAME MANAGER: Успешно установлен никнейм %s -> %s", user, new_nickname)
            else:
                logger.info("NICKNAME MANAGER: Не удалось сгенерировать никнейм для %s", user)
            
        except discord.Forbidden as e:
            logger.warning("Warning: No permission to change nickname for %s to \"%s\"", user, new_nickname)
            # Don't raise the error, just log it
        except Exception as e:
            logger.error("Error setting nickname for %s: %s", user, e)
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
    
    async def _continue_approval_process(self, interaction, user, guild, config, signed_by_name, original_message=None):
        """Continue with approval processing after authorization is successful
        
        Args:
            original_message: Optional message to update instead of interaction.message
        """
        try:
            # Determine which message to update
            target_message = original_message if original_message else interaction.message
            
            # ВАЖНО: Получаем актуальные данные из embed (на случай редактирования)
            if target_message and target_message.embeds:
                current_data = self._extract_application_data_from_embed(target_message.embeds[0])
                if current_data:
                    self.application_data = current_data
            
            # First show processing state
            processing_view = ProcessingApplicationView()
            
            # Update the target message (either original or via interaction)
            if original_message:
                # We have original message from conflict resolution
                embed = target_message.embeds[0]
                embed.color = discord.Color.orange()
                await target_message.edit(content="", embed=embed, view=processing_view)
            else:
                # Normal flow via interaction
                if interaction.response.is_done():
                    await interaction.edit_original_response(view=processing_view)
                else:
                    await interaction.response.edit_message(view=processing_view)
            
            # Small delay to show processing state
            await asyncio.sleep(0.5)
            
            # Then do all the processing
            try:
                # Assign roles and update nickname if needed
                await self._assign_roles(user, guild, config, interaction.user)
            except Exception as e:
                logger.error("Warning: Error in role assignment: %s", e)
                # Continue processing even if role assignment fails
                
            # Only do personnel processing for military recruits with default recruit rank
            if self._should_process_personnel():
                try:
                    await self._handle_auto_processing_with_auth(user, guild, config, signed_by_name, interaction.user.id)
                except Exception as e:
                    logger.error("Warning: Error in personnel processing: %s", e)
                    # Continue processing even if personnel processing fails
            
            # Send DM to user
            try:
                if self.application_data["type"] == "supplier":
                    # Special message for supplies access
                    embed = discord.Embed(
                        title=get_private_messages(guild.id,
                                                 "supplies_access.title", "📦 Доступ к поставкам одобрен!"),
                        description=get_private_messages(guild.id,
                                                       "supplies_access.description",
                                                       "Вам предоставлен доступ к системе поставок!"),
                        color=discord.Color.blue()
                    )
                    await user.send(embed=embed)
                else:
                    # Standard approval DM
                    role_type = "военнослужащего" if self.application_data["type"] == "military" else "госслужащего"
                    await MessageService.send_approval_dm(user, guild.id, role_type)
            except Exception as e:
                logger.error("Warning: Error sending DM: %s", e)
                # Continue even if DM fails
            
            # Finally, create final embed and update to approved state
            # Build approval embed manually since we might not have standard interaction
            if target_message and target_message.embeds:
                embed = target_message.embeds[0]
            else:
                embed = discord.Embed(
                    title="📝 Заявка на получение роли",
                    color=discord.Color.green()
                )
            
            embed.color = discord.Color.green()
            
            # Update or add status field
            status_field_index = None
            for i, field in enumerate(embed.fields):
                if "Статус" in field.name or "Обрабатывается" in field.value:
                    status_field_index = i
                    break
            
            if status_field_index is not None:
                embed.set_field_at(
                    status_field_index,
                    name="✅ Статус",
                    value=f"Одобрено сотрудником {interaction.user.mention}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ Статус",
                    value=f"Одобрено сотрудником {interaction.user.mention}",
                    inline=False
                )
            
            approved_view = ApprovedApplicationView()
            
            # Update target message
            if original_message:
                await target_message.edit(content="", embed=embed, view=approved_view)
            else:
                await interaction.edit_original_response(content="", embed=embed, view=approved_view)
                
        except Exception as e:
            logger.error("Error in approval process continuation: %s", e)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        " Произошла ошибка при обработке заявки.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        " Произошла ошибка при обработке заявки.",
                        ephemeral=True
                    )
            except Exception as followup_error:
                logger.error("Failed to send error message: %s", followup_error)
    
    async def _handle_auto_processing_with_auth(self, user, guild, config, signed_by_name, moderator_discord_id):
        """Handle automatic processing with pre-authorized moderator using enhanced PersonnelManager"""
        try:
            # Step 1: Personnel Processing with PersonnelManager
            # PersonnelManager теперь полностью отвечает за запись в БД
            personnel_success, personnel_message = await personnel_manager.process_role_application_approval(
                self.application_data,
                user.id,
                moderator_discord_id,
                signed_by_name
            )
            
            if personnel_success:
                logger.info("PersonnelManager: %s", personnel_message)
            else:
                logger.info("PersonnelManager: %s", personnel_message)
            
            # Step 2: Send audit notification
            audit_channel_id = config.get('audit_channel')
            if audit_channel_id:
                audit_channel = await get_channel_with_fallback(guild, audit_channel_id, "audit channel")
                if audit_channel:
                    # Get moderator user object
                    moderator_user = guild.get_member(moderator_discord_id)
                    if not moderator_user:
                        logger.warning("Warning: Could not find moderator user %s", moderator_discord_id)
                        return
                    
                    # Prepare personnel data for audit
                    personnel_data = {
                        'name': self.application_data.get('name', 'Неизвестно'),
                        'static': self.application_data.get('static', ''),
                        'rank': self.application_data.get('rank', rank_manager.get_default_recruit_rank_sync()),
                        'department': 'Военная Академия',
                        'position': 'Не назначено'
                    }
                    
                    # Send audit notification using centralized audit logger
                    await audit_logger.send_personnel_audit(
                        guild=guild,
                        action="Принят на службу",
                        target_user=user,
                        moderator=moderator_user,
                        personnel_data=personnel_data,
                        config=config
                    )
        except Exception as e:
            logger.error("Warning: Error in auto processing with auth: %s", e)
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
                await self._assign_roles(user, guild, config, None)
            except Exception as e:
                logger.error("Warning: Error in role assignment: %s", e)
                # Continue processing even if role assignment fails
                
            # Only do personnel processing for military recruits with default recruit rank
            if self._should_process_personnel():
                try:
                    await self._handle_auto_processing_with_auth(user, guild, config, signed_by_name, 0)  # Нет доступа к moderator_discord_id в этом контексте
                except Exception as e:
                    logger.error("Warning: Error in personnel processing: %s", e)
                    # Continue processing even if personnel processing fails
              # Send DM to user
            try:
                if self.application_data["type"] == "supplier":
                    # Special message for supplies access
                    embed = discord.Embed(
                        title=get_private_messages(guild.id,
                                                 "supplies_access.title", " Доступ к поставкам одобрен!"),
                        description=get_private_messages(guild.id,
                                                       "supplies_access.description",
                                                       "Вам предоставлен доступ к системе поставок!"),
                        color=discord.Color.blue()
                    )
                    await user.send(embed=embed)
                else:
                    # Standard approval DM
                    role_type = "военнослужащего" if self.application_data["type"] == "military" else "госслужащего"
                    await MessageService.send_approval_dm(user, guild.id, role_type)
            except Exception as e:
                logger.error("Warning: Error sending DM: %s", e)
                # Continue even if DM fails
            
            # Finally, create final embed and update to approved state
            embed = await self._create_approval_embed(original_message=original_message, moderator_info=signed_by_name)
            approved_view = ApprovedApplicationView()
            # Убираем кнопки после одобрения, чтобы при рестарте не возвращались старые компоненты
            await original_message.edit(content="", embed=embed, view=None)
                
        except Exception as e:
            logger.error("Error in approval process with message: %s", e)
            # Can't send error message to user since we don't have interaction here
            # Error is already logged

    async def _send_registry_error_message(self, interaction):
        """Send error message about personnel registry failure"""
        try:
            error_embed = discord.Embed(
                title="⚠️ Ошибка персонального реестра",
                description=(
                    "Заявка была успешно одобрена и пользователь получил роль, "
                    "но возникла ошибка при обновлении персонального реестра.\n\n"
                    "**Пожалуйста, обратитесь к Руководству Бригады** для решения данной проблемы."
                ),
                color=discord.Color.orange()
            )
            
            if not interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                
        except Exception as e:
            logger.warning("Failed to send registry error message: %s", e)


class DeleteConfirmationView(ui.View):
    """View for confirming deletion of pending applications"""
    
    def __init__(self, original_message):
        super().__init__(timeout=300)  # 5 minute timeout for confirmation
        self.original_message = original_message
    
    @discord.ui.button(label="Подтвердить удаление", style=discord.ButtonStyle.danger, custom_id="delete_confirm")
    async def confirm_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm and execute the deletion"""
        try:
            # Delete the original application message
            await self.original_message.delete()
            
            # Delete the ephemeral confirmation message
            await interaction.response.edit_message(
                content="🗑️ Заявка успешно удалена.",
                embed=None,
                view=None
            )
            
        except discord.NotFound:
            # Message was already deleted
            await interaction.response.edit_message(
                content="🗑️ Заявка была удалена.",
                embed=None,
                view=None
            )
        except Exception as e:
            await interaction.response.edit_message(
                content=f"❌ Произошла ошибка при удалении заявки: {str(e)}",
                embed=None,
                view=None
            )
    
    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.secondary, custom_id="delete_cancel")
    async def cancel_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the deletion"""
        await interaction.response.edit_message(
            content="❌ Удаление отменено.",
            embed=None,
            view=None
        )
    
    async def on_timeout(self):
        """Handle timeout of the confirmation view"""
        try:
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            # Try to edit the message to show timeout
            # Note: This might fail if the interaction is no longer valid
            embed = discord.Embed(
                title="⏰ Время истекло",
                description="Время подтверждения удаления истекло. Заявка не была удалена.",
                color=discord.Color.orange()
            )
            
            # We can't reliably edit the ephemeral message here since we don't have the interaction
            # The timeout will just disable the buttons
            
        except Exception as e:
            logger.error("Error in DeleteConfirmationView timeout: %s", e)


class StaticConflictConfirmationView(ui.View):
    """View for confirming static conflict resolution"""
    
    def __init__(self, application_data, old_discord_id, new_user_id, original_message):
        super().__init__(timeout=300)
        self.application_data = application_data
        self.old_discord_id = old_discord_id
        self.new_user_id = new_user_id
        self.original_message = original_message
        self.warning_deleted = False
    
    @discord.ui.button(label="Подтвердить", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_replacement(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm replacement of old record with new one"""
        try:
            # Defer the response
            await interaction.response.defer(ephemeral=True)

            # Delete the ephemeral warning immediately
            try:
                await interaction.delete_original_response()
                self.warning_deleted = True
            except Exception:
                pass
            
            # Step 1: Update original message to "Processing..."
            embed = self.original_message.embeds[0]
            embed.color = discord.Color.orange()
            
            # Check if status field already exists
            status_field_exists = any(field.name == "🔄 Статус" for field in embed.fields)
            if not status_field_exists:
                embed.add_field(
                    name="🔄 Статус",
                    value=f"Обрабатывается сотрудником {interaction.user.mention}",
                    inline=False
                )
            
            processing_view = ProcessingApplicationView()
            await self.original_message.edit(content="", embed=embed, view=processing_view)
            
            # Step 2: Replace old discord_id with new one in personnel table
            from utils.postgresql_pool import get_db_cursor
            from datetime import datetime, timezone
            
            with get_db_cursor() as cursor:
                # Update the personnel record: change discord_id and reset dismissal status
                cursor.execute("""
                    UPDATE personnel
                    SET discord_id = %s,
                        is_dismissal = false,
                        dismissal_date = NULL,
                        last_updated = %s
                    WHERE discord_id = %s;
                """, (self.new_user_id, datetime.now(timezone.utc), self.old_discord_id))
                
                logger.info(
                    "STATIC CONFLICT: Replaced discord_id %s with %s for static %s",
                    self.old_discord_id,
                    self.new_user_id,
                    self.application_data.get('static')
                )
            
            # Step 3: Update application_data with new user_id
            self.application_data['user_id'] = self.new_user_id
            self.application_data['user_mention'] = f"<@{self.new_user_id}>"
            
            # Step 4: Get user and continue with normal approval
            guild = interaction.guild
            user = guild.get_member(self.new_user_id)
            
            if not user:
                await interaction.followup.send(
                    "❌ Пользователь не найден на сервере.",
                    ephemeral=True
                )
                # Restore original message
                embed.color = discord.Color.red()
                embed.set_field_at(
                    len(embed.fields) - 1,
                    name="❌ Ошибка",
                    value="Пользователь не найден на сервере",
                    inline=False
                )
                original_view = RoleApplicationApprovalView(self.application_data)
                await self.original_message.edit(embed=embed, view=original_view)
                return
            
            # Step 5: Process the approval using the existing approval flow
            config = load_config()
            signed_by_name = interaction.user.display_name
            
            # Create approval view to use its methods
            approval_view = RoleApplicationApprovalView(self.application_data)
            
            # Call the continuation method with proper context
            await approval_view._continue_approval_process(
                interaction,
                user,
                guild,
                config,
                signed_by_name,
                self.original_message  # Pass original message for updates
            )
            
        except Exception as e:
            logger.error("Error confirming static conflict resolution: %s", e)
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                "❌ Произошла ошибка при подтверждении замены.",
                ephemeral=True
            )
    
    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.red, emoji="❌")
    async def reject_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reject the application with auto-filled reason"""
        try:
            # Show modal with pre-filled rejection reason
            rejection_modal = StaticConflictRejectionModal(
                self.application_data,
                self.original_message,
                interaction
            )
            await interaction.response.send_modal(rejection_modal)
            
        except Exception as e:
            logger.error("Error rejecting application from static conflict: %s", e)
            await interaction.response.send_message(
                "❌ Произошла ошибка при отклонении заявки.",
                ephemeral=True
            )


class StaticConflictRejectionModal(ui.Modal):
    """Modal for rejecting application with auto-filled reason"""
    
    def __init__(self, application_data, original_message, warning_interaction):
        super().__init__(title="Причина отклонения заявки")
        self.application_data = application_data
        self.original_message = original_message
        self.warning_interaction = warning_interaction
        
        self.reason_input = ui.TextInput(
            label="Причина отказа",
            style=discord.TextStyle.paragraph,
            placeholder="Укажите причину отклонения заявки",
            default="Попытка выдать себя за другого пользователя",
            min_length=5,
            max_length=500,
            required=True
        )
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process rejection with the provided reason"""
        try:
            # Defer the modal response
            await interaction.response.defer()

            # Delete the warning message immediately after confirmation
            try:
                await self.warning_interaction.delete_original_response()
            except Exception:
                pass
            
            rejection_reason = self.reason_input.value.strip()
            
            # Update the original application message
            guild = interaction.guild
            user = guild.get_member(self.application_data["user_id"])
            
            # Update embed with rejection
            embed = self.original_message.embeds[0]
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
            await self.original_message.edit(content="", embed=embed, view=rejected_view)
            
            # Send DM to user with rejection reason
            if user:
                role_type = "военнослужащего" if self.application_data["type"] == "military" else "госслужащего"
                await MessageService.send_rejection_dm(
                    user=user,
                    guild_id=interaction.guild.id,
                    rejection_reason=rejection_reason,
                    role_type=role_type
                )
            
            logger.info(
                "STATIC CONFLICT: Application rejected for user %s with reason: %s",
                self.application_data["user_id"],
                rejection_reason
            )
            
        except Exception as e:
            logger.error("Error processing rejection from static conflict modal: %s", e)
            await interaction.followup.send(
                "❌ Произошла ошибка при отклонении заявки.",
                ephemeral=True
            )