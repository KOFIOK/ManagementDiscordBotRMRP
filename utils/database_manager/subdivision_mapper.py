"""
Subdivision Mapper Utility

Maps config.json subdivision data with database subdivision records.
Provides combined subdivision information for Discord operations.

НОВАЯ АРХИТЕКТУРА:
• PostgreSQL: базовые данные (id, name, abbreviation) 
• config.json: настройки Discord (description, color, emoji, channels, pings)
• position_subdivision: связи ролей с подразделениями
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from ..postgresql_pool import get_db_cursor
from .. import config_manager

logger = logging.getLogger(__name__)


class SubdivisionMapper:
    """Maps between config.json departments and database subdivisions"""
    
    def __init__(self):
        self._subdivision_cache = {}
        self._config_cache = {}
        
        # Отображение аббревиатур БД -> ключи config.json
        self.abbreviation_mapping = {
            "УВП": "УВП",        # Управление Военной Полиции
            "CCO": "ССО",        # Силы Специальных Операций -> ССО 
            "POиO": "РОиО",      # Рота Охраны и Обеспечения -> РОиО
            "BK": "ВК",          # Военный Комиссариат -> ВК
            "MP": "МР",          # Медицинская Рота -> МР
            "Штаб": "genshtab",  # Генеральный Штаб -> genshtab
            "ВА": "ВА",          # Военная Академия
            "ВБП": "ВБП"         # Временно Без Подразделения
        }
        
        # Обратное отображение для поиска
        self.config_to_db_mapping = {v: k for k, v in self.abbreviation_mapping.items()}
    
    async def get_subdivision_with_config(self, subdivision_identifier: str, config: Dict) -> Optional[Dict[str, Any]]:
        """
        Get subdivision data combined with Discord config
        
        Args:
            subdivision_identifier: Subdivision name, abbreviation, or config key
            config: Bot configuration containing departments
            
        Returns:
            Dict containing both DB and config data, or None if not found
        """
        try:
            # Get DB subdivision data
            db_subdivision = await self._get_db_subdivision(subdivision_identifier)
            if not db_subdivision:
                return None
            
            # Get corresponding config data
            config_data = self._get_config_for_subdivision(db_subdivision, config)
            
            # Combine data
            return {
                'id': db_subdivision['id'],
                'name': db_subdivision['name'],
                'abbreviation': db_subdivision['abbreviation'],
                'discord_config': config_data
            }
            
        except Exception as e:
            logger.error(f"get_subdivision_with_config failed: {e}")
            return None
    
    async def get_all_subdivisions_with_config(self, config: Dict) -> List[Dict[str, Any]]:
        """Get all subdivisions with their Discord config data"""
        try:
            subdivisions = []
            
            # Get all DB subdivisions
            with get_db_cursor() as cursor:
                cursor.execute("SELECT id, name, abbreviation FROM subdivisions ORDER BY name;")
                db_subdivisions = cursor.fetchall()
            
            for db_sub in db_subdivisions:
                config_data = self._get_config_for_subdivision(db_sub, config)
                subdivisions.append({
                    'id': db_sub['id'],
                    'name': db_sub['name'],
                    'abbreviation': db_sub['abbreviation'],
                    'discord_config': config_data
                })
            
            return subdivisions
            
        except Exception as e:
            logger.error(f"get_all_subdivisions_with_config failed: {e}")
            return []
    
    async def _get_db_subdivision(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get subdivision from database by name, abbreviation, or partial match"""
        try:
            with get_db_cursor() as cursor:
                # Try exact match first
                cursor.execute("""
                    SELECT id, name, abbreviation 
                    FROM subdivisions 
                    WHERE name = %s OR abbreviation = %s;
                """, (identifier, identifier))
                result = cursor.fetchone()
                
                if result:
                    return dict(result)
                
                # Try partial match
                cursor.execute("""
                    SELECT id, name, abbreviation 
                    FROM subdivisions 
                    WHERE name ILIKE %s OR abbreviation ILIKE %s
                    LIMIT 1;
                """, (f"%{identifier}%", f"%{identifier}%"))
                result = cursor.fetchone()
                
                return dict(result) if result else None
                
        except Exception as e:
            logger.error(f"_get_db_subdivision failed: {e}")
            return None
    
    def _get_config_for_subdivision(self, db_subdivision: Dict, config: Dict) -> Optional[Dict[str, Any]]:
        """Get Discord config data for subdivision"""
        try:
            departments = config.get('departments', {})
            
            # Look for config entry that matches subdivision name or abbreviation
            for dept_key, dept_config in departments.items():
                dept_name = dept_config.get('name', '')
                dept_abbrev = dept_config.get('abbreviation', '')
                
                # Match by name or abbreviation
                if (dept_name == db_subdivision['name'] or 
                    dept_abbrev == db_subdivision['abbreviation'] or
                    dept_key.lower() == db_subdivision['name'].lower() or
                    dept_key.lower() == db_subdivision['abbreviation'].lower()):
                    
                    return {
                        'config_key': dept_key,
                        'roles': dept_config.get('roles', {}),
                        'channels': dept_config.get('channels', {}),
                        'colors': dept_config.get('colors', {}),
                        'emoji': dept_config.get('emoji', ''),
                        'name': dept_config.get('name', ''),
                        'abbreviation': dept_config.get('abbreviation', '')
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"_get_config_for_subdivision failed: {e}")
            return None
    
    def get_subdivision_choices(self, config: Dict) -> List[Dict[str, str]]:
        """Get subdivision choices for Discord select menus"""
        try:
            choices = []
            departments = config.get('departments', {})
            
            for dept_key, dept_config in departments.items():
                name = dept_config.get('name', dept_key)
                abbreviation = dept_config.get('abbreviation', '')
                emoji = dept_config.get('emoji', '')
                
                display_name = f"{emoji} {name}" if emoji else name
                if abbreviation:
                    display_name += f" ({abbreviation})"
                
                choices.append({
                    'label': display_name,
                    'value': dept_key,
                    'description': f"Подразделение {name}"
                })
            
            return choices
            
        except Exception as e:
            logger.error(f"get_subdivision_choices failed: {e}")
            return []
    
    async def validate_subdivision_exists(self, subdivision_identifier: str) -> bool:
        """Check if subdivision exists in database"""
        try:
            subdivision = await self._get_db_subdivision(subdivision_identifier)
            return subdivision is not None
        except Exception as e:
            logger.error(f"validate_subdivision_exists failed: {e}")
            return False

    # ================================================================
    # 🆕 НОВЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С ПОЗИЦИЯМИ И РОЛЯМИ
    # ================================================================
    
    async def get_subdivision_position_roles(self, identifier: str) -> List[Tuple[int, str]]:
        """
        Получить роли позиций подразделения из position_subdivision
        
        Args:
            identifier: Аббревиатура подразделения (БД) или ключ config.json
            
        Returns:
            List[(role_id, position_name)]
        """
        try:
            # Определяем БД аббревиатуру
            if identifier in self.abbreviation_mapping:
                db_abbreviation = identifier
            elif identifier in self.config_to_db_mapping:
                db_abbreviation = self.config_to_db_mapping[identifier]
            else:
                logger.warning(f"Неизвестный идентификатор подразделения: {identifier}")
                return []
            
            with get_db_cursor() as cursor:
                query = """
                SELECT p.role_id, p.name
                FROM subdivisions s
                JOIN position_subdivision ps ON s.id = ps.subdivision_id
                JOIN positions p ON ps.position_id = p.id
                WHERE s.abbreviation = %s AND p.role_id IS NOT NULL
                ORDER BY p.name;
                """
                
                cursor.execute(query, (db_abbreviation,))
                results = cursor.fetchall()
                
                return [(row['role_id'], row['name']) for row in results]
                
        except Exception as e:
            logger.error(f"Ошибка получения ролей {identifier}: {e}")
            return []
    
    async def get_subdivision_full_data(self, identifier: str) -> Optional[Dict]:
        """
        Получить полную информацию о подразделении (БД + config.json + позиции)
        
        Args:
            identifier: Аббревиатура подразделения (БД) или ключ config.json
            
        Returns:
            Dict с полными данными или None
        """
        try:
            # Определяем БД аббревиатуру и config ключ
            if identifier in self.abbreviation_mapping:
                # Это БД аббревиатура
                db_abbreviation = identifier
                config_key = self.abbreviation_mapping[identifier]
            elif identifier in self.config_to_db_mapping:
                # Это config ключ
                config_key = identifier
                db_abbreviation = self.config_to_db_mapping[identifier]
            else:
                logger.warning(f"Неизвестный идентификатор подразделения: {identifier}")
                return None
            
            # Получаем базовые данные из БД + позиции
            with get_db_cursor() as cursor:
                query = """
                SELECT s.id, s.name, s.abbreviation,
                       ARRAY_AGG(p.role_id ORDER BY p.name) FILTER (WHERE p.role_id IS NOT NULL) as position_role_ids,
                       ARRAY_AGG(p.name ORDER BY p.name) FILTER (WHERE p.role_id IS NOT NULL) as position_names,
                       COUNT(p.id) FILTER (WHERE p.role_id IS NOT NULL) as positions_count
                FROM subdivisions s
                LEFT JOIN position_subdivision ps ON s.id = ps.subdivision_id
                LEFT JOIN positions p ON ps.position_id = p.id
                WHERE s.abbreviation = %s
                GROUP BY s.id, s.name, s.abbreviation;
                """
                
                cursor.execute(query, (db_abbreviation,))
                result = cursor.fetchone()
                
                if not result:
                    logger.warning(f"Подразделение {db_abbreviation} не найдено в БД")
                    return None
            
            # Получаем Discord-настройки из config.json
            config_data = config_manager.load_config().get("departments", {}).get(config_key, {})
            
            # Объединяем данные
            subdivision_data = {
                # Данные из БД (авторитетный источник)
                "id": result['id'],
                "name": result['name'],
                "abbreviation": result['abbreviation'],
                "config_key": config_key,  # Добавляем ключ config.json
                "position_role_ids": list(result['position_role_ids']) if result['position_role_ids'] else [],
                "position_names": list(result['position_names']) if result['position_names'] else [],
                "positions_count": result['positions_count'],
                
                # Данные из config.json (Discord-специфичные)
                "description": config_data.get("description", "Описание отсутствует"),
                "color": config_data.get("color", 0),
                "emoji": config_data.get("emoji", "📁"),
                "is_system": config_data.get("is_system", False),
                "application_channel_id": config_data.get("application_channel_id"),
                "persistent_message_id": config_data.get("persistent_message_id"),
                "ping_contexts": config_data.get("ping_contexts", {}),
                "role_id": config_data.get("role_id")
            }
            
            return subdivision_data
            
        except Exception as e:
            logger.error(f"Ошибка получения полных данных {identifier}: {e}")
            return None
    
    async def get_all_subdivisions_enhanced(self) -> List[Dict]:
        """
        Получить все подразделения с полной информацией (БД + config.json + позиции)
        
        Returns:
            List[Dict] со всеми подразделениями
        """
        try:
            # Получаем все подразделения из БД
            with get_db_cursor() as cursor:
                query = """
                SELECT s.id, s.name, s.abbreviation,
                       COUNT(ps.id) FILTER (WHERE p.role_id IS NOT NULL) as positions_count
                FROM subdivisions s
                LEFT JOIN position_subdivision ps ON s.id = ps.subdivision_id
                LEFT JOIN positions p ON ps.position_id = p.id
                GROUP BY s.id, s.name, s.abbreviation
                ORDER BY s.name;
                """
                
                cursor.execute(query)
                results = cursor.fetchall()
            
            subdivisions = []
            for row in results:
                # Получаем полную информацию для каждого подразделения
                full_data = await self.get_subdivision_full_data(row['abbreviation'])
                if full_data:
                    subdivisions.append(full_data)
            
            return subdivisions
            
        except Exception as e:
            logger.error(f"Ошибка получения всех подразделений: {e}")
            return []
    
    async def validate_subdivision_consistency(self) -> Dict[str, List[str]]:
        """
        Проверить консистентность данных между БД и config.json
        
        Returns:
            Dict с найденными несоответствиями
        """
        issues = {
            "missing_in_db": [],
            "missing_in_config": [],
            "name_mismatch": [],
            "no_positions": [],
            "mapping_issues": []
        }
        
        try:
            # Получаем все подразделения из БД
            with get_db_cursor() as cursor:
                query = """
                SELECT s.abbreviation, s.name,
                       COUNT(ps.id) FILTER (WHERE p.role_id IS NOT NULL) as positions_count
                FROM subdivisions s
                LEFT JOIN position_subdivision ps ON s.id = ps.subdivision_id
                LEFT JOIN positions p ON ps.position_id = p.id
                GROUP BY s.id, s.abbreviation, s.name;
                """
                cursor.execute(query)
                db_results = cursor.fetchall()
            
            db_subdivisions = {row['abbreviation']: {'name': row['name'], 'positions': row['positions_count']} 
                             for row in db_results}
            
            # Получаем все подразделения из config.json
            config_departments = config_manager.load_config().get("departments", {})
            
            # Проверяем отображения
            for db_abbr in db_subdivisions:
                if db_abbr not in self.abbreviation_mapping:
                    issues["mapping_issues"].append(f"БД '{db_abbr}' не имеет отображения в config.json")
                    continue
                
                config_key = self.abbreviation_mapping[db_abbr]
                
                if config_key not in config_departments:
                    issues["missing_in_config"].append(f"'{config_key}' (для БД '{db_abbr}')")
                else:
                    # Проверяем названия
                    db_name = db_subdivisions[db_abbr]['name']
                    config_name = config_departments[config_key].get('name', '')
                    if db_name != config_name:
                        issues["name_mismatch"].append(f"{db_abbr} ({config_key}): БД='{db_name}' vs Config='{config_name}'")
                    
                    # Проверяем наличие активных позиций
                    if db_subdivisions[db_abbr]['positions'] == 0:
                        issues["no_positions"].append(f"{db_abbr} ({config_key})")
            
            # Проверяем config ключи без соответствия в БД
            for config_key in config_departments:
                if config_key not in self.config_to_db_mapping:
                    issues["missing_in_db"].append(f"'{config_key}' не имеет соответствия в БД")
            
            return issues
            
        except Exception as e:
            logger.error(f"Ошибка проверки консистентности: {e}")
            return issues
    
    def update_config_subdivision_data(self, identifier: str, data: Dict) -> bool:
        """
        Обновить данные подразделения в config.json
        
        Args:
            identifier: Аббревиатура подразделения (БД) или ключ config.json
            data: Данные для обновления
            
        Returns:
            bool: Успешность операции
        """
        try:
            # Определяем config ключ
            if identifier in self.abbreviation_mapping:
                config_key = self.abbreviation_mapping[identifier]
            elif identifier in self.config_to_db_mapping:
                config_key = identifier
            else:
                logger.error(f"Неизвестный идентификатор подразделения: {identifier}")
                return False
            
            current_config = config_manager.load_config()
            if "departments" not in current_config:
                current_config["departments"] = {}
            
            current_config["departments"][config_key] = data
            
            success = config_manager.save_config(current_config)
            if success:
                logger.info(f"✅ Данные подразделения {identifier} ({config_key}) обновлены в config.json")
            return success
        except Exception as e:
            logger.error(f"Ошибка обновления config.json для {identifier}: {e}")
            return False

    async def get_subdivision_id(self, identifier: str) -> Optional[int]:
        """Get subdivision ID by name, abbreviation, or config key"""
        try:
            # First try to convert config key to database abbreviation
            db_identifier = identifier
            if identifier in self.config_to_db_mapping:
                db_identifier = self.config_to_db_mapping[identifier]
            
            subdivision = await self._get_db_subdivision(db_identifier)
            return subdivision['id'] if subdivision else None
        except Exception as e:
            logger.error(f"get_subdivision_id failed for identifier '{identifier}': {e}")
            return None