"""
Views и модалы для управления статусом заявок склада
"""

import discord
from utils.message_manager import get_warehouse_message


class WarehouseStatusView(discord.ui.View):
    """View для отображения статуса запроса (кнопки Одобрено/Отказано)"""
    
    def __init__(self, status: str):
        super().__init__(timeout=None)
        self.status = status
        
        if status == "approved":
            button = discord.ui.Button(
                label="✅ Одобрено",
                style=discord.ButtonStyle.green,
                disabled=True,
                custom_id="warehouse_status_approved"
            )
        elif status == "rejected":
            button = discord.ui.Button(
                label="❌ Отклонено", 
                style=discord.ButtonStyle.red,
                disabled=True,
                custom_id="warehouse_status_rejected"
            )
        else:
            button = discord.ui.Button(
                label="⏳ В обработке",
                style=discord.ButtonStyle.gray,
                disabled=True,
                custom_id="warehouse_status_pending"
            )
        
        self.add_item(button)


class DeletionConfirmView(discord.ui.View):
    """View с кнопкой подтверждения удаления запроса"""
    
    def __init__(self, original_message: discord.Message):
        super().__init__(timeout=30)  # 30 секунд на подтверждение
        self.original_message = original_message
    
    @discord.ui.button(label="🗑️ Подтвердить удаление", style=discord.ButtonStyle.danger)
    async def confirm_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Подтвердить удаление запроса"""
        try:
            # Определяем, кто удаляет запрос
            if self.original_message.embeds:
                embed = self.original_message.embeds[0]
                footer_text = embed.footer.text if embed.footer else ""
                
                # Проверяем, является ли пользователь автором
                is_author = False
                if "ID пользователя:" in footer_text:
                    try:
                        author_id = int(footer_text.split("ID пользователя:")[-1].strip())
                        is_author = (author_id == interaction.user.id)
                    except (ValueError, IndexError):
                        pass
                
                # Формируем сообщение об удалении
                if is_author:
                    deletion_info = f"*Удалено автором: {interaction.user.mention}*"
                else:
                    deletion_info = f"*Удалено администратором: {interaction.user.mention}*"
            
            # Отправляем подтверждение удаления
            await interaction.response.send_message(
                f"🗑️ **Запрос склада удален**\n\n{deletion_info}",
                ephemeral=True
            )
            
            # Удаляем оригинальное сообщение
            try:
                await self.original_message.delete()
                print(f"✅ DELETE: Запрос склада удален пользователем {interaction.user.display_name}")
            except discord.NotFound:
                # Сообщение уже удалено
                pass
            except discord.Forbidden:
                await interaction.followup.send(
                    "⚠️ Нет прав для удаления сообщения. Обратитесь к администратору сервера.",
                    ephemeral=True
                )
            
        except Exception as e:
            print(f"Ошибка при удалении запроса склада: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при удалении запроса.", ephemeral=True
            )
    
    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.secondary)
    async def cancel_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Отменить удаление"""
        await interaction.response.edit_message(
            content="❌ Удаление отменено.",
            embed=None,
            view=None
        )
    
    async def on_timeout(self):
        """Обработка истечения времени ожидания"""
        # Отключаем все кнопки при таймауте
        for item in self.children:
            item.disabled = True


class RejectionReasonModal(discord.ui.Modal):
    """Модальное окно для ввода причины отказа"""
    
    def __init__(self, original_message: discord.Message):
        super().__init__(title="Причина отказа")
        self.original_message = original_message
        
        self.reason_input = discord.ui.TextInput(
            label="Причина отказа",
            placeholder="Введите причину отказа в выдаче склада...",
            style=discord.TextStyle.paragraph,
            min_length=5,
            max_length=500,
            required=True
        )
        
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отправки причины отказа"""
        try:
            reason = self.reason_input.value.strip()
            
            # Обновление embed
            embed = self.original_message.embeds[0]
            embed.color = discord.Color.red()
            
            # Добавляем информацию об отклонении
            embed.add_field(
                name="❌ Отклонено", 
                value=f"*Отклонил: {interaction.user.mention}*\n**Причина:** {reason}", 
                inline=False
            )
            
            # Заменяем view на кнопку статуса "Отклонено" и очищаем пинги
            status_view = WarehouseStatusView(status="rejected")
            
            await interaction.response.edit_message(content="", embed=embed, view=status_view)
            
        except Exception as e:
            print(f"Ошибка при отклонении запроса склада: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке отказа.", ephemeral=True
            )


class WarehouseSubmittedView(discord.ui.View):
    """View для уже отправленной заявки - только статическое сообщение без кнопок"""
    
    def __init__(self):
        super().__init__(timeout=None)
