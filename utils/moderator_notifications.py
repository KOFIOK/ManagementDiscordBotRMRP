"""
Система уведомлений для модераторов и администраторов
Автоматическая отправка сообщений при назначении ролей и прав
"""
import discord
from typing import List, Set
from utils.config_manager import load_config


async def send_moderator_welcome_dm(user: discord.Member) -> bool:
    """
    Отправить приветственное сообщение модератору в личные сообщения
    
    Args:
        user: Пользователь, которому отправляется сообщение
        
    Returns:
        bool: True если сообщение отправлено успешно, False если ошибка
    """
    try:
        embed = discord.Embed(
            title="🎖️ Добро пожаловать в команду модераторов!",
            description="Вы были назначены **модератором** в системе кадрового управления ВС РФ",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="🛡️ Ваши права и возможности:",
            value=(
                "• **Обработка заявок на увольнение** - кнопки `✅ Одобрить` / `❌ Отказать`\n"
                "• **Обработка заявок на получение ролей** - модерация заявок рядовых (для военного комиссариата)\n"
                "• **Обработка запросов склада** - выдача складского имущества (от Майора и выше)\n"
                "• **Иерархическая модерация** - при необходимости майор сможет уволить капитана\n"
                "• **Кадровый аудит** - доступ к системе учёта персонала"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Важные ограничения:",
            value=(
                "• Вы **НЕ можете** одобрить собственные рапорты\n"
                "• Вы **НЕ можете** модерировать администраторов или пользователей равного/высшего уровня"
            ),
            inline=False
        )
        
        # Получаем ID канала из конфигурации
        config = load_config()
        registration_channel_id = config.get('moderator_registration_channel')
        registration_channel_mention = f"<#{registration_channel_id}>" if registration_channel_id else "#доступ-к-кадровому"
        
        embed.add_field(
            name="📋 Как начать работу:",
            value=(
            f"1. **Регистрация в системе** - при первом одобрении заявки система покажет форму регистрации (или можете воспользоваться каналом {registration_channel_mention})\n"
            "2. **Автозаполнение данных** - ваши ФИО и статик будут извлечены из никнейма Discord\n"
            "3. **Доступ к Google Sheets** - вы автоматически получите права редактора таблиц\n"
            "4. **Начните модерировать** - все заявки обрабатываются через кнопки в интерфейсе"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Система защиты:",
            value=(
                "• **Автоформатирование** - система сама исправит формат статика\n"
                "• **Аудит действий** - все операции логируются автоматически"
            ),
            inline=False
        )
        
        embed.set_footer(
            text="💡 Система кадрового управления ВС РФ | Все действия регистрируются",
            icon_url=user.guild.icon.url if user.guild.icon else None
        )
        
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        
        await user.send(embed=embed)
        return True
        
    except discord.Forbidden:
        print(f"⚠️ Не удалось отправить DM модератору {user.display_name} - закрыты личные сообщения")
        return False
    except Exception as e:
        print(f"❌ Ошибка при отправке DM модератору {user.display_name}: {e}")
        return False


async def send_administrator_welcome_dm(user: discord.Member) -> bool:
    """
    Отправить приветственное сообщение администратору в личные сообщения
    
    Args:
        user: Пользователь, которому отправляется сообщение
        
    Returns:
        bool: True если сообщение отправлено успешно, False если ошибка
    """
    try:
        embed = discord.Embed(
            title="👑 Добро пожаловать в команду администраторов!",
            description="Вы были назначены **администратором** в системе кадрового управления ВС РФ",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="🔑 Ваши расширенные права:",
            value=(
                "• **Все права модератора** - полный доступ к обработке заявок\n"
                "• **Команда `/settings`** - универсальная настройка системы\n"
                "• **Управление модераторами** - команды `/moder add/remove/list`\n"
                "• **Управление администраторами** - команды `/admin add/remove/list`\n"
                "• **Одобрение собственных заявок** - администраторы могут модерировать себя\n"
                "• **Высший уровень иерархии** - можете модерировать всех пользователей"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Доступные настройки:",
            value=(
                "• **Настройка каналов** - увольнения, аудит, чёрный список, роли, медицина, склад\n"
                "• **Система пингов** - настройка уведомлений по подразделениям\n"
                "• **Роли-исключения** - управление ролями, не снимаемыми при увольнении\n"
                "• **Лимиты склада** - настройка лимитов по должностям и званиям\n"
                "• **Резервное копирование** - управление резервными копиями конфигурации"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Система безопасности:",
            value=(
                "• **Автоматические резервные копии** - при каждом изменении настроек\n"
                "• **Атомарная запись** - предотвращение повреждения конфигурации\n"
                "• **Иерархическая защита** - строгий контроль прав доступа\n"
                "• **Эфемерные ответы** - настройки видны только вам"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 Мониторинг и управление:",
            value=(
                "• **Кадровый аудит** - полный контроль над персоналом\n"
                "• **Система валидации** - проверка целостности данных\n"
                "• **Автоматизация процессов** - умное управление ролями и правами\n"
                "• **Интеграция с Google Sheets** - централизованное хранение данных"
            ),
            inline=False
        )
        
        embed.set_footer(
            text="🔐 Система кадрового управления ВС РФ | Высший уровень доступа",
            icon_url=user.guild.icon.url if user.guild.icon else None
        )
        
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        
        await user.send(embed=embed)
        return True
        
    except discord.Forbidden:
        print(f"⚠️ Не удалось отправить DM администратору {user.display_name} - закрыты личные сообщения")
        return False
    except Exception as e:
        print(f"❌ Ошибка при отправке DM администратору {user.display_name}: {e}")
        return False


async def send_notification_to_channel(guild: discord.Guild, user: discord.Member, role_type: str) -> bool:
    """
    Отправить уведомление в канал модерации о назначении нового модератора/администратора
    
    Args:
        guild: Сервер Discord
        user: Назначенный пользователь
        role_type: Тип роли ('moderator' или 'administrator')
        
    Returns:
        bool: True если сообщение отправлено успешно, False если ошибка
    """
    try:
        config = load_config()
        channel_id = config.get('moderator_registration_channel')
        
        if not channel_id:
            print("⚠️ Канал модерации не настроен в конфигурации")
            return False
            
        channel = guild.get_channel(channel_id)
        if not channel:
            print(f"⚠️ Канал модерации не найден (ID: {channel_id})")
            return False
        
        if role_type == 'moderator':
            title = "👮 Новый модератор назначен"
            color = discord.Color.blue()
            description = f"{user.mention} получил права **модератора** в системе кадрового управления"
        else:  # administrator
            title = "👑 Новый администратор назначен"
            color = discord.Color.gold()
            description = f"{user.mention} получил права **администратора** в системе кадрового управления"
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Информация:",
            value=(
                f"**Пользователь:** {user.mention}\n"
                f"**Никнейм:** {user.display_name}\n"
                f"**ID:** `{user.id}`\n"
                f"**Аккаунт создан:** <t:{int(user.created_at.timestamp())}:R>"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🔄 Статус:",
            value=(
                f"**Тип назначения:** {role_type.title()}\n"
                f"**Время назначения:** <t:{int(discord.utils.utcnow().timestamp())}:R>\n"
                f"**Уведомление отправлено:** ✅ Да"
            ),
            inline=True
        )
        
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        embed.set_footer(text="Система кадрового управления ВС РФ")
        
        await channel.send(embed=embed)
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при отправке уведомления в канал: {e}")
        return False


def check_if_user_is_moderator(user: discord.Member, config: dict) -> bool:
    """
    Проверить, является ли пользователь уже модератором (имеет модераторские роли)
    
    Args:
        user: Пользователь для проверки
        config: Конфигурация бота
        
    Returns:
        bool: True если пользователь уже имеет модераторские права, False если нет
    """
    moderators = config.get('moderators', {'users': [], 'roles': []})
    
    # Проверяем прямое назначение пользователя
    if user.id in moderators.get('users', []):
        return True
    
    # Проверяем модераторские роли
    moderator_role_ids = moderators.get('roles', [])
    user_role_ids = [role.id for role in user.roles]
    
    for role_id in moderator_role_ids:
        if role_id in user_role_ids:
            return True
    
    return False


def check_if_user_is_administrator(user: discord.Member, config: dict) -> bool:
    """
    Проверить, является ли пользователь уже администратором (имеет администраторские роли)
    
    Args:
        user: Пользователь для проверки
        config: Конфигурация бота
        
    Returns:
        bool: True если пользователь уже имеет администраторские права, False если нет
    """
    administrators = config.get('administrators', {'users': [], 'roles': []})
    
    # Проверяем прямое назначение пользователя
    if user.id in administrators.get('users', []):
        return True
    
    # Проверяем администраторские роли
    admin_role_ids = administrators.get('roles', [])
    user_role_ids = [role.id for role in user.roles]
    
    for role_id in admin_role_ids:
        if role_id in user_role_ids:
            return True
    
    return False


async def handle_moderator_assignment(guild: discord.Guild, target: discord.Member | discord.Role, old_config: dict) -> None:
    """
    Обработать назначение модератора: отправить уведомления новым модераторам
    
    Args:
        guild: Сервер Discord
        target: Назначенный пользователь или роль
        old_config: Конфигурация ДО изменений (для проверки кто уже был модератором)
    """
    users_to_notify: Set[discord.Member] = set()
    
    if isinstance(target, discord.Member):
        # Прямое назначение пользователя
        if not check_if_user_is_moderator(target, old_config) and not check_if_user_is_administrator(target, old_config):
            users_to_notify.add(target)
    
    elif isinstance(target, discord.Role):
        # Назначение роли - уведомляем всех участников с этой ролью
        for member in guild.members:
            if target in member.roles:
                if not check_if_user_is_moderator(member, old_config) and not check_if_user_is_administrator(member, old_config):
                    users_to_notify.add(member)
    
    # Отправляем уведомления
    for user in users_to_notify:
        dm_sent = await send_moderator_welcome_dm(user)
        channel_sent = await send_notification_to_channel(guild, user, 'moderator')
        
        status = "✅" if dm_sent else "❌"
        channel_status = "✅" if channel_sent else "❌"
        print(f"{status} Уведомление модератору {user.display_name}: DM {status}, канал {channel_status}")


async def handle_administrator_assignment(guild: discord.Guild, target: discord.Member | discord.Role, old_config: dict) -> None:
    """
    Обработать назначение администратора: отправить уведомления новым администраторам
    
    Args:
        guild: Сервер Discord
        target: Назначенный пользователь или роль
        old_config: Конфигурация ДО изменений (для проверки кто уже был администратором)
    """
    users_to_notify: Set[discord.Member] = set()
    
    if isinstance(target, discord.Member):
        # Прямое назначение пользователя
        if not check_if_user_is_administrator(target, old_config):
            users_to_notify.add(target)
    
    elif isinstance(target, discord.Role):
        # Назначение роли - уведомляем всех участников с этой ролью
        for member in guild.members:
            if target in member.roles:
                if not check_if_user_is_administrator(member, old_config):
                    users_to_notify.add(member)
    
    # Отправляем уведомления
    for user in users_to_notify:
        dm_sent = await send_administrator_welcome_dm(user)
        channel_sent = await send_notification_to_channel(guild, user, 'administrator')
        
        status = "✅" if dm_sent else "❌"
        channel_status = "✅" if channel_sent else "❌"
        print(f"{status} Уведомление администратору {user.display_name}: DM {status}, канал {channel_status}")


async def handle_role_assignment_event(member: discord.Member, before_roles: List[discord.Role], after_roles: List[discord.Role]) -> None:
    """
    Обработать событие изменения ролей пользователя (для отслеживания через Discord события)
    
    Args:
        member: Пользователь, у которого изменились роли
        before_roles: Роли до изменения
        after_roles: Роли после изменения
    """
    try:
        config = load_config()
        
        # Получаем добавленные роли
        added_roles = set(after_roles) - set(before_roles)
        
        if not added_roles:
            return
        
        moderator_role_ids = config.get('moderators', {}).get('roles', [])
        administrator_role_ids = config.get('administrators', {}).get('roles', [])
        
        # Проверяем, была ли добавлена модераторская роль
        became_moderator = False
        became_administrator = False
        
        for role in added_roles:
            if role.id in moderator_role_ids:
                # Проверяем, не был ли пользователь уже модератором/администратором
                if not check_if_user_is_moderator(member, config) and not check_if_user_is_administrator(member, config):
                    became_moderator = True
                    break
            
            if role.id in administrator_role_ids:
                # Проверяем, не был ли пользователь уже администратором
                if not check_if_user_is_administrator(member, config):
                    became_administrator = True
                    break
        
        # Отправляем уведомления
        if became_administrator:
            dm_sent = await send_administrator_welcome_dm(member)
            channel_sent = await send_notification_to_channel(member.guild, member, 'administrator')
            
            status = "✅" if dm_sent else "❌"
            channel_status = "✅" if channel_sent else "❌"
            print(f"{status} Авто-уведомление администратору {member.display_name} (роль выдана): DM {status}, канал {channel_status}")
            
        elif became_moderator:
            dm_sent = await send_moderator_welcome_dm(member)
            channel_sent = await send_notification_to_channel(member.guild, member, 'moderator')
            
            status = "✅" if dm_sent else "❌"
            channel_status = "✅" if channel_sent else "❌"
            print(f"{status} Авто-уведомление модератору {member.display_name} (роль выдана): DM {status}, канал {channel_status}")
    
    except Exception as e:
        print(f"❌ Ошибка при обработке изменения ролей для {member.display_name}: {e}")
