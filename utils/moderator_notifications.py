"""
Система уведомлений для модераторов и администраторов
Автоматическая отправка сообщений при назначении ролей и прав
Централизованная логика для всех уведомлений модераторов/администраторов
"""
import discord
from utils.config_manager import load_config


async def send_moderator_welcome_dm(user: discord.Member) -> bool:
    """Отправить приветственное сообщение модератору в ЛС"""
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
                "• Вы **НЕ можете** модерировать администраторов или пользователей равного/высшего уровня\n"
            ),
            inline=False
        )
          # Получаем канал для регистрации модераторов из конфига
        config = load_config()
        registration_channel_id = config.get('moderator_registration_channel')
        registration_channel_mention = f"<#{registration_channel_id}>" if registration_channel_id else "канале регистрации"
        
        embed.add_field(
            name="📋 Как начать работу:",
            value=(
            f"1. **Регистрация в системе** - при первом одобрении заявки система покажет форму регистрации - {registration_channel_mention}\n"
            f"2. **Автозаполнение данных** - ваши ФИО и статик будут извлечены из никнейма Discord\n"
            f"3. **Доступ к Google Sheets** - вы автоматически получите права редактора таблиц\n"
            f"4. **Начните модерировать** - все заявки обрабатываются через кнопки в интерфейсе"
            ),
            inline=False
        )
        
        embed.add_field(
            name="❓ Узнайте больше",
            value=(
            f" - Введите команду `/help` для получения справки\n"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 Система кадрового управления ВС РФ | Все действия регистрируются")
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
    """Отправить приветственное сообщение администратору в ЛС"""
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
            name="❓ Узнайте больше",
            value=(
            f" - Введите команду `/help` для получения справки\n"
            ),
            inline=False
        )
        
        embed.set_footer(text="🔐 Система кадрового управления ВС РФ | Высший уровень доступа")
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
    """Отправить уведомление в канал модерации о назначении (ОТКЛЮЧЕНО)"""
    # Функция отключена по требованию - уведомления в канал не нужны
    print(f"🔕 Уведомление в канал отключено для {role_type} {user.display_name}")
    return True  # Возвращаем True, чтобы не показывать ошибку в логах


def check_if_user_is_moderator(user: discord.Member, config: dict) -> bool:
    """Проверить, является ли пользователь уже модератором"""
    # Владелец сервера и Discord администраторы автоматически считаются администраторами, не модераторами
    if user.guild.owner_id == user.id or user.guild_permissions.administrator:
        return False
    
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
    """Проверить, является ли пользователь уже администратором"""
    # Владелец сервера и Discord администраторы автоматически считаются администраторами
    if user.guild.owner_id == user.id or user.guild_permissions.administrator:
        return True
    
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
