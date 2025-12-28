"""
Personnel Context Menu Commands with PersonnelManager integration
"""

import discord
from discord import app_commands
from discord.ext import commands
import functools
import traceback
import json

from utils.config_manager import load_config, is_moderator_or_admin, is_administrator, can_moderate_user, get_recruitment_config
from utils.database_manager import PersonnelManager
from utils.database_manager.position_service import position_service
from utils.nickname_manager import nickname_manager
from utils.message_manager import get_message, get_private_messages, get_message_with_params, get_ui_label, get_role_reason, get_role_assignment_message, get_moderator_display_name
from utils.message_service import MessageService
from utils.role_utils import role_utils
from discord import ui
import re

from utils.postgresql_pool import get_db_cursor
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


async def get_user_status(user_discord_id: int) -> dict:
    """
    Get comprehensive user status information.
    
    Returns:
        dict with keys:
        - is_active: bool - currently on active service
        - is_dismissed: bool - has been dismissed (but may have history)
        - blacklist_info: dict|None - active blacklist info if exists
        - rank: str|None - current rank if active
        - department: str|None - current department if active
        - position: str|None - current position if active
        - full_name: str|None - full name from personnel table
        - static: str|None - static number
        - join_date: datetime|None - date of joining service
    """
    try:
        from utils.database_manager import personnel_manager
        from utils.user_cache import get_cached_user_info
        
        status = {
            'is_active': False,
            'is_dismissed': False,
            'blacklist_info': None,
            'rank': None,
            'department': None,
            'position': None,
            'full_name': None,
            'static': None,
            'join_date': None
        }
        
        # First, try to get data from cache
        cached_data = await get_cached_user_info(user_discord_id)
        
        if cached_data:
            # Use cached data for basic information
            status['full_name'] = cached_data.get('full_name')
            status['static'] = cached_data.get('static')
            status['rank'] = cached_data.get('rank')
            status['department'] = cached_data.get('department')
            status['position'] = cached_data.get('position')
            
            # If we have rank data, user is likely active
            if status['rank'] and status['rank'] != 'Не указано':
                status['is_active'] = True
                status['is_dismissed'] = False
            else:
                # Need to check dismissal status from database
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        SELECT is_dismissal, join_date
                        FROM personnel 
                        WHERE discord_id = %s
                        ORDER BY id DESC
                        LIMIT 1;
                    """, (user_discord_id,))
                    
                    personnel_result = cursor.fetchone()
                    if personnel_result:
                        status['is_dismissed'] = personnel_result['is_dismissal']
                        status['join_date'] = personnel_result['join_date']
                        if not status['is_dismissed']:
                            # User has personnel record but no active service - might be inactive
                            status['is_active'] = False
            
            # ALWAYS get join_date from database (cache doesn't contain it)
            if not status['join_date']:
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        SELECT join_date
                        FROM personnel 
                        WHERE discord_id = %s
                        ORDER BY id DESC
                        LIMIT 1;
                    """, (user_discord_id,))
                    
                    result = cursor.fetchone()
                    if result:
                        status['join_date'] = result['join_date']
        else:
            # No cached data, check database directly
            with get_db_cursor() as cursor:
                # Check if user has any personnel record
                cursor.execute("""
                    SELECT id, first_name, last_name, static, is_dismissal, join_date
                    FROM personnel 
                    WHERE discord_id = %s
                    ORDER BY id DESC
                    LIMIT 1;
                """, (user_discord_id,))
                
                personnel_result = cursor.fetchone()
                if personnel_result:
                    status['is_dismissed'] = personnel_result['is_dismissal']
                    status['full_name'] = f"{personnel_result['first_name']} {personnel_result['last_name']}".strip() if personnel_result['first_name'] and personnel_result['last_name'] else None
                    status['static'] = personnel_result['static']
                    status['join_date'] = personnel_result['join_date']
                    
                    # If not dismissed, get active service info
                    if not personnel_result['is_dismissal']:
                        cursor.execute("""
                            SELECT r.name as rank_name, s.name as dept_name, pos.name as pos_name
                            FROM employees e
                            JOIN ranks r ON e.rank_id = r.id
                            JOIN subdivisions s ON e.subdivision_id = s.id
                            LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                            LEFT JOIN positions pos ON ps.position_id = pos.id
                            WHERE e.personnel_id = %s;
                        """, (personnel_result['id'],))
                        
                        service_result = cursor.fetchone()
                        if service_result:
                            status['is_active'] = True
                            status['rank'] = service_result['rank_name']
                            status['department'] = service_result['dept_name']
                            status['position'] = service_result['pos_name']
        
        # Always check blacklist (this might not be cached, so we check it separately)
        lookup_key = status['static'] or user_discord_id
        status['blacklist_info'] = await personnel_manager.check_active_blacklist(lookup_key)
        
        return status
        
    except Exception as e:
        logger.error("Error getting user status for %s: %s", user_discord_id, e)
        return {
            'is_active': False,
            'is_dismissed': False,
            'blacklist_info': None,
            'rank': None,
            'department': None,
            'position': None,
            'full_name': None,
            'static': None,
            'join_date': None
        }


async def get_user_rank_from_db(user_discord_id: int) -> str:
    """Get user's current rank from database instead of Discord roles"""
    try:
        from utils.postgresql_pool import get_db_cursor
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT r.name 
                FROM employees e
                JOIN personnel p ON e.personnel_id = p.id
                JOIN ranks r ON e.rank_id = r.id
                WHERE p.discord_id = %s AND p.is_dismissal = false;
            """, (user_discord_id,))
            
            result = cursor.fetchone()
            return result['name'] if result else None
            
    except Exception as e:
        logger.error("Error getting rank from database: %s", e)
        return None


def handle_context_errors(func):
    """Decorator to handle errors in context menu commands"""
    @functools.wraps(func)
    async def wrapper(interaction: discord.Interaction, user: discord.Member):
        try:
            logger.info(f"Context menu '{func.__name__}' called by {interaction.user.display_name} for {user.display_name}")
            return await func(interaction, user)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: %s", e)
            traceback.print_exc()
            # Don't try to respond if interaction is already done or invalid
            # Just log the error - the user will see the modal or message from the main function
            pass
    return wrapper


class RecruitmentModal(ui.Modal, title="Принятие на службу"):
    """Modal for recruiting new personnel using PersonnelManager"""
    
    def __init__(self, target_user: discord.Member, guild_id: int):
        super().__init__(title=get_message(guild_id, 'ui.modals.personnel_recruitment'))
        self.target_user = target_user
        self.guild_id = guild_id
        
        self.first_name_input = ui.TextInput(
            label=get_ui_label(guild_id, 'first_name'),
            placeholder=get_message(guild_id, 'ui.placeholders.first_name'),
            min_length=2,
            max_length=25,
            required=True
        )
        self.add_item(self.first_name_input)
        
        self.last_name_input = ui.TextInput(
            label=get_ui_label(guild_id, 'last_name'),
            placeholder=get_message(guild_id, 'ui.placeholders.last_name'),
            min_length=2,
            max_length=25,
            required=True
        )
        self.add_item(self.last_name_input)
        
        self.static_input = ui.TextInput(
            label=get_message(guild_id, 'ui.labels.static'),
            placeholder=get_message(guild_id, 'ui.placeholders.static'),
            min_length=1,
            max_length=7,
            required=True
        )
        self.add_item(self.static_input)
        
        # Если включен выбор ранга - добавляем Select через ui.Label
        self.recruitment_cfg = get_recruitment_config()
        self.allow_rank_selection = self.recruitment_cfg.get('allow_user_rank_selection', False)
        self.allow_subdivision_selection = self.recruitment_cfg.get('allow_user_subdivision_selection', False)
        
        if self.allow_rank_selection:
            from forms.role_assignment.modals import RankDropdown
            self.rank_dropdown = ui.Label(
                text='🎖️ Выберите желаемое звание:',
                component=RankDropdown(self.recruitment_cfg)
            )
            self.add_item(self.rank_dropdown)
        
        # Если включен выбор подразделения - добавляем Select через ui.Label
        if self.allow_subdivision_selection:
            from forms.role_assignment.modals import SubdivisionDropdown
            self.subdivision_dropdown = ui.Label(
                text='🏢 Выберите подразделение:',
                component=SubdivisionDropdown(self.recruitment_cfg)
            )
            self.add_item(self.subdivision_dropdown)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process recruitment submission using PersonnelManager"""
        try:
            # Check permissions first
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этой команды.",
                    ephemeral=True
                )
                return
            
            # Validate first name and last name (must be single words)
            first_name = self.first_name_input.value.strip().capitalize()
            last_name = self.last_name_input.value.strip().capitalize()
            
            if ' ' in first_name or '\t' in first_name:
                await interaction.response.send_message(
                    f" Имя не должно содержать пробелы",
                    ephemeral=True
                )
                return
            
            if ' ' in last_name or '\t' in last_name:
                await interaction.response.send_message(
                    f" Фамилия не должна содержать пробелы",
                    ephemeral=True
                )
                return
            
            # Combine first and last name
            full_name = f"{first_name} {last_name}"
            
            # Validate and format static
            static = self.static_input.value.strip()
            formatted_static = self._format_static(static)
            if not formatted_static:
                from utils.static_validator import StaticValidator
                await interaction.response.send_message(
                    StaticValidator.get_validation_error_message(),
                    ephemeral=True
                )
                return
            
            # Check blacklist by static AFTER validation
            from utils.database_manager import personnel_manager
            blacklist_info = await personnel_manager.check_active_blacklist(formatted_static)
            
            if blacklist_info:
                # User is blacklisted, deny recruitment
                start_date_str = blacklist_info['start_date'].strftime('%d.%m.%Y')
                end_date_str = blacklist_info['end_date'].strftime('%d.%m.%Y') if blacklist_info['end_date'] else 'Бессрочно'
                
                await interaction.response.send_message(
                    f"❌ **Этому пользователю запрещен приём на службу**\n\n"
                    f"📋 **{blacklist_info['full_name']} | {blacklist_info['static']} находится в Чёрном списке ВС РФ**\n"
                    f"> **Причина:** {blacklist_info['reason']}\n"
                    f"> **Период:** {start_date_str} - {end_date_str}\n\n"
                    f"*Если считаете, что это ошибка, обратитесь к руководству фракции*",
                    ephemeral=True
                )
                return
            
            # Check for static duplication (conflict with existing records)
            try:
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        SELECT discord_id, first_name, last_name, static, is_dismissal, dismissal_date
                        FROM personnel
                        WHERE static = %s AND discord_id != %s
                        LIMIT 1;
                    """, (formatted_static, self.target_user.id))
                    
                    existing_record = cursor.fetchone()
                    
                    if existing_record:
                        # Static already exists for another user - show warning
                        await self._show_static_conflict_warning(
                            interaction,
                            existing_record,
                            full_name,
                            formatted_static
                        )
                        return
            except Exception as db_error:
                logger.error("Error checking static duplication: %s", db_error)
                # Continue with recruitment if DB check fails
            
            # All validation passed, defer for processing
            await interaction.response.defer(ephemeral=True)
            
            # Получаем ранг из Select если включен выбор ранга
            rank = "Рядовой"  # Дефолтный ранг
            if self.allow_rank_selection and hasattr(self, 'rank_dropdown'):
                if self.rank_dropdown.component.values:
                    rank = self.rank_dropdown.component.values[0]
            
            # Получаем подразделение из Select если включен выбор подразделения
            subdivision = None
            if self.allow_subdivision_selection and hasattr(self, 'subdivision_dropdown'):
                if self.subdivision_dropdown.component.values:
                    subdivision = self.subdivision_dropdown.component.values[0]
            
            # Process recruitment using PersonnelManager
            success = await self._process_recruitment_with_personnel_manager(
                interaction,
                full_name,
                formatted_static,
                rank,
                subdivision
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Успешно",
                    description=f"Пользователь {self.target_user.mention} принят на службу!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📋 Детали:",
                    value=(
                        f"**Имя:** {first_name}\n"
                        f"**Фамилия:** {last_name}\n"
                        f"**Статик:** {formatted_static}\n"
                        f"**Звание:** {rank}" +
                        (f"\n**Подразделение:** {subdivision}" if subdivision else "")
                    ),
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    " Произошла ошибка при обработке принятия на службу.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error("RECRUITMENT ERROR: %s", e)
            import traceback
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Произошла ошибка при обработке запроса.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        " Произошла ошибка при обработке запроса.",
                        ephemeral=True
                    )
            except:
                logger.error("Failed to send error response: %s", e)
    
    def _format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        from utils.static_validator import StaticValidator
        is_valid, formatted = StaticValidator.validate_and_format(static_input)
        return formatted if is_valid else ""
    
    async def _show_static_conflict_warning(self, interaction, existing_record, new_name, new_static):
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
                    "Вы пытаетесь принять пользователя со статиком, который уже есть в базе данных.\n\n"
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
                    f"Изучите дело <@{old_discord_id}>, перед тем как принимать <@{self.target_user.id}> ({new_name}).\n\n"
                    "**Подтвердить** — заменить старую запись на новую (старые данные будут потеряны)\n"
                    "**Отклонить** — отменить приём с автоматической причиной"
                ),
                inline=False
            )
            
            # Create confirmation view
            conflict_view = RecruitmentStaticConflictView(
                self.target_user,
                old_discord_id,
                new_name,
                new_static,
                interaction.user
            )
            
            await interaction.response.send_message(
                embed=warning_embed,
                view=conflict_view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error("Error showing static conflict warning in recruitment: %s", e)
            await interaction.response.send_message(
                "❌ Произошла ошибка при проверке данных.",
                ephemeral=True
            )
    
    async def _process_recruitment_with_personnel_manager(self, interaction: discord.Interaction, full_name: str, static: str, rank: str, subdivision: str = None) -> bool:
        """Process recruitment using PersonnelManager"""
        try:
            logger.info(f"RECRUITMENT: Starting recruitment via PersonnelManager for {self.target_user.id}")
            logger.info("RECRUITMENT: Data - Name: '%s', Static: '%s', Rank: '%s'", full_name, static, rank)
            # Prepare application data for PersonnelManager
            application_data = {
                'user_id': self.target_user.id,
                'username': self.target_user.display_name,
                'name': full_name,
                'static': static,
                'type': 'military',
                'rank': rank,
                'subdivision': subdivision or None,
                'position': None
            }
            
            # Use PersonnelManager for recruitment
            pm = PersonnelManager()
            
            success, message = await pm.process_role_application_approval(
                application_data,
                self.target_user.id,
                interaction.user.id,
                interaction.user.display_name
            )
            
            if success:
                logger.info("RECRUITMENT: PersonnelManager processed successfully: %s", message)
                
                # Send audit notification using centralized logger
                try:
                    from utils.audit_logger import audit_logger, AuditAction
                    config = load_config()
                    
                    # Отправляем в аудит выбранное подразделение или дефолт из конфига
                    dept_name = subdivision
                    if not dept_name:
                        try:
                            cfg = load_config().get('recruitment', {}) or {}
                            default_key = cfg.get('default_subdivision_key')
                            if default_key:
                                with get_db_cursor() as cursor:
                                    cursor.execute("SELECT name FROM subdivisions WHERE abbreviation = %s", (default_key,))
                                    r = cursor.fetchone()
                                    if r:
                                        dept_name = r['name']
                        except Exception as ce:
                            logger.error("Recruitment audit department resolve failed: %s", ce)
                    personnel_data = {
                        'name': full_name,
                        'static': static,
                        'rank': rank,
                        'department': dept_name or 'Не назначено'
                    }
                    await audit_logger.send_personnel_audit(
                        guild=interaction.guild,
                        action=await AuditAction.HIRING(),
                        target_user=self.target_user,
                        moderator=interaction.user,
                        personnel_data=personnel_data,
                        config=config
                    )
                    logger.info("RECRUITMENT: Audit notification sent")
                except Exception as audit_error:
                    logger.error("RECRUITMENT: Failed to send audit notification: %s", audit_error)
                
                # Send DM to recruited user
                try:
                    dm_embed = discord.Embed(
                        title="✅ Вы приняты на службу!",
                        description=(
                            "Поздравляем! Вы успешно приняты на службу в Вооруженные Силы РФ.\n\n"
                            "📋 **Важная информация:**\n"
                            "> • Следите за каналом общения и оповещениями\n"
                            "> • Выполняйте приказы командования\n"
                            "> • Участвуйте в учебных мероприятиях для повышения\n\n"
                            "🎖️ Удачи в службе!"
                        ),
                        color=discord.Color.green()
                    )
                    dm_embed.add_field(name="ФИО", value=full_name, inline=True)
                    dm_embed.add_field(name="Статик", value=static, inline=True)
                    dm_embed.add_field(name="Звание", value="Рядовой", inline=True)
                    dm_embed.add_field(name="Подразделение", value=subdivision or "Не назначено", inline=False)
                    
                    await self.target_user.send(embed=dm_embed)
                    logger.info(f"RECRUITMENT: DM sent to {self.target_user.display_name}")
                except discord.Forbidden:
                    logger.info(f"RECRUITMENT: Could not send DM to {self.target_user.display_name} (DMs disabled)")
                except Exception as dm_error:
                    logger.error("RECRUITMENT: Failed to send DM: %s", dm_error)
                
                # Step: Assign Discord roles and set nickname (like button approval does)
                try:
                    config = load_config()
                    await self._assign_military_roles(interaction.guild, config, interaction.user, application_data)
                    logger.info("RECRUITMENT: Role assignment process completed")
                except Exception as role_error:
                    logger.error("RECRUITMENT: Failed to assign roles: %s", role_error)
                    # Continue even if role assignment fails
                    
            else:
                logger.error("RECRUITMENT: PersonnelManager failed: %s", message)
            
            return success
            
        except Exception as e:
            logger.error("RECRUITMENT: Error processing recruitment: %s", e)
            import traceback
            traceback.print_exc()
            return False
    
    async def _assign_military_roles(self, guild, config, moderator, application_data):
        """Assign military roles and set nickname using RoleUtils"""
        try:
            # Если выбранный ранг не "Рядовой", напрямую используем assign_military_roles
            selected_rank = application_data.get('rank', 'Рядовой')
            
            if selected_rank == 'Рядовой':
                # Для рядового используем стандартную функцию
                recruit_assigned = await role_utils.assign_default_recruit_rank(self.target_user, moderator)
                if not recruit_assigned:
                    logger.error(f"RECRUITMENT: Failed to assign recruit rank to {self.target_user}")
                    return
            
            # Assign military roles using RoleUtils (работает для любого ранга)
            military_assigned = await role_utils.assign_military_roles(self.target_user, application_data, moderator)
            if not military_assigned:
                logger.error(f"RECRUITMENT: Failed to assign military roles to {self.target_user}")
            
            # Set military nickname
            await self._set_military_nickname()
            
        except Exception as e:
            logger.error("RECRUITMENT: Error in _assign_military_roles: %s", e)
            raise
    
    async def _set_military_nickname(self):
        """Set nickname for military recruit using nickname_manager"""
        try:
            first_name = self.first_name_input.value.strip()
            last_name = self.last_name_input.value.strip()
            static = self.static_input.value.strip()
            full_name = f"{first_name} {last_name}"
            
            # Use nickname_manager for consistent formatting
            new_nickname = await nickname_manager.handle_hiring(
                member=self.target_user,
                rank_name="Рядовой",  # Default rank for new recruits
                first_name=first_name,
                last_name=last_name,
                static=static
            )
            
            if new_nickname:
                logger.info(f"RECRUITMENT: Set nickname using nickname_manager: {self.target_user.display_name} -> %s", new_nickname)
            else:
                # Fallback to old logic if nickname_manager fails
                full_nickname = f"ВА | {full_name}"
                if len(full_nickname) <= 32:
                    new_nickname = full_nickname
                else:
                    first_initial = first_name[0] if first_name else "И"
                    new_nickname = f"ВА | {first_initial}. {last_name}"
                
                await self.target_user.edit(nick=new_nickname, reason=get_role_reason(self.target_user.guild.id, "nickname_change.personnel_acceptance", "Приём в организацию: изменён никнейм").format(moderator="система"))
                logger.info("RECRUITMENT: Fallback nickname set: %s", new_nickname)
            
        except discord.Forbidden:
            logger.info(f"RECRUITMENT: No permission to change nickname for {self.target_user.display_name} to \"{new_nickname}\"")
        except Exception as e:
            logger.error("RECRUITMENT: Error setting nickname: %s", e)


@app_commands.context_menu(name='Принять во фракцию')
@handle_context_errors
async def recruit_user(interaction: discord.Interaction, user: discord.Member):
    """Context menu command to recruit user using PersonnelManager"""
    # Check permissions
    config = load_config()
    if not is_moderator_or_admin(interaction.user, config):
        await interaction.response.send_message(
            "❌ У вас нет прав для выполнения этой команды. Требуются права модератора или администратора.",
            ephemeral=True
        )
        return
    
    # Check if moderator can moderate this user (hierarchy check)
    if not can_moderate_user(interaction.user, user, config):
        await interaction.response.send_message(
            "❌ Вы не можете выполнять действия над этим пользователем. Недостаточно прав в иерархии.",
            ephemeral=True
        )
        return
    
    # Check if user is already on service (has a record in employees table)
    from utils.postgresql_pool import get_db_cursor
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT CONCAT(p.first_name, ' ', p.last_name) as full_name, p.static, e.subdivision_id
            FROM personnel p
            JOIN employees e ON p.id = e.personnel_id
            WHERE p.discord_id = %s AND p.is_dismissal = false
        """, (user.id,))
        existing_service = cursor.fetchone()
        
        if existing_service:
            # User is already in service - send warning
            await interaction.response.send_message(
                f"⚠️ **Пользователь уже на службе!**\n\n"
                f"**ФИО:** {existing_service['full_name']}\n"
                f"**Статик:** {existing_service['static']}\n"
                f"Для изменения данных используйте соответствующие команды редактирования.",
                ephemeral=True
            )
            return
        
        # Check if user has a personnel record (even if dismissed)
        cursor.execute("""
            SELECT id, is_dismissal FROM personnel WHERE discord_id = %s
        """, (user.id,))
        existing_personnel = cursor.fetchone()
        
        if existing_personnel:
            if existing_personnel['is_dismissal']:
                # User was dismissed, can be recruited again
                pass  # Continue with recruitment
            else:
                # User has personnel record but no active service - this shouldn't happen
                await interaction.response.send_message(
                    f"⚠️ **Найдена некорректная запись персонала для пользователя**\n\n"
                    f"Обратитесь к администратору для исправления данных.",
                    ephemeral=True
                )
                return
    
    # Проверка ЧС теперь в модальном окне после ввода static
    modal = RecruitmentModal(user, interaction.guild.id)
    await interaction.response.send_modal(modal)
    logger.info(f"Recruitment modal sent for {user.display_name}")


class DismissalModal(ui.Modal, title="Увольнение"):
    """Modal for dismissing personnel using PersonnelManager"""
    
    def __init__(self, target_user: discord.Member, guild_id: int):
        super().__init__()
        self.target_user = target_user
        self.guild_id = guild_id
        
        self.reason_input = ui.TextInput(
            label=get_ui_label(self.guild_id, 'dismissal_reason'),
            placeholder="ПСЖ, Нарушение устава, и т.д.",
            min_length=2,
            max_length=100,
            required=True
        )
        self.add_item(self.reason_input)
        
        self.blacklist_check_input = ui.TextInput(
            label="Автоматическая проверка ЧС",
            placeholder="+ или -, если хотите проверять на неустойку",
            default="+",
            min_length=1,
            max_length=1,
            required=True
        )
        self.add_item(self.blacklist_check_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process dismissal submission using PersonnelManager"""
        try:
            # Check permissions first
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    " У вас нет прав для выполнения этой команды.",
                    ephemeral=True
                )
                return

            # Determine whether to run blacklist/penalty check
            blacklist_flag = (self.blacklist_check_input.value or "").strip().lower()
            perform_blacklist_check = blacklist_flag != "-"
            
            # All validation passed, defer for processing
            await interaction.response.defer(ephemeral=True)
            
            # Process dismissal using PersonnelManager
            success = await self._process_dismissal_with_personnel_manager(
                interaction,
                self.reason_input.value.strip(),
                perform_blacklist_check
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Успешно",
                    description=f"Пользователь {self.target_user.mention} уволен со службы!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📋 Детали:",
                    value=f"**Причина:** {self.reason_input.value.strip()}",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ Произошла ошибка при обработке увольнения.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error("DISMISSAL ERROR: %s", e)
            import traceback
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        " Произошла ошибка при обработке запроса.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        " Произошла ошибка при обработке запроса.",
                        ephemeral=True
                    )
            except:
                logger.error("Failed to send error response: %s", e)
    
    async def _process_dismissal_with_personnel_manager(self, interaction: discord.Interaction, reason: str, perform_blacklist_check: bool) -> bool:
        """Process dismissal directly (same as dismissal reports)
        
        Args:
            perform_blacklist_check: skip auto-blacklist if False
        """
        try:
            logger.info(f"DISMISSAL: Starting dismissal for {self.target_user.id}")
            logger.info("DISMISSAL: Reason: '%s'", reason)
            
            # Get personnel data first
            pm = PersonnelManager()
            personnel_data_summary = await pm.get_personnel_summary(self.target_user.id)
            
            if not personnel_data_summary:
                logger.info("DISMISSAL: User not found in personnel database")
                await interaction.followup.send(
                    " Пользователь не найден в базе данных персонала.",
                    ephemeral=True
                )
                return False
            
            # Process dismissal directly (same as in dismissal reports)
            from utils.postgresql_pool import get_db_cursor
            from datetime import datetime, timezone
            import json
            
            try:
                with get_db_cursor() as cursor:
                    # Get personnel and employee data
                    cursor.execute("""
                        SELECT 
                            p.id, p.first_name, p.last_name, p.static,
                            e.id as employee_id,
                            r.name as current_rank,
                            pos.name as current_position,
                            sub.name as current_subdivision
                        FROM personnel p
                        LEFT JOIN employees e ON p.id = e.personnel_id
                        LEFT JOIN ranks r ON e.rank_id = r.id
                        LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                        LEFT JOIN positions pos ON ps.position_id = pos.id
                        LEFT JOIN subdivisions sub ON e.subdivision_id = sub.id
                        WHERE p.discord_id = %s AND p.is_dismissal = false
                    """, (self.target_user.id,))
                    
                    personnel_record = cursor.fetchone()
                    if not personnel_record:
                        logger.info("DISMISSAL: User not found or already dismissed")
                        await interaction.followup.send(
                            "❌ Пользователь не найден в базе данных или уже уволен.",
                            ephemeral=True
                        )
                        return False
                    
                    personnel_id = personnel_record['id']
                    employee_id = personnel_record['employee_id']
                    current_time = datetime.now(timezone.utc)
                    
                    # Step 1: Remove from employees table if exists
                    if employee_id:
                        cursor.execute("DELETE FROM employees WHERE id = %s", (employee_id,))
                        logger.info("DISMISSAL: Removed employee record %s", employee_id)
                    
                    # Detect presence of dismissal_reason column (compat with older schema)
                    cursor.execute("""
                        SELECT COUNT(*) as cnt
                        FROM information_schema.columns
                        WHERE table_name = 'personnel' AND column_name = 'dismissal_reason'
                    """)
                    has_dismissal_reason_col = cursor.fetchone().get('cnt', 0) > 0

                    # Step 2: Mark personnel as dismissed
                    cursor.execute("""
                        UPDATE personnel 
                        SET is_dismissal = true, 
                            dismissal_date = %s,
                            last_updated = %s
                        WHERE id = %s
                    """, (current_time.date(), current_time, personnel_id))
                    if has_dismissal_reason_col:
                        cursor.execute("""
                            UPDATE personnel
                            SET dismissal_reason = %s
                            WHERE id = %s
                        """, (reason, personnel_id))
                    logger.info("DISMISSAL: Marked personnel %s as dismissed", personnel_id)
                    
                    # Step 3: Get moderator's personnel ID
                    cursor.execute("""
                        SELECT id FROM personnel WHERE discord_id = %s
                    """, (interaction.user.id,))
                    
                    moderator_record = cursor.fetchone()
                    moderator_personnel_id = moderator_record['id'] if moderator_record else None
                    
                    # Step 4: Add history entry
                    changes_data = {
                        "rank": {
                            "new": None,
                            "previous": personnel_record.get('current_rank')
                        },
                        "position": {
                            "new": None,
                            "previous": personnel_record.get('current_position')
                        },
                        "subdivision": {
                            "new": None,
                            "previous": personnel_record.get('current_subdivision')
                        },
                        "dismissal_info": {
                            "reason": reason,
                            "static": personnel_record.get('static', ''),
                            "moderator_info": interaction.user.display_name,
                            "dismissed_at": current_time.isoformat()
                        }
                    }
                    
                    cursor.execute("""
                        INSERT INTO history (personnel_id, action_id, performed_by, details, changes, action_date)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        personnel_id,
                        3,  # Action ID for "Уволен со службы"
                        moderator_personnel_id,  # Can be NULL if moderator not in personnel
                        reason,
                        json.dumps(changes_data, ensure_ascii=False),
                        current_time
                    ))
                    logger.info("DISMISSAL: Added history entry for dismissal")
                
                success = True
                message = f"Пользователь успешно уволен из базы данных"
                logger.info("DISMISSAL: %s", message)
                
            except Exception as db_error:
                logger.error("DISMISSAL: Database error: %s", db_error)
                import traceback
                traceback.print_exc()
                success = False
                message = f"Ошибка базы данных: {str(db_error)}"
            
            if success:
                logger.info("DISMISSAL: PersonnelManager processed successfully: %s", message)
                
                # Send audit notification using centralized logger
                audit_message_url = None
                
                # Инвалидируем кэш пользователя после изменения статуса
                try:
                    from utils.user_cache import invalidate_user_cache
                    invalidate_user_cache(self.target_user.id)
                    logger.info("DISMISSAL: Инвалидация кэша для пользователя %s", self.target_user.id)
                except Exception as cache_error:
                    logger.error("DISMISSAL: Ошибка при попытке инвалидации кэша: %s", cache_error)
                try:
                    from utils.audit_logger import audit_logger, AuditAction
                    from utils.postgresql_pool import get_db_cursor
                    config = load_config()
                    
                    audit_personnel_data = {
                        'name': personnel_data_summary.get('full_name', self.target_user.display_name),
                        'static': personnel_data_summary.get('static', ''),
                        'rank': personnel_data_summary.get('rank', 'Неизвестно'),
                        'department': personnel_data_summary.get('department', 'Неизвестно'),
                        'position': personnel_data_summary.get('position', ''),
                        'reason': reason
                    }
                    
                    # Send audit and get message URL for evidence
                    audit_message_url = await audit_logger.send_personnel_audit(
                        guild=interaction.guild,
                        action=await AuditAction.DISMISSAL(),
                        target_user=self.target_user,
                        moderator=interaction.user,
                        personnel_data=audit_personnel_data,
                        config=config
                    )
                    logger.info("DISMISSAL: Audit notification sent")
                    
                    # Get personnel_id for auto-blacklist check (if allowed)
                    if perform_blacklist_check:
                        try:
                            with get_db_cursor() as cursor:
                                cursor.execute(
                                    "SELECT id FROM personnel WHERE discord_id = %s;",
                                    (self.target_user.id,)
                                )
                                result = cursor.fetchone()
                                
                                if result:
                                    personnel_id = result['id']
                                    
                                    # Check and send auto-blacklist if needed
                                    was_blacklisted = await audit_logger.check_and_send_auto_blacklist(
                                        guild=interaction.guild,
                                        target_user=self.target_user,
                                        moderator=interaction.user,
                                        personnel_id=personnel_id,
                                        personnel_data=audit_personnel_data,
                                        audit_message_url=audit_message_url,
                                        config=config
                                    )
                                    
                                    if was_blacklisted:
                                        logger.info(f"DISMISSAL: Auto-blacklist triggered for {audit_personnel_data.get('name')}")
                                else:
                                    logger.info(f"DISMISSAL: Personnel not found in DB for auto-blacklist check: {self.target_user.id}")
                                    
                        except Exception as blacklist_error:
                            logger.error("DISMISSAL: Error in auto-blacklist check: %s", blacklist_error)
                            # Don't fail the whole dismissal if blacklist check fails
                        
                except Exception as audit_error:
                    logger.error("DISMISSAL: Failed to send audit notification: %s", audit_error)
                
                # Send DM to dismissed user
                try:
                    dm_embed = discord.Embed(
                        title="📋 Вы уволены со службы",
                        description=(
                            "Вы были уволены из Вооруженных Сил РФ.\n\n"
                            "Благодарим за службу!"
                        ),
                        color=discord.Color.orange()
                    )
                    dm_embed.add_field(name="Причина увольнения", value=reason, inline=False)
                    dm_embed.add_field(name="Уволил", value=interaction.user.display_name, inline=False)
                    
                    await self.target_user.send(embed=dm_embed)
                    logger.info(f"DISMISSAL: DM sent to {self.target_user.display_name}")
                except discord.Forbidden:
                    logger.info(f"DISMISSAL: Could not send DM to {self.target_user.display_name} (DMs disabled)")
                except Exception as dm_error:
                    logger.error("DISMISSAL: Failed to send DM: %s", dm_error)
                
                # Step: Remove Discord roles and reset nickname (like button dismissal does)
                try:
                    config = load_config()
                    await self._remove_military_roles_and_reset_nickname(interaction.guild, config, interaction)
                    logger.info("DISMISSAL: Role removal process completed")
                except Exception as role_error:
                    logger.error("DISMISSAL: Failed to remove roles: %s", role_error)
                    # Continue even if role removal fails
                    
            else:
                logger.error("DISMISSAL: PersonnelManager failed: %s", message)
            
            return success
            
        except Exception as e:
            logger.error("DISMISSAL: Error processing dismissal: %s", e)
            import traceback
            traceback.print_exc()
            return False
    
    async def _remove_military_roles_and_reset_nickname(self, guild, config, interaction):
        """Remove all military roles and reset nickname using RoleUtils"""
        try:
            # Use RoleUtils to clear all roles (military, department, position, rank)
            roles_cleared = await role_utils.clear_all_roles(
                self.target_user,
                reason="Увольнение: сняты все роли",
                moderator=interaction.user
            )

            if roles_cleared:
                logger.info(f"DISMISSAL: Cleared all roles from {self.target_user.display_name}: {', '.join(roles_cleared)}")
            else:
                logger.info(f"DISMISSAL: No roles to clear for {self.target_user.display_name}")
            
            # Set dismissal nickname using nickname_manager
            try:
                dismissal_nickname = await nickname_manager.handle_dismissal(
                    member=self.target_user,
                    reason=self.reason_input.value if hasattr(self, 'reason_input') else "Увольнение через ПКМ"
                )
                if dismissal_nickname:
                    logger.info(f"DISMISSAL: Set dismissal nickname: {self.target_user.display_name} -> %s", dismissal_nickname)
                else:
                    logger.error("DISMISSAL: Failed to set dismissal nickname, keeping current")
            except Exception as nickname_error:
                logger.error("DISMISSAL: Error setting dismissal nickname: %s", nickname_error)
                # Continue even if nickname change fails
            
        except Exception as e:
            logger.error("DISMISSAL: Error in _remove_military_roles_and_reset_nickname: %s", e)
            raise

@app_commands.context_menu(name='Уволить')
@handle_context_errors
async def dismiss_user(interaction: discord.Interaction, user: discord.User):
    """Context menu command to dismiss user using PersonnelManager"""
    # Prevent double-clicks and invalid interactions
    if interaction.response.is_done():
        logger.info(f"Dismiss command ignored for {user.display_name} - interaction already responded")
        return
        
    # Check permissions
    config = load_config()
    if not is_moderator_or_admin(interaction.user, config):
        await interaction.response.send_message(
            " У вас нет прав для выполнения этой команды. Требуются права модератора или администратора.",
            ephemeral=True
        )
        return
    
    # Get member object if user is on server, or create mock user
    if isinstance(user, discord.Member):
        target_user = user
    else:
        # Try to get member object from guild
        target_user = interaction.guild.get_member(user.id)
        if not target_user:
            # Create mock user object for users who left the server
            class MockUser:
                def __init__(self, user_obj):
                    self.id = user_obj.id
                    self.display_name = user_obj.display_name
                    self.mention = user_obj.mention
                    self.name = user_obj.name
                    self._is_mock = True
                    # Add required attributes for moderation checks
                    self.roles = []  # Empty roles list
                    self.guild_permissions = discord.Permissions.none()  # No permissions
            
            target_user = MockUser(user)
    
    # Check if moderator can moderate this user (hierarchy check)
    if not can_moderate_user(interaction.user, target_user, config):
        await interaction.response.send_message(
            " Вы не можете выполнять действия над этим пользователем. Недостаточно прав в иерархии.",
            ephemeral=True
        )
        return
    
    # Check user status before proceeding
    user_status = await get_user_status(target_user.id)
    
    # Check if user is active
    if not user_status['is_active']:
        await interaction.response.send_message(
            f"⚠️ **{target_user.display_name} не состоит в вашей фракции**",
            ephemeral=True
        )
        return
    
    # Open dismissal modal
    modal = DismissalModal(target_user, interaction.guild.id)
    try:
        await interaction.response.send_modal(modal)
        logger.info(f"Dismissal modal sent for {target_user.display_name}")
    except discord.errors.HTTPException as e:
        if e.code == 40060:  # Interaction has already been acknowledged
            logger.info(f"Dismissal modal already sent for {target_user.display_name} (interaction already acknowledged)")
        else:
            logger.error("Error sending dismissal modal: %s", e)
            raise


class DepartmentActionView(ui.View):
    """View for choosing department action type (join/transfer)"""
    
    def __init__(self, target_user: discord.Member):
        super().__init__(timeout=300)
        self.target_user = target_user
    
    @ui.button(label="Принять в подразделение", style=discord.ButtonStyle.green, emoji="➕")
    async def join_department(self, interaction: discord.Interaction, button: ui.Button):
        """Handle department join action"""
        view = DepartmentSelectView(self.target_user, action_type="join")
        await interaction.response.send_message(
            f" **Выберите подразделение для принятия {self.target_user.display_name}:**",
            view=view,
            ephemeral=True
        )
    
    @ui.button(label="Перевести из подразделения", style=discord.ButtonStyle.blurple, emoji="🔄")
    async def transfer_department(self, interaction: discord.Interaction, button: ui.Button):
        """Handle department transfer action"""
        view = DepartmentSelectView(self.target_user, action_type="transfer")
        await interaction.response.send_message(
            f" **Выберите подразделение для перевода {self.target_user.display_name}:**",
            view=view,
            ephemeral=True
        )


class DepartmentSelectView(ui.View):
    """View for selecting department from config"""
    
    def __init__(self, target_user: discord.Member, action_type: str):
        super().__init__(timeout=300)
        self.target_user = target_user
        self.action_type = action_type  # "join" or "transfer"
        
        # Add department select menu
        self.add_item(DepartmentSelect(target_user, action_type))


class DepartmentSelect(ui.Select):
    """Select menu for choosing department"""
    
    def __init__(self, target_user: discord.Member, action_type: str):
        self.target_user = target_user
        self.action_type = action_type
        
        # Load departments from config
        from utils.config_manager import load_config
        config = load_config()
        departments = config.get('departments', {})
        
        # Create options from config departments
        options = []
        for dept_key, dept_config in departments.items():
            name = dept_config.get('name', dept_key)
            abbreviation = dept_config.get('abbreviation', '')
            emoji = dept_config.get('emoji', '🏢')
            
            display_name = f"{name}"
            if abbreviation:
                display_name += f" ({abbreviation})"
            
            options.append(discord.SelectOption(
                label=display_name,
                value=dept_key,
                emoji=emoji,
                description=f"Подразделение {name}"
            ))
        
        super().__init__(
            placeholder="Выберите подразделение...",
            options=options[:25],  # Discord limit
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle department selection"""
        selected_dept = self.values[0]
        
        # Load config to get department name
        from utils.config_manager import load_config
        config = load_config()
        dept_config = config.get('departments', {}).get(selected_dept, {})
        dept_name = dept_config.get('name', selected_dept)
        
        # Show position selection
        view = PositionSelectView(self.target_user, self.action_type, selected_dept, dept_name)
        
        action_text = "принятия в" if self.action_type == "join" else "перевода в"
        await interaction.response.send_message(
            f"📋 **Выберите должность для {action_text} {dept_name}:**",
            view=view,
            ephemeral=True
        )


class PositionSelectView(ui.View):
    """View for selecting position within department"""
    
    def __init__(self, target_user: discord.Member, action_type: str, dept_key: str, dept_name: str):
        super().__init__(timeout=300)
        self.target_user = target_user
        self.action_type = action_type
        self.dept_key = dept_key
        self.dept_name = dept_name
        
        # Add position select menu
        self.add_item(PositionSelect(target_user, action_type, dept_key, dept_name))


class PositionSelect(ui.Select):
    """Select menu for choosing position within department"""
    
    def __init__(self, target_user: discord.Member, action_type: str, dept_key: str, dept_name: str):
        self.target_user = target_user
        self.action_type = action_type
        self.dept_key = dept_key
        self.dept_name = dept_name
        
        # Get positions for this department from database
        options = []
        
        # Add "Без должности" option first
        options.append(discord.SelectOption(
            label="Без должности",
            value="no_position",
            description="Разжаловать с должности или не назначать",
            emoji="🚫"
        ))
        
        try:
            from utils.postgresql_pool import get_db_cursor
            
            with get_db_cursor() as cursor:
                # Get subdivision ID by name
                cursor.execute("""
                    SELECT id FROM subdivisions 
                    WHERE name = %s OR abbreviation = %s
                    LIMIT 1;
                """, (dept_name, dept_key))
                
                subdivision_result = cursor.fetchone()
                if subdivision_result:
                    subdivision_id = subdivision_result['id']
                    
                    # Get positions for this subdivision
                    cursor.execute("""
                        SELECT DISTINCT p.id, p.name 
                        FROM positions p
                        JOIN position_subdivision ps ON p.id = ps.position_id
                        WHERE ps.subdivision_id = %s
                        ORDER BY p.name;
                    """, (subdivision_id,))
                    
                    positions = cursor.fetchall()
                    
                    for pos in positions:
                        options.append(discord.SelectOption(
                            label=pos['name'],
                            value=str(pos['id']),
                            description=f"Должность в {dept_name}"
                        ))
                        
        except Exception as e:
            logger.error("Error loading positions: %s", e)
            # Fallback: if no positions found, add a generic option
            if len(options) == 1:  # Only "Без должности" option
                options.append(discord.SelectOption(
                    label="Стажёр",
                    value="default",
                    description="Должность по умолчанию"
                ))
        
        super().__init__(
            placeholder="Выберите должность...",
            options=options[:25],  # Discord limit
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle position selection and execute department change"""
        selected_position_id = self.values[0]
        position_name = None  # Will be None for "no_position"
        
        # Handle different position selections
        if selected_position_id == "no_position":
            position_name = None  # No position assigned
        elif selected_position_id == "default":
            position_name = "Стажёр"  # Default fallback
        else:
            # Get position name from database
            try:
                from utils.postgresql_pool import get_db_cursor
                with get_db_cursor() as cursor:
                    cursor.execute("SELECT name FROM positions WHERE id = %s;", (selected_position_id,))
                    result = cursor.fetchone()
                    if result:
                        position_name = result['name']
                    else:
                        position_name = "Неизвестная должность"
            except Exception as e:
                logger.error("Error getting position name: %s", e)
                position_name = "Ошибка получения должности"
        
        # Execute department change with optional position
        success, message = await self._execute_department_change(interaction, position_name, selected_position_id)
        
        # Send result message
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"{'✅' if success else '❌'} {message}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"{'✅' if success else '❌'} {message}",
                    ephemeral=True
                )
        except Exception as e:
            logger.error("Error sending result message: %s", e)
            # Try followup as last resort
            try:
                await interaction.followup.send(
                    f"{'✅' if success else '❌'} {message}",
                    ephemeral=True
                )
            except:
                pass
    
    async def _assign_position_in_db(self, user_discord_id: int, position_id: str, position_name: str, moderator_discord_id: int, old_position_name: str = None, moderator_member: discord.Member = None) -> bool:
        """Assign position to user in database and create history record"""
        try:
            from utils.postgresql_pool import get_db_cursor
            from datetime import datetime, timezone, timedelta
            from utils.user_cache import invalidate_user_cache
            
            # Get old position ID and name for role updates and history
            old_position_id = None
            user_member = None
            try:
                # Get user as member for role updates
                for guild in self.bot.guilds if hasattr(self, 'bot') else []:
                    user_member = guild.get_member(user_discord_id)
                    if user_member:
                        break
                
                if not user_member and hasattr(self, 'target_user'):
                    user_member = self.target_user
                
                # Get old position ID (for role updates only, not for history)
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        SELECT ps.position_id
                        FROM personnel p
                        JOIN employees e ON p.id = e.personnel_id
                        LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                        WHERE p.discord_id = %s AND p.is_dismissal = false
                    """, (user_discord_id,))
                    old_pos_result = cursor.fetchone()
                    if old_pos_result and old_pos_result['position_id']:
                        old_position_id = old_pos_result['position_id']
            except Exception as e:
                logger.warning("Warning: Could not get old position for role update: %s", e)
            
            with get_db_cursor() as cursor:
                # Get personnel ID
                cursor.execute("SELECT id FROM personnel WHERE discord_id = %s AND is_dismissal = false;", (user_discord_id,))
                personnel_result = cursor.fetchone()
                if not personnel_result:
                    return False
                personnel_id = personnel_result['id']
                
                # Get position_subdivision_id for the current user's subdivision
                if position_id == "default":
                    # Handle default case - find Стажёр position
                    cursor.execute("""
                        SELECT ps.id FROM position_subdivision ps
                        JOIN positions p ON ps.position_id = p.id
                        JOIN employees e ON ps.subdivision_id = e.subdivision_id
                        WHERE e.personnel_id = %s AND p.name = 'Стажёр'
                        LIMIT 1;
                    """, (personnel_id,))
                else:
                    # Normal case - find position_subdivision_id
                    cursor.execute("""
                        SELECT ps.id FROM position_subdivision ps
                        JOIN employees e ON ps.subdivision_id = e.subdivision_id
                        WHERE e.personnel_id = %s AND ps.position_id = %s
                        LIMIT 1;
                    """, (personnel_id, position_id))
                
                ps_result = cursor.fetchone()
                if not ps_result:
                    return False
                position_subdivision_id = ps_result['id']
                
                # Update employee with new position
                cursor.execute("""
                    UPDATE employees 
                    SET position_subdivision_id = %s
                    WHERE personnel_id = %s;
                """, (position_subdivision_id, personnel_id))
                
                # Get moderator personnel ID for history
                cursor.execute("SELECT id FROM personnel WHERE discord_id = %s;", (moderator_discord_id,))
                moderator_result = cursor.fetchone()
                if not moderator_result:
                    return False
                moderator_personnel_id = moderator_result['id']
                
                # Create history record for position assignment (action_id = 5)
                import json
                changes = {
                    "rank": {
                        "new": None,
                        "previous": None
                    },
                    "position": {
                        "new": position_name,
                        "previous": old_position_name  # Now tracking previous position
                    },
                    "subdivision": {
                        "new": None,
                        "previous": None
                    }
                }
                
                cursor.execute("""
                    INSERT INTO history (personnel_id, action_id, performed_by, details, changes, action_date)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (
                    personnel_id,
                    5,  # Position assignment action_id
                    moderator_personnel_id,
                    None,  # details = NULL
                    json.dumps(changes, ensure_ascii=False),
                    datetime.now(timezone(timedelta(hours=3)))  # Moscow time
                ))
                
                # Update Discord roles for position change
                if user_member:
                    try:
                        # Refresh member object to get current roles
                        try:
                            user_member = await user_member.guild.fetch_member(user_member.id)
                            logger.info("🔄 Refreshed member object before position role update (old method)")
                        except Exception as fetch_error:
                            logger.warning("Could not refresh member: %s", fetch_error)
                        
                        new_position_id = int(position_id) if position_id.isdigit() else None
                        from utils.role_utils import role_utils
                        await role_utils.smart_update_user_position_roles(
                            user_member.guild,
                            user_member,
                            new_position_id,
                            moderator_member
                        )
                    except Exception as e:
                        logger.error("Error updating position roles: %s", e)

                try:
                    invalidate_user_cache(user_discord_id)
                    logger.info("POSITION ASSIGN: Инвалидация кэша для пользователя %s", user_discord_id)
                except Exception as cache_error:
                    logger.error("POSITION ASSIGN: Ошибка при попытке инвалидации кэша: %s", cache_error)
                
                return True
                
        except Exception as e:
            logger.error("Error in _assign_position_in_db: %s", e)
            return False
    
    async def _execute_department_change(self, interaction: discord.Interaction, position_name: str, selected_position_id: str) -> tuple[bool, str]:
        """Execute department change with optional position assignment
        
        Returns:
            tuple[bool, str]: (success, message)
        """
        try:
            logger.info(f"EXECUTE DEPARTMENT CHANGE: Starting for user {self.target_user.id}, action_type={self.action_type}, dept_key={self.dept_key}, position=%s", position_name)
            
            # Import required modules
            from utils.database_manager import PersonnelManager
            from utils.database_manager.position_service import position_service
            from utils.audit_logger import audit_logger, AuditAction
            from utils.config_manager import load_config
            from utils.postgresql_pool import get_db_cursor
            from utils.user_cache import invalidate_user_cache
            from datetime import datetime, timezone, timedelta
            import json
            
            # Initialize managers
            manager = PersonnelManager()
            
            # Get subdivision ID for new department directly from config and DB
            config = load_config()
            dept_config = config.get('departments', {}).get(self.dept_key, {})
            role_id = dept_config.get('role_id')
            
            if not role_id:
                return False, f"Подразделение '{self.dept_name}' не настроено (нет role_id)."
            
            # Get subdivision ID from database by role_id
            new_subdivision_id = None
            try:
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        SELECT id FROM subdivisions WHERE role_id = %s
                    """, (role_id,))
                    result = cursor.fetchone()
                    if result:
                        new_subdivision_id = result['id']
            except Exception as e:
                logger.error("Error getting subdivision ID: %s", e)
            
            if not new_subdivision_id:
                return False, f"Подразделение '{self.dept_name}' не найдено в базе данных."
            
            # Get personnel ID
            personnel_id = await manager._get_personnel_id(self.target_user.id)
            if not personnel_id:
                return False, "Пользователь не найден в базе данных."
            
            # Get current subdivision for history
            current_subdivision = await manager._get_current_subdivision(personnel_id)
            
            # Get current position before any changes for history tracking
            old_position_name = None
            try:
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        SELECT pos.name as position_name
                        FROM personnel p
                        JOIN employees e ON p.id = e.personnel_id
                        LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                        LEFT JOIN positions pos ON ps.position_id = pos.id
                        WHERE p.discord_id = %s AND p.is_dismissal = false
                    """, (self.target_user.id,))
                    old_pos_result = cursor.fetchone()
                    if old_pos_result and old_pos_result['position_name']:
                        old_position_name = old_pos_result['position_name']
            except Exception as e:
                logger.info("Could not get old position for history: %s", e)
            
            # Get user's current rank
            rank_id = await manager._get_user_rank_id(personnel_id)
            if not rank_id:
                return False, "Не удалось определить звание пользователя."
            
            # Update employee record with new subdivision (clears position)
            success = await manager._update_employee_subdivision(personnel_id, new_subdivision_id, rank_id)
            if not success:
                return False, "Не удалось обновить подразделение пользователя."
            
            # Log department transfer to history first
            action_id = 7 if self.action_type == "join" else 8  # 7=join, 8=transfer
            
            # Get moderator personnel ID
            moderator_personnel_id = await manager._get_personnel_id(interaction.user.id)
            
            if moderator_personnel_id:
                # Create history record for department transfer
                changes = {
                    "rank": {
                        "new": None,
                        "previous": None
                    },
                    "position": {
                        "new": None,  # No position change in department transfer
                        "previous": None
                    },
                    "subdivision": {
                        "new": self.dept_name,
                        "previous": await manager._get_subdivision_name(current_subdivision) if current_subdivision else None
                    }
                }
                
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO history (personnel_id, action_id, performed_by, details, changes, action_date)
                        VALUES (%s, %s, %s, %s, %s, %s);
                    """, (
                        personnel_id,
                        action_id,
                        moderator_personnel_id,
                        f"{'Принят' if self.action_type == 'join' else 'Переведен'} в {self.dept_name}",
                        json.dumps(changes, ensure_ascii=False),
                        datetime.now(timezone(timedelta(hours=3)))  # Moscow time
                    ))
            
            # Update Discord roles for department change
            try:
                # Get old department key for role removal
                old_dept_key = None
                if current_subdivision:
                    try:
                        # Get department config key by subdivision_id
                        with get_db_cursor() as cursor:
                            # Get subdivision data
                            cursor.execute("""
                                SELECT name, abbreviation, role_id FROM subdivisions WHERE id = %s
                            """, (current_subdivision,))
                            sub_result = cursor.fetchone()
                            
                            if sub_result:
                                subdivision_name = sub_result['name']
                                role_id = sub_result['role_id']
                                
                                # Find config key by role_id
                                for dept_key, dept_config in config.get('departments', {}).items():
                                    if dept_config.get('role_id') == role_id:
                                        old_dept_key = dept_key
                                        break
                                
                                logger.info("Determined old department: '%s' (role_id=%s) → '%s'", subdivision_name, role_id, old_dept_key)
                    except Exception as e:
                        logger.info("Could not determine old department key: %s", e)
                
                # Update Discord roles using RoleUtils
                try:
                    # Clear old department roles
                    await role_utils.clear_all_department_roles(
                        self.target_user,
                        reason="Смена подразделения"
                    )

                    # Assign new department role
                    await role_utils.assign_department_role(
                        self.target_user,
                        self.dept_key,
                        interaction.user
                    )

                    logger.info("DEPARTMENT CHANGE: Updated department roles")
                except Exception as e:
                    logger.error("Error updating department roles: %s", e)
            except Exception as e:
                logger.error("Error updating department roles: %s", e)
            
            # Send audit notification for department transfer FIRST
            try:
                # Get personnel data for audit
                personnel_data_raw = await manager.get_personnel_data_for_audit(self.target_user.id)
                if personnel_data_raw:
                    # Format data for audit logger
                    full_name = f"{personnel_data_raw.get('first_name', '')} {personnel_data_raw.get('last_name', '')}".strip()
                    if not full_name:
                        full_name = "Неизвестно"
                    
                    personnel_data = {
                        'name': full_name,
                        'static': personnel_data_raw.get('static', ''),
                        'rank': personnel_data_raw.get('rank_name', 'Неизвестно'),
                        'department': self.dept_name,  # Use the new department name
                        'position': old_position_name,  # Show previous position before transfer
                        'reason': None
                    }
                    
                    await audit_logger.send_personnel_audit(
                        guild=interaction.guild,
                        action=await (AuditAction.DEPARTMENT_TRANSFER() if self.action_type == "transfer" else AuditAction.DEPARTMENT_JOIN()),
                        target_user=self.target_user,
                        moderator=interaction.user,
                        personnel_data=personnel_data
                    )
                    logger.info("Sent department transfer audit notification for %s", full_name)
                else:
                    logger.info("Could not get personnel data for department transfer audit notification")
            except Exception as e:
                logger.error("Error sending department transfer audit notification: %s", e)

            # Update nickname for department change via nickname_manager
            try:
                # Fetch fresh personnel summary to get current rank after department update
                personnel_summary = await manager.get_personnel_summary(self.target_user.id)
                rank_name = personnel_summary.get('rank', 'Не назначено') if personnel_summary else 'Не назначено'

                new_nickname = await nickname_manager.handle_transfer(
                    member=self.target_user,
                    subdivision_key=self.dept_key,
                    rank_name=rank_name
                )

                if new_nickname:
                    logger.info("DEPARTMENT CHANGE NICKNAME: Никнейм обновлён через nickname_manager: %s -> %s", self.target_user.display_name, new_nickname)
                else:
                    logger.info("DEPARTMENT CHANGE NICKNAME: Автозамена никнейма пропущена или не изменилась для %s", self.target_user.display_name)
            except Exception as e:
                logger.error("DEPARTMENT CHANGE NICKNAME ERROR: Не удалось обновить никнейм через nickname_manager: %s", e)
            
            # Assign position if selected (this will log its own history record)
            position_assigned = False
            if selected_position_id not in ["no_position", "default"] and position_name:
                position_assigned = await assign_position_in_db(
                    user_member=self.target_user,
                    position_id=selected_position_id,
                    position_name=position_name,
                    moderator_member=interaction.user,
                    old_position_name=old_position_name
                )
                logger.info("DEPARTMENT CHANGE: Position assignment result: %s", position_assigned)
                
                # Send separate audit notification for position assignment SECOND
                if position_assigned:
                    try:
                        # Get updated personnel data for position assignment audit
                        updated_personnel_data = await manager.get_personnel_data_for_audit(self.target_user.id)
                        if updated_personnel_data:
                            # Format data for position assignment audit
                            full_name = f"{updated_personnel_data.get('first_name', '')} {updated_personnel_data.get('last_name', '')}".strip()
                            if not full_name:
                                full_name = "Неизвестно"
                            
                            position_audit_data = {
                                'name': full_name,
                                'static': updated_personnel_data.get('static', ''),
                                'rank': updated_personnel_data.get('rank_name', 'Неизвестно'),
                                'department': updated_personnel_data.get('subdivision_name', self.dept_name),  # Use current department from DB
                                'position': position_name,
                                'reason': None
                            }
                            
                            await audit_logger.send_personnel_audit(
                                guild=interaction.guild,
                                action=await AuditAction.POSITION_ASSIGNMENT(),
                                target_user=self.target_user,
                                moderator=interaction.user,
                                personnel_data=position_audit_data
                            )
                            logger.info("Sent position assignment audit notification for %s", full_name)
                        else:
                            logger.info("Could not get updated personnel data for position assignment audit")
                    except Exception as e:
                        logger.error("Error sending position assignment audit notification: %s", e)
            
            # Handle "no_position" selection - check if user had a position before department change
            elif selected_position_id == "no_position" and old_position_name:
                logger.info("DEPARTMENT CHANGE: User had position '%s' before transfer, logging demotion", old_position_name)
                
                # Create history record for position demotion (action_id = 6)
                moderator_personnel_id = await manager._get_personnel_id(interaction.user.id)
                if moderator_personnel_id:
                    changes = {
                        "rank": {
                            "new": None,
                            "previous": None
                        },
                        "position": {
                            "new": None,
                            "previous": old_position_name
                        },
                        "subdivision": {
                            "new": None,  # No subdivision change in position demotion
                            "previous": None
                        }
                    }
                    
                    with get_db_cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO history (personnel_id, action_id, performed_by, details, changes, action_date)
                            VALUES (%s, %s, %s, %s, %s, %s);
                        """, (
                            personnel_id,
                            6,  # action_id for demotion
                            moderator_personnel_id,
                            f"Разжалован с должности '{old_position_name}' при переводе в {self.dept_name}",
                            json.dumps(changes, ensure_ascii=False),
                            datetime.now(timezone(timedelta(hours=3)))  # Moscow time
                        ))
                
                # Send audit notification for position demotion SECOND
                try:
                    # Get personnel data for demotion audit
                    demotion_personnel_data = await manager.get_personnel_data_for_audit(self.target_user.id)
                    if demotion_personnel_data:
                        # Format data for demotion audit
                        full_name = f"{demotion_personnel_data.get('first_name', '')} {demotion_personnel_data.get('last_name', '')}".strip()
                        if not full_name:
                            full_name = "Неизвестно"
                        
                        demotion_audit_data = {
                            'name': full_name,
                            'static': demotion_personnel_data.get('static', ''),
                            'rank': demotion_personnel_data.get('rank_name', 'Неизвестно'),
                            'department': demotion_personnel_data.get('subdivision_name', self.dept_name),
                            'position': None,  # No position after demotion
                            'reason': None
                        }
                        
                        await audit_logger.send_personnel_audit(
                            guild=interaction.guild,
                            action=await AuditAction.POSITION_DEMOTION(),
                            target_user=self.target_user,
                            moderator=interaction.user,
                            personnel_data=demotion_audit_data
                        )
                        logger.info("Sent position demotion audit notification for %s (position: %s)", full_name, old_position_name)
                    else:
                        logger.info("Could not get personnel data for position demotion audit")
                except Exception as e:
                    logger.error("Error sending position demotion audit notification: %s", e)
                
                # Update Discord roles using RoleUtils - remove position role
                try:
                    # Refresh member object to get current roles
                    try:
                        self.target_user = await self.target_user.guild.fetch_member(self.target_user.id)
                        logger.info("🔄 Refreshed member object before removing old position role")
                    except Exception as fetch_error:
                        logger.warning("Could not refresh member: %s", fetch_error)
                    
                    await role_utils.clear_all_position_roles(
                        self.target_user,
                        reason="Снятие должности"
                    )
                    logger.info(f"Removed position role for {self.target_user.display_name}")
                except Exception as e:
                    logger.error("Error removing position role: %s", e)
            
            # Remove the old department transfer history logging code that's later in the method
            # (it was moved up here)
            
            # Return success message
            action_text = "принят" if self.action_type == "join" else "переведен"
            position_text = ""
            if position_assigned:
                position_text = f"на должность **{position_name}**"
            elif selected_position_id == "no_position" and old_position_name:
                position_text = f"Пользователь **{self.target_user.display_name}** успешно {action_text} в **{self.dept_name}**{position_text}!"
            elif selected_position_id == "no_position":
                position_text = "без должности"
            
            success_message = f"Пользователь **{self.target_user.display_name}** успешно {action_text} в **{self.dept_name}**{position_text}!"
            
            logger.info(f"DEPARTMENT CHANGE: Successfully completed for user {self.target_user.id}")
            try:
                invalidate_user_cache(self.target_user.id)
                logger.info("DEPARTMENT CHANGE: Инвалидация кэша для пользователя %s", self.target_user.id)
            except Exception as cache_error:
                logger.error("DEPARTMENT CHANGE: Ошибка при попытке инвалидации кэша: %s", cache_error)
            return True, success_message
            
        except Exception as e:
            logger.error("Error in _execute_department_change: %s", e)
            import traceback
            traceback.print_exc()
            return False, f"Произошла ошибка при выполнении операции: {str(e)}"

class PositionOnlySelectView(ui.View):
    """View for selecting position only (for position assignment)"""
    
    def __init__(self, target_user: discord.Member):
        super().__init__(timeout=300)
        self.target_user = target_user
        
        # Add position select menu
        self.add_item(PositionOnlySelect(target_user))


class PositionOnlySelect(ui.Select):
    """Select menu for choosing position for assignment"""
    
    def __init__(self, target_user: discord.Member):
        self.target_user = target_user
        
        # Get user's current subdivision from database and available positions
        options = []
        self.subdivision_name = None
        
        try:
            from utils.postgresql_pool import get_db_cursor
            
            with get_db_cursor() as cursor:
                # Get user's current subdivision
                cursor.execute("""
                    SELECT s.name 
                    FROM employees e
                    JOIN personnel p ON e.personnel_id = p.id
                    JOIN subdivisions s ON e.subdivision_id = s.id
                    WHERE p.discord_id = %s AND p.is_dismissal = false;
                """, (target_user.id,))
                
                subdivision_result = cursor.fetchone()
                if not subdivision_result:
                    # User not in any subdivision
                    options = [discord.SelectOption(
                        label="❌ Ошибка: пользователь не в подразделении",
                        value="error",
                        description="Сначала назначьте пользователя в подразделение"
                    )]
                else:
                    self.subdivision_name = subdivision_result['name']
                    
                    # Get subdivision ID
                    cursor.execute("SELECT id FROM subdivisions WHERE name = %s;", (self.subdivision_name,))
                    subdivision_id_result = cursor.fetchone()
                    
                    if subdivision_id_result:
                        subdivision_id = subdivision_id_result['id']
                        
                        # Get positions for this subdivision
                        cursor.execute("""
                            SELECT DISTINCT p.id, p.name 
                            FROM positions p
                            JOIN position_subdivision ps ON p.id = ps.position_id
                            WHERE ps.subdivision_id = %s
                            ORDER BY p.name;
                        """, (subdivision_id,))
                        
                        positions = cursor.fetchall()
                        
                        if positions:
                            # Add "Без должности" option first
                            options.append(discord.SelectOption(
                                label="Без должности",
                                value="no_position",
                                description="Разжаловать с текущей должности",
                                emoji="📤"
                            ))
                            
                            for pos in positions:
                                options.append(discord.SelectOption(
                                    label=pos['name'],
                                    value=str(pos['id']),
                                    description=f"Должность в {self.subdivision_name}"
                                ))
                        else:
                            options = [discord.SelectOption(
                                label="❌ Нет доступных должностей",
                                value="no_positions",
                                description=f"В {self.subdivision_name} нет должностей для назначения"
                            )]
                        
        except Exception as e:
            logger.error("Error loading positions for assignment: %s", e)
            options = [discord.SelectOption(
                label="❌ Ошибка загрузки должностей",
                value="db_error",
                description="Попробуйте позже"
            )]
        
        super().__init__(
            placeholder="Выберите должность для назначения...",
            options=options[:25],  # Discord limit
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle position selection for assignment"""
        selected_position_id = self.values[0]
        
        # Check for error states
        if selected_position_id in ["error", "no_positions", "db_error"]:
            error_messages = {
                "error": "❌ **Ошибка:** Пользователь не числится ни в одном подразделении.\nСначала назначьте пользователя в подразделение через «Изменить подразделение».",
                "no_positions": f"❌ **Ошибка:** В подразделении «{self.subdivision_name}» нет доступных должностей для назначения.",
                "db_error": "❌ **Ошибка базы данных:** Не удалось загрузить список должностей. Попробуйте позже."
            }
            await interaction.response.send_message(error_messages[selected_position_id], ephemeral=True)
            return
        
        # Handle "no_position" selection
        if selected_position_id == "no_position":
            # Execute position removal (same as demotion button)
            await self._execute_position_removal(interaction)
            return
        
        # Get position name for regular positions
        position_name = "Неизвестная должность"
        try:
            from utils.postgresql_pool import get_db_cursor
            with get_db_cursor() as cursor:
                cursor.execute("SELECT name FROM positions WHERE id = %s;", (selected_position_id,))
                result = cursor.fetchone()
                if result:
                    position_name = result['name']
        except Exception as e:
            logger.error("Error getting position name: %s", e)
        
        # Execute position assignment
        await self._execute_position_assignment(interaction, position_name, selected_position_id)
    
    async def _execute_position_removal(self, interaction: discord.Interaction):
        """Execute position removal (same as demote_from_position button)"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Check if user has a position to remove
            current_position = await self._get_current_position()
            if not current_position:
                await interaction.followup.send(
                    f"❌ **{self.target_user.display_name}** не имеет должности для разжалования.",
                    ephemeral=True
                )
                return
            
            # Execute position removal
            success = await self._remove_position_from_db_standalone(
                self.target_user.id,
                current_position,
                interaction.user.id
            )
            
            if not success:
                await interaction.followup.send(
                    f"❌ **Ошибка БД:** Не удалось разжаловать с должности",
                    ephemeral=True
                )
                return
            
            # Send audit notification
            try:
                from utils.audit_logger import audit_logger, AuditAction
                from utils.config_manager import load_config
                from utils.database_manager import PersonnelManager
                from utils.postgresql_pool import get_db_cursor
                from utils.user_cache import get_cached_user_info, invalidate_user_cache
                
                pm = PersonnelManager()
                config = load_config()
                
                # СТРАТЕГИЯ: Кэш → БД → Обновление кэша
                personnel_data = None
                
                # ПОПЫТКА 1: Получить из кэша
                logger.info(f"AUDIT (demotion): Checking cache for user {self.target_user.id}...")
                cached_data = await get_cached_user_info(self.target_user.id)
                
                if cached_data and cached_data.get('full_name') and cached_data.get('rank'):
                    logger.info("AUDIT (demotion): Got data from cache")
                    personnel_data = {
                        'name': cached_data.get('full_name', self.target_user.display_name),
                        'static': cached_data.get('static', 'Не указано'),
                        'rank': cached_data.get('rank', 'Не назначено'),
                        'department': cached_data.get('department', 'Не назначено'),
                        'position': None
                    }
                else:
                    # ПОПЫТКА 2: Кэш пуст → идём в БД
                    logger.info("AUDIT (demotion): Cache miss, querying database...")
                    invalidate_user_cache(self.target_user.id)
                    
                    db_data = await pm.get_personnel_data_for_audit(self.target_user.id)
                    
                    if db_data and db_data.get('name') and db_data.get('rank'):
                        logger.info("AUDIT (demotion): Got data from PersonnelManager")
                        personnel_data = {
                            'name': db_data.get('name', self.target_user.display_name),
                            'static': db_data.get('static', 'Не указано'),
                            'rank': db_data.get('rank', 'Не назначено'),
                            'department': db_data.get('department', 'Не назначено'),
                            'position': None
                        }
                        await get_cached_user_info(self.target_user.id, force_refresh=True)
                    else:
                        # ПОПЫТКА 3: Прямой SQL
                        logger.info("AUDIT (demotion): Trying direct SQL...")
                        try:
                            with get_db_cursor() as cursor:
                                cursor.execute("""
                                    SELECT 
                                        p.first_name,
                                        p.last_name,
                                        p.static,
                                        r.name as rank_name,
                                        s.name as subdivision_name
                                    FROM personnel p
                                    LEFT JOIN employees e ON p.id = e.personnel_id
                                    LEFT JOIN ranks r ON e.rank_id = r.id
                                    LEFT JOIN subdivisions s ON e.subdivision_id = s.id
                                    WHERE p.discord_id = %s
                                    ORDER BY p.id DESC
                                    LIMIT 1;
                                """, (self.target_user.id,))
                                
                                db_result = cursor.fetchone()
                                if db_result:
                                    logger.info("AUDIT (demotion): Got data from SQL")
                                    personnel_data = {
                                        'name': f"{db_result['first_name'] or ''} {db_result['last_name'] or ''}".strip() or self.target_user.display_name,
                                        'static': db_result['static'] or 'Не указано',
                                        'rank': db_result['rank_name'] or 'Не назначено',
                                        'department': db_result['subdivision_name'] or 'Не назначено',
                                        'position': None
                                    }
                                    await get_cached_user_info(self.target_user.id, force_refresh=True)
                                else:
                                    logger.info("AUDIT (demotion): Ultimate fallback")
                                    personnel_data = {
                                        'name': self.target_user.display_name,
                                        'static': 'Не указано',
                                        'rank': 'Не назначено',
                                        'department': 'Не назначено',
                                        'position': None
                                    }
                        except Exception as db_fallback_error:
                            logger.warning("AUDIT (demotion): SQL failed: %s", db_fallback_error)
                            personnel_data = {
                                'name': self.target_user.display_name,
                                'static': 'Не указано',
                                'rank': 'Не назначено',
                                'department': 'Не назначено',
                                'position': None
                            }
                
                logger.info("AUDIT (demotion): Final data = %s", personnel_data)
                
                await audit_logger.send_personnel_audit(
                    guild=interaction.guild,
                    action=await AuditAction.POSITION_DEMOTION(),
                    target_user=self.target_user,
                    moderator=interaction.user,
                    personnel_data=personnel_data,
                    config=config
                )
                
            except Exception as audit_error:
                logger.error("Warning: Failed to send audit notification: %s", audit_error)
            
            # Success message
            await interaction.followup.send(
                f"✅ **{self.target_user.display_name}** разжалован с должности **{current_position}**\n"
                f"📊 Отправлен кадровый аудит",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error("Error in position removal: %s", e)
            await interaction.followup.send(f"❌ **Ошибка:** {str(e)}", ephemeral=True)
    
    async def _get_current_position(self) -> str:
        """Get user's current position name"""
        try:
            from utils.postgresql_pool import get_db_cursor
            
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT pos.name 
                    FROM employees e
                    JOIN personnel p ON e.personnel_id = p.id
                    JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                    JOIN positions pos ON ps.position_id = pos.id
                    WHERE p.discord_id = %s AND p.is_dismissal = false;
                """, (self.target_user.id,))
                
                result = cursor.fetchone()
                return result['name'] if result else None
                
        except Exception as e:
            logger.error("Error getting current position: %s", e)
            return None
    
    async def _remove_position_from_db_standalone(self, user_discord_id: int, position_name: str, moderator_discord_id: int) -> bool:
        """Remove position from user in database (standalone version)"""
        try:
            from utils.postgresql_pool import get_db_cursor
            from datetime import datetime, timezone, timedelta
            from utils.user_cache import invalidate_user_cache
            import json
            
            # Get old position ID for role updates
            old_position_id = None
            user_member = None
            try:
                # Get user as member for role updates
                if hasattr(self, 'target_user'):
                    user_member = self.target_user
                
                # Get old position
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        SELECT ps.position_id 
                        FROM personnel p
                        JOIN employees e ON p.id = e.personnel_id
                        LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                        WHERE p.discord_id = %s AND p.is_dismissal = false
                    """, (user_discord_id,))
                    old_pos_result = cursor.fetchone()
                    if old_pos_result and old_pos_result['position_id']:
                        old_position_id = old_pos_result['position_id']
            except Exception as e:
                logger.warning("Warning: Could not get old position for role update: %s", e)
            
            with get_db_cursor() as cursor:
                # Get personnel ID
                cursor.execute("SELECT id FROM personnel WHERE discord_id = %s AND is_dismissal = false;", (user_discord_id,))
                personnel_result = cursor.fetchone()
                if not personnel_result:
                    return False
                personnel_id = personnel_result['id']
                
                # Clear position_subdivision_id in employees
                cursor.execute("""
                    UPDATE employees 
                    SET position_subdivision_id = NULL
                    WHERE personnel_id = %s;
                """, (personnel_id,))
                
                # Get moderator personnel ID for history
                cursor.execute("SELECT id FROM personnel WHERE discord_id = %s;", (moderator_discord_id,))
                moderator_result = cursor.fetchone()
                if not moderator_result:
                    return False
                moderator_personnel_id = moderator_result['id']
                
                # Create history record for position demotion (action_id = 6)
                changes = {
                    "rank": {
                        "new": None,
                        "previous": None
                    },
                    "position": {
                        "new": None,
                        "previous": position_name
                    },
                    "subdivision": {
                        "new": None,
                        "previous": None
                    }
                }
                
                cursor.execute("""
                    INSERT INTO history (personnel_id, action_id, performed_by, details, changes, action_date)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (
                    personnel_id,
                    6,  # Position demotion action_id
                    moderator_personnel_id,
                    None,  # details = NULL
                    json.dumps(changes, ensure_ascii=False),
                    datetime.now(timezone(timedelta(hours=3)))  # Moscow time
                ))
                
                # Update Discord roles using RoleUtils after position removal
                if user_member:
                    try:
                        # Refresh member object to get current roles from Discord API
                        try:
                            user_member = await user_member.guild.fetch_member(user_member.id)
                            logger.info("🔄 Refreshed member object before removing position roles")
                        except Exception as fetch_error:
                            logger.warning("Could not refresh member: %s", fetch_error)
                        
                        # Remove all position roles via smart updater
                        from utils.role_utils import role_utils
                        await role_utils.smart_update_user_position_roles(
                            user_member.guild,
                            user_member,
                            None,
                            None
                        )
                        logger.info(f"Position roles removed for {user_member.display_name}")
                    except Exception as role_error:
                        logger.error("Warning: Failed to remove position role: %s", role_error)

                try:
                    invalidate_user_cache(user_discord_id)
                    logger.info("POSITION REMOVE: Инвалидация кэша для пользователя %s", user_discord_id)
                except Exception as cache_error:
                    logger.error("POSITION REMOVE: Ошибка при попытке инвалидации кэша: %s", cache_error)
                
                return True
                
        except Exception as e:
            logger.error("Error in _remove_position_from_db_standalone: %s", e)
            return False
    
    async def _execute_position_assignment(self, interaction: discord.Interaction, position_name: str, position_id: str):
        """Execute position assignment using existing logic"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Use the same assignment logic from department change
            success = await assign_position_in_db(
                user_member=self.target_user,
                position_id=position_id,
                position_name=position_name,
                moderator_member=interaction.user,
                old_position_name=None
            )
            
            if not success:
                await interaction.followup.send(
                    f"❌ **Ошибка БД:** Не удалось назначить должность «{position_name}»", 
                    ephemeral=True
                )
                return
            
            # Send audit notification
            try:
                from utils.audit_logger import audit_logger, AuditAction
                from utils.config_manager import load_config
                from utils.database_manager import PersonnelManager
                from utils.postgresql_pool import get_db_cursor
                from utils.user_cache import get_cached_user_info, invalidate_user_cache
                
                pm = PersonnelManager()
                config = load_config()
                
                # СТРАТЕГИЯ: Кэш → БД → Обновление кэша
                personnel_data = None
                
                # ПОПЫТКА 1: Получить из кэша (БЫСТРО)
                logger.info(f"AUDIT (PositionOnly): Checking cache for user {self.target_user.id}...")
                cached_data = await get_cached_user_info(self.target_user.id)
                
                if cached_data and cached_data.get('full_name') and cached_data.get('rank'):
                    # Кэш содержит полные данные
                    logger.info("AUDIT (PositionOnly): Got FULL data from cache")
                    personnel_data = {
                        'name': cached_data.get('full_name', self.target_user.display_name),
                        'static': cached_data.get('static', 'Не указано'),
                        'rank': cached_data.get('rank', 'Не назначено'),
                        'department': cached_data.get('department', self.subdivision_name or 'Не назначено'),
                        'position': position_name
                    }
                else:
                    # ПОПЫТКА 2: Кэш пуст или неполный → идём в БД
                    logger.info("AUDIT (PositionOnly): Cache miss or incomplete, querying database...")
                    
                    # Инвалидируем старый кэш
                    invalidate_user_cache(self.target_user.id)
                    
                    # Получаем из БД через PersonnelManager
                    db_data = await pm.get_personnel_data_for_audit(self.target_user.id)
                    
                    if db_data and db_data.get('name') and db_data.get('rank'):
                        logger.info("AUDIT (PositionOnly): Got data from PersonnelManager")
                        personnel_data = {
                            'name': db_data.get('name', self.target_user.display_name),
                            'static': db_data.get('static', 'Не указано'),
                            'rank': db_data.get('rank', 'Не назначено'),
                            'department': db_data.get('department', self.subdivision_name or 'Не назначено'),
                            'position': position_name
                        }
                        
                        # ОБНОВЛЯЕМ КЭШ свежими данными
                        logger.info("AUDIT (PositionOnly): Updating cache with fresh data...")
                        await get_cached_user_info(self.target_user.id, force_refresh=True)
                    else:
                        # ПОПЫТКА 3: Прямой SQL запрос (последняя надежда)
                        logger.info("AUDIT (PositionOnly): PersonnelManager returned incomplete data, trying direct SQL...")
                        try:
                            with get_db_cursor() as cursor:
                                cursor.execute("""
                                    SELECT 
                                        p.first_name,
                                        p.last_name,
                                        p.static,
                                        r.name as rank_name,
                                        s.name as subdivision_name,
                                        pos.name as position_name
                                    FROM personnel p
                                    LEFT JOIN employees e ON p.id = e.personnel_id
                                    LEFT JOIN ranks r ON e.rank_id = r.id
                                    LEFT JOIN subdivisions s ON e.subdivision_id = s.id
                                    LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                                    LEFT JOIN positions pos ON ps.position_id = pos.id
                                    WHERE p.discord_id = %s
                                    ORDER BY p.id DESC
                                    LIMIT 1;
                                """, (self.target_user.id,))
                                
                                db_result = cursor.fetchone()
                                if db_result:
                                    logger.info("AUDIT (PositionOnly): Got data from direct SQL")
                                    personnel_data = {
                                        'name': f"{db_result['first_name'] or ''} {db_result['last_name'] or ''}".strip() or self.target_user.display_name,
                                        'static': db_result['static'] or 'Не указано',
                                        'rank': db_result['rank_name'] or 'Не назначено',
                                        'department': db_result['subdivision_name'] or self.subdivision_name or 'Не назначено',
                                        'position': position_name
                                    }
                                    
                                    # ОБНОВЛЯЕМ КЭШ
                                    logger.info("AUDIT (PositionOnly): Updating cache with SQL data...")
                                    await get_cached_user_info(self.target_user.id, force_refresh=True)
                                else:
                                    # Ultimate fallback
                                    logger.info("AUDIT (PositionOnly): No data found anywhere, using ultimate fallback")
                                    personnel_data = {
                                        'name': self.target_user.display_name,
                                        'static': 'Не указано',
                                        'rank': 'Не назначено',
                                        'department': self.subdivision_name or 'Не назначено',
                                        'position': position_name
                                    }
                        except Exception as db_fallback_error:
                            logger.warning("AUDIT (PositionOnly): Direct SQL failed: %s", db_fallback_error)
                            personnel_data = {
                                'name': self.target_user.display_name,
                                'static': 'Не указано',
                                'rank': 'Не назначено',
                                'department': self.subdivision_name or 'Не назначено',
                                'position': position_name
                            }
                
                logger.info("AUDIT (PositionOnly): Final personnel_data = %s", personnel_data)
                
                await audit_logger.send_personnel_audit(
                    guild=interaction.guild,
                    action=await AuditAction.POSITION_ASSIGNMENT(),
                    target_user=self.target_user,
                    moderator=interaction.user,
                    personnel_data=personnel_data,
                    config=config
                )
                
            except Exception as audit_error:
                logger.error("Warning: Failed to send audit notification: %s", audit_error)
            
            # Success message
            await interaction.followup.send(
                f"✅ **{self.target_user.display_name}** успешно назначен на должность **{position_name}**\n"
                f" Отправлен кадровый аудит",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error("Error in position assignment: %s", e)
            await interaction.followup.send(f" **Ошибка:** {str(e)}", ephemeral=True)
    
async def assign_position_in_db(user_member: discord.Member, position_id: str, position_name: str, moderator_member: discord.Member, old_position_name: str | None = None) -> bool:
    """Общая логика назначения должности в БД и обновления ролей.
    Используется как при переводе в подразделение, так и при отдельном назначении должности.
    """
    try:
        from utils.postgresql_pool import get_db_cursor
        from datetime import datetime, timezone, timedelta
        from utils.user_cache import invalidate_user_cache
        import json

        user_discord_id = user_member.id
        moderator_discord_id = moderator_member.id

        # Получаем прошлую должность, если не передана
        if old_position_name is None:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT pos.name as position_name
                    FROM personnel p
                    JOIN employees e ON p.id = e.personnel_id
                    LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                    LEFT JOIN positions pos ON ps.position_id = pos.id
                    WHERE p.discord_id = %s AND p.is_dismissal = false
                    """,
                    (user_discord_id,)
                )
                old_pos_result = cursor.fetchone()
                if old_pos_result and old_pos_result.get('position_name'):
                    old_position_name = old_pos_result['position_name']

        with get_db_cursor() as cursor:
            # Ищем personnel_id пользователя
            cursor.execute("SELECT id FROM personnel WHERE discord_id = %s AND is_dismissal = false;", (user_discord_id,))
            personnel_result = cursor.fetchone()
            if not personnel_result:
                return False
            personnel_id = personnel_result['id']

            # Определяем текущий subdivision пользователя и позицию для него
            cursor.execute(
                """
                SELECT e.subdivision_id
                FROM employees e
                WHERE e.personnel_id = %s
                LIMIT 1;
                """,
                (personnel_id,)
            )
            emp_sub_result = cursor.fetchone()
            if not emp_sub_result or not emp_sub_result.get('subdivision_id'):
                return False
            subdivision_id = emp_sub_result['subdivision_id']

            # Берём связку position_subdivision
            cursor.execute(
                """
                SELECT ps.id FROM position_subdivision ps
                WHERE ps.subdivision_id = %s AND ps.position_id = %s
                LIMIT 1;
                """,
                (subdivision_id, position_id)
            )
            ps_result = cursor.fetchone()
            if not ps_result:
                return False
            position_subdivision_id = ps_result['id']

            # Обновляем должность сотрудника
            cursor.execute(
                """
                UPDATE employees
                SET position_subdivision_id = %s
                WHERE personnel_id = %s;
                """,
                (position_subdivision_id, personnel_id)
            )

            # Получаем personnel_id модератора для истории
            cursor.execute("SELECT id FROM personnel WHERE discord_id = %s;", (moderator_discord_id,))
            moderator_result = cursor.fetchone()
            if not moderator_result:
                return False
            moderator_personnel_id = moderator_result['id']

            # Пишем историю (action_id = 5 — назначение должности)
            changes = {
                "rank": {"new": None, "previous": None},
                "position": {"new": position_name, "previous": old_position_name},
                "subdivision": {"new": None, "previous": None},
            }

            cursor.execute(
                """
                INSERT INTO history (personnel_id, action_id, performed_by, details, changes, action_date)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    personnel_id,
                    5,
                    moderator_personnel_id,
                    None,
                    json.dumps(changes, ensure_ascii=False),
                    datetime.now(timezone(timedelta(hours=3))),
                ),
            )

        # Обновляем роли должности через умную систему позиций
        try:
            # Refresh member object to get current roles from Discord API
            try:
                user_member = await user_member.guild.fetch_member(user_member.id)
                logger.info("🔄 Refreshed member object before assigning position roles")
            except Exception as fetch_error:
                logger.warning("Could not refresh member: %s", fetch_error)
            
            from utils.role_utils import role_utils
            new_position_id_int = int(position_id) if isinstance(position_id, (int, str)) and str(position_id).isdigit() else None
            
            logger.info("POSITION ROLES DEBUG: position_id=%s, type=%s, int_value=%s", position_id, type(position_id), new_position_id_int)
            
            # Используем smart_update для корректного назначения ролей
            success = await role_utils.smart_update_user_position_roles(
                user_member.guild,
                user_member,
                new_position_id_int,
                moderator_member
            )
            
            if success:
                logger.info("POSITION ROLES: Обновлены роли должности для %s (position_id=%s)", user_member.display_name, new_position_id_int)
            else:
                logger.warning("POSITION ROLES: Не удалось обновить роли для %s", user_member.display_name)
        except Exception as role_err:
            logger.error("POSITION ROLES ERROR: %s", role_err)
            import traceback
            traceback.print_exc()

        try:
            invalidate_user_cache(user_discord_id)
            logger.info("POSITION ASSIGN (global): Инвалидация кэша для пользователя %s", user_discord_id)
        except Exception as cache_error:
            logger.error("POSITION ASSIGN (global): Ошибка при попытке инвалидации кэша: %s", cache_error)

        return True

    except Exception as e:
        logger.error("Error in assign_position_in_db: %s", e)
        return False


class RankChangeView(ui.View):
    """View for rank change with confirmation for promotion type"""
    
    def __init__(self, target_user: discord.Member, new_rank: str, is_promotion: bool):
        super().__init__(timeout=300)
        self.target_user = target_user
        self.new_rank = new_rank
        self.is_promotion = is_promotion
        
        if is_promotion:
            # Only show promotion type selection for promotions
            self.add_promotion_buttons()
    
    def add_promotion_buttons(self):
        """Add buttons for promotion type selection"""
        promotion_button = ui.Button(
            label="Повышение",
            style=discord.ButtonStyle.green,
            emoji="⬆️"
        )
        promotion_button.callback = self.handle_promotion
        self.add_item(promotion_button)
        
        restoration_button = ui.Button(
            label="Восстановление",
            style=discord.ButtonStyle.blurple,
            emoji="🔄"
        )
        restoration_button.callback = self.handle_restoration
        self.add_item(restoration_button)
    
    async def handle_promotion(self, interaction: discord.Interaction):
        """Handle regular promotion (action_id = 1)"""
        await self._execute_rank_change(interaction, action_id=1, action_name="Повышение")
    
    async def handle_restoration(self, interaction: discord.Interaction):
        """Handle rank restoration (action_id = 4)"""
        await self._execute_rank_change(interaction, action_id=4, action_name="Восстановление")
    
    async def _execute_rank_change(self, interaction: discord.Interaction, action_id: int, action_name: str):
        """Execute the rank change with specified action_id"""
        try:
            # Only defer if not already responded
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            
            # Get current rank BEFORE changing it in database
            old_rank = await get_user_rank_from_db(self.target_user.id)
            
            # Execute rank change in database
            success = await self._change_rank_in_db(
                self.target_user.id,
                self.new_rank,
                interaction.user.id,
                action_id
            )
            
            if not success:
                await interaction.followup.send(
                    f"❌ **Ошибка БД:** Не удалось изменить ранг на «{self.new_rank}»",
                    ephemeral=True
                )
                return
            
            # Send audit notification
            try:
                from utils.audit_logger import audit_logger, AuditAction
                from utils.config_manager import load_config
                from utils.database_manager import PersonnelManager
                from utils.postgresql_pool import get_db_cursor
                from utils.user_cache import get_cached_user_info, invalidate_user_cache
                
                pm = PersonnelManager()
                config = load_config()
                
                # СТРАТЕГИЯ: Кэш → БД → Обновление кэша
                personnel_data = None
                
                # ПОПЫТКА 1: Получить из кэша
                logger.info(f"AUDIT (rank): Checking cache for user {self.target_user.id}...")
                cached_data = await get_cached_user_info(self.target_user.id)
                
                if cached_data and cached_data.get('full_name'):
                    logger.info("AUDIT (rank): Got data from cache")
                    personnel_data = {
                        'name': cached_data.get('full_name', self.target_user.display_name),
                        'static': cached_data.get('static', 'Не указано'),
                        'rank': self.new_rank,  # Используем новый ранг
                        'department': cached_data.get('department', 'Не назначено'),
                        'position': cached_data.get('position', 'Не назначено')
                    }
                else:
                    # ПОПЫТКА 2: Кэш пуст → идём в БД
                    logger.info("AUDIT (rank): Cache miss, querying database...")
                    invalidate_user_cache(self.target_user.id)
                    
                    db_data = await pm.get_personnel_data_for_audit(self.target_user.id)
                    
                    if db_data and db_data.get('name'):
                        logger.info("AUDIT (rank): Got data from PersonnelManager")
                        personnel_data = {
                            'name': db_data.get('name', self.target_user.display_name),
                            'static': db_data.get('static', 'Не указано'),
                            'rank': self.new_rank,
                            'department': db_data.get('department', 'Не назначено'),
                            'position': db_data.get('position', 'Не назначено')
                        }
                        await get_cached_user_info(self.target_user.id, force_refresh=True)
                    else:
                        # ПОПЫТКА 3: Прямой SQL
                        logger.info("AUDIT (rank): Trying direct SQL...")
                        try:
                            with get_db_cursor() as cursor:
                                cursor.execute("""
                                    SELECT 
                                        p.first_name,
                                        p.last_name,
                                        p.static,
                                        s.name as subdivision_name,
                                        pos.name as position_name
                                    FROM personnel p
                                    LEFT JOIN employees e ON p.id = e.personnel_id
                                    LEFT JOIN subdivisions s ON e.subdivision_id = s.id
                                    LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                                    LEFT JOIN positions pos ON ps.position_id = pos.id
                                    WHERE p.discord_id = %s
                                    ORDER BY p.id DESC
                                    LIMIT 1;
                                """, (self.target_user.id,))
                                
                                db_result = cursor.fetchone()
                                if db_result:
                                    logger.info("AUDIT (rank): Got data from SQL")
                                    personnel_data = {
                                        'name': f"{db_result['first_name'] or ''} {db_result['last_name'] or ''}".strip() or self.target_user.display_name,
                                        'static': db_result['static'] or 'Не указано',
                                        'rank': self.new_rank,
                                        'department': db_result['subdivision_name'] or 'Не назначено',
                                        'position': db_result['position_name'] or 'Не назначено'
                                    }
                                    await get_cached_user_info(self.target_user.id, force_refresh=True)
                                else:
                                    logger.info("AUDIT (rank): Ultimate fallback")
                                    personnel_data = {
                                        'name': self.target_user.display_name,
                                        'static': 'Не указано',
                                        'rank': self.new_rank,
                                        'department': 'Не назначено',
                                        'position': 'Не назначено'
                                    }
                        except Exception as db_fallback_error:
                            logger.warning("AUDIT (rank): SQL failed: %s", db_fallback_error)
                            personnel_data = {
                                'name': self.target_user.display_name,
                                'static': 'Не указано',
                                'rank': self.new_rank,
                                'department': 'Не назначено',
                                'position': 'Не назначено'
                            }
                
                logger.info("AUDIT (rank): Final data = %s", personnel_data)
                
                # Choose audit action based on action_id
                if action_id == 1:
                    action = await AuditAction.PROMOTION()
                elif action_id == 2:
                    action = await AuditAction.DEMOTION()
                elif action_id == 4:
                    action = await AuditAction.RANK_RESTORATION()
                else:
                    action = await AuditAction.PROMOTION()  # Default
                
                await audit_logger.send_personnel_audit(
                    guild=interaction.guild,
                    action=action,
                    target_user=self.target_user,
                    moderator=interaction.user,
                    personnel_data=personnel_data,
                    config=config
                )
                
            except Exception as audit_error:
                logger.error("Warning: Failed to send audit notification: %s", audit_error)
            
            # Update Discord roles (remove old rank role, add new rank role)
            try:
                from utils.database_manager import rank_manager
                
                # Update roles using RankManager (old_rank already obtained above)
                # Determine change_type based on action_id
                if action_id == 1:
                    change_type = "promotion"
                elif action_id == 2:
                    change_type = "demotion"
                elif action_id == 4:
                    change_type = "restoration"
                else:
                    change_type = "automatic"  # fallback
                
                # Update Discord roles using RoleUtils
                try:
                    # Refresh member object to get current roles
                    try:
                        self.target_user = await self.target_user.guild.fetch_member(self.target_user.id)
                        logger.info("🔄 Refreshed member object before updating rank roles")
                    except Exception as fetch_error:
                        logger.warning("Could not refresh member: %s", fetch_error)
                    
                    rank_assigned = await role_utils.assign_rank_role(
                        self.target_user,
                        self.new_rank,
                        interaction.user,
                        reason=f"Изменение звания: {change_type}"
                    )
                    if not rank_assigned:
                        logger.error(f"Warning: Failed to assign rank role {self.new_rank}")
                    else:
                        logger.info(f"Discord roles updated: %s -> {self.new_rank}", old_rank)
                except Exception as role_error:
                    logger.error("Warning: Failed to update Discord roles: %s", role_error)
                    
            except Exception as role_error:
                logger.error("Warning: Failed to update Discord roles: %s", role_error)
            
            # Update nickname using nickname_manager
            try:
                logger.info(f"CONTEXT RANK CHANGE: %s {self.target_user.display_name} -> {self.new_rank}", action_name)
                
                # Используем универсальный метод для всех изменений звания
                change_type_map = {
                    "Повышение": "повышение",
                    "Восстановление": "восстановление", 
                    "Разжалование": "понижение"
                }
                change_type = change_type_map.get(action_name, "изменение")
                
                new_nickname = await nickname_manager.handle_rank_change(
                    member=self.target_user,
                    new_rank_name=self.new_rank,
                    change_type=change_type
                )
                
                if new_nickname:
                    logger.info(f"CONTEXT RANK NICKNAME: Никнейм обновлён через nickname_manager: {self.target_user.display_name} -> %s", new_nickname)
                else:
                    # Вычисляем предполагаемый никнейм для логирования ошибки
                    expected_nickname = nickname_manager.preview_nickname_change(
                        current_nickname=self.target_user.display_name,
                        operation='promotion',
                        rank_abbr=self.new_rank,
                        first_name='Неизвестно',
                        last_name='Неизвестно'
                    )
                    logger.error("CONTEXT RANK NICKNAME ERROR: Не удалось обновить никнейм через nickname_manager. Ожидаемый никнейм: %s", expected_nickname)
                    
            except Exception as nickname_error:
                logger.error("CONTEXT RANK NICKNAME EXCEPTION: Ошибка изменения никнейма на \"%s\": %s", new_nickname, nickname_error)
            
            # Success message
            emoji = "⬆️" if action_id in [1, 4] else "⬇️"
            nickname_info = f" (никнейм обновлён)" if 'new_nickname' in locals() and new_nickname else ""
            await interaction.followup.send(
                f"{emoji} **{self.target_user.display_name}** - {action_name.lower()} на ранг **{self.new_rank}**{nickname_info}\n",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error("Error in rank change: %s", e)
            await interaction.followup.send(f" **Ошибка:** {str(e)}", ephemeral=True)
    
    async def _change_rank_in_db(self, user_discord_id: int, new_rank: str, moderator_discord_id: int, action_id: int) -> bool:
        """Change user's rank in database and create history record"""
        try:
            from utils.postgresql_pool import get_db_cursor
            from datetime import datetime, timezone, timedelta
            
            with get_db_cursor() as cursor:
                # Get personnel ID and current rank
                cursor.execute("""
                    SELECT p.id, r.name as current_rank 
                    FROM personnel p
                    JOIN employees e ON p.id = e.personnel_id
                    JOIN ranks r ON e.rank_id = r.id
                    WHERE p.discord_id = %s AND p.is_dismissal = false;
                """, (user_discord_id,))
                personnel_result = cursor.fetchone()
                if not personnel_result:
                    return False
                personnel_id = personnel_result['id']
                previous_rank = personnel_result['current_rank']
                
                # Get new rank ID
                cursor.execute("SELECT id FROM ranks WHERE name = %s;", (new_rank,))
                rank_result = cursor.fetchone()
                if not rank_result:
                    return False
                new_rank_id = rank_result['id']
                
                # Update employee with new rank
                cursor.execute("""
                    UPDATE employees 
                    SET rank_id = %s
                    WHERE personnel_id = %s;
                """, (new_rank_id, personnel_id))
                
                # Get moderator personnel ID for history
                cursor.execute("SELECT id FROM personnel WHERE discord_id = %s;", (moderator_discord_id,))
                moderator_result = cursor.fetchone()
                if not moderator_result:
                    return False
                moderator_personnel_id = moderator_result['id']
                
                # Create history record with previous rank
                import json
                changes = {
                    "rank": {
                        "new": new_rank,
                        "previous": previous_rank
                    },
                    "position": {
                        "new": None,
                        "previous": None
                    },
                    "subdivision": {
                        "new": None,
                        "previous": None
                    }
                }
                
                cursor.execute("""
                    INSERT INTO history (personnel_id, action_id, performed_by, details, changes, action_date)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (
                    personnel_id,
                    action_id,
                    moderator_personnel_id,
                    None,  # details = NULL
                    json.dumps(changes, ensure_ascii=False),
                    datetime.now(timezone(timedelta(hours=3)))  # Moscow time
                ))
                
                return True
                
        except Exception as e:
            logger.error("Error in _change_rank_in_db: %s", e)
            return False


class RankSelectView(ui.View):
    """View for selecting rank from available options"""
    
    def __init__(self, target_user: discord.Member, available_ranks: list, current_rank: str):
        super().__init__(timeout=300)
        self.target_user = target_user
        self.current_rank = current_rank
        
        # Add rank select menu
        self.add_item(RankSelect(target_user, available_ranks, current_rank))


class RankSelect(ui.Select):
    """Select menu for choosing rank"""
    
    def __init__(self, target_user: discord.Member, available_ranks: list, current_rank: str):
        self.target_user = target_user
        self.current_rank = current_rank
        
        # Create options from available ranks
        options = []
        for i, (rank_id, rank_name, rank_level) in enumerate(available_ranks, 1):
            options.append(discord.SelectOption(
                label=f"{i}. {rank_name}",
                value=rank_name,
                description=f"Ранг уровня {rank_level}"
            ))
        
        super().__init__(
            placeholder="Выберите новый ранг...",
            options=options[:25],  # Discord limit
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle rank selection"""
        selected_rank = self.values[0]
        
        # Determine if this is promotion or demotion
        try:
            from utils.postgresql_pool import get_db_cursor
            
            # Get CURRENT rank from database
            current_rank_from_db = await get_user_rank_from_db(self.target_user.id)
            if not current_rank_from_db:
                logger.warning(f"Warning: Could not get current rank for {self.target_user.display_name}")
                is_promotion = True  # Default to promotion
            else:
                with get_db_cursor() as cursor:
                    # Get current rank level
                    cursor.execute("SELECT rank_level FROM ranks WHERE name = %s;", (current_rank_from_db,))
                    current_result = cursor.fetchone()
                    current_level = current_result['rank_level'] if current_result else 1
                    
                    # Get new rank level  
                    cursor.execute("SELECT rank_level FROM ranks WHERE name = %s;", (selected_rank,))
                    new_result = cursor.fetchone()
                    new_level = new_result['rank_level'] if new_result else 1
                    
                    is_promotion = new_level > current_level
                    logger.info("Rank comparison: %s(level %s) -> %s(level %s) = %s", current_rank_from_db, current_level, selected_rank, new_level, 'повышение' if is_promotion else 'понижение')
                
        except Exception as e:
            logger.error("Error determining rank change type: %s", e)
            is_promotion = True  # Default to promotion
        
        if is_promotion:
            # Show promotion type selection
            view = RankChangeView(self.target_user, selected_rank, is_promotion=True)
            await interaction.response.send_message(
                f"⬆️ **Повышение {self.target_user.display_name} на ранг «{selected_rank}»**\n"
                f"Выберите тип повышения:",
                view=view,
                ephemeral=True
            )
        else:
            # Direct demotion (action_id = 2)
            view = RankChangeView(self.target_user, selected_rank, is_promotion=False)
            await view._execute_rank_change(interaction, action_id=2, action_name="Разжалование")


class GeneralEditView(ui.View):
    """View for general editing options (rank, department, position)"""
    
    def __init__(self, target_user: discord.Member):
        super().__init__(timeout=300)
        self.target_user = target_user
    
    @ui.button(label="Изменить ранг", style=discord.ButtonStyle.success, emoji="🎖️", row=1)
    async def edit_rank(self, interaction: discord.Interaction, button: ui.Button):
        """Handle rank editing"""
        try:
            # from forms.personnel_context.rank_utils import RankHierarchy
            from utils.config_manager import is_administrator
            from utils.postgresql_pool import get_db_cursor
            
            # Get current rank from database
            current_rank = await get_user_rank_from_db(self.target_user.id)
            if not current_rank:
                await interaction.response.send_message(
                    f"❌ **{self.target_user.display_name}** не имеет ранга или ранг не определён.",
                    ephemeral=True
                )
                return
            
            # Get moderator's current rank (for permission check)
            moderator_rank = await get_user_rank_from_db(interaction.user.id)
            config = load_config()
            is_admin = interaction.user.guild_permissions.administrator or is_administrator(interaction.user, config)
            
            # Get all ranks from database
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id, name FROM ranks ORDER BY id;")
                all_ranks = cursor.fetchall()
                
                # Get moderator's rank level for permission filtering
                moderator_level = None
                if moderator_rank and not is_admin:
                    cursor.execute("SELECT id FROM ranks WHERE name = %s;", (moderator_rank,))
                    mod_result = cursor.fetchone()
                    if mod_result:
                        moderator_level = mod_result['id']
                
                # Get current user's rank level to exclude it
                current_level = None
                cursor.execute("SELECT id FROM ranks WHERE name = %s;", (current_rank,))
                current_result = cursor.fetchone()
                if current_result:
                    current_level = current_result['id']
            
            # Filter available ranks
            available_ranks = []
            for rank in all_ranks:
                rank_id, rank_name, rank_level = rank['id'], rank['name'], rank['id']
                
                # Skip current rank
                if rank_name == current_rank:
                    continue
                
                # For non-admins: skip ranks at moderator level and above
                if not is_admin and moderator_level and rank_level >= moderator_level:
                    continue
                
                available_ranks.append((rank_id, rank_name, rank_level))
            
            if not available_ranks:
                await interaction.response.send_message(
                    f"❌ **Нет доступных рангов** для изменения.\n"
                    f"Текущий ранг: **{current_rank}**",
                    ephemeral=True
                )
                return
            
            # Show rank selection
            view = RankSelectView(self.target_user, available_ranks, current_rank)
            admin_text = " (все ранги)" if is_admin else f" (до уровня {moderator_rank})"
            await interaction.response.send_message(
                f"🎖️ **Изменение ранга для {self.target_user.display_name}**\n"
                f"Текущий ранг: **{current_rank}**\n"
                f"Доступно рангов: **{len(available_ranks)}**{admin_text}",
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error("Error in rank editing: %s", e)
            await interaction.response.send_message(f"❌ **Ошибка:** {str(e)}", ephemeral=True)
    
    @ui.button(label="Изменить подразделение", style=discord.ButtonStyle.primary, emoji="🏢", row=1)
    async def edit_department(self, interaction: discord.Interaction, button: ui.Button):
        """Handle department editing"""
        # Send action selection view (same as before)
        view = DepartmentActionView(self.target_user)
        await interaction.response.send_message(
            f" **Изменение подразделения для {self.target_user.display_name}**\n"
            f"Выберите тип действия:",
            view=view,
            ephemeral=True
        )
    
    @ui.button(label="Изменить должность", style=discord.ButtonStyle.red, emoji="📋", row=1)
    async def edit_position(self, interaction: discord.Interaction, button: ui.Button):
        """Handle position editing"""
        # Send position selection view (same as before)
        view = PositionOnlySelectView(self.target_user)
        await interaction.response.send_message(
            f" **Управление должностью для {self.target_user.display_name}**\n"
            f"• Выберите должность из доступных в текущем подразделении\n"
            f"• Или разжалуйте с текущей должности",
            view=view,
            ephemeral=True
        )
    
    @ui.button(label="Изменить личные данные", style=discord.ButtonStyle.secondary, emoji="👤", row=0)
    async def edit_personal_data(self, interaction: discord.Interaction, button: ui.Button):
        """Handle personal data editing"""
        try:
            # Import the modal
            from .modals import PersonalDataModal
            
            # Create and show the modal
            modal = PersonalDataModal(self.target_user)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error("Error in personal data editing: %s", e)
            await interaction.response.send_message(f" **Ошибка:** {str(e)}", ephemeral=True)
    
    @ui.button(label="Изменить Discord", style=discord.ButtonStyle.secondary, emoji="🆔", row=0)
    async def edit_discord_id(self, interaction: discord.Interaction, button: ui.Button):
        """Обработка редактирования Discord ID"""
        try:
            config = load_config()
            if not is_administrator(interaction.user, config):
                await interaction.response.send_message(
                    "❌ Эту кнопку могут использовать только администраторы.",
                    ephemeral=True
                )
                return

            from .modals import ChangeDiscordIDModal
            
            modal = ChangeDiscordIDModal(self.target_user)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error("Ошибка при редактировании Discord ID: %s", e)
            await interaction.response.send_message(f"❌ **Ошибка:** {str(e)}", ephemeral=True)


@app_commands.context_menu(name='Быстро повысить (+1 ранг)')
@handle_context_errors
async def quick_promote(interaction: discord.Interaction, user: discord.Member):
    """Context menu command to quickly promote user by +1 rank"""
    # Prevent double-clicks and invalid interactions
    if interaction.response.is_done():
        logger.info(f"Quick promote command ignored for {user.display_name} - interaction already responded")
        return
        
    # Check permissions
    config = load_config()
    if not is_moderator_or_admin(interaction.user, config):
        await interaction.response.send_message("❌ У вас нет прав для повышения в ранге.", ephemeral=True)
        return
    
    # Check if moderator can moderate this user (hierarchy check)
    if not can_moderate_user(interaction.user, user, config):
        await interaction.response.send_message(
            " Вы не можете выполнять действия над этим пользователем. Недостаточно прав в иерархии.",
            ephemeral=True
        )
        return
    
    # Check if target is bot
    if user.bot:
        await interaction.response.send_message("❌ Нельзя повысить бота.", ephemeral=True)
        return
    
    # Check user status
    user_status = await get_user_status(user.id)
    
    # Check if user is active
    if not user_status['is_active']:
        await interaction.response.send_message(
            f"⚠️ **{user.display_name} не состоит в вашей фракции**",
            ephemeral=True
        )
        return
    
    try:
        from forms.personnel_context.rank_utils import RankHierarchy
        
        # Get current rank from database instead of Discord roles
        current_rank = await get_user_rank_from_db(user.id)
        if not current_rank:
            await interaction.response.send_message(
                f"❌ **{user.display_name}** не имеет ранга или ранг не определён.",
                ephemeral=True
            )
            return
        
        # Get next rank
        from utils.database_manager import rank_manager
        next_rank = await rank_manager.get_next_rank(current_rank)
        if not next_rank:
            await interaction.response.send_message(
                f"❌ **{user.display_name}** уже имеет максимальный ранг: **{current_rank}**",
                ephemeral=True
            )
            return
        
        # Defer response for processing
        await interaction.response.defer(ephemeral=True)
        
        # Execute direct promotion (action_id = 1) without asking type
        rank_view = RankChangeView(user, next_rank, is_promotion=False)  # Don't show buttons
        success = await rank_view._execute_rank_change(interaction, action_id=1, action_name="Повышение")
        
    except Exception as e:
        logger.error("Error in quick promotion: %s", e)
        if not interaction.response.is_done():
            await interaction.response.send_message(f" **Ошибка:** {str(e)}", ephemeral=True)
        else:
            await interaction.followup.send(f" **Ошибка:** {str(e)}", ephemeral=True)


@app_commands.context_menu(name='Общее редактирование')
@handle_context_errors
async def general_edit(interaction: discord.Interaction, user: discord.Member):
    """Context menu command for general editing (rank, department, position)"""
    # Prevent double-clicks and invalid interactions
    if interaction.response.is_done():
        logger.info(f"General edit command ignored for {user.display_name} - interaction already responded")
        return
        
    # Check permissions
    config = load_config()
    if not is_moderator_or_admin(interaction.user, config):
        await interaction.response.send_message("❌ У вас нет прав для редактирования данных.", ephemeral=True)
        return
    
    # Check if moderator can moderate this user (hierarchy check)
    if not can_moderate_user(interaction.user, user, config):
        await interaction.response.send_message(
            " Вы не можете выполнять действия над этим пользователем. Недостаточно прав в иерархии.",
            ephemeral=True
        )
        return
    
    # Check if target is bot
    if user.bot:
        await interaction.response.send_message("❌ Нельзя редактировать данные бота.", ephemeral=True)
        return
    
    # Get comprehensive user status
    user_status = await get_user_status(user.id)
    
    # Handle dismissed users - show information instead of edit buttons
    if user_status['is_dismissed'] and not user_status['is_active']:
        # User is dismissed, show dismissal information
        full_name = user_status['full_name'] or user.display_name
        static = user_status['static'] or 'Не указан'

        dismissal_reason = "Не указана"
        dismissal_date = None
        try:
            from utils.postgresql_pool import get_db_cursor
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as cnt
                    FROM information_schema.columns
                    WHERE table_name = 'personnel' AND column_name = 'dismissal_reason'
                """)
                has_reason_col = cursor.fetchone().get('cnt', 0) > 0

                select_query = """
                    SELECT dismissal_date%s
                    FROM personnel
                    WHERE discord_id = %%s
                    LIMIT 1;
                """ % (", dismissal_reason" if has_reason_col else "")

                cursor.execute(select_query, (user.id,))
                personnel_row = cursor.fetchone()

                if personnel_row:
                    dismissal_date = personnel_row.get('dismissal_date')
                    if has_reason_col and personnel_row.get('dismissal_reason'):
                        dismissal_reason = personnel_row['dismissal_reason']

                # Fallback to history for reason if column absent or empty
                if dismissal_reason == "Не указана":
                    cursor.execute("""
                        SELECT details
                        FROM history h
                        JOIN personnel p ON h.personnel_id = p.id
                        WHERE p.discord_id = %s AND h.action_id = 3
                        ORDER BY h.action_date DESC
                        LIMIT 1;
                    """, (user.id,))
                    history_result = cursor.fetchone()
                    if history_result and history_result['details']:
                        dismissal_reason = history_result['details']
        except Exception as e:
            logger.warning(f"Warning: Could not get dismissal reason/date for {user.id}: %s", e)

        # Check blacklist
        blacklist_text = ""
        if user_status['blacklist_info']:
            start_date_str = user_status['blacklist_info']['start_date'].strftime('%d.%m.%Y')
            end_date_str = user_status['blacklist_info']['end_date'].strftime('%d.%m.%Y') if user_status['blacklist_info']['end_date'] else 'Бессрочно'
            blacklist_text = f"\n\n⚠️ **Чёрный список:** {user_status['blacklist_info']['reason']} ({start_date_str} - {end_date_str})"

        dismissal_date_text = ""
        if 'dismissal_date' in locals() and dismissal_date:
            dismissal_date_text = f"`{dismissal_date.strftime('%d.%m.%Y')}`"
        else:
            dismissal_date_text = "`Не указана`"

        await interaction.response.send_message(
            f" **Информация о пользователе {user.mention}**\n\n"
            f"📊 **Данные:**\n"
            f"> • **Имя, Фамилия:** `{full_name}`\n"
            f"> • **Статик:** `{static}`\n"
            f"> • **Статус:** `Уволен со службы`\n"
            f"> • **Дата увольнения:** {dismissal_date_text}\n"
            f"> • **Причина увольнения:** `{dismissal_reason}`{blacklist_text}\n\n"
            f" **Для восстановления на службу используйте:**\n"
            f"• **Принять во фракцию** - для повторного приёма\n"
            f"• **Изменить ранг** - для восстановления звания",
            ephemeral=True
        )
        return
    
    # Handle users not in service (never served)
    if not user_status['is_active'] and not user_status['is_dismissed']:
        # User never served, show recruitment suggestion
        full_name = user_status['full_name'] or user.display_name
        static = user_status['static'] or 'Не указан'
        
        # Check blacklist
        blacklist_text = ""
        if user_status['blacklist_info']:
            start_date_str = user_status['blacklist_info']['start_date'].strftime('%d.%m.%Y')
            end_date_str = user_status['blacklist_info']['end_date'].strftime('%d.%m.%Y') if user_status['blacklist_info']['end_date'] else 'Бессрочно'
            blacklist_text = f"\n\n **Чёрный список:** {user_status['blacklist_info']['reason']} ({start_date_str} - {end_date_str})"
        
        await interaction.response.send_message(
            f" **Информация о пользователе {user.mention}**\n\n"
            f" **Данные:**\n"
            f"> • **Имя, Фамилия:** `{full_name}`\n"
            f"> • **Статик:** `{static}`\n"
            f"> • **Статус:** `Не состоит в фракции`{blacklist_text}\n\n"
            f" **Для приёма на службу используйте:**\n"
            f"• **Принять во фракцию** - для первичного приёма",
            ephemeral=True
        )
        return
    
    # User is active - show edit options with blacklist warning if needed
    blacklist_warning = ""
    if user_status['blacklist_info']:
        start_date_str = user_status['blacklist_info']['start_date'].strftime('%d.%m.%Y')
        end_date_str = user_status['blacklist_info']['end_date'].strftime('%d.%m.%Y') if user_status['blacklist_info']['end_date'] else 'Бессрочно'
        blacklist_warning = f"\n\n⚠️ **ВНИМАНИЕ: Пользователь в Чёрном списке!**\n> **Причина:** {user_status['blacklist_info']['reason']}\n> **Период:** {start_date_str} - {end_date_str}"
    
    # Get current user information from cache and database
    try:
        # Get data from cache first (async version that can load from DB)
        from utils.user_cache import get_cached_user_info
        user_data = await get_cached_user_info(user.id)
        
        # Get rank from database
        current_rank = user_status['rank'] or "Не указано"
        
        # Get department and position from database
        department_name = user_status['department'] or "Не указано"
        position_name = user_status['position'] or "Не назначено"
        full_name = user_status['full_name'] or user.display_name
        
        # Format user information - get static from user_data or fallback to DB query
        static = user_data.get('static', user_status['static']) if user_data else user_status['static']
        if not static:
            static = 'Не указано'
        
        # Format join date
        join_date_str = "Не указано"
        if user_status['join_date']:
            join_date_str = user_status['join_date'].strftime('%d.%m.%Y')
        
        # Send general editing view with current information
        view = GeneralEditView(user)
        await interaction.response.send_message(
            f"⚙️ **Общее редактирование для {user.mention}**\n\n"
            f"📊 **Текущая информация:**\n"
            f"> • **Имя, Фамилия:** `{full_name}`\n"
            f"> • **Статик:** `{static}`\n"
            f"> • **Звание:** `{current_rank}`\n"
            f"> • **Подразделение:** `{department_name}`\n"
            f"> • **Должность:** `{position_name}`\n"
            f"> • **Дата приёма:** `{join_date_str}`{blacklist_warning}\n\n"
            f"Выберите что хотите изменить:",
            view=view,
            ephemeral=True
        )
        
    except Exception as e:
        logger.error("Error in general editing: %s", e)
        await interaction.response.send_message(f"❌ **Ошибка:** {str(e)}", ephemeral=True)


def setup_context_commands(bot):
    """Setup context menu commands for PersonnelManager integration"""
    # Check if commands are already added to avoid duplicates
    existing_commands = [cmd.name for cmd in bot.tree.get_commands()]
    
    commands_to_add = [
        ('Принять во фракцию', recruit_user),
        ('Уволить', dismiss_user),
        ('Быстро повысить (+1 ранг)', quick_promote),
        ('Общее редактирование', general_edit)
    ]
    
    added_count = 0
    for name, command in commands_to_add:
        if name not in existing_commands:
            bot.tree.add_command(command)
            added_count += 1
            logger.info("Personnel context menu command '%s' loaded", name)
        else:
            logger.info("Personnel context menu command '%s' already loaded", name)
    
    if added_count > 0:
        logger.info("%s new personnel context menu command(s) registered", added_count)
    else:
        logger.info("All personnel context menu commands already loaded")


class RecruitmentStaticConflictView(ui.View):
    """View for confirming static conflict resolution in recruitment"""
    
    def __init__(self, target_user, old_discord_id, new_name, new_static, moderator):
        super().__init__(timeout=300)
        self.target_user = target_user
        self.old_discord_id = old_discord_id
        self.new_name = new_name
        self.new_static = new_static
        self.moderator = moderator
    
    @ui.button(label="Подтвердить", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_replacement(self, interaction: discord.Interaction, button: ui.Button):
        """Confirm replacement and proceed with recruitment"""
        try:
            # Defer the response
            await interaction.response.defer(ephemeral=True)

            # Delete the warning message immediately
            try:
                await interaction.delete_original_response()
            except Exception:
                pass
            
            # Replace old discord_id with new one in personnel table
            from datetime import datetime, timezone
            
            with get_db_cursor() as cursor:
                # Check if dismissal_reason column exists
                cursor.execute("""
                    SELECT COUNT(*) as cnt
                    FROM information_schema.columns
                    WHERE table_name = 'personnel' AND column_name = 'dismissal_reason'
                """)
                has_reason_col = cursor.fetchone().get('cnt', 0) > 0

                # Update the personnel record: change discord_id and reset dismissal status
                cursor.execute("""
                    UPDATE personnel
                    SET discord_id = %s,
                        is_dismissal = false,
                        dismissal_date = NULL,
                        last_updated = %s
                    WHERE discord_id = %s;
                """, (self.target_user.id, datetime.now(timezone.utc), self.old_discord_id))

                if has_reason_col:
                    cursor.execute("""
                        UPDATE personnel
                        SET dismissal_reason = NULL
                        WHERE discord_id = %s;
                    """, (self.target_user.id,))
                
                logger.info(
                    "RECRUITMENT STATIC CONFLICT: Replaced discord_id %s with %s for static %s",
                    self.old_discord_id,
                    self.target_user.id,
                    self.new_static
                )
            
            # Now proceed with recruitment process
            # Parse name parts
            name_parts = self.new_name.split()
            first_name = name_parts[0] if name_parts else "Неизвестно"
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Неизвестно"
            
            # Prepare application data for PersonnelManager
            application_data = {
                'user_id': self.target_user.id,
                'username': self.target_user.display_name,
                'name': self.new_name,
                'static': self.new_static,
                'type': 'military',
                'rank': "Рядовой",
                'subdivision': None,
                'position': None
            }
            
            # Use PersonnelManager for recruitment
            from utils.database_manager import PersonnelManager
            pm = PersonnelManager()
            
            success, message = await pm.process_role_application_approval(
                application_data,
                self.target_user.id,
                interaction.user.id,
                interaction.user.display_name
            )
            
            if success:
                logger.info("RECRUITMENT: PersonnelManager processed successfully: %s", message)
                
                # Send audit notification
                try:
                    from utils.audit_logger import audit_logger, AuditAction
                    config = load_config()
                    
                    # Для аудита определяем подразделение по дефолту, т.к. выбор не выполнялся
                    dept_name = None
                    try:
                        cfg = load_config().get('recruitment', {}) or {}
                        default_key = cfg.get('default_subdivision_key')
                        if default_key:
                            with get_db_cursor() as cursor:
                                cursor.execute("SELECT name FROM subdivisions WHERE abbreviation = %s", (default_key,))
                                r = cursor.fetchone()
                                if r:
                                    dept_name = r['name']
                    except Exception as ce:
                        logger.error("Recruitment static conflict audit department resolve failed: %s", ce)

                    personnel_data = {
                        'name': self.new_name,
                        'static': self.new_static,
                        'rank': "Рядовой",
                        'department': dept_name or 'Не назначено'
                    }
                    
                    await audit_logger.send_personnel_audit(
                        guild=interaction.guild,
                        action=await AuditAction.HIRING(),
                        target_user=self.target_user,
                        moderator=interaction.user,
                        personnel_data=personnel_data,
                        config=config
                    )
                    logger.info("RECRUITMENT: Audit notification sent")
                except Exception as audit_error:
                    logger.error("RECRUITMENT: Failed to send audit notification: %s", audit_error)
                
                # Assign roles and nickname
                try:
                    # Use RoleUtils to assign default recruit rank and military roles
                    recruit_assigned = await role_utils.assign_default_recruit_rank(self.target_user, self.moderator)
                    if recruit_assigned:
                        military_assigned = await role_utils.assign_military_roles(self.target_user, self.moderator)
                        
                        # Set military nickname
                        new_nickname = await nickname_manager.handle_hiring(
                            member=self.target_user,
                            rank_name="Рядовой",
                            first_name=first_name,
                            last_name=last_name,
                            static=self.new_static
                        )
                        if new_nickname:
                            logger.info("RECRUITMENT: Set nickname: %s", new_nickname)
                    
                    logger.info("RECRUITMENT: Role assignment process completed")
                except Exception as role_error:
                    logger.error("RECRUITMENT: Failed to assign roles: %s", role_error)
                
                # Send success message
                await interaction.followup.send(
                    f"✅ **Пользователь {self.target_user.mention} принят на службу!**\n\n"
                    f"**Имя:** {first_name}\n"
                    f"**Фамилия:** {last_name}\n"
                    f"**Статик:** {self.new_static}\n"
                    f"**Звание:** Рядовой",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Произошла ошибка при обработке принятия на службу.",
                    ephemeral=True
                )
            
            # Delete the warning message
        except Exception as e:
            logger.error("Error confirming recruitment static conflict: %s", e)
            await interaction.followup.send(
                "❌ Произошла ошибка при подтверждении замены.",
                ephemeral=True
            )
    
    @ui.button(label="Отклонить", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel_recruitment(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel recruitment"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Delete the warning message immediately
            try:
                await interaction.delete_original_response()
            except Exception:
                pass

            await interaction.followup.send(
                "❌ **Приём на службу отменён**\n\n"
                f"Пользователь {self.target_user.mention} не принят на службу из-за конфликта статика.\n"
                f"Причина: попытка использовать чужой статик.",
                ephemeral=True
            )
            
            logger.info(
                "RECRUITMENT STATIC CONFLICT: Recruitment cancelled for user %s (conflict with %s)",
                self.target_user.id,
                self.old_discord_id
            )
            
        except Exception as e:
            logger.error("Error cancelling recruitment: %s", e)
            await interaction.response.send_message(
                "❌ Произошла ошибка при отмене приёма.",
                ephemeral=True
            )