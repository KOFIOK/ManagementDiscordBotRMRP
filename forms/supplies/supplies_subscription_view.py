import discord
from utils.config_manager import load_config


class SuppliesSubscriptionView(discord.ui.View):
    """Представление с кнопками подписки на уведомления о поставках"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="Включить уведомления",
        emoji="🔔",
        style=discord.ButtonStyle.success,
        custom_id="supplies_subscribe"
    )
    async def subscribe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_subscription(interaction, subscribe=True)
    
    @discord.ui.button(
        label="Выключить уведомления", 
        emoji="🔕",
        style=discord.ButtonStyle.secondary,
        custom_id="supplies_unsubscribe"
    )
    async def unsubscribe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_subscription(interaction, subscribe=False)
    
    async def _handle_subscription(self, interaction: discord.Interaction, subscribe: bool):
        """Обработка подписки/отписки на уведомления"""
        try:
            config = load_config()
            subscription_role_id = config.get('supplies', {}).get('subscription_role_id')
            
            if not subscription_role_id:
                await interaction.response.send_message(
                    "❌ Роль для подписки на уведомления не настроена. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Получаем роль
            guild = interaction.guild
            subscription_role = guild.get_role(subscription_role_id)
            
            if not subscription_role:
                await interaction.response.send_message(
                    "❌ Роль для подписки не найдена на сервере. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            user = interaction.user
            
            if subscribe:
                # Включаем уведомления
                if subscription_role in user.roles:
                    await interaction.response.send_message(
                        "ℹ️ У вас уже включены уведомления о поставках!",
                        ephemeral=True
                    )
                else:
                    await user.add_roles(subscription_role, reason="Подписка на уведомления о поставках")
                    await interaction.response.send_message(
                        "✅ Уведомления о поставках **включены**!\n"
                        "🔔 Теперь вы будете получать уведомления о готовности военных объектов.",
                        ephemeral=True
                    )
            else:
                # Выключаем уведомления
                if subscription_role not in user.roles:
                    await interaction.response.send_message(
                        "ℹ️ У вас уже выключены уведомления о поставках!",
                        ephemeral=True
                    )
                else:
                    await user.remove_roles(subscription_role, reason="Отписка от уведомлений о поставках")
                    await interaction.response.send_message(
                        "✅ Уведомления о поставках **выключены**.\n"
                        "🔕 Вы больше не будете получать уведомления о готовности объектов.",
                        ephemeral=True
                    )
                    
        except Exception as e:
            print(f"❌ Ошибка при управлении подпиской на поставки: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке подписки. Попробуйте позже.",
                ephemeral=True
            )


async def send_supplies_subscription_message(channel: discord.TextChannel):
    """Отправляет сообщение с кнопками подписки на уведомления"""
    try:
        embed = discord.Embed(
            title="🔔 Подписка на уведомления о поставках",
            description=(
                "**Управление уведомлениями о военных поставках**\n\n"
                "🔔 **Включить** - Получать уведомления о готовности объектов\n"
                "🔕 **Выключить** - Отключить все уведомления\n\n"
                "ℹ️ Уведомления приходят когда военные объекты готовы к новой поставке материалов."
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Выберите нужное действие")
        
        view = SuppliesSubscriptionView()
        message = await channel.send(embed=embed, view=view)
        return message
        
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения подписки на поставки: {e}")
        return None
