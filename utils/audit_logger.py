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
    
    # Standard audit embed configuration
    AUDIT_TITLE = "Кадровый аудит ВС РФ"
    AUDIT_COLOR = 0x055000  # Green color from original template
    AUDIT_THUMBNAIL = "https://i.imgur.com/07MRSyl.png"
    
    # Blacklist check cache - prevents repeated DB queries for same user
    _blacklist_cache: Dict[int, Optional[Dict[str, Any]]] = {}
    _blacklist_cache_timestamps: Dict[int, datetime] = {}
    _blacklist_cache_ttl = 60  # 60 seconds TTL
    
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
            
            # Create audit embed
            embed = await self._create_base_embed(
                action=action,
                moderator_display=moderator_display,
                personnel_data=personnel_data
            )
            
            # Add conditional fields
            await self._add_conditional_fields(embed, personnel_data, action)
            
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
        action: str,
        moderator_display: str,
        personnel_data: Dict[str, Any]
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
        embed = discord.Embed(
            title=self.AUDIT_TITLE,
            color=self.AUDIT_COLOR,
            timestamp=datetime.utcnow()
        )
        
        # Set thumbnail
        embed.set_thumbnail(url=self.AUDIT_THUMBNAIL)
        
        # Standard fields
        embed.add_field(
            name="Кадровую отписал",
            value=moderator_display,
            inline=False
        )
        
        # Combine name and static
        name = personnel_data.get('name', 'Неизвестно')
        static = personnel_data.get('static', '')
        name_with_static = f"{name} | {static}" if static else name
        
        embed.add_field(
            name="Имя Фамилия | 6 цифр статика",
            value=name_with_static,
            inline=False
        )
        
        embed.add_field(
            name="Действие",
            value=action,
            inline=False
        )
        
        # Format date as dd-MM-yyyy
        action_date = datetime.utcnow().strftime('%d-%m-%Y')
        embed.add_field(
            name="Дата Действия",
            value=action_date,
            inline=False
        )
        
        embed.add_field(
            name="Подразделение",
            value=personnel_data.get('department', 'Неизвестно'),
            inline=False
        )
        
        embed.add_field(
            name="Воинское звание",
            value=personnel_data.get('rank', 'Неизвестно'),
            inline=False
        )
        
        return embed
    
    async def _add_conditional_fields(
        self,
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
    
    async def calculate_total_service_time(self, personnel_id: int) -> int:
        """
        Calculate total service time in days for a personnel member.
        
        Handles multiple hiring/dismissal cycles by pairing them chronologically.
        
        Args:
            personnel_id: Internal personnel.id from database
            
        Returns:
            int: Total days of service (sum of all service periods)
        """
        try:
            from utils.postgresql_pool import get_db_cursor
            
            # Get all hiring and dismissal events for this person
            with get_db_cursor() as cursor:
                # Get hiring events (action_id = 10)
                cursor.execute("""
                    SELECT action_date 
                    FROM history 
                    WHERE personnel_id = %s AND action_id = 10
                    ORDER BY action_date ASC
                """, (personnel_id,))
                hiring_dates = [row['action_date'] for row in cursor.fetchall()]
                
                # Get dismissal events (action_id = 3)
                cursor.execute("""
                    SELECT action_date 
                    FROM history 
                    WHERE personnel_id = %s AND action_id = 3
                    ORDER BY action_date ASC
                """, (personnel_id,))
                dismissal_dates = [row['action_date'] for row in cursor.fetchall()]
            
            # Calculate total service time by pairing hirings with dismissals
            total_days = 0
            
            for i, hire_date in enumerate(hiring_dates):
                # Find corresponding dismissal (or use current time if still serving)
                if i < len(dismissal_dates):
                    dismiss_date = dismissal_dates[i]
                else:
                    # Currently serving, use current time
                    dismiss_date = datetime.now()
                
                # Calculate days for this service period
                service_period = (dismiss_date - hire_date).days
                total_days += service_period
            
            print(f"📊 Calculated service time for personnel {personnel_id}: {total_days} days")
            print(f"   Hirings: {len(hiring_dates)}, Dismissals: {len(dismissal_dates)}")
            
            return total_days
            
        except Exception as e:
            print(f"❌ Error calculating service time: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
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
            embed = discord.Embed(
                title="📋 Новое дело",
                color=0xED4245  # Red color
            )
            
            embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
            
            # Field 1: Кто выдаёт
            embed.add_field(
                name="**1. Кто выдаёт**",
                value=moderator_display,
                inline=False
            )
            
            # Field 2: Кому
            embed.add_field(
                name="**2. Кому**",
                value=target_display,
                inline=False
            )
            
            # Field 3: Причина
            embed.add_field(
                name="**3. Причина**",
                value="Неустойка",
                inline=False
            )
            
            # Fields 4-5: Даты (inline для двух столбцов)
            embed.add_field(
                name="**4. Дата начала**",
                value=start_date_str,
                inline=True
            )
            
            embed.add_field(
                name="**5. Дата окончания**",
                value=end_date_str,
                inline=True
            )
            
            # Field 6: Доказательства
            embed.add_field(
                name="**6. Доказательства**",
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
            # Calculate total service time
            total_days = await self.calculate_total_service_time(personnel_id)
            
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
                    self.invalidate_blacklist_cache(target_user.id)
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
    
    async def check_active_blacklist(self, discord_id: int) -> Optional[Dict[str, Any]]:
        """
        Check if user has an active blacklist entry (with caching).
        
        Cache TTL: 60 seconds - reduces DB load for frequent checks.
        Cache is automatically invalidated when blacklist is added/removed.
        
        Args:
            discord_id: Discord ID of user to check
            
        Returns:
            Dict with blacklist info if active blacklist exists, None otherwise.
            Dict contains: id, reason, start_date, end_date, full_name, static
        """
        try:
            # Check cache first
            now = datetime.now()
            if discord_id in self._blacklist_cache:
                cache_age = (now - self._blacklist_cache_timestamps.get(discord_id, now)).total_seconds()
                if cache_age < self._blacklist_cache_ttl:
                    cached_result = self._blacklist_cache[discord_id]
                    print(f"✅ Blacklist check (CACHED): discord_id={discord_id}, active={cached_result is not None}")
                    return cached_result
            
            # Optimized query - fetch individual columns instead of string concatenation
            from utils.postgresql_pool import get_db_cursor
            
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        bl.id,
                        bl.reason,
                        bl.start_date,
                        bl.end_date,
                        p.first_name,
                        p.last_name,
                        p.static
                    FROM blacklist bl
                    INNER JOIN personnel p ON bl.personnel_id = p.id
                    WHERE p.discord_id = %s 
                      AND bl.is_active = true
                    ORDER BY bl.start_date DESC
                    LIMIT 1;
                """, (discord_id,))
                
                result = cursor.fetchone()
                
                if result:
                    # Construct full_name in Python (faster than SQL concatenation)
                    full_name = f"{result['first_name']} {result['last_name']}".strip()
                    
                    blacklist_info = {
                        'id': result['id'],
                        'reason': result['reason'],
                        'start_date': result['start_date'],
                        'end_date': result['end_date'],
                        'full_name': full_name,
                        'static': result['static']
                    }
                    
                    # Cache the positive result
                    self._blacklist_cache[discord_id] = blacklist_info
                    self._blacklist_cache_timestamps[discord_id] = now
                    
                    print(f"✅ Blacklist check (DB): discord_id={discord_id}, active=True")
                    return blacklist_info
                else:
                    # Cache negative result too (prevents repeated queries for clean users)
                    self._blacklist_cache[discord_id] = None
                    self._blacklist_cache_timestamps[discord_id] = now
                    
                    print(f"✅ Blacklist check (DB): discord_id={discord_id}, active=False")
                    return None
                    
        except Exception as e:
            print(f"❌ Error checking active blacklist: {e}")
            import traceback
            traceback.print_exc()
            # Don't cache errors - allow retry on next call
            return None
    
    def invalidate_blacklist_cache(self, discord_id: int = None):
        """
        Invalidate blacklist cache for a specific user or all users.
        
        Call this after:
        - Adding someone to blacklist (/чс)
        - Removing someone from blacklist (/чс-удалить)
        - Automatic blacklist addition (dismissal < 5 days)
        
        Args:
            discord_id: Specific user to invalidate, or None for full cache clear
        """
        if discord_id is not None:
            self._blacklist_cache.pop(discord_id, None)
            self._blacklist_cache_timestamps.pop(discord_id, None)
            print(f"🔄 Blacklist cache invalidated for discord_id={discord_id}")
        else:
            self._blacklist_cache.clear()
            self._blacklist_cache_timestamps.clear()
            print("🔄 Blacklist cache fully cleared")
    
    async def log_name_change_action(self, personnel_id: int, 
                                    old_first_name: str, old_last_name: str, old_static: str,
                                    new_first_name: str, new_last_name: str, new_static: str,
                                    moderator_discord_id: int):
        """
        Логирование изменения ФИО в таблицу history.
        
        Args:
            personnel_id: ID записи в таблице personnel
            old_first_name: Старое имя
            old_last_name: Старая фамилия  
            old_static: Старый статик
            new_first_name: Новое имя
            new_last_name: Новая фамилия
            new_static: Новый статик
            moderator_discord_id: Discord ID модератора
        """
        try:
            from utils.postgresql_pool import get_db_cursor
            import json
            
            print(f"🔍 HISTORY: Начинаем log_name_change_action для personnel_id {personnel_id}")
            
            with get_db_cursor() as cursor:
                print(f"🔍 HISTORY: Получили DB cursor")
                # Находим модератора в таблице personnel
                if moderator_discord_id == 0:
                    performed_by_id = 0  # Fallback
                    print(f"🔍 HISTORY: Используем performed_by_id = 0 (fallback)")
                else:
                    print(f"🔍 HISTORY: Ищем модератора {moderator_discord_id} в personnel...")
                    cursor.execute("SELECT id FROM personnel WHERE discord_id = %s;", (moderator_discord_id,))
                    moderator_personnel = cursor.fetchone()
                    
                    if not moderator_personnel:
                        # Если модератор не найден в personnel, создаем запись с ID 0
                        print(f"Warning: Модератор {moderator_discord_id} не найден в personnel, используем ID 0")
                        performed_by_id = 0
                    else:
                        performed_by_id = moderator_personnel['id']
                        print(f"🔍 HISTORY: Найден модератор с personnel_id {performed_by_id}")
                
                # Формируем детали изменения
                details = f"Изменение ФИО: {old_first_name} {old_last_name} → {new_first_name} {new_last_name}"
                if old_static != new_static:
                    details += f", статик: {old_static or 'отсутствует'} → {new_static or 'отсутствует'}"
                
                print(f"🔍 HISTORY: Детали: {details}")
                
                # Формируем changes в формате JSON
                changes = {
                    "first_name": {
                        "previous": old_first_name,
                        "new": new_first_name
                    },
                    "last_name": {
                        "previous": old_last_name,
                        "new": new_last_name
                    }
                }
                
                if old_static != new_static:
                    changes["static"] = {
                        "previous": old_static,
                        "new": new_static
                    }
                
                print(f"🔍 HISTORY: Changes сформированы")
                
                # Ищем action_id для "Внесение изменений в Имя или Фамилию"
                print(f"🔍 HISTORY: Ищем action_id...")
                cursor.execute("SELECT id FROM actions WHERE name = %s;", ("Внесение изменений в Имя или Фамилию",))
                action_result = cursor.fetchone()
                
                if action_result:
                    action_id = action_result['id']
                    print(f"🔍 HISTORY: Найден action_id {action_id}")
                else:
                    # Создаем новое действие если его нет
                    print(f"🔍 HISTORY: Создаем новое действие...")
                    cursor.execute("""
                        INSERT INTO actions (name) VALUES (%s) RETURNING id;
                    """, ("Внесение изменений в Имя или Фамилию",))
                    action_id = cursor.fetchone()['id']
                    print(f"Создано новое действие 'Внесение изменений в Имя или Фамилию' с ID {action_id}")
                
                # Записываем в историю
                print(f"🔍 HISTORY: Записываем в history...")
                action_date = datetime.now()
                changes_json = json.dumps(changes)
                print(f"🔍 HISTORY: Параметры INSERT:")
                print(f"  - action_date: {action_date} (type: {type(action_date)})")
                print(f"  - details: '{details}' (type: {type(details)})")
                print(f"  - performed_by: {performed_by_id} (type: {type(performed_by_id)})")
                print(f"  - action_id: {action_id} (type: {type(action_id)})")
                print(f"  - personnel_id: {personnel_id} (type: {type(personnel_id)})")
                print(f"  - changes: {changes_json} (type: {type(changes_json)}, length: {len(changes_json)})")
                
                try:
                    # ВРЕМЕННО: Попробуем INSERT без changes для диагностики
                    print(f"🔍 HISTORY: Пробуем INSERT без changes...")
                    cursor.execute("""
                        INSERT INTO history (
                            action_date, details, performed_by, action_id, personnel_id
                        ) VALUES (%s, %s, %s, %s, %s);
                    """, (
                        action_date,
                        details,
                        performed_by_id,
                        action_id,
                        personnel_id
                    ))
                    
                    print(f"🔍 HISTORY: INSERT без changes выполнен успешно!")
                    
                    # Теперь попробуем UPDATE с changes
                    print(f"🔍 HISTORY: Пробуем UPDATE с changes...")
                    cursor.execute("""
                        UPDATE history 
                        SET changes = %s 
                        WHERE personnel_id = %s AND action_id = %s AND action_date = %s;
                    """, (
                        changes_json,
                        personnel_id,
                        action_id,
                        action_date
                    ))
                    
                    print(f"🔍 HISTORY: UPDATE с changes выполнен успешно!")
                    print(f"✅ Записано в историю: изменение ФИО для personnel_id {personnel_id}, действие выполнил: {performed_by_id}")
                    
                except Exception as insert_error:
                    print(f"❌ HISTORY INSERT ERROR: {insert_error}")
                    import traceback
                    traceback.print_exc()
                    
                    # Попробуем простейший INSERT
                    print(f"🔍 HISTORY: Пробуем минимальный INSERT...")
                    try:
                        cursor.execute("""
                            INSERT INTO history (personnel_id, action_id, performed_by, action_date)
                            VALUES (%s, %s, %s, %s);
                        """, (personnel_id, action_id, performed_by_id, action_date))
                        print(f"✅ HISTORY: Минимальный INSERT выполнен успешно!")
                    except Exception as min_error:
                        print(f"❌ HISTORY MINIMAL INSERT ERROR: {min_error}")
                        import traceback
                        traceback.print_exc()
                        raise insert_error
                
                print(f"🔍 HISTORY: log_name_change_action ЗАВЕРШЕН")
                
        except Exception as e:
            print(f"❌ Ошибка логирования изменения ФИО в историю: {e}")
            import traceback
            traceback.print_exc()
            # Не прерываем выполнение, если история не записалась
    
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
                await self.log_name_change_action(
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
        
        # Убираем все нецифровые символы
        digits_only = ''.join(filter(str.isdigit, static))
        print(f"🔍 FORMAT_STATIC: Только цифры: '{digits_only}' (длина: {len(digits_only)})")
        
        # Проверяем длину
        if len(digits_only) == 6:
            # Форматируем как XXX-XXX
            result = f"{digits_only[:3]}-{digits_only[3:]}"
            print(f"🔍 FORMAT_STATIC: 6 цифр -> XXX-XXX: '{result}'")
            return result
        elif len(digits_only) == 5:
            # Форматируем как XX-XXX
            result = f"{digits_only[:2]}-{digits_only[2:]}"
            print(f"🔍 FORMAT_STATIC: 5 цифр -> XX-XXX: '{result}'")
            return result
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
            from utils.postgresql_pool import get_db_cursor
            from datetime import timedelta
            
            # Load config if not provided
            if not config:
                from utils.config_manager import load_config
                config = load_config()
            
            # Check if user already has active blacklist
            existing_blacklist = await self.check_active_blacklist(target_user.id)
            if existing_blacklist:
                return False, (
                    f"❌ Пользователь **{existing_blacklist['full_name']}** "
                    f"уже находится в чёрном списке.\n\n"
                    f"**Текущая запись:**\n"
                    f"• Причина: {existing_blacklist['reason']}\n"
                    f"• Период: {existing_blacklist['start_date'].strftime('%d.%m.%Y')} - "
                    f"{existing_blacklist['end_date'].strftime('%d.%m.%Y')}\n\n"
                    f"Используйте `/чс-удалить` для удаления существующей записи."
                )
            
            # Get target user's personnel_id and data
            personnel_id = None
            personnel_data = {}
            
            try:
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        SELECT id, first_name, last_name, static
                        FROM personnel
                        WHERE discord_id = %s;
                    """, (target_user.id,))
                    
                    result = cursor.fetchone()
                    if result:
                        personnel_id = result['id']
                        personnel_data = {
                            'name': f"{result['first_name']} {result['last_name']}",
                            'static': result['static'] or ''
                        }
                    else:
                        # User not in personnel database - create basic entry
                        return False, (
                            f"❌ Пользователь **{target_user.display_name}** "
                            f"не найден в базе данных личного состава.\n\n"
                            f"Добавление в чёрный список возможно только для пользователей, "
                            f"имеющих запись в базе данных."
                        )
            except Exception as e:
                print(f"❌ Error getting personnel data: {e}")
                return False, f"❌ Ошибка при получении данных пользователя: {e}"
            
            # Get moderator's personnel_id for "added_by"
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
            except Exception as e:
                print(f"⚠️ Error getting moderator personnel_id: {e}")
            
            # Prepare dates (Moscow timezone UTC+3)
            moscow_tz = timezone(timedelta(hours=3))
            start_date = datetime.now(moscow_tz)
            end_date = start_date + timedelta(days=duration_days)
            
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
                        reason,  # reason from parameter
                        start_date,  # start_date
                        end_date,  # end_date
                        start_date,  # last_updated
                        True,  # is_active
                        personnel_id,  # personnel_id (target user)
                        moderator_personnel_id  # added_by (moderator)
                    ))
                    
                    blacklist_id = cursor.fetchone()['id']
                    print(f"✅ Added manual blacklist record #{blacklist_id} for personnel {personnel_id}")
                    
            except Exception as e:
                print(f"❌ Error adding blacklist record: {e}")
                import traceback
                traceback.print_exc()
                return False, f"❌ Ошибка при добавлении в базу данных: {e}"
            
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
            target_display = f"{personnel_data['name']} | {personnel_data['static']}" if personnel_data['static'] else personnel_data['name']
            
            # Format dates
            start_date_str = start_date.strftime('%d.%m.%Y')
            end_date_str = end_date.strftime('%d.%m.%Y')
            timestamp_str = start_date.strftime('%d.%m.%Y %H:%M')
            
            # Create embed
            embed = discord.Embed(
                title="📋 Новое дело",
                color=0xED4245  # Red color
            )
            
            embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
            
            embed.add_field(name="**1. Кто выдаёт**", value=moderator_display, inline=False)
            embed.add_field(name="**2. Кому**", value=target_display, inline=False)
            embed.add_field(name="**3. Причина**", value=reason, inline=False)
            embed.add_field(name="**4. Дата начала**", value=start_date_str, inline=True)
            embed.add_field(name="**5. Дата окончания**", value=end_date_str, inline=True)
            embed.add_field(name="**6. Доказательства**", value=evidence_url if evidence_url else "Не указано", inline=False)
            
            embed.set_footer(text=timestamp_str)
            
            # Get ping roles
            blacklist_ping_roles = config.get('blacklist_role_mentions', [])
            ping_content = " ".join([f"<@&{role_id}>" for role_id in blacklist_ping_roles])
            
            # Send to blacklist channel
            blacklist_message = await blacklist_channel.send(
                content="-# " + ping_content if ping_content else None,
                embed=embed
            )
            
            # Invalidate cache
            self.invalidate_blacklist_cache(target_user.id)
            
            success_message = (
                f"✅ Пользователь **{personnel_data['name']}** успешно добавлен в чёрный список.\n\n"
                f"**Детали:**\n"
                f"• Статик: {personnel_data['static']}\n"
                f"• Причина: {reason}\n"
                f"• Период: {start_date_str} - {end_date_str}\n"
                f"• Модератор: {moderator_display}\n\n"
                f"[Перейти к сообщению в чёрном списке]({blacklist_message.jump_url})"
            )
            
            print(f"✅ Manual blacklist added for {personnel_data['name']} by {moderator.display_name}")
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
        
        Args:
            discord_id: Discord ID of user to remove from blacklist
            moderator: Moderator performing the removal
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            from utils.postgresql_pool import get_db_cursor
            
            # Check if user has active blacklist
            blacklist_info = await self.check_active_blacklist(discord_id)
            
            if not blacklist_info:
                return False, "Пользователь не найден в активном чёрном списке."
            
            # Delete blacklist entry completely
            with get_db_cursor() as cursor:
                cursor.execute("""
                    DELETE FROM blacklist
                    WHERE id = %s;
                """, (blacklist_info['id'],))
            
            # Invalidate cache for this user
            self.invalidate_blacklist_cache(discord_id)
            
            success_message = (
                f"✅ Пользователь **{blacklist_info['full_name']}** ({blacklist_info['static']}) "
                f"успешно удалён из чёрного списка.\n\n"
                f"**Детали удалённой записи:**\n"
                f"• Причина: {blacklist_info['reason']}\n"
                f"• Дата начала: {blacklist_info['start_date'].strftime('%d.%m.%Y')}\n"
                f"• Дата окончания: {blacklist_info['end_date'].strftime('%d.%m.%Y')}\n"
                f"• Снял с чёрного списка: {moderator.display_name}"
            )
            
            print(f"✅ Blacklist DELETED for discord_id={discord_id} by {moderator.display_name}")
            return True, success_message
            
        except Exception as e:
            error_msg = f"❌ Ошибка при удалении из чёрного списка: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return False, error_msg


# Global instance for easy access
audit_logger = PersonnelAuditLogger()
