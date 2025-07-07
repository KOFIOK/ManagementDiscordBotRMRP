import discord
from datetime import datetime

from utils.config_manager import load_config


class SafeDocumentsManager:
    def __init__(self):
        self.config = load_config()

    async def handle_new_submission(self, interaction: discord.Interaction, form_data: dict):
        """Обработка новой заявки на безопасные документы"""
        try:
            # Определяем департамент пользователя
            from utils.department_manager import DepartmentManager
            dept_manager = DepartmentManager()
            user_department = dept_manager.get_user_department_name(interaction.user)
            
            # Создаем данные заявки
            application_data = {
                'user_id': interaction.user.id,
                'username': str(interaction.user),
                'timestamp': datetime.now().isoformat(),
                'status': 'pending',
                'department': user_department,  # Сохраняем департамент
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
            
            # Формируем content с пингами
            ping_content = await self.get_ping_content(channel, 'safe_documents', user_department)
            
            # Отправляем заявку с пингами в content
            message = await channel.send(content=ping_content, embed=embed, view=view)
            application_data['message_id'] = message.id
            
            # Обновляем view с ID сообщения
            view.application_data = application_data
            await message.edit(view=view)
            
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
            if not await self.check_moderator_permissions(
                interaction.user, 
                application_data.get('department'),
                application_data.get('user_id')
            ):
                error_message = await self.get_permission_error_message(
                    interaction.user,
                    application_data.get('department'),
                    application_data.get('user_id')
                )
                await interaction.response.send_message(
                    error_message,
                    ephemeral=True
                )
                return
            
            # Обновляем статус
            application_data['status'] = 'approved'
            application_data['approved_by'] = interaction.user.id
            application_data['approved_at'] = datetime.now().strftime("%d.%m.%Y в %H:%M")
            
            # Создаем новый embed
            embed = self.create_application_embed(application_data)
            
            # Создаем специальный view для одобренных заявок
            from .views import SafeDocumentsApprovedView
            view = SafeDocumentsApprovedView(application_data)
            
            # Обновляем сообщение с очисткой content (убираем пинги)
            await interaction.response.edit_message(content="", embed=embed, view=view)
            
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
            if not await self.check_moderator_permissions(
                interaction.user, 
                application_data.get('department'),
                application_data.get('user_id')
            ):
                error_message = await self.get_permission_error_message(
                    interaction.user,
                    application_data.get('department'),
                    application_data.get('user_id')
                )
                await interaction.response.send_message(
                    error_message,
                    ephemeral=True
                )
                return
            
            # Обновляем статус
            application_data['status'] = 'rejected'
            application_data['rejected_by'] = interaction.user.id
            application_data['rejected_at'] = datetime.now().strftime("%d.%m.%Y в %H:%M")
            application_data['rejection_reason'] = reason
            
            # Создаем новый embed
            embed = self.create_application_embed(application_data)
            
            # Создаем специальный view для отклоненных заявок
            from .views import SafeDocumentsRejectedView
            view = SafeDocumentsRejectedView(application_data)
            
            # Обновляем сообщение с очисткой content (убираем пинги)
            await interaction.response.edit_message(content="", embed=embed, view=view)
            
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
                interaction.user.id == original_data.get('user_id') or  # Автор заявки
                await self.check_moderator_permissions(
                    interaction.user, 
                    original_data.get('department'),
                    original_data.get('user_id')
                )  # Модератор
            )
            
            if not can_edit:
                # Если пользователь не автор заявки, показываем детальную ошибку
                if interaction.user.id != original_data.get('user_id'):
                    error_message = await self.get_permission_error_message(
                        interaction.user,
                        original_data.get('department'),
                        original_data.get('user_id')
                    )
                else:
                    error_message = "❌ У вас нет прав для редактирования этой заявки!"
                
                await interaction.response.send_message(
                    error_message,
                    ephemeral=True
                )
                return
            
            # Сохраняем важные поля из оригинальных данных
            updated_data['user_id'] = original_data.get('user_id')
            updated_data['username'] = original_data.get('username')
            updated_data['timestamp'] = original_data.get('timestamp')
            updated_data['message_id'] = original_data.get('message_id')
            
            # СОХРАНЯЕМ ОРИГИНАЛЬНЫЙ СТАТУС И СВЯЗАННЫЕ ДАННЫЕ
            original_status = original_data.get('status', 'pending')
            updated_data['status'] = original_status
            
            # Если заявка была одобрена, сохраняем данные об одобрении
            if original_status == 'approved':
                updated_data['approved_by'] = original_data.get('approved_by')
                updated_data['approved_at'] = original_data.get('approved_at')
            # Если заявка была отклонена, сохраняем данные об отклонении
            elif original_status == 'rejected':
                updated_data['rejected_by'] = original_data.get('rejected_by')
                updated_data['rejected_at'] = original_data.get('rejected_at')
                updated_data['rejection_reason'] = original_data.get('rejection_reason')
            
            # Обновляем данные редактирования
            updated_data['edited_by'] = interaction.user.id
            updated_data['edited_at'] = datetime.now().strftime("%d.%m.%Y в %H:%M")
            
            # Создаем новый embed
            embed = self.create_application_embed(updated_data)
            
            # Выбираем правильный view в зависимости от статуса
            if original_status == 'approved':
                from .views import SafeDocumentsApprovedView
                view = SafeDocumentsApprovedView(updated_data)
                content = ""  # Для одобренных заявок content пустой
            elif original_status == 'rejected':
                from .views import SafeDocumentsRejectedView
                view = SafeDocumentsRejectedView(updated_data)
                content = ""  # Для отклоненных заявок content пустой
            else:
                # Статус pending - обычный view с пингами
                from .views import SafeDocumentsApplicationView
                view = SafeDocumentsApplicationView(updated_data)
                # Для pending заявок сохраняем пинги
                user_department = updated_data.get('department')
                content = await self.get_ping_content(interaction.guild.get_channel(interaction.channel_id), 'safe_documents', user_department)
            
            # Обновляем текущее сообщение с правильным content
            await interaction.response.edit_message(content=content, embed=embed, view=view)
            
        except Exception as e:
            print(f"Error in handle_edit_update: {e}")
            await interaction.response.send_message(
                f"❌ Произошла ошибка при обновлении заявки: {str(e)}",
                ephemeral=True
            )

    def create_application_embed(self, application_data: dict) -> discord.Embed:
        """Создание embed для заявки"""
        status = application_data.get('status', 'pending')
        
        # Определяем цвет в зависимости от статуса
        if status == 'approved':
            color = discord.Color.green()
        elif status == 'rejected':
            color = discord.Color.red()
        else:
            color = discord.Color.yellow()
        
        # Создаем заголовок в description
        user_id = application_data.get('user_id')
        description = f"### 📋 Заявка от <@{user_id}>"
        
        embed = discord.Embed(
            description=description,
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
            text=f"ID: {application_data.get('user_id', 'Неизвестно')}"
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

    async def check_moderator_permissions(self, user: discord.Member, department: str = None, application_user_id: int = None) -> bool:
        """
        Проверка прав модератора с учетом иерархии
        
        Args:
            user: Пользователь, который пытается модерировать
            department: Департамент заявки (для проверки департаментных прав)
            application_user_id: ID автора заявки (для проверки иерархии)
            
        Returns:
            bool: True если пользователь может модерировать эту заявку
        """
        try:
            # Проверяем администраторов (высший приоритет - могут модерировать всё)
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
            
            # Проверяем, является ли пользователь модератором
            is_moderator_by_user = user.id in mod_users
            moderator_roles = [role for role in user.roles if role.id in mod_roles]
            is_moderator_by_role = len(moderator_roles) > 0
            
            if not (is_moderator_by_user or is_moderator_by_role):
                # Не модератор, проверяем департаментные права
                if department:
                    departments = self.config.get('departments', {})
                    for dept_key, dept_data in departments.items():
                        if dept_data.get('name') == department or dept_key.lower() == department.lower():
                            # Проверяем ключевую роль департамента
                            key_role_id = dept_data.get('key_role_id')
                            if key_role_id and key_role_id in user_role_ids:
                                return True
                return False
            
            # Если автор заявки не указан, разрешаем модерацию
            if not application_user_id:
                return True
            
            # Проверяем, не модерирует ли пользователь сам себя
            if user.id == application_user_id:
                return False  # Нельзя модерировать собственные заявки
            
            # Получаем автора заявки для проверки иерархии
            application_user = user.guild.get_member(application_user_id)
            if not application_user:
                return True  # Если автор не найден, разрешаем модерацию
            
            app_user_role_ids = [role.id for role in application_user.roles]
            
            # Проверяем, является ли автор заявки администратором
            app_is_admin = (
                application_user_id in admin_users or
                any(role_id in app_user_role_ids for role_id in admin_roles)
            )
            
            if app_is_admin:
                return False  # Модераторы не могут модерировать администраторов
            
            # Проверяем, является ли автор заявки модератором
            app_is_moderator_by_user = application_user_id in mod_users
            app_moderator_roles = [role for role in application_user.roles if role.id in mod_roles]
            app_is_moderator_by_role = len(app_moderator_roles) > 0
            
            if not (app_is_moderator_by_user or app_is_moderator_by_role):
                return True  # Модератор может модерировать обычного пользователя
            
            # Оба являются модераторами - проверяем иерархию ролей
            if is_moderator_by_role and app_is_moderator_by_role:
                # Находим наивысшую модераторскую роль у текущего пользователя
                user_highest_mod_role_position = max(role.position for role in moderator_roles)
                
                # Находим наивысшую модераторскую роль у автора заявки
                app_highest_mod_role_position = max(role.position for role in app_moderator_roles)
                
                # Модератор с более высокой ролью может модерировать модератора с более низкой ролью
                return user_highest_mod_role_position > app_highest_mod_role_position
            
            # Если один модератор по пользователю, а другой по роли - проверяем должности
            if is_moderator_by_user and app_is_moderator_by_role:
                # Модератор по пользователю не может модерировать модератора по роли
                return False
            
            if is_moderator_by_role and app_is_moderator_by_user:
                # Модератор по роли может модерировать модератора по пользователю
                return True
            
            # Оба модераторы по пользователю - запрещаем модерацию друг друга
            if is_moderator_by_user and app_is_moderator_by_user:
                return False
            
            # Проверяем права на конкретный департамент
            if department:
                departments = self.config.get('departments', {})
                for dept_key, dept_data in departments.items():
                    if dept_data.get('name') == department or dept_key.lower() == department.lower():
                        # Проверяем ключевую роль департамента
                        key_role_id = dept_data.get('key_role_id')
                        if key_role_id and key_role_id in user_role_ids:
                            return True
            
            return True  # По умолчанию разрешаем, если дошли до этого места
            
        except Exception as e:
            print(f"Error checking moderator permissions: {e}")
            return False

    async def get_permission_error_message(self, user: discord.Member, department: str = None, application_user_id: int = None) -> str:
        """
        Получить детальное сообщение об ошибке доступа
        
        Args:
            user: Пользователь, который пытается модерировать
            department: Департамент заявки
            application_user_id: ID автора заявки
            
        Returns:
            str: Детальное сообщение об ошибке
        """
        try:
            config = self.config
            admin_users = config.get('administrators', {}).get('users', [])
            admin_roles = config.get('administrators', {}).get('roles', [])
            mod_users = config.get('moderators', {}).get('users', [])
            mod_roles = config.get('moderators', {}).get('roles', [])
            
            user_role_ids = [role.id for role in user.roles]
            
            # Проверяем, является ли пользователь администратором
            is_admin = (
                user.id in admin_users or
                any(role_id in admin_roles for role_id in user_role_ids)
            )
            
            if is_admin:
                return "✅ У вас есть права администратора"
            
            # Проверяем, является ли пользователь модератором
            is_moderator_by_user = user.id in mod_users
            moderator_roles = [role for role in user.roles if role.id in mod_roles]
            is_moderator_by_role = len(moderator_roles) > 0
            
            if not (is_moderator_by_user or is_moderator_by_role):
                # Проверяем департаментные права
                if department:
                    departments = config.get('departments', {})
                    for dept_key, dept_data in departments.items():
                        if dept_data.get('name') == department or dept_key.lower() == department.lower():
                            key_role_id = dept_data.get('key_role_id')
                            if key_role_id and key_role_id in user_role_ids:
                                return "✅ У вас есть права командира департамента"
                
                return "❌ **Недостаточно прав для модерации**\n\nУ вас нет прав модератора, администратора или командира департамента."
            
            # Пользователь - модератор, проверяем ограничения
            if not application_user_id:
                return "✅ У вас есть права модератора"
            
            # Проверяем самомодерацию
            if user.id == application_user_id:
                return "❌ **Недостаточно прав для модерации**\n\nВы не можете модерировать собственные заявки."
            
            # Получаем автора заявки для проверки иерархии
            application_user = user.guild.get_member(application_user_id)
            if not application_user:
                return "✅ У вас есть права модератора"
            
            app_user_role_ids = [role.id for role in application_user.roles]
            
            # Проверяем, является ли автор заявки администратором
            app_is_admin = (
                application_user_id in admin_users or
                any(role_id in app_user_role_ids for role_id in admin_roles)
            )
            
            if app_is_admin:
                return "❌ **Недостаточно прав для модерации**\n\nВы не можете модерировать заявки администраторов."
            
            # Проверяем иерархию модераторов
            app_is_moderator_by_user = application_user_id in mod_users
            app_moderator_roles = [role for role in application_user.roles if role.id in mod_roles]
            app_is_moderator_by_role = len(app_moderator_roles) > 0
            
            if not (app_is_moderator_by_user or app_is_moderator_by_role):
                return "✅ У вас есть права модератора"
            
            # Оба модераторы - проверяем иерархию
            if is_moderator_by_role and app_is_moderator_by_role:
                user_highest_position = max(role.position for role in moderator_roles)
                app_highest_position = max(role.position for role in app_moderator_roles)
                
                if user_highest_position > app_highest_position:
                    return "✅ У вас более высокая модераторская роль"
                else:
                    user_highest_role = max(moderator_roles, key=lambda r: r.position)
                    app_highest_role = max(app_moderator_roles, key=lambda r: r.position)
                    
                    return (
                        f"❌ **Недостаточно прав для модерации**\n\n"
                        f"Ваша роль: **{user_highest_role.name}** (позиция {user_highest_position})\n"
                        f"Роль автора заявки: **{app_highest_role.name}** (позиция {app_highest_position})\n\n"
                        f"Вы можете модерировать только пользователей с более низкими ролями."
                    )
            
            if is_moderator_by_user and app_is_moderator_by_role:
                return "❌ **Недостаточно прав для модерации**\n\nВы не можете модерировать пользователей с модераторскими ролями."
            
            if is_moderator_by_role and app_is_moderator_by_user:
                return "✅ У вас есть модераторская роль"
            
            if is_moderator_by_user and app_is_moderator_by_user:
                return "❌ **Недостаточно прав для модерации**\n\nВы не можете модерировать других модераторов с персональными правами."
            
            return "✅ У вас есть права модератора"
            
        except Exception as e:
            print(f"Error getting permission error message: {e}")
            return "❌ Произошла ошибка при проверке прав доступа."

    async def get_ping_content(self, channel: discord.TextChannel, context: str, department: str = None) -> str:
        """Получает содержимое пинга для определенного контекста и департамента"""
        try:
            if not department:
                return ""
            
            departments = self.config.get('departments', {})
            
            # Находим департамент
            dept_data = None
            for dept_key, data in departments.items():
                if data.get('name') == department or dept_key.lower() == department.lower():
                    dept_data = data
                    break
            
            if not dept_data:
                return ""
            
            # Получаем роли для пинга
            ping_contexts = dept_data.get('ping_contexts', {})
            role_ids = ping_contexts.get(context, [])
            
            # Если для указанного контекста нет ролей, пробуем общий контекст
            if not role_ids:
                role_ids = ping_contexts.get('general', [])
            
            if not role_ids:
                return ""
            
            # Формируем пинг
            mentions = []
            for role_id in role_ids:
                role = channel.guild.get_role(role_id)
                if role:
                    mentions.append(role.mention)
            
            if mentions:
                return f"-# {' '.join(mentions)}"
            else:
                return ""
                
        except Exception as e:
            print(f"Error getting ping content: {e}")
            return ""

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
                "• Игровой номер телефона\n\n"
                "**Процесс рассмотрения:**\n"
                "1. Подача заявки через форму\n"
                "2. Проверка вашим руководством\n"
                "3. Подтверждение или отклонение с указанием причины\n"
                "4. Для отчёта на повышение нужна ссылка на подтверждённое заявление\n\n"
                "Нажмите кнопку ниже для подачи заявки.\n"
            ),
            color=discord.Color.blue()
        )
        
        embed.set_footer(
            text="Многие поля формы будут автоматически заполнены из вашего профиля, если данные доступны"
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
