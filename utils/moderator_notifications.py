"""
Система уведомлений для модераторов и администраторов
Автоматическая отправка сообщений при назначении ролей и прав
Централизованная логика для всех уведомлений модераторов/администраторов
"""
import discord


async def send_moderator_welcome_dm(user: discord.Member) -> bool:
    """Отправить приветственное сообщение модератору в ЛС"""
    try:
        embed = discord.Embed(
            title="🎖️ Добро пожаловать в команду модераторов!",
            description="Вы были назначены **модератором** в системе кадрового управления Вашей Фракции",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="🛡️ Ваши права и возможности:",
            value=(
                "- **Обработка различного рода заявок**\n> - кнопки `✅ Одобрить` / `❌ Отказать`\n"
                "- **Обработка запросов склада**\n> - выдача складского имущества\n"
                "- **Иерархическая модерация**\n> - контроль согласно иерархии discord ролей\n"
                "- **Кадровый аудит**\n> - доступ к системе учёта персонала\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Важные ограничения:",
            value=(
                "- Вы **НЕ можете** одобрить собственные рапорты\n"
                "- Вы **НЕ можете** модерировать администраторов или пользователей равного/высшего уровня\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="❓ Узнайте больше",
            value=(
                "Введите команду `/help` на дискорд-сервере для получения полной справки по системе\n"
                "> - Подробнее о системе можно узнать в документации [GitHub](https://github.com/KOFIOK/armyDiscordBot)"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 Система кадрового управления")
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
            description="Вы были назначены **администратором** в системе кадрового управления Вашей Фракции",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="🔑 Ваши расширенные права:",
            value=(
                "- **Все права модератора**\n> - полный доступ к обработке заявок\n"
                "- **Команда `/settings`**\n> - универсальная настройка системы\n"
                "- **Управление модераторами**\n> - команды `/moder add/remove/list`\n"
                "- **Управление администраторами**\n> - команды `/admin add/remove/list`\n"
                "- **Одобрение собственных заявок**\n> - администраторы могут модерировать себя\n"
                "- **Высший уровень иерархии**\n> - можете модерировать всех пользователей\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Доступные настройки (/settings):",
            value=(
                "- **Каналы подразделений**\n> - настройка заявлений в части\n"
                "- **Каналы системы**\n> - увольнения, аудит, чёрный список, роли, медицина\n"
                "- **Система пингов**\n> - настройка уведомлений по подразделениям\n"
                "- **Роли-исключения**\n> - управление ролями, не снимаемыми при увольнении\n"
                "- **Лимиты склада**\n> - настройка лимитов по должностям и званиям (НЕ ТЕСТИРОВАЛОСЬ)\n"
                "- **И другие**\n> - подробности в `/help`\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="❓ Узнайте больше",
            value=(
                "Введите команду `/help` на дискорд-сервере для получения полной справки по системе\n"
                "> - Подробнее о системе можно узнать в документации [GitHub](https://github.com/KOFIOK/armyDiscordBot)"
            ),
            inline=False
        )
        
        embed.set_footer(text="🔐 Система кадрового управления")
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        
        await user.send(embed=embed)
        return True
        
    except discord.Forbidden:
        print(f"⚠️ Не удалось отправить DM администратору {user.display_name} - закрыты личные сообщения")
        return False
    except Exception as e:
        print(f"❌ Ошибка при отправке DM администратору {user.display_name}: {e}")
        return False


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
