"""
Rank Management System for PostgreSQL Integration

This module provides functionality for managing ranks with automatic synchronization
between config.json and the PostgreSQL ranks table. Provides database operations
for rank CRUD, hierarchy management, and rank data retrieval.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from ..postgresql_pool import get_db_cursor
from utils.config_manager import load_config, save_config
from utils.message_manager import get_role_reason, get_moderator_display_name

logger = logging.getLogger(__name__)


class RankManager:
    """Advanced rank management with PostgreSQL integration
    
    Provides database operations for rank management including CRUD operations,
    hierarchy management, and rank data retrieval. Does not handle Discord
    role assignments - use role_utils.py for that functionality.
    """
    
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
    
    async def get_rank_by_id(self, rank_id: int) -> Optional[Dict[str, Any]]:
        """
        Get rank information by ID from database
        
        Args:
            rank_id (int): ID of the rank to get
            
        Returns:
            Optional[Dict[str, Any]]: Rank data or None if not found
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, role_id, rank_level, abbreviation
                    FROM ranks 
                    WHERE id = %s AND role_id IS NOT NULL;
                """, (rank_id,))
                
                result = cursor.fetchone()
                
                if result:
                    return {
                        'id': result['id'],
                        'name': result['name'],
                        'role_id': result['role_id'],
                        'rank_level': result['rank_level'],
                        'abbreviation': result.get('abbreviation', result['name'][:3].upper())
                    }
                    
                return None
                
        except Exception as e:
            logger.error(f"Error getting rank by ID '{rank_id}': {e}")
            return None
    
    async def get_first_rank(self) -> Optional[Dict[str, Any]]:
        """
        Get the first rank from database (lowest rank level)
        
        Returns:
            Optional[Dict[str, Any]]: First rank data or None if not found
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, role_id, rank_level, abbreviation
                    FROM ranks 
                    WHERE role_id IS NOT NULL
                    ORDER BY rank_level ASC
                    LIMIT 1;
                """)
                
                result = cursor.fetchone()
                
                if result:
                    return {
                        'id': result['id'],
                        'name': result['name'],
                        'role_id': result['role_id'],
                        'rank_level': result['rank_level'],
                        'abbreviation': result.get('abbreviation', result['name'][:3].upper())
                    }
                    
                return None
                
        except Exception as e:
            logger.error(f"Error getting first rank: {e}")
            return None

    async def get_default_recruit_rank(self) -> Optional[str]:
        """
        Get the default recruit rank (lowest rank_level)
        
        Returns:
            Rank name or None if no ranks found
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT name
                    FROM ranks 
                    WHERE role_id IS NOT NULL
                    ORDER BY rank_level ASC
                    LIMIT 1;
                """)
                
                result = cursor.fetchone()
                return result['name'] if result else None
                
        except Exception as e:
            logger.error(f"Ошибка получения начального звания: {str(e)}")
            return None

    def get_default_recruit_rank_sync(self) -> Optional[str]:
        """
        Synchronous version of get_default_recruit_rank
        Use only when async is not possible
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT name
                    FROM ranks
                    WHERE role_id IS NOT NULL
                    ORDER BY rank_level ASC
                    LIMIT 1;
                """)

                result = cursor.fetchone()
                return result['name'] if result else None

        except Exception as e:
            logger.error(f"Ошибка в синхронном получении начального звания: {str(e)}")
            return None

    async def update_rank_in_database(self, rank_name: str, new_role_id: int, new_rank_level: int, new_abbreviation: str = None) -> Tuple[bool, str]:
        """
        Update existing rank in database

        Args:
            rank_name: Name of the rank to update
            new_role_id: New Discord role ID
            new_rank_level: New rank hierarchy level
            new_abbreviation: New rank abbreviation (optional)

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            with get_db_cursor() as cursor:
                # Check if rank exists
                cursor.execute("SELECT id FROM ranks WHERE name = %s;", (rank_name,))
                existing_rank = cursor.fetchone()

                if not existing_rank:
                    return False, f"Ранг '{rank_name}' не найден в базе данных"

                # Update rank
                update_query = """
                    UPDATE ranks
                    SET role_id = %s, rank_level = %s, abbreviation = %s
                    WHERE name = %s;
                """
                cursor.execute(update_query, (new_role_id, new_rank_level, new_abbreviation, rank_name))

                message = f"Ранг '{rank_name}' обновлен в базе данных"
                logger.info(f"Updated rank in DB: {rank_name} -> role_id: {new_role_id}, level: {new_rank_level}, abbr: {new_abbreviation}")
                return True, message

        except Exception as e:
            logger.error(f"Error updating rank '{rank_name}': {e}")
            return False, f"Ошибка при обновлении ранга: {e}"

    async def delete_rank_from_database(self, rank_name: str) -> Tuple[bool, str]:
        """
        Delete rank from database (only removes Discord role association, keeps name for history)

        Args:
            rank_name: Name of the rank to delete

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            with get_db_cursor() as cursor:
                # Check if rank exists
                cursor.execute("SELECT id, role_id FROM ranks WHERE name = %s;", (rank_name,))
                existing_rank = cursor.fetchone()

                if not existing_rank:
                    return False, f"Ранг '{rank_name}' не найден в базе данных"

                if existing_rank['role_id'] is None:
                    return False, f"Ранг '{rank_name}' уже не имеет Discord роли"

                # Remove role association (don't delete the rank completely to preserve history)
                cursor.execute("""
                    UPDATE ranks
                    SET role_id = NULL, abbreviation = NULL
                    WHERE name = %s;
                """, (rank_name,))

                message = f"Discord роль ранга '{rank_name}' удалена из базы данных"
                logger.info(f"Removed Discord role from rank: {rank_name}")
                return True, message

        except Exception as e:
            logger.error(f"Error deleting rank '{rank_name}': {e}")
            return False, f"Ошибка при удалении ранга: {e}"


# Global instance
rank_manager = RankManager()