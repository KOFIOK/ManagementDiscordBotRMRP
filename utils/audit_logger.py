"""
Centralized Audit Notification System

This module provides a unified interface for sending personnel audit notifications
to the audit channel. Eliminates code duplication across dismissal, hiring, and other
personnel action workflows.

Key features:
- Centralized embed formatting with standard "Кадровый аудит ВС РФ" template
- Dynamic action type loading from PostgreSQL actions table
- Automatic moderator info retrieval from PersonnelManager
- Conditional field display (position, reason, etc.)
- Consistent thumbnail and timestamp formatting
"""

import discord
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from enum import Enum
from utils.message_manager import get_audit_embed_field, get_audit_config, get_blacklist_config


class AuditAction:
    """
    Dynamic audit action types loaded from PostgreSQL actions table.
    
    Instead of hardcoded enum, actions are loaded from database on first use
    and cached for performance. This allows the bot to adapt to changes in
    the actions table without code modifications.
    
    Usage:
        # Actions are loaded dynamically from DB
        action = await AuditAction.get("Принят на службу")
        
        # Or use helper methods for common actions
        action = await AuditAction.HIRING()
        action = await AuditAction.DISMISSAL()
    """
    
    # Cache for loaded actions
    _actions_cache: Optional[Dict[str, int]] = None
    _cache_timestamp: Optional[datetime] = None
    _cache_duration = 300  # 5 minutes
    
    @classmethod
    async def _load_actions_from_db(cls) -> Dict[str, int]:
        """
        Load all actions from PostgreSQL actions table.
        
        Returns:
            Dict[str, int]: Mapping of action name to action ID
        """
        try:
            from utils.postgresql_pool import get_db_cursor
            
            actions = {}
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id, name FROM actions ORDER BY id;")
                rows = cursor.fetchall()
                for row in rows:
                    actions[row['name']] = row['id']
            
            print(f"Loaded {len(actions)} actions from database")
            return actions
            
        except Exception as e:
            print(f"Error loading actions from database: {e}")
            # Fallback to common actions if DB fails
            return {
                "Принят на службу": 10,
                "Уволен со службы": 3,
                "Повышен в звании": 1,
                "Разжалован в звании": 2,
                "Принят в подразделение": 7,
                "Переведён в подразделение": 8,
                "Назначение на должность": 5,
                "Разжалование с должности": 6,
                "Восстановлен в звании": 4,
                "Внесение изменений в Имя или Фамилию": 9
            }
    
    @classmethod
    async def get_actions(cls) -> Dict[str, int]:
        """
        Get all actions from cache or load from database.
        
        Returns:
            Dict[str, int]: Mapping of action name to action ID
        """
        current_time = datetime.now()
        
        # Check if cache is valid
        if (cls._actions_cache is not None and 
            cls._cache_timestamp is not None and
            (current_time - cls._cache_timestamp).seconds < cls._cache_duration):
            return cls._actions_cache
        
        # Load from database
        cls._actions_cache = await cls._load_actions_from_db()
        cls._cache_timestamp = current_time
        
        return cls._actions_cache
    
    @classmethod
    async def get(cls, action_name: str) -> str:
        """
        Get action name (validates against database).
        
        Args:
            action_name: Name of the action (e.g., "Принят на службу")
            
        Returns:
            str: Action name if valid, raises ValueError if not found
        """
        actions = await cls.get_actions()
        if action_name not in actions:
            available = ", ".join(actions.keys())
            raise ValueError(
                f"Action '{action_name}' not found in database. "
                f"Available actions: {available}"
            )
        return action_name
    
    @classmethod
    async def refresh_cache(cls):
        """Force refresh of actions cache from database"""
        cls._actions_cache = None
        cls._cache_timestamp = None
        await cls.get_actions()
    
    # Helper methods for common actions (based on current DB state)
    @classmethod
    async def HIRING(cls) -> str:
        """Принят на службу (ID: 10)"""
        return await cls.get("Принят на службу")
    
    @classmethod
    async def DISMISSAL(cls) -> str:
        """Уволен со службы (ID: 3)"""
        return await cls.get("Уволен со службы")
    
    @classmethod
    async def PROMOTION(cls) -> str:
        """Повышен в звании (ID: 1)"""
        return await cls.get("Повышен в звании")
    
    @classmethod
    async def DEMOTION(cls) -> str:
        """Разжалован в звании (ID: 2)"""
        return await cls.get("Разжалован в звании")
    
    @classmethod
    async def RANK_RESTORATION(cls) -> str:
        """Восстановлен в звании (ID: 4)"""
        return await cls.get("Восстановлен в звании")
    
    @classmethod
    async def POSITION_ASSIGNMENT(cls) -> str:
        """Назначение на должность (ID: 5)"""
        return await cls.get("Назначение на должность")
    
    @classmethod
    async def POSITION_DEMOTION(cls) -> str:
        """Разжалование с должности (ID: 6)"""
        return await cls.get("Разжалование с должности")
    
    @classmethod
    async def DEPARTMENT_JOIN(cls) -> str:
        """Принят в подразделение (ID: 7)"""
        return await cls.get("Принят в подразделение")
    
    @classmethod
    async def DEPARTMENT_TRANSFER(cls) -> str:
        """Переведён в подразделение (ID: 8)"""
        return await cls.get("Переведён в подразделение")
    
    @classmethod
    async def NAME_CHANGE(cls) -> str:
        """Внесение изменений в Имя или Фамилию (ID: 9)"""
        return await cls.get("Внесение изменений в Имя или Фамилию")


class PersonnelAuditLogger:
    """
    Centralized personnel audit logger with PostgreSQL integration.
    
    Provides consistent audit embed formatting and sending to audit channel.
    All personnel actions should use this logger for audit trail consistency.
    
    Usage:
        audit_logger = PersonnelAuditLogger()
        
        # Using helper methods (recommended)
        await audit_logger.send_personnel_audit(
            guild=interaction.guild,
            action=await AuditAction.DISMISSAL(),
            target_user=user,
            moderator=interaction.user,
            personnel_data={
                'name': 'Иван Петров',
                'static': '123-456',
                'rank': 'Рядовой',
                'department': 'ВКС',
                'position': 'Стрелок',  # Optional
                'reason': 'ПСЖ'  # Optional
            }
        )
        
        # Or using direct action name from database
        await audit_logger.send_personnel_audit(
            guild=interaction.guild,
            action="Уволен со службы",
            target_user=user,
            moderator=interaction.user,
            personnel_data={...}
        )
    """
    
    def __init__(self):
        """Initialize audit logger"""
        pass
    
    async def send_personnel_audit(
        self,
        guild: discord.Guild,
        action: str,
        target_user: discord.User,
        moderator: discord.User,
        personnel_data: Dict[str, Any],
        config: Optional[Dict] = None,
        custom_fields: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Send standardized personnel audit notification to audit channel.
        
        Args:
            guild: Discord guild where action occurred
            action: Type of action (string from AuditAction or direct action name)
            target_user: User who is subject of the action
            moderator: User who performed the action
            personnel_data: Dict containing personnel information:
                - name: Full name (required)
                - static: Static number (required)
                - rank: Military rank (required)
                - department: Department/subdivision (required)
                - position: Position (optional, hidden if "Не назначено")
                - reason: Reason for action (optional, for dismissals/hirings)
            config: Bot configuration (loaded if not provided)
            custom_fields: Additional custom fields to add to embed
            
        Returns:
            str: Jump URL of audit message if sent successfully, None otherwise
        """
        try:
            # Load config if not provided
            if not config:
                from utils.config_manager import load_config
                config = load_config()
            
            # Get audit channel
            audit_channel_id = config.get('audit_channel')
            if not audit_channel_id:
                print("Audit channel not configured")
                return None
            
            audit_channel = guild.get_channel(audit_channel_id)
            if not audit_channel:
                print(f"Audit channel {audit_channel_id} not found")
                return None
            
            # Get moderator info from PersonnelManager
            moderator_display = await self._get_moderator_info_from_pm(moderator.id)
            if not moderator_display:
                moderator_display = moderator.display_name
            
            # Get audit configuration
            audit_config = get_audit_config(guild.id)
            
            # Create audit embed
            embed = await self._create_base_embed(
                guild_id=guild.id,
                action=action,
                moderator_display=moderator_display,
                personnel_data=personnel_data,
                audit_config=audit_config
            )
            
            # Add conditional fields
            await self._add_conditional_fields(guild.id, embed, personnel_data, action)
            
            # Add custom fields if provided
            if custom_fields:
                for field_name, field_value in custom_fields.items():
                    embed.add_field(name=field_name, value=field_value, inline=False)
            
            # Send to audit channel with user mention
            audit_message = await audit_channel.send(
                content=f"<@{target_user.id}>",
                embed=embed
            )
            
            print(f"Sent audit notification for {action} - {personnel_data.get('name')}")
            return audit_message.jump_url
            
        except Exception as e:
            print(f"Error sending audit notification: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _get_moderator_info_from_pm(self, moderator_discord_id: int) -> Optional[str]:
        """
        Get moderator info from PostgreSQL personnel database.
        
        Returns:
            str: "Имя Фамилия | static" or None if not found
        """
        try:
            from utils.postgresql_pool import get_db_cursor
            
            # Query personnel table directly (without is_dismissal check for moderators)
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        first_name,
                        last_name,
                        static
                    FROM personnel
                    WHERE discord_id = %s
                    ORDER BY id DESC
                    LIMIT 1;
                """, (moderator_discord_id,))
                
                result = cursor.fetchone()
                
                if result:
                    first_name = result['first_name'] or ''
                    last_name = result['last_name'] or ''
                    static = result['static'] or ''
                    
                    full_name = f"{first_name} {last_name}".strip()
                    
                    if full_name and static:
                        return f"{full_name} | {static}"
                    elif full_name:
                        return full_name
                    elif static:
                        return static
            
            return None
            
        except Exception as e:
            print(f"⚠️ Could not get moderator info from personnel DB: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _create_base_embed(
        self,
        guild_id: int,
        action: str,
        moderator_display: str,
        personnel_data: Dict[str, Any],
        audit_config: Dict[str, Any]
    ) -> discord.Embed:
        """
        Create base audit embed with standard fields.
        
        Standard fields:
        - Кадровую отписал
        - Имя Фамилия | 6 цифр статика
        - Действие
        - Дата Действия
        - Подразделение
        - Воинское звание
        """
        # Use Moscow timezone (UTC+3)
        moscow_tz = timezone(timedelta(hours=3))
        moscow_time = datetime.now(moscow_tz)
        
        # Parse color (handle both hex string and int)
        color_value = audit_config.get('color', self.AUDIT_COLOR)
        if isinstance(color_value, str) and color_value.startswith('#'):
            color_value = int(color_value[1:], 16)
        elif isinstance(color_value, str):
            try:
                color_value = int(color_value, 16)
            except ValueError:
                color_value = self.AUDIT_COLOR
        
        embed = discord.Embed(
            title=audit_config.get('title', self.AUDIT_TITLE),
            color=color_value,
            timestamp=moscow_time
        )
        
        # Set thumbnail
        thumbnail_url = audit_config.get('thumbnail', self.AUDIT_THUMBNAIL)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        
        # Standard fields
        embed.add_field(
            name=get_audit_embed_field(guild_id, 'moderator', 'Кадровую отписал'),
            value=moderator_display,
            inline=False
        )
        
        # Combine name and static
        name = personnel_data.get('name', 'Неизвестно')
        static = personnel_data.get('static', '')
        name_with_static = f"{name} | {static}" if static else name
        
        embed.add_field(
            name=get_audit_embed_field(guild_id, 'name_static', 'Имя Фамилия | № Паспорта'),
            value=name_with_static,
            inline=False
        )
        
        embed.add_field(
            name=get_audit_embed_field(guild_id, 'action', 'Действие'),
            value=action,
            inline=False
        )
        
        # Format date as dd.MM.yyyy using Moscow time
        action_date = moscow_time.strftime('%d.%m.%Y')
        embed.add_field(
            name=get_audit_embed_field(guild_id, 'action_date', 'Дата Действия'),
            value=action_date,
            inline=False
        )
        
        embed.add_field(
            name=get_audit_embed_field(guild_id, 'department', 'Подразделение'),
            value=personnel_data.get('department', 'Неизвестно'),
            inline=False
        )
        
        embed.add_field(
            name=get_audit_embed_field(guild_id, 'rank', 'Воинское звание'),
            value=personnel_data.get('rank', 'Неизвестно'),
            inline=False
        )
        
        return embed
    
    async def _add_conditional_fields(
        self,
        guild_id: int,
        embed: discord.Embed,
        personnel_data: Dict[str, Any],
        action: str
    ):
        """
        Add conditional fields based on data availability and action type.
        
        Conditional fields:
        - Должность (if not "Не назначено", empty, or "None")
        - Причина увольнения (for dismissals)
        """
        # Position field - only if meaningful value exists
        position = personnel_data.get('position', '')
        if position and position not in ['Не назначено', '', 'None']:
            embed.add_field(
                name="Должность",
                value=position,
                inline=False
            )
        
        # Reason field - context-dependent
        reason = personnel_data.get('reason', '')
        if reason:
            # Check action type by string content
            if "Уволен" in action:
                embed.add_field(
                    name="Причина увольнения",
                    value=reason,
                    inline=False
                )
            else:
                # Generic reason field for other actions
                embed.add_field(
                    name="Примечание",
                    value=reason,
                    inline=False
                )
    
    async def _add_conditional_fields(
        self,
        guild_id: int,
        embed: discord.Embed,
        personnel_data: Dict[str, Any],
        action: str
    ):
        """
        Add conditional fields based on data availability and action type.
        
        Conditional fields:
        - Должность (if not "Не назначено", empty, or "None")
        - Причина увольнения (for dismissals)
        """
        # Position field - only if meaningful value exists
        position = personnel_data.get('position', '')
        if position and position not in ['Не назначено', '', 'None']:
            embed.add_field(
                name="Должность",
                value=position,
                inline=False
            )
        
        # Reason field - context-dependent
        reason = personnel_data.get('reason', '')
        if reason:
            # Check action type by string content
            if "Уволен" in action:
                embed.add_field(
                    name="Причина увольнения",
                    value=reason,
                    inline=False
                )
            else:
                # Generic reason field for other actions
                embed.add_field(
                    name="Примечание",
                    value=reason,
                    inline=False
                )
    
    async def send_blacklist_notification(
        self,
        guild: discord.Guild,
        target_user: discord.User,
        moderator: discord.User,
        personnel_data: Dict[str, Any],
        personnel_id: int,
        reason: str,
        auto_generated: bool = False,
        audit_message_url: Optional[str] = None,
        config: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Send blacklist notification to blacklist channel and add to database.
        
        Args:
            guild: Discord guild where action occurred
            target_user: User being blacklisted
            moderator: User who performed the action (or system for auto)
            personnel_data: Dict containing personnel information
            personnel_id: Internal personnel.id of target user
            reason: Reason for blacklist
            auto_generated: Whether this was auto-generated (early dismissal)
            audit_message_url: URL to dismissal audit message (for evidence)
            config: Bot configuration (loaded if not provided)
            
        Returns:
            str: Jump URL of blacklist message if sent successfully, None otherwise
        """
        try:
            from utils.postgresql_pool import get_db_cursor
            from datetime import timedelta
            
            # Load config if not provided
            if not config:
                from utils.config_manager import load_config
                config = load_config()
            
            # Get blacklist channel
            blacklist_channel_id = config.get('blacklist_channel')
            if not blacklist_channel_id:
                print("⚠️ Blacklist channel not configured")
                return None
            
            blacklist_channel = guild.get_channel(blacklist_channel_id)
            if not blacklist_channel:
                print(f"⚠️ Blacklist channel {blacklist_channel_id} not found")
                return None
            
            # Get moderator personnel_id for "added_by"
            moderator_personnel_id = None
            try:
                with get_db_cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM personnel WHERE discord_id = %s;",
                        (moderator.id,)
                    )
                    result = cursor.fetchone()
                    if result:
                        moderator_personnel_id = result['id']
                    else:
                        print(f"⚠️ Moderator not found in personnel DB: {moderator.id}")
            except Exception as e:
                print(f"⚠️ Error getting moderator personnel_id: {e}")
            
            # Get moderator info for "Кто выдаёт"
            if auto_generated:
                # For auto-generated, use the actual moderator who triggered dismissal
                # but we could also use a system user if configured
                moderator_display = await self._get_moderator_info_from_pm(moderator.id)
                if not moderator_display:
                    # Fallback to system user if moderator not found
                    moderator_display = "Система | 00-000"
            else:
                moderator_display = await self._get_moderator_info_from_pm(moderator.id)
                if not moderator_display:
                    moderator_display = moderator.display_name
            
            # Prepare "Кому" field
            name = personnel_data.get('name', 'Неизвестно')
            static = personnel_data.get('static', '')
            target_display = f"{name} | {static}" if static else name
            
            # Prepare dates
            # Prepare dates (Moscow timezone UTC+3)
            moscow_tz = timezone(timedelta(hours=3))
            start_date = datetime.now(moscow_tz)
            end_date = start_date + timedelta(days=14)
            start_date_str = start_date.strftime('%d.%m.%Y')
            end_date_str = end_date.strftime('%d.%m.%Y')
            
            # Format timestamp for embed field
            timestamp_str = start_date.strftime('%d.%m.%Y %H:%M')
            
            # Insert into blacklist table
            try:
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO blacklist (
                            reason, start_date, end_date, last_updated, 
                            is_active, personnel_id, added_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id;
                    """, (
                        "Неустойка",  # reason
                        start_date,  # start_date
                        end_date,  # end_date
                        start_date,  # last_updated
                        True,  # is_active
                        personnel_id,  # personnel_id (target user)
                        moderator_personnel_id  # added_by (moderator)
                    ))
                    
                    blacklist_id = cursor.fetchone()['id']
                    print(f"✅ Added blacklist record #{blacklist_id} for personnel {personnel_id}")
                    
            except Exception as e:
                print(f"❌ Error adding blacklist record to database: {e}")
                import traceback
                traceback.print_exc()
                # Continue anyway to send Discord notification
            
            # Create embed with fields (not description for better formatting)
            blacklist_config = get_blacklist_config(guild.id)
            
            # Parse color
            color_value = blacklist_config.get('color', 0xED4245)
            if isinstance(color_value, str) and color_value.startswith('#'):
                color_value = int(color_value[1:], 16)
            elif isinstance(color_value, str):
                try:
                    color_value = int(color_value, 16)
                except ValueError:
                    color_value = 0xED4245
            
            embed = discord.Embed(
                title=blacklist_config.get('title', "📋 Новое дело"),
                color=color_value
            )
            
            # Set thumbnail
            thumbnail_url = blacklist_config.get('thumbnail')
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
            
            # Field 1: Кто выдаёт
            fields = blacklist_config.get('fields', {})
            embed.add_field(
                name=fields.get('moderator', "**1. Кто выдаёт**"),
                value=moderator_display,
                inline=False
            )
            
            # Field 2: Кому
            embed.add_field(
                name=fields.get('target', "**2. Кому**"),
                value=target_display,
                inline=False
            )
            
            # Field 3: Причина
            embed.add_field(
                name=fields.get('reason', "**3. Причина**"),
                value="Неустойка",
                inline=False
            )
            
            # Fields 4-5: Даты (inline для двух столбцов)
            embed.add_field(
                name=fields.get('start_date', "**4. Дата начала**"),
                value=start_date_str,
                inline=True
            )
            
            embed.add_field(
                name=fields.get('end_date', "**5. Дата окончания**"),
                value=end_date_str,
                inline=True
            )
            
            # Field 6: Доказательства
            embed.add_field(
                name=fields.get('evidence', "**6. Доказательства**"),
                value=audit_message_url if audit_message_url else "Не указано",
                inline=False
            )
            
            embed.set_footer(text=timestamp_str)
            
            # Get blacklist ping roles from config
            blacklist_ping_roles = config.get('blacklist_role_mentions', [])
            ping_content = " ".join([f"<@&{role_id}>" for role_id in blacklist_ping_roles])
            
            # Send to blacklist channel with pings
            blacklist_message = await blacklist_channel.send(
                content="-# " + ping_content if ping_content else None,
                embed=embed
            )
            
            print(f"✅ Sent blacklist notification for {name} (auto: {auto_generated})")
            return blacklist_message.jump_url
            
        except Exception as e:
            print(f"❌ Error sending blacklist notification: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def check_and_send_auto_blacklist(
        self,
        guild: discord.Guild,
        target_user: discord.User,
        moderator: discord.User,
        personnel_id: int,
        personnel_data: Dict[str, Any],
        audit_message_url: Optional[str] = None,
        config: Optional[Dict] = None
    ) -> bool:
        """
        Check if user should be auto-blacklisted (served < 5 days) and send notification.
        
        Args:
            guild: Discord guild
            target_user: User being dismissed
            moderator: User who performed dismissal
            personnel_id: Internal personnel.id from database
            personnel_data: Dict containing personnel information
            audit_message_url: URL to dismissal audit message (for evidence)
            config: Bot configuration (loaded if not provided)
            
        Returns:
            bool: True if user was auto-blacklisted, False otherwise
        """
        try:
            # Import personnel_manager for service time calculation
            from utils.database_manager import personnel_manager
            
            # Проверяет, есть ли у пользователя какие-либо записи о приеме во фракцию
            # (чтобы избежать ложного черного списка для устаревших пользователей)
            # Фиксит баг с legacy пользователями, у которых нет записей о приеме во фракцию
            from utils.postgresql_pool import get_db_cursor
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as hiring_count 
                    FROM history 
                    WHERE personnel_id = %s AND action_id = 10;
                """, (personnel_id,))
                hiring_result = cursor.fetchone()
                has_hiring_records = hiring_result['hiring_count'] > 0 if hiring_result else False
            
            if not has_hiring_records:
                print(f"ℹ️ No hiring records found for {personnel_data.get('name')} - skipping auto-blacklist check")
                return False
            
            # Calculate total service time
            total_days = await personnel_manager.calculate_total_service_time(personnel_id)
            
            # Check if served less than 5 days
            if total_days < 5:
                print(f"⚠️ Auto-blacklist triggered: {personnel_data.get('name')} served only {total_days} days")
                
                # Prepare blacklist reason
                reason = f"Ранний роспуск (отслужил {total_days} из 5 обязательных дней)"
                
                # Send blacklist notification and add to database
                blacklist_url = await self.send_blacklist_notification(
                    guild=guild,
                    target_user=target_user,
                    moderator=moderator,
                    personnel_data=personnel_data,
                    personnel_id=personnel_id,  # Pass personnel_id for database insert
                    reason=reason,
                    auto_generated=True,
                    audit_message_url=audit_message_url,
                    config=config
                )
                
                if blacklist_url:
                    print(f"✅ Auto-blacklist successful for {personnel_data.get('name')}")
                    # Invalidate cache for this user
                    from utils.database_manager import personnel_manager
                    personnel_manager.invalidate_blacklist_cache(target_user.id)
                    # Also invalidate general user cache since blacklist status changed
                    from utils.user_cache import invalidate_user_cache
                    invalidate_user_cache(target_user.id)
                    return True
                else:
                    print(f"❌ Auto-blacklist failed for {personnel_data.get('name')}")
                    return False
            else:
                print(f"✅ No auto-blacklist: {personnel_data.get('name')} served {total_days} days")
                return False
                
        except Exception as e:
            print(f"❌ Error in auto-blacklist check: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def update_personnel_profile_with_history(self, discord_id: int, first_name: str, 
                                                  last_name: str, static: str, 
                                                  moderator_discord_id: int) -> Tuple[bool, str]:
        """
        Обновить имя, фамилию и статик сотрудника с записью в историю.
        
        Args:
            discord_id (int): Discord ID пользователя
            first_name (str): Новое имя
            last_name (str): Новая фамилия
            static (str): Новый статик (опционально)
            moderator_discord_id (int): Discord ID модератора
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            from utils.postgresql_pool import get_db_cursor
            print(f"🔍 AUDIT: Начинаем update_personnel_profile_with_history для {discord_id}")
            
            with get_db_cursor() as cursor:
                print(f"🔍 AUDIT: Получили DB cursor")
                # Получаем current data для истории
                cursor.execute("""
                    SELECT id, first_name, last_name, static 
                    FROM personnel 
                    WHERE discord_id = %s AND is_dismissal = false;
                """, (discord_id,))
                
                current_data = cursor.fetchone()
                print(f"🔍 AUDIT: current_data получен: {current_data is not None}")
                if not current_data:
                    return False, f"Активный персонал с ID {discord_id} не найден"
                
                personnel_id = current_data['id']
                old_first_name = current_data['first_name']
                old_last_name = current_data['last_name']
                old_static = current_data['static']
                
                print(f"🔍 AUDIT: Старые данные: {old_first_name} {old_last_name} | {old_static}")
                print(f"🔍 AUDIT: Новые данные: {first_name} {last_name} | {static}")
                
                # Форматируем статик
                if static:
                    print(f"🔍 AUDIT: Форматируем статик '{static}'...")
                    formatted_static = self._format_static_for_db(static)
                    print(f"🔍 AUDIT: Отформатированный статик: '{formatted_static}'")
                else:
                    formatted_static = old_static  # Оставляем старый статик
                    print(f"🔍 AUDIT: Используем старый статик: '{formatted_static}'")
                
                # Обновляем данные
                print(f"🔍 AUDIT: Начинаем UPDATE personnel...")
                if static:
                    cursor.execute("""
                        UPDATE personnel 
                        SET first_name = %s, 
                            last_name = %s,
                            static = %s,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE discord_id = %s AND is_dismissal = false;
                    """, (first_name, last_name, formatted_static, discord_id))
                    
                    message = f"Данные персонала обновлены: {first_name} {last_name}, статик: {formatted_static}"
                else:
                    cursor.execute("""
                        UPDATE personnel 
                        SET first_name = %s, 
                            last_name = %s,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE discord_id = %s AND is_dismissal = false;
                    """, (first_name, last_name, discord_id))
                    
                    message = f"Данные персонала обновлены: {first_name} {last_name}"
                
                print(f"🔍 AUDIT: UPDATE personnel завершен")
                
                # Создаем запись в истории
                print(f"🔍 AUDIT: Начинаем log_name_change_action...")
                from utils.database_manager import personnel_manager
                await personnel_manager.log_name_change_action(
                    personnel_id, 
                    old_first_name, old_last_name, old_static,
                    first_name, last_name, formatted_static,
                    moderator_discord_id
                )
                print(f"🔍 AUDIT: log_name_change_action завершен")
                
                print(f"✅ {message} (ID: {discord_id}) с записью в историю")
                return True, message
                
        except Exception as e:
            error_msg = f"Ошибка обновления профиля персонала с историей: {e}"
            print(error_msg)
            return False, error_msg
    
    def _format_static_for_db(self, static: str) -> str:
        """
        Форматирует статик для базы данных.
        
        Args:
            static: Сырой статик от пользователя
            
        Returns:
            str: Отформатированный статик
        """
        print(f"🔍 FORMAT_STATIC: Входной статик: '{static}' (type: {type(static)})")
        
        if not static:
            print(f"🔍 FORMAT_STATIC: Статик пустой, возвращаем пустую строку")
            return ""
        
        # Используем унифицированную валидацию
        from utils.static_validator import StaticValidator
        is_valid, formatted = StaticValidator.validate_and_format(static)
        
        if is_valid:
            print(f"🔍 FORMAT_STATIC: Успешно отформатировано: '{formatted}'")
            return formatted
        else:
            # Возвращаем как есть, если не подходит под стандарт
            result = static.strip()
            print(f"🔍 FORMAT_STATIC: Нестандартная длина, возвращаем как есть: '{result}'")
            return result
    
    async def add_to_blacklist_manual(
        self,
        guild: discord.Guild,
        target_user: discord.Member,
        moderator: discord.Member,
        reason: str,
        duration_days: int = 14,
        evidence_url: Optional[str] = None,
        config: Optional[Dict] = None
    ) -> tuple[bool, str]:
        """
        Manually add user to blacklist (via /чс command).
        Handles Discord notifications only - database operations done by personnel_manager.
        
        Args:
            guild: Discord guild
            target_user: User to add to blacklist
            moderator: Moderator adding to blacklist
            reason: Reason for blacklist
            duration_days: Duration in days (default 14)
            evidence_url: URL to evidence (optional)
            config: Bot configuration (loaded if not provided)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Load config if not provided
            if not config:
                from utils.config_manager import load_config
                config = load_config()
            
            # Add to blacklist via database manager
            from utils.database_manager import personnel_manager
            success, db_message, blacklist_data = await personnel_manager.add_to_blacklist(
                target_user.id, moderator.id, reason, duration_days
            )
            
            if not success:
                return False, db_message
            
            # Get blacklist channel
            blacklist_channel_id = config.get('blacklist_channel')
            if not blacklist_channel_id:
                return False, "❌ Канал чёрного списка не настроен в конфигурации."
            
            blacklist_channel = guild.get_channel(blacklist_channel_id)
            if not blacklist_channel:
                return False, f"❌ Канал чёрного списка не найден (ID: {blacklist_channel_id})."
            
            # Get moderator info
            moderator_display = await self._get_moderator_info_from_pm(moderator.id)
            if not moderator_display:
                moderator_display = moderator.display_name
            
            # Prepare target display
            personnel_data = blacklist_data['personnel_data']
            target_display = f"{personnel_data['name']} | {personnel_data['static']}" if personnel_data['static'] else personnel_data['name']
            
            # Format dates
            start_date = blacklist_data['start_date']
            end_date = blacklist_data['end_date']
            start_date_str = start_date.strftime('%d.%m.%Y')
            end_date_str = end_date.strftime('%d.%m.%Y')
            timestamp_str = start_date.strftime('%d.%m.%Y %H:%M')
            
            # Get blacklist configuration
            blacklist_config = get_blacklist_config(guild.id)
            
            # Parse color
            color_value = blacklist_config.get('color', 0xED4245)
            if isinstance(color_value, str) and color_value.startswith('#'):
                color_value = int(color_value[1:], 16)
            elif isinstance(color_value, str):
                try:
                    color_value = int(color_value, 16)
                except ValueError:
                    color_value = 0xED4245
            
            # Create embed
            embed = discord.Embed(
                title=blacklist_config.get('title', "📋 Новое дело"),
                color=color_value
            )
            
            # Set thumbnail
            thumbnail_url = blacklist_config.get('thumbnail')
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
            
            # Add fields using configuration
            fields = blacklist_config.get('fields', {})
            embed.add_field(
                name=fields.get('moderator', "**1. Кто выдаёт**"), 
                value=moderator_display, 
                inline=False
            )
            embed.add_field(
                name=fields.get('target', "**2. Кому**"), 
                value=target_display, 
                inline=False
            )
            embed.add_field(
                name=fields.get('reason', "**3. Причина**"), 
                value=reason, 
                inline=False
            )
            embed.add_field(
                name=fields.get('start_date', "**4. Дата начала**"), 
                value=start_date_str, 
                inline=True
            )
            embed.add_field(
                name=fields.get('end_date', "**5. Дата окончания**"), 
                value=end_date_str, 
                inline=True
            )
            embed.add_field(
                name=fields.get('evidence', "**6. Доказательства**"), 
                value=evidence_url if evidence_url else "Не указано", 
                inline=False
            )
            
            embed.set_footer(text=timestamp_str)
            
            # Get ping roles
            blacklist_ping_roles = config.get('blacklist_role_mentions', [])
            ping_content = " ".join([f"<@&{role_id}>" for role_id in blacklist_ping_roles])
            
            # Send to blacklist channel
            blacklist_message = await blacklist_channel.send(
                content="-# " + ping_content if ping_content else None,
                embed=embed
            )
            
            success_message = (
                blacklist_config['success']['title'].format(name=personnel_data['name']) + "\n\n" +
                blacklist_config['success']['details'].format(
                    reason=reason,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    moderator=moderator.display_name
                ) + "\n\n" +
                blacklist_config['success']['view_link'].format(link=blacklist_message.jump_url)
            )
            
            print(f"✅ Manual blacklist successful for {personnel_data['name']}")
            return True, success_message
            
        except Exception as e:
            error_msg = f"❌ Ошибка при добавлении в чёрный список: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return False, error_msg

    async def remove_from_blacklist(self, discord_id: int, moderator: discord.Member) -> tuple[bool, str]:
        """
        Remove user from blacklist (DELETE record).
        Handles Discord notifications only - database operations done by personnel_manager.
        
        Args:
            discord_id: Discord ID of user to remove from blacklist
            moderator: Moderator performing the removal
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Remove from blacklist via database manager
            from utils.database_manager import personnel_manager
            success, db_message, removed_data = await personnel_manager.remove_from_blacklist(discord_id)
            
            if not success:
                return False, db_message
            
            success_message = (
                f"✅ Пользователь **{removed_data['full_name']}** ({removed_data['static']}) "
                f"успешно удалён из чёрного списка.\n\n"
                f"**Детали удалённой записи:**\n"
                f"• Причина: {removed_data['reason']}\n"
                f"• Дата начала: {removed_data['start_date'].strftime('%d.%m.%Y')}\n"
                f"• Дата окончания: {removed_data['end_date'].strftime('%d.%m.%Y')}\n"
                f"• Снял с чёрного списка: {moderator.display_name}"
            )
            
            print(f"✅ Blacklist removal successful for discord_id={discord_id} by {moderator.display_name}")
            return True, success_message
            
        except Exception as e:
            error_msg = f"❌ Ошибка при удалении из чёрного списка: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return False, error_msg

    async def update_personnel_profile_with_history(self, discord_id: int, first_name: str,
                                                  last_name: str, static: str,
                                                  moderator_discord_id: int) -> Tuple[bool, str]:
        """
        Update personnel profile (name/static) with history logging and audit notification.

        This is the main entry point for personnel profile updates that need to be audited.

        Args:
            discord_id: Discord ID of the user being updated
            first_name: New first name
            last_name: New last name
            static: New static number
            moderator_discord_id: Discord ID of the moderator making the change

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            print(f"🔍 AUDIT: Начинаем update_personnel_profile_with_history для {discord_id}")

            # Get current data for comparison
            from utils.postgresql_pool import get_db_cursor
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT first_name, last_name, static
                    FROM personnel
                    WHERE discord_id = %s AND is_dismissal = false;
                """, (discord_id,))
                current_data = cursor.fetchone()

            if not current_data:
                return False, f"Пользователь с Discord ID {discord_id} не найден в базе данных"

            print(f"🔍 AUDIT: current_data получен: {current_data is not None}")
            print(f"🔍 AUDIT: Старые данные: {current_data['first_name']} {current_data['last_name']} | {current_data['static']}")
            print(f"🔍 AUDIT: Новые данные: {first_name} {last_name} | {static}")

            # Format static
            from utils.database_manager.manager import PersonnelManager
            pm = PersonnelManager()
            formatted_static = pm._format_static_for_db(static)
            print(f"🔍 AUDIT: Форматируем статик '{static}'...")
            print(f"🔍 FORMAT_STATIC: Входной статик: '{static}' (type: {type(static)})")
            print(f"🔍 FORMAT_STATIC: Только цифры: '{''.join(filter(str.isdigit, static))}' (длина: {len(''.join(filter(str.isdigit, static)))})")
            print(f"🔍 FORMAT_STATIC: {len(''.join(filter(str.isdigit, static)))} цифр -> XXX-XXX: '{formatted_static}'")
            print(f"🔍 AUDIT: Отформатированный статик: '{formatted_static}'")

            # Update personnel profile
            print(f"🔍 AUDIT: Начинаем UPDATE personnel...")
            success, message = pm.update_personnel_profile(discord_id, first_name, last_name, formatted_static)
            if not success:
                return False, message
            print(f"🔍 AUDIT: UPDATE personnel завершен")

            # Get personnel_id for the user being updated
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT id FROM personnel WHERE discord_id = %s AND is_dismissal = false;
                """, (discord_id,))
                personnel_result = cursor.fetchone()
                
            if not personnel_result:
                return False, f"Не удалось найти personnel_id для пользователя {discord_id}"
                
            personnel_id = personnel_result['id']
            print(f"🔍 AUDIT: personnel_id получен: {personnel_id}")

            # Log to history
            print(f"🔍 AUDIT: Начинаем log_name_change_action...")
            history_success = await pm.log_name_change_action(
                personnel_id=personnel_id,
                old_first_name=current_data['first_name'],
                old_last_name=current_data['last_name'],
                old_static=current_data['static'] or '',
                new_first_name=first_name,
                new_last_name=last_name,
                new_static=formatted_static,
                moderator_discord_id=moderator_discord_id
            )

            if not history_success:
                print(f"⚠️ AUDIT: History logging failed, but profile update succeeded")
            else:
                print(f"✅ AUDIT: History logging successful")

            # Get personnel data for audit notification
            personnel_data = await pm.get_personnel_data_for_audit(discord_id)
            if not personnel_data:
                return True, f"Профиль обновлен, но не удалось получить данные для аудита"

            # Note: Audit notification is sent from the modal/form handler, not here
            print(f"✅ AUDIT: Profile update completed successfully")

            return True, f"Профиль успешно обновлен: {first_name} {last_name} | {formatted_static}"

        except Exception as e:
            error_msg = f"Ошибка при обновлении профиля с историей: {e}"
            print(f"❌ AUDIT: {error_msg}")
            import traceback
            traceback.print_exc()
            return False, error_msg


# Global instance for easy access
audit_logger = PersonnelAuditLogger()
