"""
Role Utilities

Утилиты для унификации логики управления ролями.
Использует существующие менеджеры без изменения database_manager.
"""

import discord
from typing import List, Set, Optional, Tuple
from utils.message_manager import get_role_reason
from utils.ping_manager import ping_manager
from utils.database_manager import rank_manager, position_service
from utils.config_manager import load_config
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class RoleUtils:
    """
    Утилиты для унификации логики управления ролями.
    Обеспечивает консистентную обработку ролей для всех типов заявок.
    """

    @staticmethod
    async def clear_all_department_roles(user: discord.Member, reason: str = "role_removal.department_change") -> List[str]:
        """
        Удалить ВСЕ роли подразделений у пользователя

        Args:
            user: Discord пользователь
            reason: Причина для аудита

        Returns:
            List[str]: Список удаленных ролей
        """
        removed_roles = []
        all_dept_role_ids = ping_manager.get_all_department_role_ids()

        for role_id in all_dept_role_ids:
            role = user.guild.get_role(role_id)
            if role and role in user.roles:
                try:
                    await user.remove_roles(
                        role,
                        reason=get_role_reason(user.guild.id, reason, "Очистка ролей подразделений").format(moderator="система")
                    )
                    removed_roles.append(role.name)
                except discord.Forbidden:
                    logger.info("Нет прав для удаления роли подразделения %s у %s", role.name, user)
                except Exception as e:
                    logger.error("Ошибка при удалении роли подразделения %s у %s: %s", role.name, user, e)

        return removed_roles

    @staticmethod
    async def clear_all_position_roles(user: discord.Member, reason: str = "role_removal.position_change") -> List[str]:
        """
        Удалить ВСЕ роли должностей у пользователя

        Args:
            user: Discord пользователь
            reason: Причина для аудита

        Returns:
            List[str]: Список удаленных ролей
        """
        removed_roles = []
        
        # Получаем все роли должностей из конфига (assignable роли подразделений)
        all_position_role_ids = ping_manager.get_all_position_role_ids()
        
        # Также получаем все индивидуальные роли должностей из БД
        try:
            from utils.postgresql_pool import get_db_cursor
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT p.role_id 
                    FROM position_subdivision ps
                    JOIN positions p ON ps.position_id = p.id
                    WHERE p.role_id IS NOT NULL
                """)
                db_position_roles = cursor.fetchall()
                # Добавляем роли из БД к списку
                for row in db_position_roles:
                    if row['role_id'] and row['role_id'] not in all_position_role_ids:
                        all_position_role_ids.append(row['role_id'])
        except Exception as e:
            logger.warning("Не удалось получить роли должностей из БД: %s", e)

        for role_id in all_position_role_ids:
            role = user.guild.get_role(role_id)
            if role and role in user.roles:
                try:
                    await user.remove_roles(
                        role,
                        reason=get_role_reason(user.guild.id, reason, "Очистка ролей должностей").format(moderator="система")
                    )
                    removed_roles.append(role.name)
                except discord.Forbidden:
                    logger.info("Нет прав для удаления роли должности %s у %s", role.name, user)
                except Exception as e:
                    logger.error("Ошибка при удалении роли должности %s у %s: %s", role.name, user, e)

        return removed_roles

    @staticmethod
    async def assign_department_role(user: discord.Member, dept_code: str, moderator: discord.Member) -> bool:
        """
        Назначить роль подразделения пользователю

        Args:
            user: Discord пользователь
            dept_code: Код подразделения
            moderator: Модератор, выполняющий действие

        Returns:
            bool: Успешно ли назначена роль
        """
        try:
            dept_role_id = ping_manager.get_department_role_id(dept_code)
            if not dept_role_id:
                logger.info("Роль для подразделения %s не настроена", dept_code)
                return False

            dept_role = user.guild.get_role(dept_role_id)
            if not dept_role:
                logger.info("Роль подразделения %s не найдена на сервере", dept_code)
                return False

            # Получить имя подразделения для причины
            try:
                dept_info = ping_manager.get_department_info(dept_code)
                if isinstance(dept_info, dict):
                    dept_name = dept_info.get('name', dept_code)
                else:
                    dept_name = dept_code
            except Exception as dept_info_error:
                logger.warning("Не удалось получить информацию о подразделении %s: %s", dept_code, dept_info_error)
                dept_name = dept_code

            reason = get_role_reason(
                user.guild.id,
                "department_application.approved",
                f"Заявка в подразделение: одобрена ({dept_name})"
            ).format(moderator=moderator.display_name, department_name=dept_name)

            await user.add_roles(dept_role, reason=reason)
            logger.info("Назначена роль подразделения %s пользователю %s", dept_role.name, user)
            return True

        except Exception as e:
            logger.error("Ошибка при назначении роли подразделения %s пользователю %s: %s", dept_code, user, e)
            return False

    @staticmethod
    async def assign_position_roles(user: discord.Member, dept_code: str, moderator: discord.Member) -> List[str]:
        """
        Назначить роли должностей для подразделения

        Args:
            user: Discord пользователь
            dept_code: Код подразделения
            moderator: Модератор, выполняющий действие

        Returns:
            List[str]: Список назначенных ролей
        """
        assigned_roles = []
        assignable_role_ids = ping_manager.get_department_assignable_position_roles(dept_code)

        if not assignable_role_ids:
            logger.info("Нет настроенных ролей должностей для подразделения %s", dept_code)
            return assigned_roles

        moderator_display = moderator.display_name

        for role_id in assignable_role_ids:
            role = user.guild.get_role(role_id)
            if not role:
                logger.info("Роль с ID %s не найдена на сервере", role_id)
                continue

            if role in user.roles:
                continue  # Уже имеет эту роль

            try:
                reason = get_role_reason(
                    user.guild.id,
                    "role_assignment.position",
                    "Назначение роли должности"
                ).format(moderator=moderator_display)

                await user.add_roles(role, reason=reason)
                assigned_roles.append(role.name)
                logger.info("Назначена роль должности %s пользователю %s", role.name, user)

            except discord.Forbidden:
                logger.info("Нет прав для назначения роли %s пользователю %s", role.name, user)
            except Exception as e:
                logger.error("Ошибка при назначении роли %s пользователю %s: %s", role.name, user, e)

        return assigned_roles

    @staticmethod
    async def smart_update_user_position_roles(guild: discord.Guild, user: discord.Member, 
                                             new_position_id: Optional[int], moderator=None) -> bool:
        """
        Умное обновление ролей должностей - автоматически определить текущие роли и заменить их
        
        Args:
            guild: Discord сервер
            user: Discord пользователь
            new_position_id: ID новой должности (None для снятия всех ролей должностей)
            moderator: Модератор, выполнивший действие
            
        Returns:
            bool: Успешно ли выполнено
        """
        try:
            # Получить отображаемое имя модератора
            from utils.message_manager import get_moderator_display_name
            moderator_display = await get_moderator_display_name(moderator)
            
            # Получить данные о ролях из position_service
            cache_data = position_service.get_position_roles_cache()
            all_position_roles = cache_data['role_to_position']  # {role_id: position_id}
            position_to_role = cache_data['position_to_role']    # {position_id: role_id}
            
            # Получить ID новой роли из кэша
            new_role_id = None
            if new_position_id and new_position_id in position_to_role:
                new_role_id = position_to_role[new_position_id]
            elif new_position_id:
                logger.info("Должность %s не найдена в кэше", new_position_id)
            
            # Найти текущие роли должностей у пользователя
            roles_to_remove = []
            
            for role in user.roles:
                if role.id in all_position_roles:
                    # Удалить только если это не новая роль, которую мы добавляем
                    if role.id != new_role_id:
                        roles_to_remove.append(role)
                    else:
                        logger.info("Сохраняем роль (уже назначена): %s", role.name)
            
            # Пакетные операции с ролями для лучшей производительности
            role_changes = []
            
            # Удалить старые роли должностей
            if roles_to_remove:
                try:
                    reason = get_role_reason(guild.id, "role_removal.position_change", "Смена должности: снята роль").format(moderator=moderator_display)
                    await user.remove_roles(*roles_to_remove, reason=reason)
                    for role in roles_to_remove:
                        logger.info(f" Удалена роль должности: {role.name}")
                        role_changes.append(f"-{role.name}")
                except Exception as e:
                    logger.error("Ошибка при удалении ролей: %s", e)
            
            # Добавить новую роль должности
            if new_position_id and new_role_id:
                # Проверить, есть ли уже эта роль
                has_new_role = any(role.id == new_role_id for role in user.roles)
                
                if not has_new_role:
                    new_role = guild.get_role(new_role_id)
                    if new_role:
                        try:
                            # Получить название должности из базы данных
                            position_data = position_service.get_position_by_id(new_position_id)
                            position_name = position_data['name'] if position_data else f"Должность ID {new_position_id}"
                            
                            reason = get_role_reason(
                                guild.id,
                                "position_assignment.assigned",
                                "Назначение должности"
                            ).format(position=position_name, moderator=moderator_display)
                            await user.add_roles(new_role, reason=reason)
                            role_changes.append(f"+{position_name}")
                        except Exception as e:
                            logger.error("Ошибка при добавлении роли: %s", e)
                    else:
                        logger.info("Роль с ID %s не найдена на сервере", new_role_id)
                else:
                    logger.info("У пользователя уже есть целевая роль")
            
            # Итог
            if role_changes:
                logger.info(f"Изменения ролей: {', '.join(role_changes)}")
            else:
                logger.info(f"Изменения ролей не требуются для {user.display_name}")
            
            return True
            
        except Exception as e:
            logger.error("Ошибка в умном обновлении ролей должностей: %s", e)
            return False

    @staticmethod
    async def assign_military_roles(user: discord.Member, application_data: dict, moderator: discord.Member) -> List[str]:
        """
        Назначить роли для военнослужащего (из конфига + ранг)

        Args:
            user: Discord пользователь
            application_data: Данные заявки
            moderator: Модератор, выполняющий действие

        Returns:
            List[str]: Список назначенных ролей
        """
        assigned_roles = []
        config = load_config()
        role_ids = config.get('military_roles', [])

        moderator_display = moderator.display_name

        # Назначить базовые военные роли
        for role_id in role_ids:
            role = user.guild.get_role(role_id)
            if not role:
                logger.info("Военная роль с ID %s не найдена", role_id)
                continue

            if role in user.roles:
                continue  # Уже имеет эту роль

            try:
                reason = get_role_reason(
                    user.guild.id,
                    "role_assignment.military",
                    "Заявка на роль военнослужащего: одобрена"
                ).format(moderator=moderator_display)

                await user.add_roles(role, reason=reason)
                assigned_roles.append(role.name)
                logger.info("Назначена военная роль %s пользователю %s", role.name, user)

            except discord.Forbidden:
                logger.info("Нет прав для назначения военной роли %s пользователю %s", role.name, user)
            except Exception as e:
                logger.error("Ошибка при назначении военной роли %s пользователю %s: %s", role.name, user, e)

        # Назначить ранг из заявки
        rank_name = application_data.get('rank')
        if rank_name:
            reason = get_role_reason(user.guild.id, "role_assignment.approved", "Заявка на роль: одобрена").format(moderator=moderator.display_name)
            rank_assigned = await RoleUtils.assign_rank_role(user, rank_name, moderator, reason=reason)
            if rank_assigned:
                # Найдем название роли ранга для добавления в список
                from utils.database_manager.rank_manager import rank_manager
                rank_data = rank_manager.get_rank_by_name(rank_name)
                if rank_data and rank_data.get('role_id'):
                    rank_role = user.guild.get_role(rank_data['role_id'])
                    if rank_role:
                        assigned_roles.append(f"{rank_role.name} ({rank_name})")
        else:
            # Если ранг не указан, назначить начальный ранг новобранца
            recruit_assigned = await RoleUtils.assign_default_recruit_rank(user, moderator)
            if recruit_assigned:
                from utils.database_manager.rank_manager import rank_manager
                default_rank = rank_manager.get_default_recruit_rank_sync()
                if default_rank:
                    rank_data = rank_manager.get_rank_by_name(default_rank)
                    if rank_data and rank_data.get('role_id'):
                        rank_role = user.guild.get_role(rank_data['role_id'])
                        if rank_role:
                            assigned_roles.append(f"{rank_role.name} ({default_rank})")

        # Назначить роль подразделения из заявки (если указано)
        subdivision_name = application_data.get('subdivision')
        try:
            logger.debug("ROLE UTILS: subdivision passed to assign_military_roles=%s", subdivision_name or '<none>')
        except Exception:
            pass
        if subdivision_name:
            from utils.postgresql_pool import get_db_cursor
            try:
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        SELECT role_id FROM subdivisions 
                        WHERE name = %s AND role_id IS NOT NULL
                        LIMIT 1
                    """, (subdivision_name,))
                    result = cursor.fetchone()
                    
                    if result:
                        subdivision_role = user.guild.get_role(result['role_id'])
                        if subdivision_role and subdivision_role not in user.roles:
                            try:
                                reason = get_role_reason(
                                    user.guild.id,
                                    "role_assignment.military",
                                    "Заявка на роль военнослужащего: одобрена"
                                ).format(moderator=moderator_display)
                                
                                await user.add_roles(subdivision_role, reason=reason)
                                assigned_roles.append(f"{subdivision_role.name} (подразделение)")
                                logger.info("Назначена роль подразделения %s пользователю %s", subdivision_role.name, user)
                            except discord.Forbidden:
                                logger.info("Нет прав для назначения роли подразделения %s пользователю %s", subdivision_role.name, user)
                            except Exception as e:
                                logger.error("Ошибка при назначении роли подразделения %s пользователю %s: %s", subdivision_role.name, user, e)
                        else:
                            try:
                                logger.info("ROLE UTILS: subdivision role_id=%s not found or role already present", result.get('role_id'))
                            except Exception:
                                pass
            except Exception as e:
                logger.error("Ошибка при получении роли подразделения %s: %s", subdivision_name, e)
        else:
            try:
                logger.info("ROLE UTILS: subdivision missing in application_data; department role will not be assigned")
            except Exception:
                pass

        return assigned_roles

    @staticmethod
    async def assign_civilian_roles(user: discord.Member, application_data: dict, moderator: discord.Member) -> List[str]:
        """
        Назначить роли для госслужащего (из конфига)

        Args:
            user: Discord пользователь
            application_data: Данные заявки
            moderator: Модератор, выполняющий действие

        Returns:
            List[str]: Список назначенных ролей
        """
        assigned_roles = []
        config = load_config()
        role_ids = config.get('civilian_roles', [])

        moderator_display = moderator.display_name

        for role_id in role_ids:
            role = user.guild.get_role(role_id)
            if not role:
                logger.info("Роль госслужащего с ID %s не найдена", role_id)
                continue

            if role in user.roles:
                continue  # Уже имеет эту роль

            try:
                reason = get_role_reason(
                    user.guild.id,
                    "role_assignment.civilian",
                    "Заявка на роль госслужащего: одобрена"
                ).format(moderator=moderator_display)

                await user.add_roles(role, reason=reason)
                assigned_roles.append(role.name)
                logger.info("Назначена роль госслужащего %s пользователю %s", role.name, user)

            except discord.Forbidden:
                logger.info("Нет прав для назначения роли %s пользователю %s", role.name, user)
            except Exception as e:
                logger.error("Ошибка при назначении роли %s пользователю %s: %s", role.name, user, e)

        return assigned_roles

    @staticmethod
    async def assign_supplier_roles(user: discord.Member, application_data: dict, moderator: discord.Member) -> List[str]:
        """
        Назначить роли для поставщика (из конфига)

        Args:
            user: Discord пользователь
            application_data: Данные заявки
            moderator: Модератор, выполняющий действие

        Returns:
            List[str]: Список назначенных ролей
        """
        assigned_roles = []
        config = load_config()
        role_ids = config.get('supplier_roles', [])

        moderator_display = moderator.display_name

        for role_id in role_ids:
            role = user.guild.get_role(role_id)
            if not role:
                logger.info("Роль поставщика с ID %s не найдена", role_id)
                continue

            if role in user.roles:
                continue  # Уже имеет эту роль

            try:
                reason = get_role_reason(
                    user.guild.id,
                    "role_assignment.supplier",
                    "Заявка на доступ к поставкам: одобрена"
                ).format(moderator=moderator_display)

                await user.add_roles(role, reason=reason)
                assigned_roles.append(role.name)
                logger.info("Назначена роль поставщика %s пользователю %s", role.name, user)

            except discord.Forbidden:
                logger.info("Нет прав для назначения роли %s пользователю %s", role.name, user)
            except Exception as e:
                logger.error("Ошибка при назначении роли %s пользователю %s: %s", role.name, user, e)

    @staticmethod
    async def clear_all_rank_roles(user: discord.Member, reason: str = "role_removal.rank_change") -> List[str]:
        """
        Удалить ВСЕ роли рангов у пользователя

        Args:
            user: Discord пользователь
            reason: Причина для аудита

        Returns:
            List[str]: Список удаленных ролей
        """
        removed_roles = []
        all_rank_role_ids = RoleUtils._get_all_rank_role_ids()

        for role_id in all_rank_role_ids:
            role = user.guild.get_role(role_id)
            if role and role in user.roles:
                try:
                    await user.remove_roles(
                        role,
                        reason=get_role_reason(user.guild.id, reason, "Очистка ролей рангов").format(moderator="система")
                    )
                    removed_roles.append(role.name)
                except discord.Forbidden:
                    logger.info("Нет прав для удаления роли ранга %s у %s", role.name, user)
                except Exception as e:
                    logger.error("Ошибка при удалении роли ранга %s у %s: %s", role.name, user, e)

        return removed_roles

    @staticmethod
    async def clear_all_roles(user: discord.Member, reason: str = "role_removal.dismissal", moderator: discord.Member = None) -> List[str]:
        """
        Удалить ВСЕ роли у пользователя (для увольнения)

        Args:
            user: Discord пользователь
            reason: Причина для аудита
            moderator: Модератор, выполняющий действие

        Returns:
            List[str]: Список удаленных ролей
        """
        removed_roles = []

        try:
            # Удалить роли подразделений
            dept_roles = await RoleUtils.clear_all_department_roles(user, reason)
            removed_roles.extend(dept_roles)

            # Удалить роли должностей
            pos_roles = await RoleUtils.clear_all_position_roles(user, reason)
            removed_roles.extend(pos_roles)

            # Удалить роли рангов
            rank_roles = await RoleUtils.clear_all_rank_roles(user, reason)
            removed_roles.extend(rank_roles)

            # Удалить остальные роли (кроме @everyone)
            for role in user.roles:
                if role != user.guild.default_role:  # Не удалять @everyone
                    try:
                        audit_reason = get_role_reason(
                            user.guild.id,
                            reason,
                            "Полное снятие ролей при увольнении"
                        )
                        if moderator:
                            audit_reason = audit_reason.format(moderator=moderator.display_name)
                        else:
                            audit_reason = audit_reason.format(moderator="система")

                        await user.remove_roles(role, reason=audit_reason)
                        removed_roles.append(role.name)
                    except discord.Forbidden:
                        logger.info("Нет прав для удаления роли {role.name} у %s", user)
                    except Exception as e:
                        logger.error("Ошибка при удалении роли {role.name} у %s: %s", user, e)

        except Exception as e:
            logger.error("Ошибка при полном снятии ролей у %s: %s", user, e)

        return removed_roles

    @staticmethod
    def _get_all_rank_role_ids() -> Set[int]:
        """
        Получить все role IDs рангов из базы данных

        Returns:
            Set[int]: Множество ID ролей рангов
        """
        try:
            from utils.postgresql_pool import get_db_cursor
            role_ids = set()
            with get_db_cursor() as cursor:
                cursor.execute("SELECT role_id FROM ranks WHERE role_id IS NOT NULL")
                results = cursor.fetchall()
                for row in results:
                    role_ids.add(row['role_id'])
            return role_ids
        except Exception as e:
            logger.error("Ошибка получения ролей рангов: %s", e)
            return set()

    @staticmethod
    async def assign_rank_role(user: discord.Member, rank_name: str, moderator: discord.Member, reason: str = None) -> bool:
        """
        Назначить роль ранга пользователю

        Args:
            user: Discord пользователь
            rank_name: Название ранга
            moderator: Модератор, выполняющий действие
            reason: Причина назначения роли (опционально)

        Returns:
            bool: Успешно ли назначена роль
        """
        try:
            from utils.database_manager.rank_manager import rank_manager

            # Получить информацию о ранге
            rank_data = rank_manager.get_rank_by_name(rank_name)
            if not rank_data:
                logger.info("Ранг '%s' не найден в базе данных", rank_name)
                return False

            role_id = rank_data.get('role_id')
            if not role_id:
                logger.info("У ранга '%s' не настроена роль Discord", rank_name)
                return False

            role = user.guild.get_role(role_id)
            if not role:
                logger.info("Роль ранга '%s' (ID: %s) не найдена на сервере", rank_name, role_id)
                return False

            # Сначала очистить все роли рангов
            await RoleUtils.clear_all_rank_roles(user, reason="role_removal.rank_change")

            # Назначить новую роль ранга
            audit_reason = get_role_reason(
                user.guild.id,
                "role_assignment.rank",
                f"Назначение ранга: {rank_name}"
            ).format(moderator=moderator.display_name)

            await user.add_roles(role, reason=audit_reason)
            logger.info("Назначена роль ранга %s (%s) пользователю %s", role.name, rank_name, user)
            return True

        except Exception as e:
            logger.error("Ошибка при назначении роли ранга '%s' пользователю %s: %s", rank_name, user, e)
            return False

    @staticmethod
    async def assign_default_recruit_rank(user: discord.Member, moderator: discord.Member) -> bool:
        """
        Назначить начальный ранг новобранца

        Args:
            user: Discord пользователь
            moderator: Модератор, выполняющий действие

        Returns:
            bool: Успешно ли назначен ранг
        """
        try:
            from utils.database_manager.rank_manager import RankManager
            from utils.config_manager import load_config

            rank_manager = RankManager()
            config = load_config()

            # Check if default recruit rank is configured
            default_rank_id = config.get('default_recruit_rank_id')
            if default_rank_id:
                default_rank = await rank_manager.get_rank_by_id(default_rank_id)
                if default_rank:
                    return await RoleUtils.assign_rank_role(user, default_rank['name'], moderator)
                else:
                    logger.info("Настроенное начальное звание с ID %s не найдено, используем первое из базы данных", default_rank_id)

            # Fallback to first rank in database
            default_rank = await rank_manager.get_first_rank()
            if not default_rank:
                logger.info("Не найден начальный ранг новобранца")
                return False

            return await RoleUtils.assign_rank_role(user, default_rank['name'], moderator)

        except Exception as e:
            logger.error("Ошибка при назначении начального ранга пользователю %s: %s", user, e)
            return False

    @staticmethod
    async def update_user_rank(user: discord.Member, old_rank_name: str, new_rank_name: str, moderator: discord.Member, change_type: str = None) -> Tuple[bool, str]:
        """
        Обновить ранг пользователя (смена с одного ранга на другой)

        Args:
            user: Discord пользователь
            old_rank_name: Название старого ранга
            new_rank_name: Название нового ранга
            moderator: Модератор, выполняющий действие
            change_type: Тип изменения ('promotion', 'demotion', 'transfer')

        Returns:
            Tuple[bool, str]: (успешно, сообщение)
        """
        try:
            from utils.database_manager.rank_manager import rank_manager

            # Получить данные рангов из базы данных
            old_rank_data = rank_manager.get_rank_by_name(old_rank_name) if old_rank_name else None
            new_rank_data = rank_manager.get_rank_by_name(new_rank_name)

            if not new_rank_data:
                return False, f"Новый ранг '{new_rank_name}' не найден в базе данных"

            # Определить тип изменения
            if change_type is None:
                change_type = "automatic"
                if old_rank_data and new_rank_data:
                    old_level = old_rank_data.get('rank_level', 0)
                    new_level = new_rank_data.get('rank_level', 0)
                    if new_level > old_level:
                        change_type = "promotion"
                    elif new_level < old_level:
                        change_type = "demotion"
                    else:
                        change_type = "transfer"

            moderator_display = moderator.display_name

            # Удалить старую роль ранга
            if old_rank_data and old_rank_data.get('role_id'):
                old_role = user.guild.get_role(old_rank_data['role_id'])
                if old_role and old_role in user.roles:
                    reason = get_role_reason(
                        user.guild.id,
                        f"rank_change.{change_type}",
                        f"Смена ранга: {old_rank_name} → {new_rank_name}"
                    ).format(moderator=moderator_display)
                    await user.remove_roles(old_role, reason=reason)
                    logger.info(f" Удалена старая роль ранга {old_role.name} у {user.display_name}")
                else:
                    logger.info(f" Старая роль ранга не найдена или не назначена: role_id={old_rank_data.get('role_id')}")
            else:
                logger.info("Нет данных о старом ранге для удаления: %s", old_rank_name)

            # Назначить новую роль ранга
            if new_rank_data.get('role_id'):
                new_role = user.guild.get_role(new_rank_data['role_id'])
                if new_role and new_role not in user.roles:
                    reason = get_role_reason(
                        user.guild.id,
                        f"rank_change.{change_type}",
                        f"Смена ранга: {old_rank_name or 'нет'} → {new_rank_name}"
                    ).format(moderator=moderator_display)
                    await user.add_roles(new_role, reason=reason)
                    logger.info(f" Назначена новая роль ранга {new_role.name} пользователю {user.display_name}")

                    return True, f"Ранг обновлен: {old_rank_name or 'нет'} → {new_rank_name}"
                elif new_role:
                    logger.info(f" Новая роль ранга уже назначена: {new_role.name}")
                    return True, f"Роль ранга уже назначена: {new_rank_name}"
                else:
                    return False, f"Роль для ранга '{new_rank_name}' не найдена на сервере (ID: {new_rank_data['role_id']})"
            else:
                return False, f"У ранга '{new_rank_name}' не настроена Discord роль"

        except Exception as e:
            error_msg = f"Ошибка обновления ранга: {str(e)}"
            logger.error("%s", error_msg)
            return False, error_msg


# Глобальный экземпляр
role_utils = RoleUtils()