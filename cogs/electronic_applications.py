"""
Электронные заявки на вступление/восстановление
Обработка вебхук-сообщений с заявками и отправка их в ЛС пользователям
"""

import discord
from discord.ext import commands
from typing import Optional
from utils.config_manager import load_config
from utils.logging_setup import get_logger
from utils.electronic_applications_utils import (
    markdown_to_discord,
    parse_discord_tag_from_content,
    find_user_by_tag,
    load_template,
    get_application_type
)

logger = get_logger(__name__)


class ElectronicApplicationsCog(commands.Cog):
    """Обработка электронных заявок через вебхуки"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = load_config()
        self.ea_config = self.config.get('electronic_applications', {})
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Event listener для обработки вебхук-сообщений с заявками"""
        
        # Проверяем, что это вебхук-сообщение в правильном канале
        if not message.webhook_id:
            return
        
        if self.ea_config.get('enabled', False):
            if message.channel.id != self.ea_config.get('channel_id'):
                return
        else:
            return
        
        try:
            logger.info(f"ELEC_APP: Получено вебхук-сообщение в канале {message.channel.id}")
            
            # Сбор текста из контента и embed-полей (вебхук часто кладет данные в поля)
            content_parts = []
            if message.content:
                content_parts.append(message.content)

            for embed in message.embeds:
                if embed.title:
                    content_parts.append(embed.title)
                if embed.description:
                    content_parts.append(embed.description)
                for field in embed.fields:
                    # Сохраняем поле в формате "имя\nзначение" — так Regex видит и заголовок, и значение
                    content_parts.append(f"{field.name}\n{field.value}")

            aggregated_content = "\n".join(content_parts).strip()

            # 1. Парсинг Discord-тага из агрегированного текста
            pattern = self.ea_config.get('discord_tag_pattern', '')
            discord_tag = parse_discord_tag_from_content(aggregated_content, pattern)
            
            if not discord_tag:
                logger.warning("ELEC_APP: Не удалось распарсить Discord-тег")
                await self._add_reaction(message, 'failure')
                return
            
            # 2. Поиск пользователя на сервере
            user = find_user_by_tag(message.guild, discord_tag)
            if not user:
                logger.warning(f"ELEC_APP: Пользователь не найден: {discord_tag}")
                await self._add_reaction(message, 'failure')
                return
            
            # 3. Определение типа заявки
            app_type = get_application_type(aggregated_content)
            
            # 4. Загрузка шаблона
            template_config = self.ea_config.get('templates', {}).get(app_type, {})
            template_path = template_config.get('path', self.ea_config.get('template_path', ''))
            
            template_content = load_template(template_path)
            if not template_content:
                logger.warning(f"ELEC_APP: Не удалось загрузить шаблон для типа: {app_type}")
                await self._add_reaction(message, 'failure')
                return
            
            # 5. Конвертация markdown → Discord и отправка DM
            dm_text = markdown_to_discord(template_content)
            
            try:
                await user.send(dm_text)
                logger.info(f"ELEC_APP SUCCESS: Сообщение отправлено пользователю {user.display_name}")
                await self._add_reaction(message, 'success')
            except discord.Forbidden:
                logger.warning(f"ELEC_APP: ДМ закрыты для пользователя {user.display_name}")
                await self._add_reaction(message, 'failure')
            except Exception as send_error:
                logger.error(f"ELEC_APP: Ошибка при отправке ДМ: {send_error}")
                await self._add_reaction(message, 'failure')
        
        except Exception as e:
            logger.error(f"ELEC_APP: Критическая ошибка при обработке: {e}")
            await self._add_reaction(message, 'failure')
    
    async def _add_reaction(self, message: discord.Message, status: str):
        """Добавление реакции к сообщению"""
        try:
            if status == 'success':
                reaction = self.ea_config.get('success_reaction', '✅')
            else:
                reaction = self.ea_config.get('failure_reaction', '❌')
            
            await message.add_reaction(reaction)
            logger.info(f"ELEC_APP: Реакция добавлена: {reaction}")
        except Exception as e:
            logger.error(f"ELEC_APP: Ошибка при добавлении реакции: {e}")


async def setup(bot: commands.Bot):
    """Загрузка Cog'а"""
    await bot.add_cog(ElectronicApplicationsCog(bot))
    logger.info("✅ ElectronicApplicationsCog загружен")
