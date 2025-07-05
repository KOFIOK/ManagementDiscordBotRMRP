"""
Утилиты для системы склада - создание закрепленных сообщений и восстановление views
"""

import discord


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
                    print(f"✅ Восстановлен view для закрепленного сообщения склада (ID: {message.id})")
                    return True
                else:
                    print(f"✅ Закрепленное сообщение склада уже имеет view (ID: {message.id})")
                    return True
        
        print("⚠️ Закрепленное сообщение склада не найдено")
        return False
        
    except Exception as e:
        print(f"❌ Ошибка при восстановлении закрепленного сообщения склада: {e}")
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
                        print(f"Ошибка при восстановлении view для сообщения {message.id}: {e}")
        
        if restored_count > 0:
            print(f"✅ Восстановлено {restored_count} warehouse views в канале {channel.name}")
        
    except Exception as e:
        print(f"❌ Ошибка при восстановлении warehouse views: {e}")


async def send_warehouse_message(channel):
    """Отправить закрепленное сообщение склада - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    # Проверяем, что канал существует
    if not channel:
        print("❌ Канал склада не найден!")
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
                    print(f"Удалено старое сообщение склада {message.id}")
                except:
                    pass
    except Exception as e:
        print(f"Ошибка при проверке закрепленных сообщений: {e}")
    
    # Создаем новое сообщение
    embed = discord.Embed(
        title="📦 Запрос складского имущества",
        description=(
            "Добро пожаловать в систему склада ВС РФ!\n"
            "Выберите категорию складского имущества для запроса.\n\n"
            "### 📋 Правила запроса:\n"
            "> • **Кулдаун**: 6 часов между запросами\n"
            "> • **Лимиты**: в соответствии с должностью/званием\n"
            "> • **Модерация**: все запросы проходят проверку\n"
            "> • **Обязательно**: указывайте корректные данные\n\n"
            "### 📦 Доступные категории:\n"
            "> 🔫 **Оружие** - стрелковое вооружение\n"
            "> 🦺 **Бронежилеты** - защитное снаряжение\n"
            "> 💊 **Медикаменты** - аптечки, обезболивающие, дефибрилляторы\n"
            "> 📦 **Другое** - материалы, патроны, спецоборудование\n\n"
            "### ⚠️ Ограничения:\n"
            "> • **Оружие**: максимум 3 единицы оружия\n"
            "> • **Боеприпасы**: максимум 1.000 материалов\n"
            "> • **Бронежилеты**: максимум 15 единиц\n"
            "> • **Аптечки**: максимум 20 единиц\n\n"
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
    view = WarehousePinMessageView()  # Без параметров!
    
    # Отправляем сообщение
    try:
        message = await channel.send(embed=embed, view=view)
        print(f"✅ Сообщение склада отправлено (ID: {message.id})")
        
        # Закрепляем сообщение
        await message.pin()
        print(f"✅ Сообщение склада закреплено (ID: {message.id})")
        
        return True
        
    except discord.Forbidden:
        print(f"❌ Нет прав для отправки/закрепления сообщений в канале {channel.name}")
        raise Exception("Бот не имеет прав для отправки или закрепления сообщений в этом канале")
    except discord.HTTPException as e:
        if e.code == 30003:  # Too many pinned messages
            print(f"❌ Слишком много закрепленных сообщений в канале {channel.name}")
            raise Exception("В канале слишком много закрепленных сообщений (лимит 50)")
        else:
            print(f"❌ HTTP ошибка: {e}")
            raise Exception(f"Ошибка при создании сообщения: {e}")
    except Exception as e:
        print(f"❌ Ошибка при создании сообщения склада: {e}")
        raise


async def recreate_warehouse_pinned_message(channel):
    """Пересоздать закрепленное сообщение склада с обновленными кнопками"""
    try:
        from forms.warehouse import WarehousePinMessageView
        
        # Удаляем старое закрепленное сообщение если есть
        pinned_messages = await channel.pins()
        for message in pinned_messages:
            if (message.author == channel.guild.me and 
                message.embeds and 
                len(message.embeds) > 0 and
                message.embeds[0].title and
                "Запрос складского имущества" in message.embeds[0].title):
                
                print(f"🗑️ Удаляем старое сообщение склада (ID: {message.id})")
                await message.unpin()
                await message.delete()
                break
        
        # Создаём новое сообщение
        await send_warehouse_message(channel)
        print("✅ Пересоздано закрепленное сообщение склада с обновленными кнопками")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при пересоздании сообщения склада: {e}")
        return False
