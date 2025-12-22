"""
Утилиты для системы склада - создание закрепленных сообщений и восстановление views
"""

import discord
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

async def restore_warehouse_pinned_message(channel):
    """Восстановить закрепленное сообщение склада после перезапуска"""
    try:
        from forms.warehouse import WarehousePinMessageView
        
        # Ищем закрепленное сообщение склада
        pinned_messages = await channel.pins()
        for message in pinned_messages:
            if (message.author == channel.guild.me and 
                message.embeds and 
                len(message.embeds) > 0 and
                message.embeds[0].title and
                "Запрос складского имущества" in message.embeds[0].title):
                
                # Проверяем, есть ли уже view
                if not message.components:
                    # Восстанавливаем view для закрепленного сообщения
                    view = WarehousePinMessageView()
                    await message.edit(view=view)
                    logger.info(f"Восстановлен view для закрепленного сообщения склада (ID: {message.id})")
                    return True
                else:
                    logger.info(f"Закрепленное сообщение склада уже имеет view (ID: {message.id})")
                    return True
        
        logger.info("Закрепленное сообщение склада не найдено")
        return False
        
    except Exception as e:
        logger.warning("Ошибка при восстановлении закрепленного сообщения склада: %s", e)
        return False


async def restore_warehouse_request_views(channel):
    """Восстановить view для заявок склада в канале"""
    try:
        from forms.warehouse import WarehousePersistentRequestView, WarehousePersistentMultiRequestView
        
        restored_count = 0
        
        # Проходим по последним сообщениям в канале
        async for message in channel.history(limit=100):
            if (message.author == channel.guild.me and 
                message.embeds and 
                len(message.embeds) > 0):
                
                embed = message.embeds[0]
                
                # Проверяем, что это заявка склада
                if (embed.title and 
                    "Запрос склада" in embed.title):
                    
                    # Пропускаем, если уже есть view или заявка закрыта
                    if message.components or "✅ Одобрено" in str(embed.fields) or "❌ Отклонено" in str(embed.fields):
                        continue
                    
                    try:
                        # Определяем тип заявки по количеству полей
                        is_multi_request = False
                        for field in embed.fields:
                            if "Запрашиваемые предметы" in field.name and "поз.)" in field.value:
                                is_multi_request = True
                                break
                        
                        # Восстанавливаем соответствующий view
                        if is_multi_request:
                            view = WarehousePersistentMultiRequestView()
                        else:
                            view = WarehousePersistentRequestView()
                        
                        # Добавляем view к сообщению
                        await message.edit(view=view)
                        restored_count += 1
                        
                    except Exception as e:
                        logger.error(f"Ошибка при восстановлении view для сообщения {message.id}: %s", e)
        
        if restored_count > 0:
            logger.info(f"Восстановлено %s warehouse views в канале {channel.name}", restored_count)
        
    except Exception as e:
        logger.warning("Ошибка при восстановлении warehouse views: %s", e)


async def send_warehouse_message(channel):
    """Отправить закрепленное сообщение склада - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    # Проверяем, что канал существует
    if not channel:
        logger.info("Канал склада не найден!")
        return False
    
    # Удаляем старые закрепленные сообщения склада
    try:
        pinned_messages = await channel.pins()
        for message in pinned_messages:
            if (message.author == channel.guild.me and 
                message.embeds and
                len(message.embeds) > 0 and
                message.embeds[0].title and
                "Запрос складского имущества" in message.embeds[0].title):
                try:
                    await message.unpin()
                    await message.delete()
                    logger.info(f"Удалено старое сообщение склада {message.id}")
                except:
                    pass
    except Exception as e:
        logger.error("Ошибка при проверке закрепленных сообщений: %s", e)
    
    # Создаем новое сообщение
    # Загружаем общие лимиты из конфигурации
    try:
        from utils.config_manager import load_config
        cfg = load_config()
        gl = cfg.get('warehouse_general_limits', {
            'weapons_max': 3,
            'materials_max': 2000,
            'armor_max': 20,
            'medkits_max': 25,
            'other_max': 15
        })
    except Exception:
        gl = {'weapons_max': 3, 'materials_max': 2000, 'armor_max': 20, 'medkits_max': 25, 'other_max': 15}

    embed = discord.Embed(
        title="📦 Запрос складского имущества",
        description=(
            "Добро пожаловать в систему склада!\n"
            "Выберите категорию складского имущества для запроса.\n\n"
            "### 📋 Правила запроса:\n"
            "> • **Кулдаун**: 6 часов между запросами\n"
            "> • **Лимиты**: в соответствии с должностью/званием\n"
            "> • **Модерация**: все запросы проходят проверку\n"
            "> • **Обязательно**: указывайте корректные данные\n\n"
            "### ⚠️ Ограничения (правило `4.20. Слив склада`):\n"
            f"> • **Оружие**: максимум {gl.get('weapons_max', 3)} единицы\n"
            f"> • **Материалы**: максимум {gl.get('materials_max', 2000)}\n"
            f"> • **Бронежилеты**: максимум {gl.get('armor_max', 20)} единиц\n"
            f"> • **Аптечки**: максимум {gl.get('medkits_max', 25)} единиц\n"
            f"> • **Прочее**: максимум {gl.get('other_max', 15)} предметов\n\n"
            "*Точные лимиты зависят от вашей должности и звания*"
        ),
        color=discord.Color.orange(),
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(
        name="📢 Информация по складу",
        value=(
            "После выбора категории откроется форма для ввода:\n"
            "• Имя Фамилия\n"
            "• Статик\n"
            "• Количество предметов\n\n"
            "Ваши данные будут автоматически заполнены из системы, если они есть."
        ),
        inline=False
    )
    
    embed.set_footer(
        text="Склад ВС РФ | Выберите категорию ниже",
        icon_url=channel.guild.icon.url if channel.guild.icon else None
    )
      # Создаем view с категориями - ИСПРАВЛЕННАЯ ВЕРСИЯ
    from forms.warehouse import WarehousePinMessageView
    view = WarehousePinMessageView()
    
    # Отправляем сообщение
    try:
        message = await channel.send(embed=embed, view=view)
        logger.info(f"Сообщение склада отправлено (ID: {message.id})")
        
        # Закрепляем сообщение
        await message.pin()
        logger.info(f"Сообщение склада закреплено (ID: {message.id})")
        
        return True
        
    except discord.Forbidden:
        logger.info(f"Нет прав для отправки/закрепления сообщений в канале {channel.name}")
        raise Exception("Бот не имеет прав для отправки или закрепления сообщений в этом канале")
    except discord.HTTPException as e:
        if e.code == 30003:
            logger.info(f"Слишком много закрепленных сообщений в канале {channel.name}")
            raise Exception("В канале слишком много закрепленных сообщений (лимит 50)")
        else:
            logger.warning("HTTP ошибка: %s", e)
            raise Exception(f"Ошибка при создании сообщения: {e}")
    except Exception as e:
        logger.warning("Ошибка при создании сообщения склада: %s", e)
        raise


async def recreate_warehouse_pinned_message(channel):
    """Пересоздать закрепленное сообщение склада с обновленными кнопками"""
    try:
        # Удаляем старое закрепленное сообщение если есть
        pinned_messages = await channel.pins()
        for message in pinned_messages:
            if (message.author == channel.guild.me and 
                message.embeds and 
                len(message.embeds) > 0 and
                message.embeds[0].title and
                "Запрос складского имущества" in message.embeds[0].title):
                
                logger.info(f"Удаляем старое сообщение склада (ID: {message.id})")
                await message.unpin()
                await message.delete()
                break
        
        # Создаём новое сообщение
        await send_warehouse_message(channel)
        logger.info("Пересоздано закрепленное сообщение склада с обновленными кнопками")
        return True
        
    except Exception as e:
        logger.warning("Ошибка при пересоздании сообщения склада: %s", e)
        return False