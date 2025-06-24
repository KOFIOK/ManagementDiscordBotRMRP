"""
Persistent Views для кнопок модерации заявок склада
"""

import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .status import WarehouseStatusView, DeletionConfirmView, RejectionReasonModal
    from .edit import WarehouseEditSelectView


class WarehousePersistentRequestView(discord.ui.View):
    """Persistent View для модерации одиночных запросов склада"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✅ Выдать склад", style=discord.ButtonStyle.green, custom_id="warehouse_approve", row=0)
    async def approve_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Одобрить запрос склада"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этого действия!", ephemeral=True
                )
                return
            
            # Обновление embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            
            # Добавляем информацию об одобрении
            embed.add_field(
                name="✅ Одобрено", 
                value=f"*Склад выдал: {interaction.user.mention}*", 
                inline=False
            )
            
            # Заменяем view на кнопку статуса "Одобрено" и очищаем пинги
            from .status import WarehouseStatusView
            status_view = WarehouseStatusView(status="approved")
            
            await interaction.response.edit_message(content="", embed=embed, view=status_view)
            
            # 📋 АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ЗАПИСИ АУДИТА
            try:
                from forms.warehouse.audit import create_automatic_audit_from_approval
                
                # Извлекаем информацию из embed'а заявки
                recipient_id = None
                items_list = []
                
                # Ищем ID получателя в footer
                if embed.footer and embed.footer.text and "ID пользователя:" in embed.footer.text:
                    try:
                        recipient_id = int(embed.footer.text.split("ID пользователя:")[-1].strip())
                    except (ValueError, IndexError):
                        pass
                
                # Извлекаем предметы из description
                if embed.description:
                    # Ищем строки с предметами (обычно содержат × или x)
                    for line in embed.description.split('\n'):
                        if '×' in line or 'x' in line:
                            items_list.append(line.strip())
                
                # Если не нашли предметы в description, ищем в полях
                if not items_list:
                    for field in embed.fields:
                        if any(keyword in field.name.lower() for keyword in ['предмет', 'запрос', 'заявка']):
                            if field.value:
                                for line in field.value.split('\n'):
                                    if '×' in line or 'x' in line:
                                        items_list.append(line.strip())
                
                items_text = '\n'.join(items_list) if items_list else "Предметы не указаны"
                request_url = interaction.message.jump_url
                
                # Создаем запись аудита, если получатель найден
                if recipient_id:
                    recipient = interaction.guild.get_member(recipient_id)
                    if recipient:
                        await create_automatic_audit_from_approval(
                            interaction.guild,
                            interaction.user,  # модератор
                            recipient,         # получатель
                            items_text,        # предметы
                            request_url        # ссылка на заявку
                        )
                        print(f"📋 AUTO AUDIT: Создана запись аудита для выдачи {recipient.display_name}")
                    else:
                        print(f"⚠️ AUTO AUDIT: Получатель с ID {recipient_id} не найден на сервере")
                else:
                    print(f"⚠️ AUTO AUDIT: Не удалось извлечь ID получателя из заявки")
                    
            except Exception as audit_error:
                print(f"❌ AUTO AUDIT: Ошибка при создании автоматического аудита: {audit_error}")
                # Не прерываем основной процесс одобрения из-за ошибки аудита
            
        except Exception as e:
            print(f"Ошибка при одобрении запроса склада: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.", ephemeral=True
            )
    
    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.red, custom_id="warehouse_reject", row=0)
    async def reject_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Отклонить запрос склада"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этого действия!", ephemeral=True
                )
                return

            # Показываем модальное окно для ввода причины отказа
            from .status import RejectionReasonModal
            rejection_modal = RejectionReasonModal(interaction.message)
            await interaction.response.send_modal(rejection_modal)
            
        except Exception as e:
            print(f"Ошибка при отклонении запроса склада: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.", ephemeral=True
            )

    @discord.ui.button(label="🗑️ Удалить запрос", style=discord.ButtonStyle.secondary, custom_id="warehouse_delete", row=1)
    async def delete_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Удалить запрос (доступно автору или администраторам)"""
        try:
            # Проверяем права на удаление
            can_delete = await self._check_delete_permissions(interaction)
            if not can_delete:
                return
            
            # Показываем ephemeral сообщение с кнопкой подтверждения
            embed = discord.Embed(
                title="⚠️ Подтверждение удаления",
                description="Вы действительно хотите удалить этот запрос склада?\n\n**Это действие необратимо!**",
                color=discord.Color.orange()
            )
            from .status import DeletionConfirmView
            confirm_view = DeletionConfirmView(interaction.message)
            await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
            
        except Exception as e:
            print(f"Ошибка при попытке удаления запроса склада: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.", ephemeral=True
            )

    @discord.ui.button(label="📝 Редактировать", style=discord.ButtonStyle.secondary, custom_id="warehouse_edit", row=1)
    async def edit_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Редактировать заявку (доступно только модераторам)"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для редактирования заявок!", ephemeral=True
                )
                return
            
            # Проверяем, что заявка ещё не обработана (нет статуса одобрения/отказа)
            embed = interaction.message.embeds[0]
            embed_text = str(embed.to_dict())
            
            if "✅ Одобрено" in embed_text or "❌ Отклонено" in embed_text:
                await interaction.response.send_message(
                    "❌ Нельзя редактировать уже обработанную заявку!", ephemeral=True
                )
                return
            
            # Показываем select menu с предметами для редактирования
            from .edit import WarehouseEditSelectView
            view = WarehouseEditSelectView(interaction.message)
            await interaction.response.send_message(
                "📝 Выберите предмет для редактирования:",
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Ошибка при попытке редактирования заявки: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.", ephemeral=True
            )
    
    async def _check_delete_permissions(self, interaction: discord.Interaction) -> bool:
        """Проверить права на удаление запроса"""
        try:
            # 1. Проверяем, является ли пользователь системным или Discord администратором
            from utils.moderator_auth import has_admin_permissions
            if await has_admin_permissions(interaction.user, interaction.guild):
                return True
            
            # 2. Проверяем, является ли пользователь автором запроса
            if interaction.message.embeds:
                embed = interaction.message.embeds[0]
                if embed.footer and embed.footer.text:
                    # Извлекаем ID автора из footer
                    footer_text = embed.footer.text
                    if "ID пользователя:" in footer_text:
                        try:
                            author_id = int(footer_text.split("ID пользователя:")[-1].strip())
                            if author_id == interaction.user.id:
                                return True
                        except (ValueError, IndexError):
                            pass
            
            # Если ни одно условие не выполнено - отказываем в доступе
            await interaction.response.send_message(
                "❌ У вас нет прав для удаления этого запроса!\n"
                "Удалить запрос может только его автор или администратор.",
                ephemeral=True
            )
            return False
            
        except Exception as e:
            print(f"Ошибка при проверке прав на удаление: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при проверке прав доступа.", ephemeral=True
            )
            return False


class WarehousePersistentMultiRequestView(discord.ui.View):
    """Persistent View для модерации множественных запросов склада"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✅ Выдать склад", style=discord.ButtonStyle.green, custom_id="warehouse_multi_approve", row=0)
    async def approve_all_requests(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Одобрить все запросы в заявке"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этого действия!", ephemeral=True
                )
                return

            # Обновление embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            
            # Добавляем информацию об одобрении
            embed.add_field(
                name="✅ Одобрено", 
                value=f"*Одобрил: {interaction.user.mention}*", 
                inline=False
            )
            
            # Заменяем view на кнопку статуса "Одобрено" и очищаем пинги
            from .status import WarehouseStatusView
            status_view = WarehouseStatusView(status="approved")
            
            await interaction.response.edit_message(content="", embed=embed, view=status_view)
            
            # 📋 АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ЗАПИСИ АУДИТА для множественного запроса
            try:
                from forms.warehouse.audit import create_automatic_audit_from_approval
                
                # Извлекаем информацию из embed'а заявки
                recipient_id = None
                items_list = []
                
                # Ищем ID получателя в footer
                if embed.footer and embed.footer.text and "ID пользователя:" in embed.footer.text:
                    try:
                        recipient_id = int(embed.footer.text.split("ID пользователя:")[-1].strip())
                    except (ValueError, IndexError):
                        pass
                
                # Извлекаем предметы из description (для множественных запросов)
                if embed.description:
                    for line in embed.description.split('\n'):
                        if '×' in line or 'x' in line:
                            items_list.append(line.strip())
                
                # Также проверяем поля embed'а
                if not items_list:
                    for field in embed.fields:
                        if any(keyword in field.name.lower() for keyword in ['предмет', 'запрос', 'заявка']):
                            if field.value:
                                for line in field.value.split('\n'):
                                    if '×' in line or 'x' in line:
                                        items_list.append(line.strip())
                
                items_text = '\n'.join(items_list) if items_list else "Множественный запрос - предметы не указаны"
                request_url = interaction.message.jump_url
                
                # Создаем запись аудита, если получатель найден
                if recipient_id:
                    recipient = interaction.guild.get_member(recipient_id)
                    if recipient:
                        await create_automatic_audit_from_approval(
                            interaction.guild,
                            interaction.user,  # модератор
                            recipient,         # получатель
                            items_text,        # предметы
                            request_url        # ссылка на заявку
                        )
                        print(f"📋 AUTO AUDIT: Создана запись аудита для множественной выдачи {recipient.display_name}")
                    else:
                        print(f"⚠️ AUTO AUDIT: Получатель с ID {recipient_id} не найден на сервере")
                else:
                    print(f"⚠️ AUTO AUDIT: Не удалось извлечь ID получателя из множественной заявки")
                    
            except Exception as audit_error:
                print(f"❌ AUTO AUDIT: Ошибка при создании автоматического аудита: {audit_error}")
                # Не прерываем основной процесс одобрения из-за ошибки аудита
            
        except Exception as e:
            print(f"Ошибка при одобрении множественного запроса: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса!", ephemeral=True
            )
    
    @discord.ui.button(label="❌ Отклонить заявку", style=discord.ButtonStyle.red, custom_id="warehouse_multi_reject", row=0)
    async def reject_all_requests(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Отклонить всю заявку"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этого действия!", ephemeral=True
                )
                return

            # Показываем модальное окно для ввода причины отказа
            from .status import RejectionReasonModal
            rejection_modal = RejectionReasonModal(interaction.message)
            await interaction.response.send_modal(rejection_modal)
            
        except Exception as e:
            print(f"Ошибка при отклонении множественной заявки: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.", ephemeral=True
            )

    @discord.ui.button(label="🗑️ Удалить запрос", style=discord.ButtonStyle.secondary, custom_id="warehouse_multi_delete", row=1)
    async def delete_all_requests(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Удалить всю заявку (доступно автору или администраторам)"""
        try:
            # Проверяем права на удаление
            can_delete = await self._check_delete_permissions(interaction)
            if not can_delete:
                return
            
            # Показываем ephemeral сообщение с кнопкой подтверждения
            embed = discord.Embed(
                title="⚠️ Подтверждение удаления",
                description="Вы действительно хотите удалить этот запрос склада?\n\n**Это действие необратимо!**",
                color=discord.Color.orange()
            )
            
            from .status import DeletionConfirmView
            confirm_view = DeletionConfirmView(interaction.message)
            await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
        except Exception as e:
            print(f"Ошибка при попытке удаления множественной заявки: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.", ephemeral=True
            )

    @discord.ui.button(label="📝 Редактировать", style=discord.ButtonStyle.secondary, custom_id="warehouse_multi_edit", row=1)
    async def edit_multi_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Редактировать множественную заявку (доступно только модераторам)"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для редактирования заявок!", ephemeral=True
                )
                return
            
            # Проверяем, что заявка ещё не обработана (нет статуса одобрения/отказа)
            embed = interaction.message.embeds[0]
            embed_text = str(embed.to_dict())
            
            if "✅ Одобрено" in embed_text or "❌ Отклонено" in embed_text:
                await interaction.response.send_message(
                    "❌ Нельзя редактировать уже обработанную заявку!", ephemeral=True
                )
                return
            
            # Показываем select menu с предметами для редактирования
            from .edit import WarehouseEditSelectView
            view = WarehouseEditSelectView(interaction.message)
            await interaction.response.send_message(
                "📝 Выберите предмет для редактирования:",
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Ошибка при попытке редактирования множественной заявки: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.", ephemeral=True
            )
    
    async def _check_delete_permissions(self, interaction: discord.Interaction) -> bool:
        """Проверить права на удаление запроса"""
        try:
            # 1. Проверяем, является ли пользователь системным или Discord администратором
            from utils.moderator_auth import has_admin_permissions
            if await has_admin_permissions(interaction.user, interaction.guild):
                return True
            
            # 2. Проверяем, является ли пользователь автором запроса
            if interaction.message.embeds:
                embed = interaction.message.embeds[0]
                if embed.footer and embed.footer.text:
                    # Извлекаем ID автора из footer
                    footer_text = embed.footer.text
                    if "ID пользователя:" in footer_text:
                        try:
                            author_id = int(footer_text.split("ID пользователя:")[-1].strip())
                            if author_id == interaction.user.id:
                                return True
                        except (ValueError, IndexError):
                            pass
            
            # Если ни одно условие не выполнено - отказываем в доступе
            await interaction.response.send_message(
                "❌ У вас нет прав для удаления этого запроса!\n"
                "Удалить запрос может только его автор или администратор.",
                ephemeral=True
            )
            return False
            
        except Exception as e:
            print(f"Ошибка при проверке прав на удаление: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при проверке прав доступа.", ephemeral=True
            )
            return False
