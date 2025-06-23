"""
Система аудита склада - автоматическая и ручная
Включает в себя:
1. Автоматический аудит при одобрении заявок
2. Ручное создание записей аудита (выдача/чистка)
3. Модальные окна для заполнения форм аудита
"""

import discord
from datetime import datetime
from typing import Optional
from utils.config_manager import load_config


# =================== PERSISTENT VIEWS для аудита склада ===================

class WarehouseAuditPinMessageView(discord.ui.View):
    """View для закрепленного сообщения аудита склада"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="📋 Аудит выдачи", 
        style=discord.ButtonStyle.primary, 
        custom_id="warehouse_audit_issue"
    )
    async def create_issue_audit(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Создать запись аудита выдачи"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для создания записей аудита!\n"
                    "Доступно только модераторам и администраторам.",
                    ephemeral=True
                )
                return
            
            # Показываем модальное окно для создания аудита выдачи
            modal = WarehouseIssueAuditModal()
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"Ошибка при создании аудита выдачи: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при открытии формы аудита.", ephemeral=True
            )
    
    @discord.ui.button(
        label="🧹 Аудит чистки", 
        style=discord.ButtonStyle.secondary, 
        custom_id="warehouse_audit_cleaning"
    )
    async def create_cleaning_audit(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Создать запись аудита чистки"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для создания записей аудита!\n"
                    "Доступно только модераторам и администраторам.",
                    ephemeral=True
                )
                return
            
            # Показываем модальное окно для создания аудита чистки
            modal = WarehouseCleaningAuditModal()
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"Ошибка при создании аудита чистки: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при открытии формы аудита.", ephemeral=True
            )


# =================== МОДАЛЬНЫЕ ОКНА для аудита ===================

class WarehouseIssueAuditModal(discord.ui.Modal):
    """Модальное окно для создания записи аудита выдачи"""
    
    def __init__(self):
        super().__init__(title="Аудит выдачи склада")
        self.recipient_input = discord.ui.TextInput(
            label="Кому выдано",
            placeholder="@пользователь, ID пользователя или имя получателя",
            min_length=2,
            max_length=100,
            required=True
        )
        
        self.items_input = discord.ui.TextInput(
            label="Какие предметы выданы",
            placeholder="Перечислите выданные предметы",
            style=discord.TextStyle.paragraph,
            min_length=5,
            max_length=1000,
            required=True
        )
        
        self.reason_input = discord.ui.TextInput(
            label="Ссылка на заявку или причина",
            placeholder="Вставьте ссылку на заявку или укажите причину выдачи",
            style=discord.TextStyle.paragraph,
            min_length=5,
            max_length=500,
            required=True
        )
        
        self.comment_input = discord.ui.TextInput(
            label="Комментарий (опционально)",
            placeholder="Дополнительные сведения",
            style=discord.TextStyle.paragraph,
            min_length=0,
            max_length=300,
            required=False
        )
        
        self.add_item(self.recipient_input)
        self.add_item(self.items_input)
        self.add_item(self.reason_input)
        self.add_item(self.comment_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отправки формы аудита выдачи"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Создаем запись аудита
            audit_data = {
                "type": "issue",
                "issuer": interaction.user,
                "recipient": self.recipient_input.value.strip(),
                "items": self.items_input.value.strip(),
                "reason": self.reason_input.value.strip(),
                "comment": self.comment_input.value.strip() if self.comment_input.value else None,
                "timestamp": datetime.now()
            }
            
            success = await create_audit_record(interaction.guild, audit_data)
            
            if not success:
                await interaction.followup.send(
                    "❌ Ошибка при создании записи аудита. Проверьте настройки канала.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"Ошибка при обработке аудита выдачи: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при создании записи аудита.",
                ephemeral=True
            )


class WarehouseCleaningAuditModal(discord.ui.Modal):
    """Модальное окно для создания записи аудита чистки"""
    
    def __init__(self):
        super().__init__(title="Аудит чистки склада")
        
        self.action_input = discord.ui.TextInput(
            label="Что было выполнено",
            placeholder="чистка/сортировка/удаление лишнего/проверка остатков",
            style=discord.TextStyle.paragraph,
            min_length=5,
            max_length=500,
            required=True
        )
        
        self.details_input = discord.ui.TextInput(
            label="Подробности (опционально)",
            placeholder="Дополнительная информация о проведенной работе",
            style=discord.TextStyle.paragraph,
            min_length=0,
            max_length=800,
            required=False
        )
        
        self.add_item(self.action_input)
        self.add_item(self.details_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отправки формы аудита чистки"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Создаем запись аудита
            audit_data = {
                "type": "cleaning",
                "cleaner": interaction.user,
                "action": self.action_input.value.strip(),
                "details": self.details_input.value.strip() if self.details_input.value else None,
                "timestamp": datetime.now()
            }
            
            success = await create_audit_record(interaction.guild, audit_data)
            
            if not success:
                await interaction.followup.send(
                    "❌ Ошибка при создании записи аудита. Проверьте настройки канала.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"Ошибка при обработке аудита чистки: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при создании записи аудита.",
                ephemeral=True
            )


# =================== ФУНКЦИИ для создания записей аудита ===================

async def create_audit_record(guild: discord.Guild, audit_data: dict) -> bool:
    """
    Создать запись аудита в канале аудита склада
    
    Args:
        guild: Сервер Discord
        audit_data: Данные для создания записи аудита
        
    Returns:
        bool: True если запись создана успешно
    """
    try:
        config = load_config()
        audit_channel_id = config.get('warehouse_audit_channel')
        
        if not audit_channel_id:
            print("❌ Канал аудита склада не настроен")
            return False
        
        channel = guild.get_channel(audit_channel_id)
        if not channel:
            print(f"❌ Канал аудита склада не найден (ID: {audit_channel_id})")
            return False        
        if audit_data["type"] == "issue":
            embed = await create_issue_audit_embed(audit_data)
            await channel.send(embed=embed)
        elif audit_data["type"] == "cleaning":
            embed = await create_cleaning_audit_embed(audit_data)
            # Для аудита чистки создаем content с пингами кураторов
            content = await create_cleaning_audit_content()
            await channel.send(content=content, embed=embed)
        else:
            print(f"❌ Неизвестный тип аудита: {audit_data['type']}")
            return False
        
        print(f"✅ Запись аудита создана в канале {channel.name}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при создании записи аудита: {e}")
        return False


async def create_issue_audit_embed(audit_data: dict) -> discord.Embed:
    """Создать embed для записи аудита выдачи"""
    embed = discord.Embed(
        title="📋 Аудит выдачи склада",
        color=discord.Color.blue(),
        timestamp=audit_data["timestamp"]
    )
    
    embed.add_field(
        name="👤 Выдал",
        value=audit_data["issuer"].mention,
        inline=True
    )
    
    # Обрабатываем получателя - может быть ID, упоминание или текст
    recipient_text = audit_data["recipient"]
    
    # Проверяем, является ли это Discord ID (только цифры)
    if recipient_text.isdigit():
        try:
            user_id = int(recipient_text)
            recipient_display = f"<@{user_id}>"
        except ValueError:
            recipient_display = recipient_text
    else:
        recipient_display = recipient_text
    
    embed.add_field(
        name="👥 Получил",
        value=recipient_display,
        inline=True
    )
    
    embed.add_field(
        name="📦 Предметы",
        value=audit_data["items"],
        inline=False
    )
    
    embed.add_field(
        name="🔗 Ссылка/Причина",
        value=audit_data["reason"],
        inline=False
    )
    
    if audit_data.get("comment"):
        embed.add_field(
            name="💬 Комментарий",
            value=audit_data["comment"],
            inline=False
        )
    
    embed.set_footer(
        text=f"ID аудитора: {audit_data['issuer'].id}",
        icon_url=audit_data["issuer"].display_avatar.url
    )
    
    return embed


async def create_cleaning_audit_embed(audit_data: dict) -> discord.Embed:
    """Создать embed для записи аудита чистки"""
    embed = discord.Embed(
        title="🧹 Аудит чистки склада",
        color=discord.Color.orange(),
        timestamp=audit_data["timestamp"]
    )
    
    embed.add_field(
        name="👤 Ответственный",
        value=audit_data["cleaner"].mention,
        inline=True
    )
    
    embed.add_field(
        name="🔧 Выполненные действия",
        value=audit_data["action"],
        inline=False
    )
    
    if audit_data.get("details"):
        embed.add_field(
            name="📋 Подробности",
            value=audit_data["details"],
            inline=False
        )
    
    embed.set_footer(
        text=f"ID ответственного: {audit_data['cleaner'].id}",
        icon_url=audit_data["cleaner"].display_avatar.url
    )
    
    return embed


async def create_automatic_audit_from_approval(
    guild: discord.Guild, 
    moderator: discord.Member, 
    recipient: discord.Member, 
    items: str, 
    request_url: str
) -> bool:
    """
    Создать автоматическую запись аудита при одобрении заявки склада
    
    Args:
        guild: Сервер Discord
        moderator: Модератор, который одобрил заявку
        recipient: Пользователь, который получил предметы
        items: Строка с перечислением предметов
        request_url: Ссылка на оригинальную заявку
        
    Returns:
        bool: True если запись создана успешно    """
    try:
        audit_data = {
            "type": "issue",
            "issuer": moderator,
            "recipient": recipient.mention,  # Используем mention для автоматических записей
            "items": items,
            "reason": f"[Ссылка на заявку]({request_url})",
            "comment": "Автоматическая запись при одобрении заявки",
            "timestamp": datetime.now()
        }
        
        success = await create_audit_record(guild, audit_data)
        
        if success:
            print(f"✅ Автоматический аудит создан для выдачи {recipient.display_name}")
        else:
            print(f"❌ Не удалось создать автоматический аудит для {recipient.display_name}")
        
        return success
        
    except Exception as e:
        print(f"❌ Ошибка при создании автоматического аудита: {e}")
        return False


# =================== УТИЛИТЫ для аудита склада ===================

async def send_warehouse_audit_message(channel: discord.TextChannel) -> bool:
    """
    Отправить закрепленное сообщение для аудита склада
    
    Args:
        channel: Канал для отправки сообщения
        
    Returns:
        bool: True если сообщение отправлено успешно
    """
    try:
        embed = discord.Embed(
            title="📋 Аудит склада",
            description=(
                "**Система учета движения складского имущества**\n\n"
                "🔹 **Аудит выдачи** - для записи выдачи предметов со склада\n"
                "🔹 **Аудит чистки** - для записи работ по чистке и сортировке склада\n\n"
                "⚠️ Доступно только модераторам и администраторам"
            ),
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="📋 Аудит выдачи включает:",
            value="• Кто выдал предметы\n• Кому выданы предметы\n• Список выданных предметов\n• Ссылка на заявку или причина выдачи",
            inline=False
        )
        
        embed.add_field(
            name="🧹 Аудит чистки включает:",
            value="• Кто проводил чистку\n• Выполненные действия (чистка/сортировка/удаление)",
            inline=False
        )
        
        embed.set_footer(text="Все записи аудита автоматически сохраняются с отметкой времени")
        
        view = WarehouseAuditPinMessageView()
        message = await channel.send(embed=embed, view=view)
        
        # Пытаемся закрепить сообщение
        try:
            await message.pin()
            print(f"✅ Сообщение аудита склада закреплено в {channel.name}")
        except discord.Forbidden:
            print(f"⚠️ Нет прав для закрепления сообщения в {channel.name}")
        except discord.HTTPException as e:
            print(f"⚠️ Ошибка при закреплении сообщения в {channel.name}: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения аудита склада: {e}")
        return False


async def restore_warehouse_audit_views(channel: discord.TextChannel) -> bool:
    """
    Восстановить view для существующих сообщений аудита склада
    
    Args:
        channel: Канал аудита склада
        
    Returns:
        bool: True если views восстановлены успешно
    """
    try:
        print(f"🔄 Восстановление views аудита склада в {channel.name}")
        
        # Ищем все сообщения аудита склада (не только закрепленное)
        restored_count = 0
        
        async for message in channel.history(limit=50):
            if (message.author.id == channel.guild.me.id and 
                message.embeds and 
                len(message.embeds) > 0 and
                message.embeds[0].title and
                "Аудит склада" in message.embeds[0].title):
                
                # Проверяем, есть ли уже view
                if not message.components:
                    view = WarehouseAuditPinMessageView()
                    try:
                        await message.edit(view=view)
                        print(f"✅ View восстановлен для сообщения аудита склада (ID: {message.id})")
                        restored_count += 1
                    except discord.NotFound:
                        print(f"⚠️ Сообщение аудита склада не найдено для восстановления (ID: {message.id})")
                    except Exception as e:
                        print(f"❌ Ошибка при восстановлении view аудита склада (ID: {message.id}): {e}")
                else:
                    print(f"ℹ️ Сообщение аудита склада уже имеет view (ID: {message.id})")
        
        if restored_count > 0:
            print(f"✅ Восстановлено {restored_count} view(s) для сообщений аудита склада")
        else:
            print(f"ℹ️ Сообщения аудита склада с отсутствующими views не найдены в {channel.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при восстановлении views аудита склада: {e}")
        return False


async def restore_warehouse_audit_pinned_message(channel: discord.TextChannel) -> bool:
    """
    Восстановить закрепленное сообщение аудита склада после перезапуска
    
    Args:
        channel: Канал аудита склада
        
    Returns:
        bool: True если сообщение аудита найдено и восстановлено
    """
    try:
        # Сначала ищем среди закрепленных сообщений
        pinned_messages = await channel.pins()
        
        for message in pinned_messages:
            if (message.author == channel.guild.me and 
                message.embeds and 
                len(message.embeds) > 0 and
                message.embeds[0].title and
                "Аудит склада" in message.embeds[0].title):
                
                # Проверяем, есть ли уже view
                if not message.components:
                    # Восстанавливаем view для закрепленного сообщения
                    view = WarehouseAuditPinMessageView()
                    await message.edit(view=view)
                    print(f"✅ Восстановлен view для закрепленного сообщения аудита склада (ID: {message.id})")
                    return True
                else:
                    print(f"✅ Закрепленное сообщение аудита склада уже имеет view (ID: {message.id})")
                    return True
        
        # Если среди закрепленных не найдено, ищем в истории канала
        async for message in channel.history(limit=50):
            if (message.author == channel.guild.me and 
                message.embeds and 
                len(message.embeds) > 0 and
                message.embeds[0].title and
                "Аудит склада" in message.embeds[0].title):
                
                # Проверяем, есть ли уже view
                if not message.components:
                    # Восстанавливаем view для сообщения аудита
                    view = WarehouseAuditPinMessageView()
                    await message.edit(view=view)
                    print(f"✅ Восстановлен view для сообщения аудита склада в истории (ID: {message.id})")
                    
                    # Пытаемся закрепить сообщение
                    if not message.pinned:
                        try:
                            await message.pin()
                            print(f"✅ Сообщение аудита склада закреплено (ID: {message.id})")
                        except discord.Forbidden:
                            print(f"⚠️ Нет прав для закрепления сообщения аудита")
                        except discord.HTTPException as e:
                            print(f"⚠️ Ошибка при закреплении сообщения аудита: {e}")
                    
                    return True
                else:
                    print(f"✅ Сообщение аудита склада в истории уже имеет view (ID: {message.id})")
                    
                    # Пытаемся закрепить сообщение если оно не закреплено
                    if not message.pinned:
                        try:
                            await message.pin()
                            print(f"✅ Сообщение аудита склада закреплено (ID: {message.id})")
                        except discord.Forbidden:
                            print(f"⚠️ Нет прав для закрепления сообщения аудита")
                        except discord.HTTPException as e:
                            print(f"⚠️ Ошибка при закреплении сообщения аудита: {e}")
                    
                    return True
        
        return False
        
    except Exception as e:
        print(f"❌ Ошибка при восстановлении сообщения аудита склада: {e}")
        return False


async def create_cleaning_audit_content() -> str:
    """Создать content с пингами кураторов для аудита чистки"""
    config = load_config()
    curators = config.get('warehouse_audit_curators', [])
    
    if not curators:
        return "-# Кураторы ГО не настроены"
    
    curator_mentions = []
    for curator in curators:
        if isinstance(curator, str) and curator.isdigit():
            # Это ID пользователя
            curator_mentions.append(f"<@{curator}>")
        elif isinstance(curator, str) and curator.startswith('<@&') and curator.endswith('>'):
            # Это роль
            curator_mentions.append(curator)
        elif isinstance(curator, str):
            # Это текст или имя - не пингуем
            continue
    
    if curator_mentions:
        return f"-# {' '.join(curator_mentions)}"
    else:
        return "-# Кураторы ГО не настроены"
