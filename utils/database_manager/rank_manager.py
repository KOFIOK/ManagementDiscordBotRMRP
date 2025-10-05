"""
Rank Management System for PostgreSQL Integration

This module provides functionality for managing ranks with automatic synchronization
between config.json and the PostgreSQL ranks table.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from ..postgresql_pool import get_db_cursor
from utils.config_manager import load_config, save_config

logger = logging.getLogger(__name__)


class RankManager:
    """Advanced rank management with PostgreSQL integration"""
    
    def __init__(self):
        logger.info("RankManager инициализирован")
    
    async def add_rank_to_database(self, rank_name: str, role_id: int, rank_level: int) -> Tuple[bool, str]:
        """
        Add rank to database when added through /settings
        
        Args:
            rank_name: Name of the rank (e.g., "Рядовой")
            role_id: Discord role ID 
            rank_level: Rank hierarchy level
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            with get_db_cursor() as cursor:
                # Check if rank already exists
                cursor.execute("SELECT id FROM ranks WHERE name = %s;", (rank_name,))
                existing_rank = cursor.fetchone()
                
                if existing_rank:
                    # Update existing rank with role_id and level
                    cursor.execute("""
                        UPDATE ranks 
                        SET role_id = %s, rank_level = %s
                        WHERE name = %s;
                    """, (role_id, rank_level, rank_name))
                    
                    message = f"Ранг '{rank_name}' обновлен в базе данных"
                    logger.info(f"Updated rank in DB: {rank_name} -> role_id: {role_id}, level: {rank_level}")
                else:
                    # Insert new rank
                    cursor.execute("""
                        INSERT INTO ranks (name, role_id, rank_level)
                        VALUES (%s, %s, %s);
                    """, (rank_name, role_id, rank_level))
                    
                    message = f"Ранг '{rank_name}' добавлен в базу данных"
                    logger.info(f"Added new rank to DB: {rank_name} -> role_id: {role_id}, level: {rank_level}")
                
                return True, message
                
        except Exception as e:
            error_msg = f"Ошибка при добавлении ранга в БД: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def remove_rank_from_database(self, rank_name: str) -> Tuple[bool, str]:
        """
        Remove or deactivate rank in database when removed through /settings
        
        Args:
            rank_name: Name of the rank to remove
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            with get_db_cursor() as cursor:
                # Check if rank exists and is used by any personnel
                cursor.execute("""
                    SELECT COUNT(*) as usage_count 
                    FROM employees e
                    JOIN ranks r ON e.rank_id = r.id
                    WHERE r.name = %s;
                """, (rank_name,))
                
                usage_result = cursor.fetchone()
                usage_count = usage_result['usage_count'] if usage_result else 0
                
                if usage_count > 0:
                    # Don't delete, just deactivate by setting role_id = NULL
                    cursor.execute("""
                        UPDATE ranks 
                        SET role_id = NULL
                        WHERE name = %s;
                    """, (rank_name,))
                    
                    message = f"Ранг '{rank_name}' деактивирован (используется {usage_count} сотрудниками)"
                    logger.info(f"Deactivated rank in DB: {rank_name} (used by {usage_count} employees)")
                else:
                    # Safe to delete
                    cursor.execute("DELETE FROM ranks WHERE name = %s;", (rank_name,))
                    
                    message = f"Ранг '{rank_name}' удален из базы данных"
                    logger.info(f"Deleted rank from DB: {rank_name}")
                
                return True, message
                
        except Exception as e:
            error_msg = f"Ошибка при удалении ранга из БД: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def sync_database_to_config(self) -> Tuple[bool, str]:
        """
        Synchronize all ranks from PostgreSQL database to config.json
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Get all active ranks from database
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT name, role_id, rank_level
                    FROM ranks 
                    WHERE role_id IS NOT NULL
                    ORDER BY rank_level;
                """)
                
                db_ranks = cursor.fetchall()
            
            if not db_ranks:
                return True, "Нет активных рангов в базе данных для синхронизации"
            
            # Load current config
            config = load_config()
            
            # Update rank_roles from database
            config['rank_roles'] = {}
            synced_count = 0
            
            for rank_row in db_ranks:
                rank_name = rank_row['name']
                role_id = rank_row['role_id']
                rank_level = rank_row['rank_level']
                
                config['rank_roles'][rank_name] = {
                    'role_id': role_id,
                    'rank_level': rank_level
                }
                synced_count += 1
                logger.info(f"Synced from DB to config: {rank_name} -> role_id: {role_id}, level: {rank_level}")
            
            # Save updated config
            save_config(config)
            
            message = f"Загружено {synced_count} рангов из базы данных в конфигурацию"
            logger.info(message)
            return True, message
            
        except Exception as e:
            error_msg = f"Ошибка при загрузке рангов из БД: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def sync_config_to_database(self) -> Tuple[bool, str]:
        """
        Synchronize all ranks from config.json to database
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            config = load_config()
            rank_roles = config.get('rank_roles', {})
            
            if not rank_roles:
                return True, "Нет рангов в конфигурации для синхронизации"
            
            synced_count = 0
            for rank_name, rank_data in rank_roles.items():
                if isinstance(rank_data, dict):
                    role_id = rank_data.get('role_id')
                    rank_level = rank_data.get('rank_level')
                    
                    if role_id and rank_level:
                        success, _ = await self.add_rank_to_database(rank_name, role_id, rank_level)
                        if success:
                            synced_count += 1
            
            message = f"Синхронизировано {synced_count} рангов из конфигурации в БД"
            logger.info(message)
            return True, message
            
        except Exception as e:
            error_msg = f"Ошибка при синхронизации рангов: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def get_all_active_ranks(self) -> List[Dict[str, Any]]:
        """
        Get all active ranks from database
        
        Returns:
            List of rank dictionaries
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, role_id, rank_level
                    FROM ranks 
                    WHERE role_id IS NOT NULL
                    ORDER BY rank_level;
                """)
                
                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
                
        except Exception as e:
            logger.error(f"Error getting active ranks: {e}")
            return []
    
    async def get_next_rank(self, current_rank_name: str) -> Optional[str]:
        """
        Get next rank in hierarchy
        
        Args:
            current_rank_name: Current rank name
            
        Returns:
            Next rank name or None if at highest level
        """
        try:
            with get_db_cursor() as cursor:
                # Get current rank level
                cursor.execute("""
                    SELECT rank_level 
                    FROM ranks 
                    WHERE name = %s AND role_id IS NOT NULL;
                """, (current_rank_name,))
                
                current_result = cursor.fetchone()
                if not current_result:
                    return None
                
                current_level = current_result['rank_level']
                
                # Get next rank
                cursor.execute("""
                    SELECT name 
                    FROM ranks 
                    WHERE rank_level > %s AND role_id IS NOT NULL
                    ORDER BY rank_level 
                    LIMIT 1;
                """, (current_level,))
                
                next_result = cursor.fetchone()
                return next_result['name'] if next_result else None
                
        except Exception as e:
            logger.error(f"Error getting next rank for '{current_rank_name}': {e}")
            return None
    
    async def get_previous_rank(self, current_rank_name: str) -> Optional[str]:
        """
        Get previous rank in hierarchy (for demotions)
        
        Args:
            current_rank_name: Current rank name
            
        Returns:
            Previous rank name or None if at lowest level
        """
        try:
            with get_db_cursor() as cursor:
                # Get current rank level
                cursor.execute("""
                    SELECT rank_level 
                    FROM ranks 
                    WHERE name = %s AND role_id IS NOT NULL;
                """, (current_rank_name,))
                
                current_result = cursor.fetchone()
                if not current_result:
                    return None
                
                current_level = current_result['rank_level']
                
                # Get previous rank
                cursor.execute("""
                    SELECT name 
                    FROM ranks 
                    WHERE rank_level < %s AND role_id IS NOT NULL
                    ORDER BY rank_level DESC
                    LIMIT 1;
                """, (current_level,))
                
                prev_result = cursor.fetchone()
                return prev_result['name'] if prev_result else None
                
        except Exception as e:
            logger.error(f"Error getting previous rank for '{current_rank_name}': {e}")
            return None
    
    async def update_user_rank_roles(self, guild, user, old_rank_name: str, new_rank_name: str) -> Tuple[bool, str]:
        """
        Update Discord rank roles for user
        
        Args:
            guild: Discord guild
            user: Discord user/member
            old_rank_name: Previous rank name
            new_rank_name: New rank name
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Get rank data from database
            old_rank_data = self.get_rank_by_name(old_rank_name) if old_rank_name else None
            new_rank_data = self.get_rank_by_name(new_rank_name)
            
            if not new_rank_data:
                return False, f"Новый ранг '{new_rank_name}' не найден в БД"
            
            # Remove old rank role
            if old_rank_data and old_rank_data.get('role_id'):
                old_role = guild.get_role(old_rank_data['role_id'])
                if old_role and old_role in user.roles:
                    await user.remove_roles(old_role, reason=f"Смена ранга: {old_rank_name} -> {new_rank_name}")
                    logger.info(f"✅ Removed old rank role {old_role.name} from {user.display_name}")
                else:
                    logger.info(f"⚠️ Old role not found or not assigned: role_id={old_rank_data.get('role_id')}")
            else:
                logger.info(f"⚠️ No old rank data to remove: {old_rank_name}")
            
            # Add new rank role
            if new_rank_data.get('role_id'):
                new_role = guild.get_role(new_rank_data['role_id'])
                if new_role and new_role not in user.roles:
                    await user.add_roles(new_role, reason=f"Смена ранга: {old_rank_name} -> {new_rank_name}")
                    logger.info(f"✅ Added new rank role {new_role.name} to {user.display_name}")
                    
                    return True, f"Роли обновлены: {old_rank_name} -> {new_rank_name}"
                elif new_role:
                    logger.info(f"⚠️ New role already assigned: {new_role.name}")
                    return True, f"Роль уже назначена: {new_rank_name}"
                else:
                    return False, f"Роль для ранга '{new_rank_name}' не найдена на сервере (ID: {new_rank_data['role_id']})"
            else:
                return False, f"У ранга '{new_rank_name}' не настроена роль"
                
        except Exception as e:
            error_msg = f"Ошибка обновления ролей: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def get_rank_by_name(self, rank_name: str) -> Optional[Dict[str, Any]]:
        """
        Get rank information by name from database
        
        Args:
            rank_name (str): Name of the rank to get
            
        Returns:
            Optional[Dict[str, Any]]: Rank data or None if not found
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT name, role_id, rank_level, abbreviation
                    FROM ranks 
                    WHERE name = %s AND role_id IS NOT NULL;
                """, (rank_name,))
                
                result = cursor.fetchone()
                
                if result:
                    return {
                        'name': result['name'],
                        'role_id': result['role_id'],
                        'rank_level': result['rank_level'],
                        'abbreviation': result.get('abbreviation', rank_name[:3].upper())
                    }
                    
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения ранга {rank_name}: {str(e)}")
            return None


# Global instance
rank_manager = RankManager()