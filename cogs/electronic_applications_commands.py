"""
Команда для редактирования шаблона электронных заявок
"""

import discord
from discord import app_commands
from discord.ext import commands
from utils.config_manager import load_config, is_administrator
from utils.logging_setup import get_logger
from pathlib import Path

logger = get_logger(__name__)


class ElectronicApplicationsCommands(commands.Cog):
    """Команды для управления электронными заявками"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(
        name="message_request_edit",
        description="📋 Обновить шаблон сообщения электронных заявок"
    )
    @app_commands.describe(
        template_file="📄 Файл с новым шаблоном (.md формат)",
        application_type="Тип заявки: 'вступление' или 'восстановление'"
    )
    async def message_request_edit(
        self,
        interaction: discord.Interaction,
        template_file: discord.Attachment,
        application_type: str = "вступление"
    ):
        """
        Редактирование шаблона сообщения для электронных заявок
        
        Файл должен быть в markdown формате (.md)
        """
        
        # Проверка прав
        config = load_config()
        if not is_administrator(interaction.user, config):
            await interaction.response.send_message(
                "❌ У вас нет прав для редактирования шаблонов. Требуются права администратора.",
                ephemeral=True
            )
            return
        
        # Проверка типа заявки
        app_type = application_type.lower().strip()
        if app_type not in ['вступление', 'восстановление']:
            await interaction.response.send_message(
                "❌ Неверный тип заявки. Используйте: 'вступление' или 'восстановление'",
                ephemeral=True
            )
            return
        
        # Проверка расширения файла
        if not template_file.filename.endswith('.md'):
            await interaction.response.send_message(
                "❌ Файл должен быть в формате .md (markdown)",
                ephemeral=True
            )
            return
        
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Загружаем контент файла
            file_content = await template_file.read()
            file_text = file_content.decode('utf-8')
            
            # Определяем путь сохранения
            config = load_config()
            ea_config = config.get('electronic_applications', {})
            
            if app_type == 'вступление':
                save_path = ea_config.get('template_path', 'data/electronic_applications.md')
            else:  # восстановление
                templates = ea_config.get('templates', {})
                restore_config = templates.get('восстановление', {})
                save_path = restore_config.get('path', 'data/electronic_applications_restore.md')
            
            # Создаём директорию, если её нет
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Сохраняем файл
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(file_text)
            
            logger.info(f"ELEC_APP EDIT: Шаблон '{app_type}' обновлён пользователем {interaction.user.display_name}")
            
            await interaction.followup.send(
                f"✅ Шаблон для заявок на **{app_type}** успешно обновлён!\n"
                f"📄 Файл сохранён: `{save_path}`\n"
                f"📝 Размер: {len(file_text)} символов\n"
                f"👤 Обновлено: {interaction.user.mention}",
                ephemeral=True
            )
        
        except UnicodeDecodeError:
            await interaction.followup.send(
                "❌ Ошибка декодирования файла. Убедитесь, что файл в кодировке UTF-8.",
                ephemeral=True
            )
            logger.error(f"ELEC_APP EDIT: Ошибка декодирования файла от {interaction.user.display_name}")
        
        except Exception as e:
            await interaction.followup.send(
                f"❌ Ошибка при сохранении файла: {str(e)[:100]}",
                ephemeral=True
            )
            logger.error(f"ELEC_APP EDIT ERROR: {e}")


async def setup(bot: commands.Bot):
    """Загрузка команды"""
    await bot.add_cog(ElectronicApplicationsCommands(bot))
    logger.info("✅ ElectronicApplicationsCommands загружены")
