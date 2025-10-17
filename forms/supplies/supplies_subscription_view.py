import discord
from utils.config_manager import load_config
from utils.message_manager import get_supplies_message, get_supplies_color


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
                    get_supplies_message(interaction.guild.id, "subscription.error_role_not_configured"),
                    ephemeral=True
                )
                return
            
            # Получаем роль
            guild = interaction.guild
            subscription_role = guild.get_role(subscription_role_id)
            
            if not subscription_role:
                await interaction.response.send_message(
                    get_supplies_message(interaction.guild.id, "subscription.error_role_not_found"),
                    ephemeral=True
                )
                return
            
            user = interaction.user
            
            if subscribe:
                # Включаем уведомления
                if subscription_role in user.roles:
                    await interaction.response.send_message(
                        get_supplies_message(interaction.guild.id, "subscription.info_already_subscribed"),
                        ephemeral=True
                    )
                else:
                    await user.add_roles(subscription_role, reason="Подписка на уведомления о поставках")
                    await interaction.response.send_message(
                        get_supplies_message(interaction.guild.id, "subscription.success_subscribed"),
                        ephemeral=True
                    )
            else:
                # Выключаем уведомления
                if subscription_role not in user.roles:
                    await interaction.response.send_message(
                        get_supplies_message(interaction.guild.id, "subscription.info_already_unsubscribed"),
                        ephemeral=True
                    )
                else:
                    await user.remove_roles(subscription_role, reason="Отписка от уведомлений о поставках")
                    await interaction.response.send_message(
                        get_supplies_message(interaction.guild.id, "subscription.success_unsubscribed"),
                        ephemeral=True
                    )
                    
        except Exception as e:
            print(f"❌ Ошибка при управлении подпиской на поставки: {e}")
            await interaction.response.send_message(
                get_supplies_message(interaction.guild.id, "subscription.error_subscription_processing"),
                ephemeral=True
            )


async def send_supplies_subscription_message(channel: discord.TextChannel):
    """Отправляет сообщение с кнопками подписки на уведомления"""
    try:
        embed = discord.Embed(
            title=get_supplies_message(channel.guild.id, "subscription.embed_title"),
            description=get_supplies_message(channel.guild.id, "subscription.embed_description"),
            color=get_supplies_color(channel.guild.id, "colors.timer_embed")
        )
        embed.set_footer(text=get_supplies_message(channel.guild.id, "subscription.embed_footer"))
        
        view = SuppliesSubscriptionView()
        message = await channel.send(embed=embed, view=view)
        return message
        
    except Exception as e:
        print(get_supplies_message(channel.guild.id, "subscription.error_send_subscription_message").format(error=e))
        return None
