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
                    print(f"⚠️ Нет прав для удаления роли подразделения {role.name} у {user}")
                except Exception as e:
                    print(f"❌ Ошибка при удалении роли подразделения {role.name} у {user}: {e}")

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
        all_position_role_ids = ping_manager.get_all_position_role_ids()

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
                    print(f"⚠️ Нет прав для удаления роли должности {role.name} у {user}")
                except Exception as e:
                    print(f"❌ Ошибка при удалении роли должности {role.name} у {user}: {e}")

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
                print(f"❌ Роль для подразделения {dept_code} не настроена")
                return False

            dept_role = user.guild.get_role(dept_role_id)
            if not dept_role:
                print(f"❌ Роль подразделения {dept_code} не найдена на сервере")
                return False

            # Получить имя подразделения для причины
            dept_info = ping_manager.get_department_info(dept_code)
            dept_name = dept_info.get('name', dept_code) if dept_info else dept_code

            reason = get_role_reason(
                user.guild.id,
                "department_application.approved",
                f"Заявка в подразделение: одобрена ({dept_name})"
            ).format(moderator=moderator.display_name)

            await user.add_roles(dept_role, reason=reason)
            print(f"✅ Назначена роль подразделения {dept_role.name} пользователю {user}")
            return True

        except Exception as e:
            print(f"❌ Ошибка при назначении роли подразделения {dept_code} пользователю {user}: {e}")
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
            print(f"⚠️ Нет настроенных ролей должностей для подразделения {dept_code}")
            return assigned_roles

        moderator_display = moderator.display_name

        for role_id in assignable_role_ids:
            role = user.guild.get_role(role_id)
            if not role:
                print(f"❌ Роль с ID {role_id} не найдена на сервере")
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
                print(f"✅ Назначена роль должности {role.name} пользователю {user}")

            except discord.Forbidden:
                print(f"⚠️ Нет прав для назначения роли {role.name} пользователю {user}")
            except Exception as e:
                print(f"❌ Ошибка при назначении роли {role.name} пользователю {user}: {e}")

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
                print(f"⚠️ Должность {new_position_id} не найдена в кэше")
            
            # Найти текущие роли должностей у пользователя
            roles_to_remove = []
            
            for role in user.roles:
                if role.id in all_position_roles:
                    # Удалить только если это не новая роль, которую мы добавляем
                    if role.id != new_role_id:
                        roles_to_remove.append(role)
                    else:
                        print(f"🔍 Сохраняем роль (уже назначена): {role.name}")
            
            # Пакетные операции с ролями для лучшей производительности
            role_changes = []
            
            # Удалить старые роли должностей
            if roles_to_remove:
                try:
                    reason = get_role_reason(guild.id, "role_removal.position_change", "Смена должности: снята роль").format(moderator=moderator_display)
                    await user.remove_roles(*roles_to_remove, reason=reason)
                    for role in roles_to_remove:
                        print(f"🔄 Удалена роль должности: {role.name}")
                        role_changes.append(f"-{role.name}")
                except Exception as e:
                    print(f"⚠️ Ошибка при удалении ролей: {e}")
            
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
                            
                            reason = get_role_reason(guild.id, "position_assignment.assigned", "Назначение должности").format(position=position_name)
                            await user.add_roles(new_role, reason=reason)
                            role_changes.append(f"+{position_name}")
                        except Exception as e:
                            print(f"⚠️ Ошибка при добавлении роли: {e}")
                    else:
                        print(f"⚠️ Роль с ID {new_role_id} не найдена на сервере")
                else:
                    print(f"ℹ️ У пользователя уже есть целевая роль")
            
            # Итог
            if role_changes:
                print(f"📋 Изменения ролей: {', '.join(role_changes)}")
            else:
                print(f"ℹ️ Изменения ролей не требуются для {user.display_name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка в умном обновлении ролей должностей: {e}")
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
                print(f"❌ Военная роль с ID {role_id} не найдена")
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
                print(f"✅ Назначена военная роль {role.name} пользователю {user}")

            except discord.Forbidden:
                print(f"⚠️ Нет прав для назначения военной роли {role.name} пользователю {user}")
            except Exception as e:
                print(f"❌ Ошибка при назначении военной роли {role.name} пользователю {user}: {e}")

        # Назначить ранг из заявки
        rank_name = application_data.get('rank')
        if rank_name:
            from utils.message_manager import get_role_reason
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
                print(f"❌ Роль госслужащего с ID {role_id} не найдена")
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
                print(f"✅ Назначена роль госслужащего {role.name} пользователю {user}")

            except discord.Forbidden:
                print(f"⚠️ Нет прав для назначения роли {role.name} пользователю {user}")
            except Exception as e:
                print(f"❌ Ошибка при назначении роли {role.name} пользователю {user}: {e}")

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
                print(f"❌ Роль поставщика с ID {role_id} не найдена")
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
                print(f"✅ Назначена роль поставщика {role.name} пользователю {user}")

            except discord.Forbidden:
                print(f"⚠️ Нет прав для назначения роли {role.name} пользователю {user}")
            except Exception as e:
                print(f"❌ Ошибка при назначении роли {role.name} пользователю {user}: {e}")

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
                    print(f"⚠️ Нет прав для удаления роли ранга {role.name} у {user}")
                except Exception as e:
                    print(f"❌ Ошибка при удалении роли ранга {role.name} у {user}: {e}")

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
                        print(f"⚠️ Нет прав для удаления роли {role.name} у {user}")
                    except Exception as e:
                        print(f"❌ Ошибка при удалении роли {role.name} у {user}: {e}")

        except Exception as e:
            print(f"❌ Ошибка при полном снятии ролей у {user}: {e}")

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
            print(f"❌ Ошибка получения ролей рангов: {e}")
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
                print(f"❌ Ранг '{rank_name}' не найден в базе данных")
                return False

            role_id = rank_data.get('role_id')
            if not role_id:
                print(f"❌ У ранга '{rank_name}' не настроена роль Discord")
                return False

            role = user.guild.get_role(role_id)
            if not role:
                print(f"❌ Роль ранга '{rank_name}' (ID: {role_id}) не найдена на сервере")
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
            print(f"✅ Назначена роль ранга {role.name} ({rank_name}) пользователю {user}")
            return True

        except Exception as e:
            print(f"❌ Ошибка при назначении роли ранга '{rank_name}' пользователю {user}: {e}")
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
                    print(f"⚠️ Настроенное начальное звание с ID {default_rank_id} не найдено, используем первое из базы данных")

            # Fallback to first rank in database
            default_rank = await rank_manager.get_first_rank()
            if not default_rank:
                print(f"❌ Не найден начальный ранг новобранца")
                return False

            return await RoleUtils.assign_rank_role(user, default_rank['name'], moderator)

        except Exception as e:
            print(f"❌ Ошибка при назначении начального ранга пользователю {user}: {e}")
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
                    print(f"✅ Удалена старая роль ранга {old_role.name} у {user.display_name}")
                else:
                    print(f"⚠️ Старая роль ранга не найдена или не назначена: role_id={old_rank_data.get('role_id')}")
            else:
                print(f"⚠️ Нет данных о старом ранге для удаления: {old_rank_name}")

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
                    print(f"✅ Назначена новая роль ранга {new_role.name} пользователю {user.display_name}")

                    return True, f"Ранг обновлен: {old_rank_name or 'нет'} → {new_rank_name}"
                elif new_role:
                    print(f"⚠️ Новая роль ранга уже назначена: {new_role.name}")
                    return True, f"Роль ранга уже назначена: {new_rank_name}"
                else:
                    return False, f"Роль для ранга '{new_rank_name}' не найдена на сервере (ID: {new_rank_data['role_id']})"
            else:
                return False, f"У ранга '{new_rank_name}' не настроена Discord роль"

        except Exception as e:
            error_msg = f"Ошибка обновления ранга: {str(e)}"
            print(error_msg)
            return False, error_msg


# Глобальный экземпляр
role_utils = RoleUtils()