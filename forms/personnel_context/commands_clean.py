"""
Personnel Context Menu Commands with PersonnelManager integration
"""

import discord
from discord import app_commands
from discord.ext import commands
import functools
import traceback

from utils.config_manager import load_config, is_moderator_or_admin, is_administrator, can_moderate_user
from utils.database_manager import PersonnelManager
from utils.database_manager.position_manager import position_manager
from utils.nickname_manager import nickname_manager
from discord import ui
import re


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
        print(f"Error getting rank from database: {e}")
        return None


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


class RecruitmentModal(ui.Modal, title="Принятие на службу"):
    """Modal for recruiting new personnel using PersonnelManager"""
    
    def __init__(self, target_user: discord.Member):
        super().__init__()
        self.target_user = target_user
        
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Например: Олег Дубов",
            min_length=2,
            max_length=50,
            required=True
        )
        self.add_item(self.name_input)
        
        self.static_input = ui.TextInput(
            label="Статик",
            placeholder="123-456 (допускается 5-6 цифр)",
            min_length=5,
            max_length=7,
            required=True
        )
        self.add_item(self.static_input)
        
        # Rank is always "Рядовой" for new recruits, no need for input field
        
        self.recruitment_type_input = ui.TextInput(
            label="Порядок набора",
            placeholder="Экскурсия или Призыв",
            min_length=1,
            max_length=20,
            required=True
        )
        self.add_item(self.recruitment_type_input)
    
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
            
            # Validate and format static
            static = self.static_input.value.strip()
            formatted_static = self._format_static(static)
            if not formatted_static:
                await interaction.response.send_message(
                    "❌ Неверный формат статика. Статик должен содержать 5 или 6 цифр.\n"
                    "Примеры: 123456, 123-456, 12345, 12-345, 123 456",
                    ephemeral=True
                )
                return
            
            # Validate recruitment type
            recruitment_type = self.recruitment_type_input.value.strip().lower()
            if recruitment_type not in ["экскурсия", "призыв"]:
                await interaction.response.send_message(
                    "❌ Порядок набора должен быть: 'Экскурсия' или 'Призыв'.",
                    ephemeral=True
                )
                return
            
            # All validation passed, defer for processing
            await interaction.response.defer(ephemeral=True)
            
            # Process recruitment using PersonnelManager
            success = await self._process_recruitment_with_personnel_manager(
                interaction,
                self.name_input.value.strip(),
                formatted_static,
                "Рядовой",  # Always set rank as "Рядовой" for new recruits
                recruitment_type
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
                        f"**ФИО:** {self.name_input.value.strip()}\n"
                        f"**Статик:** {formatted_static}\n"
                        f"**Звание:** Рядовой\n"
                        f"**Порядок набора:** {recruitment_type}"
                    ),
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ Произошла ошибка при обработке принятия на службу.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ RECRUITMENT ERROR: {e}")
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
                        "❌ Произошла ошибка при обработке запроса.",
                        ephemeral=True
                    )
            except:
                print(f"Failed to send error response: {e}")
    
    def _format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return ""
    
    async def _process_recruitment_with_personnel_manager(self, interaction: discord.Interaction, full_name: str, static: str, rank: str, recruitment_type: str) -> bool:
        """Process recruitment using PersonnelManager"""
        try:
            print(f"🔄 RECRUITMENT: Starting recruitment via PersonnelManager for {self.target_user.id}")
            print(f"🔄 RECRUITMENT: Data - Name: '{full_name}', Static: '{static}', Rank: '{rank}', Type: '{recruitment_type}'")
            
            # Prepare application data for PersonnelManager
            application_data = {
                'user_id': self.target_user.id,
                'username': self.target_user.display_name,
                'name': full_name,
                'static': static,
                'type': 'military',
                'recruitment_type': recruitment_type.lower(),
                'rank': rank,
                'subdivision': 'Военная Академия',
                'position': None,
                'reason': f"Набор: {recruitment_type}"
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
                print(f"✅ RECRUITMENT: PersonnelManager processed successfully: {message}")
                
                # Send audit notification using centralized logger
                try:
                    from utils.audit_logger import audit_logger, AuditAction
                    config = load_config()
                    
                    personnel_data = {
                        'name': full_name,
                        'static': static,
                        'rank': rank,
                        'department': 'Военная Академия',
                        'reason': recruitment_type.capitalize()
                    }
                    
                    await audit_logger.send_personnel_audit(
                        guild=interaction.guild,
                        action=await AuditAction.HIRING(),
                        target_user=self.target_user,
                        moderator=interaction.user,
                        personnel_data=personnel_data,
                        config=config
                    )
                    print(f"✅ RECRUITMENT: Audit notification sent")
                except Exception as audit_error:
                    print(f"⚠️ RECRUITMENT: Failed to send audit notification: {audit_error}")
                
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
                    dm_embed.add_field(name="Подразделение", value="Военная Академия", inline=False)
                    
                    await self.target_user.send(embed=dm_embed)
                    print(f"✅ RECRUITMENT: DM sent to {self.target_user.display_name}")
                except discord.Forbidden:
                    print(f"⚠️ RECRUITMENT: Could not send DM to {self.target_user.display_name} (DMs disabled)")
                except Exception as dm_error:
                    print(f"⚠️ RECRUITMENT: Failed to send DM: {dm_error}")
                
                # Step: Assign Discord roles and set nickname (like button approval does)
                try:
                    config = load_config()
                    await self._assign_military_roles(interaction.guild, config)
                    print(f"✅ RECRUITMENT: Role assignment process completed")
                except Exception as role_error:
                    print(f"⚠️ RECRUITMENT: Failed to assign roles: {role_error}")
                    # Continue even if role assignment fails
            else:
                print(f"❌ RECRUITMENT: PersonnelManager failed: {message}")
            
            return success
            
        except Exception as e:
            print(f"❌ RECRUITMENT: Error processing recruitment: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _assign_military_roles(self, guild, config):
        """Assign military roles and set nickname (same as button approval)"""
        try:
            # Get military roles from config
            role_ids = config.get('military_roles', [])
            
            # Assign roles
            for role_id in role_ids:
                role = guild.get_role(role_id)
                if role and role not in self.target_user.roles:
                    try:
                        await self.target_user.add_roles(role, reason="Принят на службу через ПКМ")
                    except discord.Forbidden:
                        print(f"⚠️ RECRUITMENT: No permission to assign role {role.name}")
                    except Exception as e:
                        print(f"❌ RECRUITMENT: Error assigning role {role.name}: {e}")
            
            # Set military nickname
            await self._set_military_nickname()
            
        except Exception as e:
            print(f"❌ RECRUITMENT: Error in _assign_military_roles: {e}")
            raise
    
    async def _set_military_nickname(self):
        """Set nickname for military recruit using nickname_manager"""
        try:
            full_name = self.name_input.value.strip()
            static = self.static_input.value.strip()
            
            # Extract first and last name
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else "Неизвестно"
            last_name = name_parts[-1] if len(name_parts) > 1 else "Неизвестно"
            
            # Use nickname_manager for consistent formatting
            new_nickname = await nickname_manager.handle_hiring(
                member=self.target_user,
                rank_name="Рядовой",  # Default rank for new recruits
                first_name=first_name,
                last_name=last_name,
                static=static
            )
            
            if new_nickname:
                print(f"✅ RECRUITMENT: Set nickname using nickname_manager: {self.target_user.display_name} -> {new_nickname}")
            else:
                # Fallback to old logic if nickname_manager fails
                full_nickname = f"ВА | {full_name}"
                if len(full_nickname) <= 32:
                    new_nickname = full_nickname
                else:
                    first_initial = first_name[0] if first_name else "И"
                    new_nickname = f"ВА | {first_initial}. {last_name}"
                
                await self.target_user.edit(nick=new_nickname, reason="Принят на службу через ПКМ (fallback)")
                print(f"✅ RECRUITMENT: Fallback nickname set: {new_nickname}")
            
        except discord.Forbidden:
            print(f"⚠️ RECRUITMENT: No permission to change nickname for {self.target_user.display_name} to \"{new_nickname}\"")
        except Exception as e:
            print(f"❌ RECRUITMENT: Error setting nickname: {e}")


@app_commands.context_menu(name='Принять на службу')
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
    
    # Check if user has active blacklist entry
    from utils.audit_logger import audit_logger
    
    blacklist_info = await audit_logger.check_active_blacklist(user.id)
    
    if blacklist_info:
        # User is blacklisted, deny recruitment
        start_date_str = blacklist_info['start_date'].strftime('%d.%m.%Y')
        end_date_str = blacklist_info['end_date'].strftime('%d.%m.%Y') if blacklist_info['end_date'] else 'Бессрочно'
        
        await interaction.response.send_message(
            f"❌ **Этому пользователю запрещен приём на службу**\n\n"
            f"📋 **{blacklist_info['full_name']} | {blacklist_info['static']} находится в Чёрном списке ВС РФ**\n"
            f"> **Причина:** {blacklist_info['reason']}\n"
            f"> **Период:** {start_date_str} - {end_date_str}\n\n"
            f"*Для снятия с чёрного списка обратитесь к руководству бригады.*",
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
    
    # No blacklist, proceed with recruitment
    modal = RecruitmentModal(user)
    await interaction.response.send_modal(modal)
    print(f"✅ Recruitment modal sent for {user.display_name}")


class DismissalModal(ui.Modal, title="Увольнение"):
    """Modal for dismissing personnel using PersonnelManager"""
    
    def __init__(self, target_user: discord.Member):
        super().__init__()
        self.target_user = target_user
        
        self.reason_input = ui.TextInput(
            label="Причина увольнения",
            placeholder="ПСЖ, Нарушение устава, и т.д.",
            min_length=2,
            max_length=100,
            required=True
        )
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process dismissal submission using PersonnelManager"""
        try:
            # Check permissions first
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этой команды.",
                    ephemeral=True
                )
                return
            
            # All validation passed, defer for processing
            await interaction.response.defer(ephemeral=True)
            
            # Process dismissal using PersonnelManager
            success = await self._process_dismissal_with_personnel_manager(
                interaction,
                self.reason_input.value.strip()
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
            print(f"❌ DISMISSAL ERROR: {e}")
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
                        "❌ Произошла ошибка при обработке запроса.",
                        ephemeral=True
                    )
            except:
                print(f"Failed to send error response: {e}")
    
    async def _process_dismissal_with_personnel_manager(self, interaction: discord.Interaction, reason: str) -> bool:
        """Process dismissal directly (same as dismissal reports)"""
        try:
            print(f"🔄 DISMISSAL: Starting dismissal for {self.target_user.id}")
            print(f"🔄 DISMISSAL: Reason: '{reason}'")
            
            # Get personnel data first
            pm = PersonnelManager()
            personnel_data_summary = await pm.get_personnel_summary(self.target_user.id)
            
            if not personnel_data_summary:
                print(f"❌ DISMISSAL: User not found in personnel database")
                await interaction.followup.send(
                    "❌ Пользователь не найден в базе данных персонала.",
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
                        print(f"❌ DISMISSAL: User not found or already dismissed")
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
                        print(f"✅ DISMISSAL: Removed employee record {employee_id}")
                    
                    # Step 2: Mark personnel as dismissed
                    cursor.execute("""
                        UPDATE personnel 
                        SET is_dismissal = true, 
                            dismissal_date = %s, 
                            last_updated = %s
                        WHERE id = %s
                    """, (current_time.date(), current_time, personnel_id))
                    print(f"✅ DISMISSAL: Marked personnel {personnel_id} as dismissed")
                    
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
                    print(f"✅ DISMISSAL: Added history entry for dismissal")
                
                success = True
                message = f"Пользователь успешно уволен из базы данных"
                print(f"✅ DISMISSAL: {message}")
                
            except Exception as db_error:
                print(f"❌ DISMISSAL: Database error: {db_error}")
                import traceback
                traceback.print_exc()
                success = False
                message = f"Ошибка базы данных: {str(db_error)}"
            
            if success:
                print(f"✅ DISMISSAL: PersonnelManager processed successfully: {message}")
                
                # Send audit notification using centralized logger
                audit_message_url = None
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
                    print(f"✅ DISMISSAL: Audit notification sent")
                    
                    # Get personnel_id for auto-blacklist check
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
                                    print(f"✅ DISMISSAL: Auto-blacklist triggered for {audit_personnel_data.get('name')}")
                            else:
                                print(f"⚠️ DISMISSAL: Personnel not found in DB for auto-blacklist check: {self.target_user.id}")
                                
                    except Exception as blacklist_error:
                        print(f"⚠️ DISMISSAL: Error in auto-blacklist check: {blacklist_error}")
                        # Don't fail the whole dismissal if blacklist check fails
                        
                except Exception as audit_error:
                    print(f"⚠️ DISMISSAL: Failed to send audit notification: {audit_error}")
                
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
                    print(f"✅ DISMISSAL: DM sent to {self.target_user.display_name}")
                except discord.Forbidden:
                    print(f"⚠️ DISMISSAL: Could not send DM to {self.target_user.display_name} (DMs disabled)")
                except Exception as dm_error:
                    print(f"⚠️ DISMISSAL: Failed to send DM: {dm_error}")
                
                # Step: Remove Discord roles and reset nickname (like button dismissal does)
                try:
                    config = load_config()
                    await self._remove_military_roles_and_reset_nickname(interaction.guild, config)
                    print(f"✅ DISMISSAL: Role removal process completed")
                except Exception as role_error:
                    print(f"⚠️ DISMISSAL: Failed to remove roles: {role_error}")
                    # Continue even if role removal fails
            else:
                print(f"❌ DISMISSAL: PersonnelManager failed: {message}")
            
            return success
            
        except Exception as e:
            print(f"❌ DISMISSAL: Error processing dismissal: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _remove_military_roles_and_reset_nickname(self, guild, config):
        """Remove all roles except excluded ones, then set dismissal nickname using nickname_manager"""
        try:
            # Step 1: Remove ALL roles except excluded ones
            excluded_role_ids = set(config.get('excluded_roles', []))
            roles_to_remove = []
            
            for role in self.target_user.roles:
                # Skip @everyone and excluded roles
                if role.is_default() or role.id in excluded_role_ids:
                    continue
                roles_to_remove.append(role)
            
            # Remove all roles at once for better performance
            if roles_to_remove:
                try:
                    await self.target_user.remove_roles(*roles_to_remove, reason="Уволен со службы через ПКМ")
                    print(f"✅ DISMISSAL: Removed {len(roles_to_remove)} roles from {self.target_user.display_name}")
                except discord.Forbidden:
                    print(f"⚠️ DISMISSAL: No permission to remove roles")
                except Exception as e:
                    print(f"❌ DISMISSAL: Error removing roles: {e}")
            else:
                print(f"ℹ️ DISMISSAL: No roles to remove for {self.target_user.display_name}")
            
            # Step 2: Set dismissal nickname using nickname_manager
            try:
                dismissal_nickname = await nickname_manager.handle_dismissal(
                    member=self.target_user,
                    reason=self.reason_input.value if hasattr(self, 'reason_input') else "Увольнение через ПКМ"
                )
                if dismissal_nickname:
                    print(f"✅ DISMISSAL: Set dismissal nickname: {self.target_user.display_name} -> {dismissal_nickname}")
                else:
                    print(f"⚠️ DISMISSAL: Failed to set dismissal nickname, keeping current")
            except Exception as nickname_error:
                print(f"❌ DISMISSAL: Error setting dismissal nickname: {nickname_error}")
                # Continue even if nickname change fails
            
        except Exception as e:
            print(f"❌ DISMISSAL: Error in _remove_military_roles_and_reset_nickname: {e}")
            raise

@app_commands.context_menu(name='Уволить')
@handle_context_errors
async def dismiss_user(interaction: discord.Interaction, user: discord.User):
    """Context menu command to dismiss user using PersonnelManager"""
    # Check permissions
    config = load_config()
    if not is_moderator_or_admin(interaction.user, config):
        await interaction.response.send_message(
            "❌ У вас нет прав для выполнения этой команды. Требуются права модератора или администратора.",
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
            "❌ Вы не можете выполнять действия над этим пользователем. Недостаточно прав в иерархии.",
            ephemeral=True
        )
        return
    
    # Open dismissal modal
    modal = DismissalModal(target_user)
    await interaction.response.send_modal(modal)
    print(f"✅ Dismissal modal sent for {target_user.display_name}")


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
            f"🏢 **Выберите подразделение для принятия {self.target_user.display_name}:**",
            view=view,
            ephemeral=True
        )
    
    @ui.button(label="Перевести из подразделения", style=discord.ButtonStyle.blurple, emoji="🔄")
    async def transfer_department(self, interaction: discord.Interaction, button: ui.Button):
        """Handle department transfer action"""
        view = DepartmentSelectView(self.target_user, action_type="transfer")
        await interaction.response.send_message(
            f"🔄 **Выберите подразделение для перевода {self.target_user.display_name}:**",
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
            emoji="📤"
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
            print(f"Error loading positions: {e}")
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
                print(f"Error getting position name: {e}")
                position_name = "Ошибка получения должности"
        
        # Execute department change with optional position
        await self._execute_department_change(interaction, position_name, selected_position_id)
    
    async def _assign_position_in_db(self, user_discord_id: int, position_id: str, position_name: str, moderator_discord_id: int) -> bool:
        """Assign position to user in database and create history record"""
        try:
            from utils.postgresql_pool import get_db_cursor
            from datetime import datetime, timezone, timedelta
            
            # Get old position ID and name for role updates and history
            old_position_id = None
            old_position_name = None
            user_member = None
            try:
                # Get user as member for role updates
                for guild in self.bot.guilds if hasattr(self, 'bot') else []:
                    user_member = guild.get_member(user_discord_id)
                    if user_member:
                        break
                
                if not user_member and hasattr(self, 'target_user'):
                    user_member = self.target_user
                
                # Get old position
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        SELECT ps.position_id, pos.name as position_name
                        FROM personnel p
                        JOIN employees e ON p.id = e.personnel_id
                        LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                        LEFT JOIN positions pos ON ps.position_id = pos.id
                        WHERE p.discord_id = %s AND p.is_dismissal = false
                    """, (user_discord_id,))
                    old_pos_result = cursor.fetchone()
                    if old_pos_result and old_pos_result['position_id']:
                        old_position_id = old_pos_result['position_id']
                        old_position_name = old_pos_result['position_name']
            except Exception as e:
                print(f"Warning: Could not get old position for role update: {e}")
            
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
                        new_position_id = int(position_id) if position_id.isdigit() else None
                        await position_manager.smart_update_user_position_roles(
                            user_member.guild,
                            user_member,
                            new_position_id
                        )
                    except Exception as e:
                        print(f"⚠️ Error updating position roles: {e}")
                
                return True
                
        except Exception as e:
            print(f"Error in _assign_position_in_db: {e}")
            return False
    
    async def _execute_department_change(self, interaction: discord.Interaction, position_name: str, position_id: str):
        """Execute the department change (same as approving department application)"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Import necessary modules
            from utils.database_manager import PersonnelManager, personnel_manager
            from utils.audit_logger import audit_logger, AuditAction
            from utils.config_manager import load_config
            from utils.ping_manager import ping_manager
            
            # Initialize managers
            pm = PersonnelManager()
            config = load_config()
            
            # Step 1: Process department change in database
            application_data = {
                'target_department': self.dept_name,
                'reason': None,  # details = NULL
                'application_type': self.action_type
            }
            
            moderator_info = f"{interaction.user.display_name} ({interaction.user.id})"
            
            if self.action_type == "transfer":
                success, db_message = await pm.process_department_transfer(
                    application_data=application_data,
                    user_discord_id=self.target_user.id,
                    moderator_discord_id=interaction.user.id,
                    moderator_info=moderator_info
                )
            else:
                success, db_message = await pm.process_department_join(
                    application_data=application_data,
                    user_discord_id=self.target_user.id,
                    moderator_discord_id=interaction.user.id,
                    moderator_info=moderator_info
                )
            
            if not success:
                await interaction.followup.send(f"❌ **Ошибка БД (подразделение):** {db_message}", ephemeral=True)
                return
            
            # Step 2: Process position assignment in database (only if position selected)
            position_had_no_position_before = False  # Track if user had no position before
            
            if position_name is not None and position_id != "no_position":
                position_success = await self._assign_position_in_db(
                    self.target_user.id, 
                    position_id, 
                    position_name, 
                    interaction.user.id
                )
                
                if not position_success:
                    await interaction.followup.send(f"❌ **Ошибка БД (должность):** Не удалось назначить должность", ephemeral=True)
                    return
            elif position_id == "no_position":
                # User selected "Без должности" - check if they had a position before and remove it
                try:
                    # Get current position before removal
                    current_position = await self._get_current_user_position(self.target_user.id)
                    
                    if current_position and current_position.strip():
                        # User had a position, remove it from database
                        position_removal_success = await self._remove_position_from_db(
                            self.target_user.id,
                            current_position,
                            interaction.user.id
                        )
                        
                        if not position_removal_success:
                            await interaction.followup.send(f"❌ **Ошибка БД (снятие должности):** Не удалось снять должность", ephemeral=True)
                            return
                        
                        # Set position_name to None to trigger demotion audit
                        position_name = None
                        print(f"✅ Position removed from database: {current_position} for user {self.target_user.id}")
                    else:
                        # User had no position to remove, skip position audit
                        position_name = "skip_audit"
                        position_had_no_position_before = True
                        print(f"ℹ️ User {self.target_user.id} had no position to remove - skipping position audit")
                        
                except Exception as e:
                    print(f"❌ Error checking/removing current position: {e}")
                    await interaction.followup.send(f"❌ **Ошибка:** Не удалось обработать снятие должности", ephemeral=True)
                    return
            else:
                # Handle "no position" case - check if user had a position before
                current_position = await self._get_current_user_position(self.target_user.id)
                if current_position:
                    # User had a position, so we're demoting them
                    position_success = await self._remove_position_from_db(
                        self.target_user.id,
                        current_position,
                        interaction.user.id
                    )
                    if not position_success:
                        await interaction.followup.send(f"❌ **Ошибка БД (разжалование):** Не удалось разжаловать с должности", ephemeral=True)
                        return
                    position_name = None  # Will trigger position demotion audit
                else:
                    # User had no position before, so no position audit needed
                    position_name = "skip_audit"  # Special marker to skip position audit
            
            # Step 3: Update Discord roles
            dept_role_id = ping_manager.get_department_role_id(self.dept_key)
            if dept_role_id:
                dept_role = interaction.guild.get_role(dept_role_id)
                if dept_role:
                    # Remove all department roles
                    all_dept_role_ids = ping_manager.get_all_department_role_ids()
                    for role_id in all_dept_role_ids:
                        role = interaction.guild.get_role(role_id)
                        if role and role in self.target_user.roles:
                            try:
                                await self.target_user.remove_roles(role, reason="Department change via context menu")
                            except:
                                pass
                    
                    # Add new department role
                    await self.target_user.add_roles(dept_role, reason=f"Department change by {interaction.user}")
            
            # Step 3.5: Update position roles after department change
            # Since department transfer clears all positions, we need to remove old position roles
            try:
                from utils.database_manager.position_manager import position_manager
                await position_manager.smart_update_user_position_roles(
                    self.target_user.guild,
                    self.target_user,
                    None  # No position after department transfer
                )
                print(f"✅ Position roles cleared after department transfer for {self.target_user.display_name}")
            except Exception as position_role_error:
                print(f"⚠️ Warning: Failed to clear position roles after department transfer: {position_role_error}")
            
            # Step 4: Update nickname using nickname_manager
            try:
                # Получаем полную информацию пользователя из БД (включая звание из employees)
                personnel_data_for_nick = await pm.get_personnel_summary(self.target_user.id)
                current_rank = personnel_data_for_nick.get('rank', 'Рядовой') if personnel_data_for_nick else 'Рядовой'
                
                # Используем nickname_manager для перевода (он сам получит аббревиатуру из БД)
                new_nickname = await nickname_manager.handle_transfer(
                    member=self.target_user,
                    subdivision_key=self.dept_key,  # Прямо используем ключ подразделения
                    rank_name=current_rank
                )
                
                if new_nickname:
                    print(f"✅ DEPT TRANSFER: Никнейм обновлён через nickname_manager: {self.target_user.display_name} -> {new_nickname}")
                else:
                    # Вычисляем предполагаемый никнейм для логирования ошибки
                    expected_nickname = nickname_manager.preview_nickname_change(
                        current_nickname=self.target_user.display_name,
                        operation='transfer',
                        subdivision_abbr=config.get('departments', {}).get(self.dept_key, {}).get('abbreviation', self.dept_key),
                        rank_abbr=current_rank,
                        first_name=personnel_data_for_nick.get('first_name', 'Неизвестно') if personnel_data_for_nick else 'Неизвестно',
                        last_name=personnel_data_for_nick.get('last_name', 'Неизвестно') if personnel_data_for_nick else 'Неизвестно'
                    )
                    print(f"❌ DEPT TRANSFER ERROR: Не удалось обновить никнейм через nickname_manager. Ожидаемый никнейм: {expected_nickname}")
                    
                    # Fallback к старому методу
                    dept_config = config.get('departments', {}).get(self.dept_key, {})
                    abbreviation = dept_config.get('abbreviation', '')
                    if abbreviation:
                        fallback_nick = f"{abbreviation} | {self.target_user.name}"
                        await self.target_user.edit(nick=fallback_nick[:32], reason="Department transfer fallback")
                        print(f"⚠️ DEPT TRANSFER FALLBACK: Использован fallback никнейм: {fallback_nick[:32]}")
                    
            except Exception as e:
                # Вычисляем предполагаемый никнейм для логирования ошибки
                try:
                    personnel_data_for_error = await pm.get_personnel_summary(self.target_user.id)
                    expected_nickname = nickname_manager.preview_nickname_change(
                        current_nickname=self.target_user.display_name,
                        operation='transfer',
                        subdivision_abbr=config.get('departments', {}).get(self.dept_key, {}).get('abbreviation', self.dept_key),
                        rank_abbr=personnel_data_for_error.get('rank', 'Рядовой') if personnel_data_for_error else 'Рядовой',
                        first_name=personnel_data_for_error.get('first_name', 'Неизвестно') if personnel_data_for_error else 'Неизвестно',
                        last_name=personnel_data_for_error.get('last_name', 'Неизвестно') if personnel_data_for_error else 'Неизвестно'
                    )
                    print(f"❌ DEPT TRANSFER EXCEPTION: Ошибка изменения никнейма: {e}. Ожидаемый никнейм: {expected_nickname}")
                except Exception as preview_error:
                    print(f"❌ DEPT TRANSFER EXCEPTION: Ошибка изменения никнейма на \"{expected_nickname}\": {e}. Ошибка предпросмотра: {preview_error}")
                
                # Fallback к старому методу даже при исключении
                try:
                    dept_config = config.get('departments', {}).get(self.dept_key, {})
                    abbreviation = dept_config.get('abbreviation', '')
                    if abbreviation:
                        fallback_nick = f"{abbreviation} | {self.target_user.name}"
                        await self.target_user.edit(nick=fallback_nick[:32], reason="Department transfer fallback after error")
                        print(f"⚠️ DEPT TRANSFER EXCEPTION FALLBACK: Использован fallback никнейм: {fallback_nick[:32]}")
                except Exception as fallback_error:
                    print(f"❌ DEPT TRANSFER COMPLETE FAILURE: Даже fallback не сработал: {fallback_error}")
            
            # Step 5: Send FIRST audit notification - Department Change
            personnel_data = await pm.get_personnel_data_for_audit(self.target_user.id)
            if not personnel_data:
                personnel_data = {
                    'name': self.target_user.display_name,
                    'static': 'Неизвестно',
                    'rank': 'Неизвестно',
                    'department': self.dept_name,
                    'position': 'Не назначено'  # Don't include position in first audit
                }
            else:
                personnel_data['department'] = self.dept_name
                personnel_data['position'] = 'Не назначено'  # Don't include position in first audit
            
            if self.action_type == "transfer":
                action1 = await AuditAction.DEPARTMENT_TRANSFER()
            else:
                action1 = await AuditAction.DEPARTMENT_JOIN()
            
            await audit_logger.send_personnel_audit(
                guild=interaction.guild,
                action=action1,
                target_user=self.target_user,
                moderator=interaction.user,
                personnel_data=personnel_data,
                config=config
            )
            
            # Step 6: Send SECOND audit notification - Position Assignment/Demotion (only if needed)
            if position_name != "skip_audit":
                if position_name is None:
                    # Position demotion
                    personnel_data['position'] = None
                    action2 = await AuditAction.POSITION_DEMOTION()
                else:
                    # Position assignment
                    personnel_data['position'] = position_name
                    action2 = await AuditAction.POSITION_ASSIGNMENT()
                
                await audit_logger.send_personnel_audit(
                    guild=interaction.guild,
                    action=action2,
                    target_user=self.target_user,
                    moderator=interaction.user,
                    personnel_data=personnel_data,
                    config=config
                )
                
                position_info = f", должность: **{position_name or 'разжалован с должности'}**"
                audit_count = "2 кадровых аудита: подразделение + должность"
            else:
                # No position audit needed (user had no position before)
                if position_had_no_position_before:
                    position_info = ", должность: **без должности (как и ранее)**"
                else:
                    position_info = ", должность: **без изменений**"
                audit_count = "1 кадровый аудит: подразделение"
            
            # Step 7: Success message
            action_text = "переведен в" if self.action_type == "transfer" else "принят в"
            
            await interaction.followup.send(
                f"✅ **{self.target_user.display_name}** успешно {action_text} **{self.dept_name}**{position_info}\n"
                f"📊 Отправлено {audit_count}",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error in department change: {e}")
            await interaction.followup.send(f"❌ **Ошибка:** {str(e)}", ephemeral=True)
    
    async def _get_current_user_position(self, user_discord_id: int) -> str:
        """Get user's current position name or None if no position"""
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
                """, (user_discord_id,))
                
                result = cursor.fetchone()
                return result['name'] if result else None
                
        except Exception as e:
            print(f"Error getting current position: {e}")
            return None
    
    async def _remove_position_from_db(self, user_discord_id: int, position_name: str, moderator_discord_id: int) -> bool:
        """Remove position from user in database and create history record"""
        try:
            from utils.postgresql_pool import get_db_cursor
            from datetime import datetime, timezone, timedelta
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
                print(f"Warning: Could not get old position for role update: {e}")
            
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
                        "new": None,  # Removed position
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
                
                # Update Discord roles after position removal
                if user_member:
                    try:
                        # Remove all position roles using smart update
                        await position_manager.smart_update_user_position_roles(
                            user_member.guild,
                            user_member,
                            None  # No new position
                        )
                        print(f"✅ Position role removed for {user_member.display_name}")
                    except Exception as role_error:
                        print(f"Warning: Failed to remove position role: {role_error}")
                
                return True
                
        except Exception as e:
            print(f"Error in _remove_position_from_db: {e}")
            return False





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
            print(f"Error loading positions for assignment: {e}")
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
            print(f"Error getting position name: {e}")
        
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
                
                pm = PersonnelManager()
                config = load_config()
                
                # Get personnel data for audit
                personnel_data = await pm.get_personnel_data_for_audit(self.target_user.id)
                if not personnel_data:
                    personnel_data = {
                        'name': self.target_user.display_name,
                        'static': 'Неизвестно',
                        'rank': 'Неизвестно',
                        'department': 'Неизвестно',
                        'position': None
                    }
                else:
                    personnel_data['position'] = None
                
                await audit_logger.send_personnel_audit(
                    guild=interaction.guild,
                    action=await AuditAction.POSITION_DEMOTION(),
                    target_user=self.target_user,
                    moderator=interaction.user,
                    personnel_data=personnel_data,
                    config=config
                )
                
            except Exception as audit_error:
                print(f"Warning: Failed to send audit notification: {audit_error}")
            
            # Success message
            await interaction.followup.send(
                f"✅ **{self.target_user.display_name}** разжалован с должности **{current_position}**\n"
                f"📊 Отправлен кадровый аудит",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error in position removal: {e}")
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
            print(f"Error getting current position: {e}")
            return None
    
    async def _remove_position_from_db_standalone(self, user_discord_id: int, position_name: str, moderator_discord_id: int) -> bool:
        """Remove position from user in database (standalone version)"""
        try:
            from utils.postgresql_pool import get_db_cursor
            from datetime import datetime, timezone, timedelta
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
                print(f"Warning: Could not get old position for role update: {e}")
            
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
                
                # Update Discord roles after position removal
                if user_member:
                    try:
                        # Remove all position roles using smart update
                        await position_manager.smart_update_user_position_roles(
                            user_member.guild,
                            user_member,
                            None  # No new position
                        )
                        print(f"✅ Position role removed for {user_member.display_name}")
                    except Exception as role_error:
                        print(f"Warning: Failed to remove position role: {role_error}")
                
                return True
                
        except Exception as e:
            print(f"Error in _remove_position_from_db_standalone: {e}")
            return False
    
    async def _execute_position_assignment(self, interaction: discord.Interaction, position_name: str, position_id: str):
        """Execute position assignment using existing logic"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Use the same assignment logic from department change
            success = await self._assign_position_in_db(
                self.target_user.id, 
                position_id, 
                position_name, 
                interaction.user.id
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
                
                pm = PersonnelManager()
                config = load_config()
                
                # Get personnel data for audit
                personnel_data = await pm.get_personnel_data_for_audit(self.target_user.id)
                if not personnel_data:
                    personnel_data = {
                        'name': self.target_user.display_name,
                        'static': 'Неизвестно',
                        'rank': 'Неизвестно',
                        'department': self.subdivision_name or 'Неизвестно',
                        'position': position_name
                    }
                else:
                    personnel_data['position'] = position_name
                
                await audit_logger.send_personnel_audit(
                    guild=interaction.guild,
                    action=await AuditAction.POSITION_ASSIGNMENT(),
                    target_user=self.target_user,
                    moderator=interaction.user,
                    personnel_data=personnel_data,
                    config=config
                )
                
            except Exception as audit_error:
                print(f"Warning: Failed to send audit notification: {audit_error}")
            
            # Success message
            await interaction.followup.send(
                f"✅ **{self.target_user.display_name}** успешно назначен на должность **{position_name}**\n"
                f"📊 Отправлен кадровый аудит",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error in position assignment: {e}")
            await interaction.followup.send(f"❌ **Ошибка:** {str(e)}", ephemeral=True)
    
    async def _assign_position_in_db(self, user_discord_id: int, position_id: str, position_name: str, moderator_discord_id: int) -> bool:
        """Assign position to user in database and create history record (reuse existing logic)"""
        try:
            from utils.postgresql_pool import get_db_cursor
            from datetime import datetime, timezone, timedelta
            
            # Get old position name for history tracking
            old_position_name = None
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT pos.name as position_name
                    FROM personnel p
                    JOIN employees e ON p.id = e.personnel_id
                    LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
                    LEFT JOIN positions pos ON ps.position_id = pos.id
                    WHERE p.discord_id = %s AND p.is_dismissal = false
                """, (user_discord_id,))
                old_pos_result = cursor.fetchone()
                if old_pos_result and old_pos_result['position_name']:
                    old_position_name = old_pos_result['position_name']
            
            # Get user as member for role updates
            user_member = None
            try:
                # Get user as member for role updates
                if hasattr(self, 'target_user'):
                    user_member = self.target_user
            except Exception as e:
                print(f"Warning: Could not get user member for role update: {e}")
            
            with get_db_cursor() as cursor:
                # Get personnel ID
                cursor.execute("SELECT id FROM personnel WHERE discord_id = %s AND is_dismissal = false;", (user_discord_id,))
                personnel_result = cursor.fetchone()
                if not personnel_result:
                    return False
                personnel_id = personnel_result['id']
                
                # Get position_subdivision_id for the current user's subdivision
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
                        new_position_id = int(position_id) if position_id.isdigit() else None
                        await position_manager.smart_update_user_position_roles(
                            user_member.guild,
                            user_member,
                            new_position_id
                        )
                    except Exception as e:
                        print(f"⚠️ Error updating position roles: {e}")
                
                return True
                
        except Exception as e:
            print(f"Error in _assign_position_in_db: {e}")
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
                
                pm = PersonnelManager()
                config = load_config()
                
                # Get personnel data for audit
                personnel_data = await pm.get_personnel_data_for_audit(self.target_user.id)
                if not personnel_data:
                    personnel_data = {
                        'name': self.target_user.display_name,
                        'static': 'Неизвестно',
                        'rank': self.new_rank,
                        'department': 'Неизвестно',
                        'position': 'Неизвестно'
                    }
                else:
                    personnel_data['rank'] = self.new_rank
                
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
                print(f"Warning: Failed to send audit notification: {audit_error}")
            
            # Update Discord roles (remove old rank role, add new rank role)
            try:
                from utils.database_manager import rank_manager
                
                # Update roles using RankManager (old_rank already obtained above)
                role_success, role_message = await rank_manager.update_user_rank_roles(
                    interaction.guild, 
                    self.target_user, 
                    old_rank, 
                    self.new_rank
                )
                
                if not role_success:
                    print(f"Warning: Failed to update Discord roles: {role_message}")
                else:
                    print(f"✅ Discord roles updated: {old_rank} -> {self.new_rank}")
                    
            except Exception as role_error:
                print(f"Warning: Failed to update Discord roles: {role_error}")
            
            # Update nickname using nickname_manager
            try:
                print(f"🎆 CONTEXT RANK CHANGE: {action_name} {self.target_user.display_name} -> {self.new_rank}")
                
                # Используем nickname_manager для автоматического обновления никнейма
                new_nickname = await nickname_manager.handle_promotion(
                    member=self.target_user,
                    new_rank_name=self.new_rank
                )
                
                if new_nickname:
                    print(f"✅ CONTEXT RANK NICKNAME: Никнейм обновлён через nickname_manager: {self.target_user.display_name} -> {new_nickname}")
                else:
                    # Вычисляем предполагаемый никнейм для логирования ошибки
                    expected_nickname = nickname_manager.preview_nickname_change(
                        current_nickname=self.target_user.display_name,
                        operation='promotion',
                        rank_abbr=self.new_rank,
                        first_name='Неизвестно',
                        last_name='Неизвестно'
                    )
                    print(f"❌ CONTEXT RANK NICKNAME ERROR: Не удалось обновить никнейм через nickname_manager. Ожидаемый никнейм: {expected_nickname}")
                    
            except Exception as nickname_error:
                print(f"⚠️ CONTEXT RANK NICKNAME EXCEPTION: Ошибка изменения никнейма на \"{new_nickname}\": {nickname_error}")
            
            # Success message
            emoji = "⬆️" if action_id in [1, 4] else "⬇️"
            nickname_info = f" (никнейм обновлён)" if 'new_nickname' in locals() and new_nickname else ""
            await interaction.followup.send(
                f"{emoji} **{self.target_user.display_name}** - {action_name.lower()} на ранг **{self.new_rank}**{nickname_info}\n",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error in rank change: {e}")
            await interaction.followup.send(f"❌ **Ошибка:** {str(e)}", ephemeral=True)
    
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
            print(f"Error in _change_rank_in_db: {e}")
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
                print(f"Warning: Could not get current rank for {self.target_user.display_name}")
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
                    print(f"🔍 Rank comparison: {current_rank_from_db}(level {current_level}) -> {selected_rank}(level {new_level}) = {'повышение' if is_promotion else 'понижение'}")
                
        except Exception as e:
            print(f"Error determining rank change type: {e}")
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
    
    @ui.button(label="Изменить ранг", style=discord.ButtonStyle.primary, emoji="🎖️")
    async def edit_rank(self, interaction: discord.Interaction, button: ui.Button):
        """Handle rank editing"""
        try:
            from forms.personnel_context.rank_utils import RankHierarchy
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
            print(f"Error in rank editing: {e}")
            await interaction.response.send_message(f"❌ **Ошибка:** {str(e)}", ephemeral=True)
    
    @ui.button(label="Изменить подразделение", style=discord.ButtonStyle.secondary, emoji="🏢")
    async def edit_department(self, interaction: discord.Interaction, button: ui.Button):
        """Handle department editing"""
        # Send action selection view (same as before)
        view = DepartmentActionView(self.target_user)
        await interaction.response.send_message(
            f"🏢 **Изменение подразделения для {self.target_user.display_name}**\n"
            f"Выберите тип действия:",
            view=view,
            ephemeral=True
        )
    
    @ui.button(label="Изменить должность", style=discord.ButtonStyle.secondary, emoji="📋")
    async def edit_position(self, interaction: discord.Interaction, button: ui.Button):
        """Handle position editing"""
        # Send position selection view (same as before)
        view = PositionOnlySelectView(self.target_user)
        await interaction.response.send_message(
            f"📋 **Управление должностью для {self.target_user.display_name}**\n"
            f"• Выберите должность из доступных в текущем подразделении\n"
            f"• Или разжалуйте с текущей должности",
            view=view,
            ephemeral=True
        )


@app_commands.context_menu(name='Быстро повысить')
@handle_context_errors
async def quick_promote(interaction: discord.Interaction, user: discord.Member):
    """Context menu command to quickly promote user by +1 rank"""
    # Check permissions
    config = load_config()
    if not is_moderator_or_admin(interaction.user, config):
        await interaction.response.send_message("❌ У вас нет прав для повышения в ранге.", ephemeral=True)
        return
    
    # Check if moderator can moderate this user (hierarchy check)
    if not can_moderate_user(interaction.user, user, config):
        await interaction.response.send_message(
            "❌ Вы не можете выполнять действия над этим пользователем. Недостаточно прав в иерархии.",
            ephemeral=True
        )
        return
    
    # Check if target is bot
    if user.bot:
        await interaction.response.send_message("❌ Нельзя повысить бота.", ephemeral=True)
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
        next_rank = RankHierarchy.get_next_rank(current_rank)
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
        print(f"Error in quick promotion: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ **Ошибка:** {str(e)}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ **Ошибка:** {str(e)}", ephemeral=True)


@app_commands.context_menu(name='Общее редактирование')
@handle_context_errors
async def general_edit(interaction: discord.Interaction, user: discord.Member):
    """Context menu command for general editing (rank, department, position)"""
    # Check permissions
    config = load_config()
    if not is_moderator_or_admin(interaction.user, config):
        await interaction.response.send_message("❌ У вас нет прав для редактирования данных.", ephemeral=True)
        return
    
    # Check if moderator can moderate this user (hierarchy check)
    if not can_moderate_user(interaction.user, user, config):
        await interaction.response.send_message(
            "❌ Вы не можете выполнять действия над этим пользователем. Недостаточно прав в иерархии.",
            ephemeral=True
        )
        return
    
    # Check if target is bot
    if user.bot:
        await interaction.response.send_message("❌ Нельзя редактировать данные бота.", ephemeral=True)
        return
    
    # Send general editing view
    view = GeneralEditView(user)
    await interaction.response.send_message(
        f"⚙️ **Общее редактирование для {user.display_name}**\n"
        f"Выберите что хотите изменить:",
        view=view,
        ephemeral=True
    )


def setup_context_commands(bot):
    """Setup context menu commands for PersonnelManager integration"""
    # Check if commands are already added to avoid duplicates
    existing_commands = [cmd.name for cmd in bot.tree.get_commands()]
    
    commands_to_add = [
        ('Принять на службу', recruit_user),
        ('Уволить', dismiss_user),
        ('Быстро повысить', quick_promote),
        ('Общее редактирование', general_edit)
    ]
    
    added_count = 0
    for name, command in commands_to_add:
        if name not in existing_commands:
            bot.tree.add_command(command)
            added_count += 1
            print(f"✅ Personnel context menu command '{name}' loaded")
        else:
            print(f"ℹ️ Personnel context menu command '{name}' already loaded")
    
    if added_count > 0:
        print(f"✅ {added_count} new personnel context menu command(s) registered")
    else:
        print("ℹ️ All personnel context menu commands already loaded")