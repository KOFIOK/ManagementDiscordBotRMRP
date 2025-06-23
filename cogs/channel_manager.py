import discord
from discord import app_commands
from discord.ext import commands
import datetime

from forms.settings_form import send_settings_message
from utils.config_manager import load_config, save_config
# Enhanced config manager for backup functionality
from utils.config_manager import (
    create_backup, list_backups, restore_from_backup, 
    export_config, import_config, get_config_status
)


# ===================== СИСТЕМА УВЕДОМЛЕНИЙ МОДЕРАТОРОВ =====================

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
                "• **Обработка заявок на увольнение** - кнопки ✅ Одобрить / ❌ Отказать\n"
                "• **Обработка заявок на получение ролей** - модерация военных и гражданских заявок\n"
                "• **Обработка запросов склада** - выдача складского имущества\n"
                "• **Иерархическая модерация** - вы можете модерировать пользователей согласно иерархии\n"
                "• **Кадровый аудит** - доступ к системе учёта персонала"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Важные ограничения:",
            value=(
                "• Вы **НЕ можете** одобрить собственные рапорты (кроме администраторов)\n"
                "• Вы **НЕ можете** модерировать администраторов или пользователей равного/высшего уровня\n"
                "• У вас **НЕТ доступа** к командам настройки системы (`/settings`, `/moder`, `/admin`)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📋 Как начать работу:",
            value=(
                "1. **Регистрация в системе** - при первом одобрении заявки система покажет форму регистрации\n"
                "2. **Автозаполнение данных** - ваши ФИО и статик будут извлечены из никнейма Discord\n"
                "3. **Доступ к Google Sheets** - вы автоматически получите права редактора таблиц\n"
                "4. **Начните модерировать** - все заявки обрабатываются через кнопки в интерфейсе"
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


async def handle_moderator_assignment(guild: discord.Guild, target: discord.Member | discord.Role, old_config: dict) -> None:
    """Обработать назначение модератора: отправить уведомления новым модераторам"""
    users_to_notify = set()
    
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
        print(f"{status} Уведомление модератору {user.display_name}: DM {status}")


async def handle_administrator_assignment(guild: discord.Guild, target: discord.Member | discord.Role, old_config: dict) -> None:
    """Обработать назначение администратора: отправить уведомления новым администраторам"""
    users_to_notify = set()
    
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
        print(f"{status} Уведомление администратору {user.display_name}: DM {status}")


# ===================== ОСНОВНОЙ COG =====================

class ChannelManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="settings", description="⚙️ Настройка каналов Discord бота")
    async def settings(self, interaction: discord.Interaction):
        """Unified command for bot configuration with interactive interface"""
        # Check if user has administrator permissions (custom admins or Discord admins)
        from utils.config_manager import is_administrator
        config = load_config()
        
        if not (interaction.user.guild_permissions.administrator or is_administrator(interaction.user, config)):
            await interaction.response.send_message(
                "❌ У вас нет прав для выполнения этой команды. Требуются права администратора.", 
                ephemeral=True
            )
            return
            
        await send_settings_message(interaction)

    # Moderator management commands
    moder = app_commands.Group(name="moder", description="👮 Управление модераторами")

    @moder.command(name="add", description="➕ Добавить модератора (роль или пользователя)")
    @app_commands.describe(target="Роль или пользователь для назначения модератором")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_moderator(self, interaction: discord.Interaction, target: discord.Member | discord.Role):
        """Add a user or role as moderator"""
        try:
            config = load_config()
            old_config = config.copy()  # Сохраняем старую конфигурацию для проверки
            moderators = config.get('moderators', {'users': [], 'roles': []})
            
            if isinstance(target, discord.Member):
                if target.id not in moderators['users']:
                    moderators['users'].append(target.id)
                    config['moderators'] = moderators
                    save_config(config)
                    
                    # Отправляем уведомления новому модератору
                    await handle_moderator_assignment(interaction.guild, target, old_config)
                    
                    await interaction.response.send_message(
                        f"✅ Пользователь {target.mention} добавлен в список модераторов.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"⚠️ Пользователь {target.mention} уже является модератором.",
                        ephemeral=True
                    )
            
            elif isinstance(target, discord.Role):
                if target.id not in moderators['roles']:
                    moderators['roles'].append(target.id)
                    config['moderators'] = moderators
                    save_config(config)
                      # Отправляем уведомления всем участникам с этой ролью
                    await handle_moderator_assignment(interaction.guild, target, old_config)
                    
                    await interaction.response.send_message(
                        f"✅ Роль {target.mention} добавлена в список модераторских ролей.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"⚠️ Роль {target.mention} уже является модераторской.",
                        ephemeral=True
                    )
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при добавлении модератора: {e}",
                ephemeral=True
            )
            print(f"Add moderator error: {e}")

    @moder.command(name="remove", description="➖ Убрать модератора (роль или пользователя)")
    @app_commands.describe(target="Роль или пользователь для удаления из модераторов")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_moderator(self, interaction: discord.Interaction, target: discord.Member | discord.Role):
        """Remove a user or role from moderators"""
        try:
            config = load_config()
            moderators = config.get('moderators', {'users': [], 'roles': []})
            
            if isinstance(target, discord.Member):
                if target.id in moderators['users']:
                    moderators['users'].remove(target.id)
                    config['moderators'] = moderators
                    save_config(config)
                    
                    await interaction.response.send_message(
                        f"✅ Пользователь {target.mention} удален из списка модераторов.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"⚠️ Пользователь {target.mention} не является модератором.",
                        ephemeral=True
                    )
            
            elif isinstance(target, discord.Role):
                if target.id in moderators['roles']:
                    moderators['roles'].remove(target.id)
                    config['moderators'] = moderators
                    save_config(config)
                    
                    await interaction.response.send_message(
                        f"✅ Роль {target.mention} удалена из списка модераторских ролей.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"⚠️ Роль {target.mention} не является модераторской.",
                        ephemeral=True
                    )
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при удалении модератора: {e}",
                ephemeral=True
            )
            print(f"Remove moderator error: {e}")

    @moder.command(name="list", description="📋 Показать список модераторов")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_moderators(self, interaction: discord.Interaction):
        """List all moderators and moderator roles"""
        try:
            config = load_config()
            moderators = config.get('moderators', {'users': [], 'roles': []})
            
            embed = discord.Embed(
                title="👮 Список модераторов",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Moderator users
            user_list = []
            for user_id in moderators.get('users', []):
                user = interaction.guild.get_member(user_id)
                if user:
                    user_list.append(f"• {user.mention} ({user.display_name})")
                else:
                    user_list.append(f"• <@{user_id}> (пользователь не найден)")
            
            if user_list:
                embed.add_field(
                    name="👤 Пользователи-модераторы",
                    value="\n".join(user_list),
                    inline=False
                )
            else:
                embed.add_field(
                    name="👤 Пользователи-модераторы",
                    value="Нет назначенных пользователей",
                    inline=False
                )
              # Moderator roles
            role_list = []
            for role_id in moderators.get('roles', []):
                role = interaction.guild.get_role(role_id)
                if role:
                    role_list.append(f"• {role.mention}")
                else:
                    role_list.append(f"• <@&{role_id}> (роль не найдена)")
            
            if role_list:
                embed.add_field(
                    name="🛡️ Модераторские роли",
                    value="\n".join(role_list),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🛡️ Модераторские роли",
                    value="Нет назначенных ролей",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при получении списка модераторов: {e}",
                ephemeral=True
            )
            print(f"List moderators error: {e}")    # Error handling for commands
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle app command errors"""
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "❌ У вас нет прав для выполнения этой команды. Требуются права администратора.", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Произошла ошибка: {error}", 
                ephemeral=True
            )
            print(f"App command error: {error}")

    @app_commands.command(name="config-backup", description="🔄 Управление резервными копиями конфигурации")
    @app_commands.describe(
        action="Действие с резервными копиями",
        backup_name="Имя файла резервной копии (для восстановления)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Создать резервную копию", value="create"),
        app_commands.Choice(name="Список резервных копий", value="list"),
        app_commands.Choice(name="Восстановить из копии", value="restore"),
        app_commands.Choice(name="Статус системы", value="status")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def config_backup(self, interaction: discord.Interaction, action: str, backup_name: str = None):
        """Manage configuration backups"""
        
        if action == "create":
            backup_path = create_backup("manual")
            if backup_path:
                await interaction.response.send_message(
                    f"✅ **Резервная копия создана**\n"
                    f"📁 Файл: `{backup_path}`\n"
                    f"📅 Время: <t:{int(datetime.datetime.now().timestamp())}:F>",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ **Ошибка создания резервной копии**\n"
                    "Проверьте права доступа к папке data/backups",
                    ephemeral=True
                )
        
        elif action == "list":
            backups = list_backups()
            if not backups:
                await interaction.response.send_message(
                    "📂 **Резервные копии не найдены**\n"
                    "Используйте команду с действием 'create' для создания первой копии.",
                    ephemeral=True
                )
                return
            
            backup_list = []
            for i, backup in enumerate(backups[:10], 1):  # Show only last 10
                # Extract timestamp from filename
                try:
                    timestamp_part = backup.split('_')[2]  # config_backup_TIMESTAMP_reason.json
                    timestamp = datetime.datetime.strptime(timestamp_part, "%Y%m%d")
                    date_str = timestamp.strftime("%d.%m.%Y")
                except:
                    date_str = "неизвестно"
                
                backup_list.append(f"`{i}.` {backup} ({date_str})")
            
            embed = discord.Embed(
                title="📂 Список резервных копий",
                description="\n".join(backup_list),
                color=discord.Color.blue()
            )
            embed.add_field(
                name="ℹ️ Использование",
                value="Для восстановления используйте команду с действием 'restore' и укажите полное имя файла",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        elif action == "restore":
            if not backup_name:
                await interaction.response.send_message(
                    "❌ **Укажите имя файла резервной копии**\n"
                    "Используйте действие 'list' для просмотра доступных копий.",
                    ephemeral=True
                )
                return
            
            if restore_from_backup(backup_name):
                await interaction.response.send_message(
                    f"✅ **Конфигурация восстановлена**\n"
                    f"📁 Из файла: `{backup_name}`\n"
                    f"⚠️ Перезапустите бота для применения изменений",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ **Ошибка восстановления**\n"
                    f"Файл `{backup_name}` не найден или повреждён.",
                    ephemeral=True
                )
        
        elif action == "status":
            status = get_config_status()
            
            config_status = "✅ Валидная" if status['config_valid'] else "❌ Повреждена"
            if not status['config_exists']:
                config_status = "❌ Отсутствует"
            
            embed = discord.Embed(
                title="📊 Статус системы конфигурации",
                color=discord.Color.green() if status['config_valid'] else discord.Color.red()
            )
            
            embed.add_field(
                name="📄 Главный файл конфигурации",
                value=f"Статус: {config_status}\nРазмер: {status['config_size']} байт",
                inline=True
            )
            
            embed.add_field(
                name="🔄 Резервные копии",
                value=f"Количество: {status['backup_count']}\nПоследняя: {status['last_backup'] or 'нет'}",
                inline=True
            )
            
            if not status['config_valid']:
                embed.add_field(
                    name="🚨 Рекомендации",
                    value="Конфигурация повреждена! Используйте действие 'restore' для восстановления.",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="config-export", description="📤 Экспорт конфигурации для переноса")
    @app_commands.describe(filename="Имя файла для экспорта (без расширения)")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_export(self, interaction: discord.Interaction, filename: str = None):
        """Export configuration for migration"""
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"config_export_{timestamp}"
        
        export_path = f"data/{filename}.json"
        
        if export_config(export_path):
            await interaction.response.send_message(
                f"✅ **Конфигурация экспортирована**\n"
                f"📁 Файл: `{export_path}`\n"
                f"💡 Этот файл можно использовать для переноса настроек на другой сервер",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ **Ошибка экспорта конфигурации**\n"
                "Проверьте права доступа к папке data",
                ephemeral=True
            )    # Administrator management command group
    admin = app_commands.Group(name="admin", description="👑 Управление администраторами")

    @admin.command(name="add", description="➕ Добавить администратора (роль или пользователя)")
    @app_commands.describe(target="Роль или пользователь для назначения администратором")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_administrator(self, interaction: discord.Interaction, target: discord.Member | discord.Role):
        """Add a user or role as administrator"""
        try:
            config = load_config()
            old_config = config.copy()  # Сохраняем старую конфигурацию для проверки
            administrators = config.get('administrators', {'users': [], 'roles': []})
            
            if isinstance(target, discord.Member):
                if target.id not in administrators['users']:
                    administrators['users'].append(target.id)
                    config['administrators'] = administrators
                    save_config(config)
                      # Отправляем уведомления новому администратору
                    await handle_administrator_assignment(interaction.guild, target, old_config)
                    
                    await interaction.response.send_message(
                        f"✅ Пользователь {target.mention} добавлен в список администраторов.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"⚠️ Пользователь {target.mention} уже является администратором.",
                        ephemeral=True
                    )
            
            elif isinstance(target, discord.Role):
                if target.id not in administrators['roles']:
                    administrators['roles'].append(target.id)
                    config['administrators'] = administrators
                    save_config(config)
                      # Отправляем уведомления всем участникам с этой ролью
                    await handle_administrator_assignment(interaction.guild, target, old_config)
                    
                    await interaction.response.send_message(
                        f"✅ Роль {target.mention} добавлена в список администраторских ролей.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"⚠️ Роль {target.mention} уже является администраторской.",
                        ephemeral=True
                    )
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при добавлении администратора: {e}",
                ephemeral=True
            )
            print(f"Add administrator error: {e}")

    @admin.command(name="remove", description="➖ Убрать администратора (роль или пользователя)")
    @app_commands.describe(target="Роль или пользователь для удаления из администраторов")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_administrator(self, interaction: discord.Interaction, target: discord.Member | discord.Role):
        """Remove a user or role from administrators"""
        try:
            config = load_config()
            administrators = config.get('administrators', {'users': [], 'roles': []})
            
            if isinstance(target, discord.Member):
                if target.id in administrators['users']:
                    administrators['users'].remove(target.id)
                    config['administrators'] = administrators
                    save_config(config)
                    
                    await interaction.response.send_message(
                        f"✅ Пользователь {target.mention} удален из списка администраторов.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"⚠️ Пользователь {target.mention} не является администратором.",
                        ephemeral=True
                    )
            
            elif isinstance(target, discord.Role):
                if target.id in administrators['roles']:
                    administrators['roles'].remove(target.id)
                    config['administrators'] = administrators
                    save_config(config)
                    
                    await interaction.response.send_message(
                        f"✅ Роль {target.mention} удалена из списка администраторских ролей.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"⚠️ Роль {target.mention} не является администраторской.",
                        ephemeral=True
                    )
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при удалении администратора: {e}",
                ephemeral=True
            )
            print(f"Remove administrator error: {e}")

    @admin.command(name="list", description="📋 Показать список администраторов")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_administrators(self, interaction: discord.Interaction):
        """List all administrators and administrator roles"""
        try:
            config = load_config()
            administrators = config.get('administrators', {'users': [], 'roles': []})
            
            embed = discord.Embed(
                title="👑 Список администраторов",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )
            
            # Administrator users
            user_list = []
            for user_id in administrators.get('users', []):
                user = interaction.guild.get_member(user_id)
                if user:
                    user_list.append(f"• {user.mention} ({user.display_name})")
                else:
                    user_list.append(f"• <@{user_id}> (пользователь не найден)")
            
            if user_list:
                embed.add_field(
                    name="👤 Пользователи-администраторы",
                    value="\n".join(user_list),
                    inline=False
                )
            else:
                embed.add_field(
                    name="👤 Пользователи-администраторы",
                    value="Нет назначенных пользователей",
                    inline=False
                )
            
            # Administrator roles
            role_list = []
            for role_id in administrators.get('roles', []):
                role = interaction.guild.get_role(role_id)
                if role:
                    role_list.append(f"• {role.mention}")
                else:
                    role_list.append(f"• <@&{role_id}> (роль не найдена)")
            
            if role_list:
                embed.add_field(
                    name="👑 Администраторские роли",
                    value="\n".join(role_list),
                    inline=False
                )
            else:
                embed.add_field(
                    name="👑 Администраторские роли",
                    value="Нет назначенных ролей",
                    inline=False
                )
            
            embed.add_field(
                name="ℹ️ Привилегии администраторов",
                value=(
                    "• Одобрение/отклонение ЛЮБЫХ рапортов на увольнение\n"
                    "• Одобрение/отклонение ЛЮБЫХ заявок на выдачу ролей\n"
                    "• Доступ к команде /settings\n"
                    "• Игнорируют иерархические ограничения модераторов"
                ),
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при получении списка администраторов: {e}",
                ephemeral=True
            )
            print(f"List administrators error: {e}")

    @app_commands.command(name="send_welcome_message", description="📨 Отправить приветственное сообщение пользователю")
    @app_commands.describe(user="Пользователь, которому отправить приветственное сообщение")
    async def send_welcome_message(self, interaction: discord.Interaction, user: discord.Member):
        """Send welcome message to a specific user (admin only)"""
        try:
            # Check if user has administrator permissions
            from utils.config_manager import is_administrator
            config = load_config()
            
            if not (interaction.user.guild_permissions.administrator or is_administrator(interaction.user, config)):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этой команды. Требуются права администратора.", 
                    ephemeral=True
                )
                return
            
            # Import welcome system
            from forms.welcome_system import WelcomeSystem
            
            # Send welcome message
            success = await WelcomeSystem.send_welcome_message(user)
            
            if success:
                await interaction.response.send_message(
                    f"✅ Приветственное сообщение успешно отправлено пользователю {user.mention}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"⚠️ Не удалось отправить приветственное сообщение пользователю {user.mention}. "
                    f"Возможно, у пользователя закрыты личные сообщения.",
                    ephemeral=True
                )
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при отправке приветственного сообщения: {e}",
                ephemeral=True
            )
            print(f"Send welcome message error: {e}")

# Setup function for adding the cog to the bot
async def setup(bot):
    await bot.add_cog(ChannelManagementCog(bot))
