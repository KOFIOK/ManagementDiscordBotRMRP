import discord
from datetime import datetime

from utils.config_manager import load_config


class SafeDocumentsManager:
    def __init__(self):
        self.config = load_config()

    async def handle_new_submission(self, interaction: discord.Interaction, form_data: dict):
        """Обработка новой заявки на безопасные документы"""
        try:
            # Создаем данные заявки
            application_data = {
                'user_id': interaction.user.id,
                'username': str(interaction.user),
                'timestamp': datetime.now().isoformat(),
                'status': 'pending',
                **form_data
            }
            
            # Создаем embed для заявки
            embed = self.create_application_embed(application_data)
            
            # Создаем view для модерации
            from .views import SafeDocumentsApplicationView
            view = SafeDocumentsApplicationView(application_data)
            
            # Отправляем заявку в канал для модерации
            channel_id = self.config.get('safe_documents_channel')
            if not channel_id:
                await interaction.response.send_message(
                    "❌ Канал для безопасных документов не настроен!",
                    ephemeral=True
                )
                return
            
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "❌ Канал для безопасных документов не найден!",
                    ephemeral=True
                )
                return
            
            # Отправляем заявку
            message = await channel.send(embed=embed, view=view)
            application_data['message_id'] = message.id
            
            # Обновляем view с ID сообщения
            view.application_data = application_data
            await message.edit(view=view)
            
            # Пингуем роли
            await self.ping_roles(channel, 'safe_documents', form_data.get('department'))
            
            # Отвечаем пользователю
            await interaction.response.send_message(
                "✅ Ваша заявка на безопасные документы была отправлена на рассмотрение!",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error in handle_new_submission: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Произошла ошибка при обработке заявки: {str(e)}",
                    ephemeral=True
                )

    async def handle_approval(self, interaction: discord.Interaction, application_data: dict):
        """Обработка одобрения заявки"""
        try:
            # Проверяем права модератора
            if not await self.check_moderator_permissions(interaction.user, application_data.get('department')):
                await interaction.response.send_message(
                    "❌ У вас нет прав для одобрения этой заявки!",
                    ephemeral=True
                )
                return
            
            # Обновляем статус
            application_data['status'] = 'approved'
            application_data['approved_by'] = interaction.user.id
            application_data['approved_at'] = datetime.now().isoformat()
            
            # Создаем новый embed
            embed = self.create_application_embed(application_data)
            
            # Создаем новый view (без кнопок, так как заявка обработана)
            from .views import SafeDocumentsApplicationView
            view = SafeDocumentsApplicationView(application_data, disabled=True)
            
            # Обновляем сообщение
            await interaction.response.edit_message(embed=embed, view=view)
            
            # Уведомляем пользователя
            await self.notify_user(interaction.guild, application_data, 'approved')
            
        except Exception as e:
            print(f"Error in handle_approval: {e}")
            await interaction.response.send_message(
                f"❌ Произошла ошибка при одобрении заявки: {str(e)}",
                ephemeral=True
            )

    async def handle_rejection(self, interaction: discord.Interaction, application_data: dict, reason: str):
        """Обработка отклонения заявки"""
        try:
            # Проверяем права модератора
            if not await self.check_moderator_permissions(interaction.user, application_data.get('department')):
                await interaction.response.send_message(
                    "❌ У вас нет прав для отклонения этой заявки!",
                    ephemeral=True
                )
                return
            
            # Обновляем статус
            application_data['status'] = 'rejected'
            application_data['rejected_by'] = interaction.user.id
            application_data['rejected_at'] = datetime.now().isoformat()
            application_data['rejection_reason'] = reason
            
            # Создаем новый embed
            embed = self.create_application_embed(application_data)
            
            # Создаем новый view (без кнопок)
            from .views import SafeDocumentsApplicationView
            view = SafeDocumentsApplicationView(application_data, disabled=True)
            
            # Обновляем сообщение
            await interaction.response.edit_message(embed=embed, view=view)
            
            # Уведомляем пользователя
            await self.notify_user(interaction.guild, application_data, 'rejected', reason)
            
        except Exception as e:
            print(f"Error in handle_rejection: {e}")
            await interaction.response.send_message(
                f"❌ Произошла ошибка при отклонении заявки: {str(e)}",
                ephemeral=True
            )

    async def handle_edit_update(self, interaction: discord.Interaction, updated_data: dict, original_data: dict):
        """Обработка обновления отредактированной заявки"""
        try:
            # Проверяем права на редактирование
            can_edit = (
                interaction.user.id == original_data['user_id'] or  # Автор заявки
                await self.check_moderator_permissions(interaction.user, original_data.get('department'))  # Модератор
            )
            
            if not can_edit:
                await interaction.response.send_message(
                    "❌ У вас нет прав для редактирования этой заявки!",
                    ephemeral=True
                )
                return
            
            # Обновляем данные
            updated_data['status'] = 'pending'  # Сбрасываем статус на ожидание
            updated_data['edited_by'] = interaction.user.id
            updated_data['edited_at'] = datetime.now().isoformat()
            
            # Создаем новый embed
            embed = self.create_application_embed(updated_data)
            
            # Создаем новый view
            from .views import SafeDocumentsApplicationView
            view = SafeDocumentsApplicationView(updated_data)
            
            # Находим оригинальное сообщение и обновляем его
            channel_id = self.config.get('safe_documents_channel')
            if channel_id:
                channel = interaction.guild.get_channel(channel_id)
                if channel and original_data.get('message_id'):
                    try:
                        message = await channel.fetch_message(original_data['message_id'])
                        await message.edit(embed=embed, view=view)
                    except discord.NotFound:
                        # Сообщение не найдено, создаем новое
                        message = await channel.send(embed=embed, view=view)
                        updated_data['message_id'] = message.id
            
            await interaction.response.send_message(
                "✅ Заявка успешно обновлена!",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error in handle_edit_update: {e}")
            await interaction.response.send_message(
                f"❌ Произошла ошибка при обновлении заявки: {str(e)}",
                ephemeral=True
            )

    def create_application_embed(self, application_data: dict) -> discord.Embed:
        """Создание embed для заявки"""
        status = application_data.get('status', 'pending')
        
        # Определяем цвет и заголовок в зависимости от статуса
        if status == 'approved':
            color = discord.Color.green()
            title = "✅ Заявка на безопасные документы (Одобрена)"
        elif status == 'rejected':
            color = discord.Color.red()
            title = "❌ Заявка на безопасные документы (Отклонена)"
        else:
            color = discord.Color.yellow()
            title = "📋 Заявка на безопасные документы (На рассмотрении)"
        
        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.fromisoformat(application_data['timestamp'])
        )
        
        # Основная информация
        embed.add_field(
            name="👤 Имя Фамилия",
            value=application_data.get('name', 'Не указано'),
            inline=True
        )
        
        embed.add_field(
            name="🎭 Статик",
            value=application_data.get('static', 'Не указано'),
            inline=True
        )
        
        embed.add_field(
            name="📞 Игровой телефон",
            value=application_data.get('phone', 'Не указано'),
            inline=True
        )
        
        embed.add_field(
            name="📧 Почта",
            value=application_data.get('email', 'Не указано'),
            inline=True
        )
        
        embed.add_field(
            name="📎 Копия всех документов",
            value=application_data.get('documents', 'Не указано'),
            inline=False
        )
        
        # Информация о пользователе
        embed.set_footer(
            text=f"Заявка от {application_data.get('username', 'Неизвестно')} • ID: {application_data.get('user_id', 'Неизвестно')}"
        )
        
        # Дополнительная информация в зависимости от статуса
        if status == 'approved':
            embed.add_field(
                name="✅ Одобрено",
                value=f"<@{application_data.get('approved_by', 'Неизвестно')}>\n{application_data.get('approved_at', 'Неизвестно')}",
                inline=True
            )
        elif status == 'rejected':
            embed.add_field(
                name="❌ Отклонено",
                value=f"<@{application_data.get('rejected_by', 'Неизвестно')}>\n{application_data.get('rejected_at', 'Неизвестно')}",
                inline=True
            )
            
            if application_data.get('rejection_reason'):
                embed.add_field(
                    name="📝 Причина отклонения",
                    value=application_data['rejection_reason'],
                    inline=False
                )
        
        # Информация о редактировании
        if application_data.get('edited_by'):
            embed.add_field(
                name="✏️ Последнее редактирование",
                value=f"<@{application_data['edited_by']}>\n{application_data.get('edited_at', 'Неизвестно')}",
                inline=True
            )
        
        return embed

    async def check_moderator_permissions(self, user: discord.Member, department: str = None) -> bool:
        """Проверка прав модератора"""
        try:
            # Проверяем администраторов
            admin_users = self.config.get('administrators', {}).get('users', [])
            admin_roles = self.config.get('administrators', {}).get('roles', [])
            
            if user.id in admin_users:
                return True
                
            user_role_ids = [role.id for role in user.roles]
            if any(role_id in admin_roles for role_id in user_role_ids):
                return True
            
            # Проверяем модераторов
            mod_users = self.config.get('moderators', {}).get('users', [])
            mod_roles = self.config.get('moderators', {}).get('roles', [])
            
            if user.id in mod_users:
                return True
                
            if any(role_id in mod_roles for role_id in user_role_ids):
                return True
            
            # Проверяем права на конкретный департамент
            if department:
                departments = self.config.get('departments', {})
                for dept_key, dept_data in departments.items():
                    if dept_data.get('name') == department or dept_key.lower() == department.lower():
                        # Проверяем ключевую роль департамента
                        key_role_id = dept_data.get('key_role_id')
                        if key_role_id and key_role_id in user_role_ids:
                            return True
            
            return False
            
        except Exception as e:
            print(f"Error checking moderator permissions: {e}")
            return False

    async def ping_roles(self, channel: discord.TextChannel, context: str, department: str = None):
        """Пинг ролей для определенного контекста"""
        try:
            if not department:
                return
            
            departments = self.config.get('departments', {})
            
            # Находим департамент
            dept_data = None
            for dept_key, data in departments.items():
                if data.get('name') == department or dept_key.lower() == department.lower():
                    dept_data = data
                    break
            
            if not dept_data:
                return
            
            # Получаем роли для пинга
            ping_contexts = dept_data.get('ping_contexts', {})
            role_ids = ping_contexts.get(context, [])
            
            if not role_ids:
                return
            
            # Формируем пинг
            mentions = []
            for role_id in role_ids:
                role = channel.guild.get_role(role_id)
                if role:
                    mentions.append(role.mention)
            
            if mentions:
                ping_message = f"📋 Новая заявка на безопасные документы: {' '.join(mentions)}"
                await channel.send(ping_message, delete_after=60)  # Удаляем через минуту
                
        except Exception as e:
            print(f"Error pinging roles: {e}")

    async def notify_user(self, guild: discord.Guild, application_data: dict, status: str, reason: str = None):
        """Уведомление пользователя о результате рассмотрения заявки"""
        try:
            user_id = application_data.get('user_id')
            if not user_id:
                return
            
            user = guild.get_member(user_id)
            if not user:
                return
            
            if status == 'approved':
                embed = discord.Embed(
                    title="✅ Заявка одобрена",
                    description="Ваша заявка на безопасные документы была одобрена!",
                    color=discord.Color.green()
                )
            elif status == 'rejected':
                embed = discord.Embed(
                    title="❌ Заявка отклонена",
                    description="Ваша заявка на безопасные документы была отклонена.",
                    color=discord.Color.red()
                )
                
                if reason:
                    embed.add_field(
                        name="📝 Причина",
                        value=reason,
                        inline=False
                    )
            else:
                return
            
            embed.add_field(
                name="📋 Данные заявки",
                value=f"**Имя Фамилия:** {application_data.get('name', 'Не указано')}\n"
                      f"**Статик:** {application_data.get('static', 'Не указано')}\n"
                      f"**Телефон:** {application_data.get('phone', 'Не указано')}\n"
                      f"**Почта:** {application_data.get('email', 'Не указано')}",
                inline=False
            )
            
            embed.timestamp = datetime.now()
            
            try:
                await user.send(embed=embed)
            except discord.Forbidden:
                # Если не можем отправить ЛС, можно попробовать отправить в канал
                pass
                
        except Exception as e:
            print(f"Error notifying user: {e}")


async def ensure_safe_documents_pin_message(bot, channel_id: int = None) -> bool:
    """
    Создает или обновляет закрепленное сообщение с кнопкой подачи заявки на safe documents
    
    Args:
        bot: Экземпляр бота Discord
        channel_id: ID канала для отправки сообщения (если None, берется из конфига)
        
    Returns:
        bool: True если сообщение создано/обновлено успешно
    """
    try:
        config = load_config()
        
        # Определяем канал
        if not channel_id:
            channel_id = config.get('safe_documents_channel')
            
        if not channel_id:
            print("❌ Safe documents channel not configured")
            return False
            
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"❌ Safe documents channel {channel_id} not found")
            return False
        
        # Создаем embed для закрепленного сообщения
        embed = discord.Embed(
            title="📋 Система безопасных документов",
            description=(
                "Здесь вы можете подать заявку на размещение ваших документов в безопасном хранилище.\n\n"
                "**Что нужно подготовить:**\n"
                "• Имя Фамилия\n"
                "• Статик\n"
                "• Копия всех документов (паспорт, мед книжка, справка нарколога, права, военный билет)\n"
                "• Игровой номер телефона\n"
                "• Ваша почта [Discord@rmrp.ru]\n\n"
                "**Процесс рассмотрения:**\n"
                "1. Подача заявки через форму\n"
                "2. Проверка модераторами\n"
                "3. Одобрение или отклонение с указанием причины\n"
                "4. Возможность редактирования заявки\n\n"
                "Нажмите кнопку ниже для подачи заявки."
            ),
            color=discord.Color.blue()
        )
        
        embed.set_footer(
            text="Все поля формы будут автоматически заполнены из вашего профиля, если данные доступны"
        )
        
        # Создаем view с кнопкой
        from .views import SafeDocumentsPinView
        view = SafeDocumentsPinView()
        
        # Проверяем существующие сообщения в канале
        async for message in channel.history(limit=50):
            if (message.author == bot.user and 
                message.embeds and 
                len(message.embeds) > 0 and
                "Система безопасных документов" in message.embeds[0].title):
                
                try:
                    # Обновляем существующее сообщение
                    await message.edit(embed=embed, view=view)
                    
                    # Закрепляем сообщение если оно не закреплено
                    if not message.pinned:
                        await message.pin()
                    
                    print(f"✅ Safe documents pin message updated in {channel.name}")
                    return True
                    
                except discord.Forbidden:
                    print(f"❌ No permission to edit/pin message in {channel.name}")
                    return False
                except Exception as e:
                    print(f"❌ Error updating safe documents message: {e}")
                    continue
        
        # Если существующее сообщение не найдено, создаем новое
        try:
            message = await channel.send(embed=embed, view=view)
            await message.pin()
            
            print(f"✅ Safe documents pin message created in {channel.name}")
            return True
            
        except discord.Forbidden:
            print(f"❌ No permission to send/pin message in {channel.name}")
            return False
        except Exception as e:
            print(f"❌ Error creating safe documents pin message: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error in ensure_safe_documents_pin_message: {e}")
        return False


async def setup_safe_documents_system(bot) -> bool:
    """
    Настройка системы safe documents при старте бота
    
    Args:
        bot: Экземпляр бота Discord
        
    Returns:
        bool: True если система настроена успешно
    """
    try:
        config = load_config()
        channel_id = config.get('safe_documents_channel')
        
        if not channel_id:
            print("ℹ️ Safe documents channel not configured, skipping setup")
            return True
            
        success = await ensure_safe_documents_pin_message(bot, channel_id)
        
        if success:
            print("✅ Safe documents system setup completed")
        else:
            print("❌ Safe documents system setup failed")
            
        return success
        
    except Exception as e:
        print(f"❌ Error setting up safe documents system: {e}")
        return False
