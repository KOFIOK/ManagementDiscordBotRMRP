"""
Message Management Cog for Army Discord Bot
Provides administrative commands for managing bot messages
"""
import discord
from discord import app_commands
from discord.ext import commands
import os
import json
from typing import Dict, Any, Optional
from utils.message_manager import (
    get_message, save_guild_messages, load_guild_messages,
    validate_messages_structure, get_performance_report
)
from utils.config_manager import is_administrator, load_config
import datetime

class MessageManagement(commands.Cog):
    """Cog for managing bot messages through Discord commands"""

    def __init__(self, bot):
        self.bot = bot
        self.messages_dir = 'data/messages'
        self.backups_dir = os.path.join(self.messages_dir, 'backups')

        # Ensure backup directory exists
        os.makedirs(self.backups_dir, exist_ok=True)

    def _get_guild_messages_file(self, guild_id: int) -> str:
        """Get path to guild-specific messages file"""
        return os.path.join(self.messages_dir, f'messages-{guild_id}.yml')

    def _create_backup(self, guild_id: int, reason: str = "manual") -> str:
        """Create a backup of guild messages"""
        os.makedirs(self.backups_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"messages-{guild_id}_{timestamp}_{reason}.yml"
        backup_path = os.path.join(self.backups_dir, backup_filename)

        try:
            # Load current messages
            messages = load_guild_messages(guild_id)

            # Save backup
            import yaml
            with open(backup_path, 'w', encoding='utf-8') as f:
                yaml.dump(messages, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            # Clean up old backups (keep only 10 most recent per guild)
            self._cleanup_old_backups(guild_id)

            return backup_filename

        except Exception as e:
            raise Exception(f"Failed to create backup: {e}")

    def _cleanup_old_backups(self, guild_id: int):
        """Keep only 10 most recent backups for this guild"""
        if not os.path.exists(self.backups_dir):
            return

        try:
            # Find all backups for this guild
            guild_backups = [f for f in os.listdir(self.backups_dir) 
                           if f.startswith(f'messages-{guild_id}_') and f.endswith('.yml')]
            guild_backups.sort(key=lambda x: os.path.getmtime(os.path.join(self.backups_dir, x)), reverse=True)

            # Keep only first 10 (most recent)
            if len(guild_backups) > 10:
                for old_backup in guild_backups[10:]:
                    old_path = os.path.join(self.backups_dir, old_backup)
                    os.remove(old_path)

        except Exception as e:
            print(f"Warning: Failed to cleanup old backups: {e}")

        except Exception as e:
            print(f"Warning: Failed to cleanup old backups: {e}")

    def _get_message_categories(self, guild_id: int) -> Dict[str, str]:
        """Get available message categories for specific guild"""
        # Динамическая загрузка категорий из YAML файла
        try:
            messages = load_guild_messages(guild_id)  # Загружаем сообщения для конкретного гильда

            categories = {}
            if 'private_messages' in messages:
                for category_key in messages['private_messages'].keys():
                    # Преобразуем ключи в читаемые названия
                    category_names = {
                        "welcome": "Приветственные сообщения",
                        "role_assignment": "Назначение ролей",
                        "dismissal": "Увольнения",
                        "personnel": "Кадровые сообщения",
                        "department_applications": "Заявки в подразделения",
                        "leave_requests": "Заявки на отгул",
                        "safe_documents": "Безопасные документы",
                        "moderator_notifications": "Уведомления модераторов"
                    }
                    categories[category_key] = category_names.get(category_key, category_key.replace('_', ' ').title())

            return categories
        except Exception as e:
            print(f"Warning: Failed to load categories dynamically: {e}")
            # Fallback to hardcoded categories
            return {
                "welcome": "Приветственные сообщения",
                "role_assignment": "Назначение ролей",
                "dismissal": "Увольнения",
                "personnel": "Кадровые сообщения",
                "department_applications": "Заявки в подразделения",
                "leave_requests": "Заявки на отгул",
                "safe_documents": "Безопасные документы",
                "moderator_notifications": "Уведомления модераторов"
            }

    def _get_messages_in_category(self, guild_id: int, category: str) -> Dict[str, str]:
        """Get all messages in a specific category"""
        messages = load_guild_messages(guild_id)
        category_messages = {}

        # Check if category exists in private_messages
        if 'private_messages' in messages and category in messages['private_messages']:
            def extract_messages(data, prefix=""):
                result = {}
                for key, value in data.items():
                    current_key = f"{prefix}.{key}" if prefix else key
                    if isinstance(value, dict):
                        result.update(extract_messages(value, current_key))
                    elif isinstance(value, str):
                        result[current_key] = value
                return result

            category_messages = extract_messages(messages['private_messages'][category])

        # Also check direct categories (for non-private messages)
        elif category in messages:
            def extract_messages(data, prefix=""):
                result = {}
                for key, value in data.items():
                    current_key = f"{prefix}.{key}" if prefix else key
                    if isinstance(value, dict):
                        result.update(extract_messages(value, current_key))
                    elif isinstance(value, str):
                        result[current_key] = value
                return result

            category_messages = extract_messages(messages[category])

        return category_messages

    async def _check_admin_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has administrator permissions"""
        config = load_config()
        return is_administrator(interaction.user, config)

    @app_commands.command(name="messages", description="Управление сообщениями бота")
    @app_commands.describe(action="Действие с сообщениями")
    @app_commands.choices(action=[
        app_commands.Choice(name="📋 Список категорий", value="list"),
        app_commands.Choice(name="📊 Статистика", value="stats"),
        app_commands.Choice(name="💾 Создать бэкап", value="backup"),
        app_commands.Choice(name="🔄 Восстановить из бэкапа", value="restore")
    ])
    async def messages_command(self, interaction: discord.Interaction, action: str):
        """Main messages management command"""

        # Check admin permissions
        if not await self._check_admin_permissions(interaction):
            await interaction.response.send_message(
                "❌ У вас нет прав администратора для выполнения этой команды.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            if action == "list":
                await self._handle_list_categories(interaction)
            elif action == "stats":
                await self._handle_stats(interaction)
            elif action == "backup":
                await self._handle_backup(interaction)
            elif action == "restore":
                await self._handle_restore_list(interaction)

        except Exception as e:
            await interaction.followup.send(
                f"❌ Произошла ошибка: {str(e)}",
                ephemeral=True
            )

    async def _handle_list_categories(self, interaction: discord.Interaction):
        """Handle listing message categories"""
        categories = self._get_message_categories(interaction.guild.id)

        embed = discord.Embed(
            title="📂 Категории сообщений",
            description="Выберите категорию для просмотра сообщений:",
            color=0x00ff00
        )

        for category_key, category_name in categories.items():
            message_count = len(self._get_messages_in_category(interaction.guild.id, category_key))
            embed.add_field(
                name=f"{category_name}",
                value=f"`{category_key}` - {message_count} сообщений",
                inline=False
            )

        # Add navigation hint
        embed.set_footer(text="Используйте /messages_edit <категория> или /messages_download для скачивания файла")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="messages_edit", description="Редактировать сообщения")
    @app_commands.describe(category="Категория сообщения")
    @app_commands.choices(category=[
        app_commands.Choice(name="Приветственные сообщения", value="welcome"),
        app_commands.Choice(name="Назначение ролей", value="role_assignment"),
        app_commands.Choice(name="Увольнения", value="dismissal"),
        app_commands.Choice(name="Кадровые сообщения", value="personnel"),
        app_commands.Choice(name="Заявки в подразделения", value="department_applications"),
        app_commands.Choice(name="Заявки на отгул", value="leave_requests"),
        app_commands.Choice(name="Безопасные документы", value="safe_documents"),
        app_commands.Choice(name="Уведомления модераторов", value="moderator_notifications")
    ])
    async def messages_edit_command(self, interaction: discord.Interaction, category: str):
        """Edit messages in a specific category"""

        # Check admin permissions
        if not await self._check_admin_permissions(interaction):
            await interaction.response.send_message(
                "❌ У вас нет прав администратора для выполнения этой команды.",
                ephemeral=True
            )
            return

        # Validate category exists
        available_categories = self._get_message_categories(interaction.guild.id)
        if category not in available_categories:
            await interaction.response.send_message(
                f"❌ Категория `{category}` не найдена.\n\nДоступные категории:\n" +
                "\n".join([f"• `{key}` - {name}" for key, name in available_categories.items()]),
                ephemeral=True
            )
            return

        # Get messages in category
        messages = self._get_messages_in_category(interaction.guild.id, category)

        if not messages:
            await interaction.response.send_message(
                f"❌ В категории `{category}` нет доступных сообщений.",
                ephemeral=True
            )
            return

        # Create select menu for message selection
        options = []
        for key, value in list(messages.items())[:25]:  # Discord limit is 25 options
            # Truncate long values for display
            display_value = value[:50] + "..." if len(value) > 50 else value
            display_value = display_value.replace('\n', ' ')  # Remove newlines

            options.append(
                discord.SelectOption(
                    label=key[:25],  # Discord limit is 25 chars for label
                    description=display_value[:50],  # Discord limit is 50 chars for description
                    value=key
                )
            )

        if not options:
            await interaction.response.send_message(
                f"❌ В категории `{category}` нет доступных для редактирования сообщений.",
                ephemeral=True
            )
            return

        select = discord.ui.Select(
            placeholder="Выберите сообщение для редактирования...",
            options=options,
            custom_id=f"message_select_{category}"
        )

        view = MessageSelectView(select, self, interaction.guild.id, category)
        embed = discord.Embed(
            title=f"📝 Редактирование сообщений: {category}",
            description="Выберите сообщение для редактирования:",
            color=0x3498db
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="messages_download", description="Скачать файл сообщений для редактирования")
    async def messages_download_command(self, interaction: discord.Interaction):
        """Download the entire messages file for editing"""

        # Check admin permissions
        if not await self._check_admin_permissions(interaction):
            await interaction.response.send_message(
                "❌ У вас нет прав администратора для выполнения этой команды.",
                ephemeral=True
            )
            return

        await self._handle_full_file_download(interaction)

    @app_commands.command(name="messages_upload", description="Загрузить отредактированный файл сообщений")
    @app_commands.describe(file="YAML файл с отредактированными сообщениями")
    async def messages_upload_command(self, interaction: discord.Interaction, file: discord.Attachment):
        """Upload edited messages file"""

        # Check admin permissions
        if not await self._check_admin_permissions(interaction):
            await interaction.response.send_message(
                "❌ У вас нет прав администратора для выполнения этой команды.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Check if file is YAML
            if not file.filename.endswith('.yml') and not file.filename.endswith('.yaml'):
                await interaction.followup.send(
                    "❌ Файл должен иметь расширение .yml или .yaml",
                    ephemeral=True
                )
                return

            # Check file size (Discord limit is 25MB, but we want reasonable size)
            if file.size > 1024 * 1024:  # 1MB limit
                await interaction.followup.send(
                    "❌ Файл слишком большой (максимум 1MB)",
                    ephemeral=True
                )
                return

            # Download file content
            file_content = await file.read()
            yaml_content = file_content.decode('utf-8')
            
            # Parse YAML
            import yaml
            try:
                new_messages = yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                await interaction.followup.send(
                    f"❌ Ошибка в формате YAML файла: {str(e)}",
                    ephemeral=True
                )
                return

            # Validate structure
            from utils.message_manager import validate_messages_structure
            is_valid, errors = validate_messages_structure(interaction.guild.id, new_messages)
            
            if not is_valid:
                error_text = "\n".join([f"• {error}" for error in errors[:5]])  # Show first 5 errors
                if len(errors) > 5:
                    error_text += f"\n... и ещё {len(errors) - 5} ошибок"
                
                await interaction.followup.send(
                    f"❌ Найдены ошибки в структуре файла:\n{error_text}",
                    ephemeral=True
                )
                return

            # Create backup before applying changes
            try:
                self._create_backup(interaction.guild.id, "upload_full_file")
            except Exception as e:
                print(f"Warning: Failed to create backup before upload: {e}")

            # Save new messages
            success = save_guild_messages(interaction.guild.id, new_messages, create_backup=False)
            
            if success:
                embed = discord.Embed(
                    title="✅ Файл загружен успешно",
                    description="Сообщения обновлены из загруженного файла.",
                    color=0x00ff00
                )
                
                embed.add_field(
                    name="📊 Статистика",
                    value=f"Размер файла: {len(yaml_content)} символов\nВалидация: ✅ Пройдена",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ Ошибка сохранения файла сообщений.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Ошибка обработки файла: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="messages_add_category", description="Добавить новую категорию сообщений (Для новых функций, для разработчиков)")
    @app_commands.describe(
        category_key="Ключ категории (латиницей, без пробелов)",
        category_name="Отображаемое название категории"
    )
    async def messages_add_category_command(self, interaction: discord.Interaction, category_key: str, category_name: str):
        """Add a new message category"""

        # Check admin permissions
        if not await self._check_admin_permissions(interaction):
            await interaction.response.send_message(
                "❌ У вас нет прав администратора для выполнения этой команды.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Validate category key format
            if not category_key.replace('_', '').isalnum():
                await interaction.followup.send(
                    "❌ Ключ категории должен содержать только буквы, цифры и подчеркивания.",
                    ephemeral=True
                )
                return

            # Load current messages
            messages = load_guild_messages(interaction.guild.id)

            # Check if category already exists
            if 'private_messages' in messages and category_key in messages['private_messages']:
                await interaction.followup.send(
                    f"❌ Категория `{category_key}` уже существует.",
                    ephemeral=True
                )
                return

            # Initialize private_messages structure if needed
            if 'private_messages' not in messages:
                messages['private_messages'] = {}

            # Add new category with sample message
            messages['private_messages'][category_key] = {
                "sample_message": f"Пример сообщения для категории '{category_name}'"
            }

            # Save messages
            success = save_guild_messages(interaction.guild.id, messages, create_backup=True)

            if success:
                embed = discord.Embed(
                    title="✅ Категория добавлена",
                    description=f"Новая категория сообщений успешно создана.",
                    color=0x00ff00
                )

                embed.add_field(
                    name="📁 Категория",
                    value=f"Ключ: `{category_key}`\nНазвание: {category_name}",
                    inline=False
                )

                embed.add_field(
                    name="📝 Следующие шаги",
                    value="1. Используйте `/messages_download` для получения файла\n"
                          "2. Добавьте сообщения в новую категорию\n"
                          "3. Загрузите файл обратно через `/messages_upload`",
                    inline=False
                )

                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ Ошибка сохранения новой категории.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Ошибка добавления категории: {str(e)}",
                ephemeral=True
            )

    async def _handle_stats(self, interaction: discord.Interaction):
        """Handle showing message system statistics"""
        try:
            # Get performance report
            report = get_performance_report()

            # Validate structure
            is_valid, errors = validate_messages_structure(interaction.guild.id)

            embed = discord.Embed(
                title="📊 Статистика системы сообщений",
                color=0x3498db
            )

            # Cache stats
            cache_stats = report.get('cache_performance', {})
            embed.add_field(
                name="💾 Кэширование",
                value=f"Попаданий: {cache_stats.get('cache_hits', 0)}\n"
                      f"Промахов: {cache_stats.get('cache_misses', 0)}\n"
                      f"Точность: {cache_stats.get('hit_rate', '0%')}",
                inline=True
            )

            # File info
            file_info = report.get('file_info', {})
            embed.add_field(
                name="📁 Файлы",
                value=f"Размер: {file_info.get('default_messages_size_kb', 0)} KB\n"
                      f"Бэкапов: {file_info.get('backup_count', 0)}\n"
                      f"Статус: {'✅' if file_info.get('default_messages_exists') else '❌'}",
                inline=True
            )

            # System info
            system_info = report.get('system_info', {})
            embed.add_field(
                name="⚙️ Система",
                value=f"Python: {system_info.get('python_version', 'unknown')}\n"
                      f"Платформа: {system_info.get('platform', 'unknown')}",
                inline=True
            )

            # Validation status
            validation_status = "✅ Структура корректна" if is_valid else f"⚠️ Найдено проблем: {len(errors)}"
            embed.add_field(
                name="🔍 Валидация",
                value=validation_status,
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                f"❌ Ошибка получения статистики: {str(e)}",
                ephemeral=True
            )

    async def _handle_backup(self, interaction: discord.Interaction):
        """Handle creating a backup"""
        try:
            backup_name = self._create_backup(interaction.guild.id, "admin_command")

            embed = discord.Embed(
                title="💾 Бэкап создан",
                description=f"Создан бэкап сообщений гильдии: `{backup_name}`",
                color=0x00ff00
            )

            # Count remaining backups for this guild
            if os.path.exists(self.backups_dir):
                guild_backup_count = len([f for f in os.listdir(self.backups_dir) 
                                        if f.startswith(f'messages-{interaction.guild.id}_') and f.endswith('.yml')])
                embed.set_footer(text=f"Всего бэкапов для гильдии: {guild_backup_count} (хранится не более 10)")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                f"❌ Ошибка создания бэкапа: {str(e)}",
                ephemeral=True
            )

    async def _handle_restore_list(self, interaction: discord.Interaction):
        """Handle listing available backups for restore"""
        if not os.path.exists(self.backups_dir):
            await interaction.followup.send(
                "❌ Бэкапы не найдены.",
                ephemeral=True
            )
            return

        try:
            # Find backups for this guild
            guild_backups = [f for f in os.listdir(self.backups_dir) 
                           if f.startswith(f'messages-{interaction.guild.id}_') and f.endswith('.yml')]
            guild_backups.sort(key=lambda x: os.path.getmtime(os.path.join(self.backups_dir, x)), reverse=True)

            if not guild_backups:
                await interaction.followup.send(
                    "❌ Доступных бэкапов для этой гильдии нет.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🔄 Доступные бэкапы",
                description="Выберите бэкап для восстановления:",
                color=0xffa500
            )

            for i, backup in enumerate(guild_backups[:5]):  # Show first 5
                backup_path = os.path.join(self.backups_dir, backup)
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(backup_path))
                size = os.path.getsize(backup_path)

                embed.add_field(
                    name=f"📁 {backup}",
                    value=f"Дата: {mtime.strftime('%Y-%m-%d %H:%M')}\nРазмер: {size} bytes",
                    inline=False
                )

            embed.set_footer(text="Используйте /messages restore <имя_бэкапа> для восстановления")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                f"❌ Ошибка получения списка бэкапов: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="messages_restore", description="Восстановить сообщения из бэкапа")
    @app_commands.describe(backup_name="Имя файла бэкапа")
    async def messages_restore_command(self, interaction: discord.Interaction, backup_name: str):
        """Restore messages from a backup"""

        # Check admin permissions
        if not await self._check_admin_permissions(interaction):
            await interaction.response.send_message(
                "❌ У вас нет прав администратора для выполнения этой команды.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            backup_path = os.path.join(self.backups_dir, backup_name)

            if not os.path.exists(backup_path):
                await interaction.followup.send(
                    f"❌ Бэкап `{backup_name}` не найден.",
                    ephemeral=True
                )
                return

            # Load backup
            import yaml
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_messages = yaml.safe_load(f)

            # Save as current messages (without creating another backup)
            success = save_guild_messages(interaction.guild.id, backup_messages, create_backup=False)

            if success:
                embed = discord.Embed(
                    title="✅ Восстановление завершено",
                    description=f"Сообщения восстановлены из бэкапа: `{backup_name}`",
                    color=0x00ff00
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ Ошибка сохранения восстановленных сообщений.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Ошибка восстановления: {str(e)}",
                ephemeral=True
            )


    async def _handle_full_file_download(self, interaction: discord.Interaction):
        """Handle downloading the entire messages file for editing"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Load current messages
            messages = load_guild_messages(interaction.guild.id)

            # Serialize to YAML
            import yaml
            yaml_content = yaml.dump(messages, allow_unicode=True, default_flow_style=False, sort_keys=False)

            # Create filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"messages-{interaction.guild.id}_{timestamp}.yml"

            # Create Discord file
            from io import BytesIO
            file_obj = BytesIO(yaml_content.encode('utf-8'))
            discord_file = discord.File(file_obj, filename=filename)

            # Create embed with instructions
            embed = discord.Embed(
                title="📥 Файл сообщений скачан",
                description="Файл содержит все сообщения бота для редактирования.",
                color=0x3498db
            )

            embed.add_field(
                name="📝 Инструкции по редактированию",
                value="1. Отредактируйте файл в текстовом редакторе\n"
                      "2. Сохраните изменения\n"
                      "3. Загрузите файл обратно с помощью `/messages_upload`\n"
                      "4. Бот автоматически создаст бэкап перед применением изменений",
                inline=False
            )

            embed.add_field(
                name="⚠️ Важные замечания",
                value="- Не меняйте структуру YAML файла\n"
                      "- Сохраняйте кодировку UTF-8\n"
                      "- Максимальный размер файла: 1MB\n"
                      "- Файл будет проверен на корректность перед сохранением"
                      "- Функция не протестирована достаточно хорошо, используйте с осторожностью",
                inline=False
            )

            embed.set_footer(text=f"Размер файла: {len(yaml_content)} символов")

            # Send file with embed
            await interaction.followup.send(embed=embed, file=discord_file, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                f"❌ Ошибка создания файла для скачивания: {str(e)}",
                ephemeral=True
            )


class MessageSelectView(discord.ui.View):
    """View for selecting a message to edit"""

    def __init__(self, select, cog, guild_id, category):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.cog = cog
        self.guild_id = guild_id
        self.category = category
        self.add_item(select)

        # Set the callback for the select
        select.callback = self.select_callback

    async def select_callback(self, interaction: discord.Interaction):
        """Handle message selection"""
        # Get the select component from the interaction
        select = self.children[0]  # The select is the first child
        selected_key = select.values[0]

        # Get current message content
        try:
            # For private messages, we need to add the private_messages prefix
            full_key = f"private_messages.{self.category}.{selected_key}"
            current_message = get_message(self.guild_id, full_key)

            # Create modal for editing
            modal = MessageEditModal(self.cog, self.guild_id, full_key, current_message)
            await interaction.response.send_modal(modal)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка получения сообщения: {str(e)}",
                ephemeral=True
            )
        """Handle message selection"""
        selected_key = select.values[0]

        # Get current message content
        try:
            # For private messages, we need to add the private_messages prefix
            full_key = f"private_messages.{self.category}.{selected_key}"
            current_message = get_message(self.guild_id, full_key)

            # Create modal for editing
            modal = MessageEditModal(self.cog, self.guild_id, full_key, current_message)
            await interaction.response.send_modal(modal)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка получения сообщения: {str(e)}",
                ephemeral=True
            )


class MessageEditModal(discord.ui.Modal, title="Редактирование сообщения"):
    """Modal for editing message content"""

    def __init__(self, cog, guild_id, message_key, current_content):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.message_key = message_key

        # Create text input with truncated key for label
        # Discord limits label to 45 characters
        truncated_key = message_key[-35:] if len(message_key) > 35 else message_key
        label_text = f"Ключ: {truncated_key}" if len(f"Ключ: {truncated_key}") <= 45 else f"Ключ: ...{truncated_key[-30:]}"
        
        self.message_input = discord.ui.TextInput(
            label=label_text,
            style=discord.TextStyle.paragraph,
            placeholder=f"Полный ключ: {message_key}\n\nВведите новое содержимое сообщения...",
            default=current_content,
            max_length=4000,  # Discord limit for modals
            required=True
        )
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        try:
            new_content = self.message_input.value

            # Load current messages
            messages = load_guild_messages(self.guild_id)

            # Parse the full key path (private_messages.category.key)
            key_parts = self.message_key.split('.')
            if len(key_parts) < 3 or key_parts[0] != 'private_messages':
                raise ValueError("Invalid message key format")

            category = key_parts[1]
            message_key = '.'.join(key_parts[2:])

            # Navigate to the message location in private_messages
            if 'private_messages' not in messages:
                messages['private_messages'] = {}
            if category not in messages['private_messages']:
                messages['private_messages'][category] = {}

            current = messages['private_messages'][category]

            # Navigate to parent of the message
            sub_keys = message_key.split('.')
            for key in sub_keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # Update the message
            current[sub_keys[-1]] = new_content

            # Save messages (without automatic backup since we create manual backup below)
            success = save_guild_messages(self.guild_id, messages, create_backup=False)

            if success:
                # Create backup manually with descriptive name
                try:
                    self.cog._create_backup(self.guild_id, f"edit_{sub_keys[-1]}")
                except Exception as e:
                    print(f"Warning: Failed to create backup: {e}")

                embed = discord.Embed(
                    title="✅ Сообщение обновлено",
                    description=f"Ключ: `{self.message_key}`\n\n**Новое содержимое:**\n{new_content[:500]}{'...' if len(new_content) > 500 else ''}",
                    color=0x00ff00
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    "❌ Ошибка сохранения сообщения.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка обновления сообщения: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(MessageManagement(bot))