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

class ChannelManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="settings", description="⚙️ Настройка каналов Discord бота")
    @app_commands.checks.has_permissions(administrator=True)
    async def settings(self, interaction: discord.Interaction):
        """Unified command for bot configuration with interactive interface"""
        await send_settings_message(interaction)

    @app_commands.command(name="addmoder", description="👮 Добавить модератора (роль или пользователя)")
    @app_commands.describe(target="Роль или пользователь для назначения модератором")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_moderator(self, interaction: discord.Interaction, target: discord.Member | discord.Role):
        """Add a user or role as moderator"""
        try:
            config = load_config()
            moderators = config.get('moderators', {'users': [], 'roles': []})
            
            if isinstance(target, discord.Member):
                if target.id not in moderators['users']:
                    moderators['users'].append(target.id)
                    config['moderators'] = moderators
                    save_config(config)
                    
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

    @app_commands.command(name="removemoder", description="🚫 Убрать модератора (роль или пользователя)")
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

    @app_commands.command(name="listmoders", description="📋 Показать список модераторов")
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
            )

# Setup function for adding the cog to the bot
async def setup(bot):
    await bot.add_cog(ChannelManagementCog(bot))
