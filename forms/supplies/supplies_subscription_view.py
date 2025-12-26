import discord
from utils.config_manager import load_config
from utils.message_manager import get_supplies_message, get_supplies_color, get_role_reason, get_moderator_display_name
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


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
                    "🚫 Роль для подписки на уведомления о поставках не настроена. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Получаем роль
            guild = interaction.guild
            subscription_role = guild.get_role(subscription_role_id)
            
            if not subscription_role:
                await interaction.response.send_message(
                    "🚫 Роль для подписки на уведомления о поставках не найдена на сервере. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            user = interaction.user
            # Get user display name for audit reasons
            user_display = await get_moderator_display_name(user)
            
            if subscribe:
                # Включаем уведомления
                if subscription_role in user.roles:
                    await interaction.response.send_message(
                        get_supplies_message(interaction.guild.id, "already_subscribed"),
                        ephemeral=True
                    )
                else:
                    reason = get_role_reason(interaction.guild.id, "supplies_subscription.enabled", "Подписка на поставки: включена").format(user=user_display)
                    await user.add_roles(subscription_role, reason=reason)
                    await interaction.response.send_message(
                        get_supplies_message(interaction.guild.id, "subscribed"),
                        ephemeral=True
                    )
            else:
                # Выключаем уведомления
                if subscription_role not in user.roles:
                    await interaction.response.send_message(
                        get_supplies_message(interaction.guild.id, "already_unsubscribed"),
                        ephemeral=True
                    )
                else:
                    await user.remove_roles(subscription_role, reason=get_role_reason(interaction.guild.id, "supplies_subscription.disabled", "Подписка на поставки: отключена").format(user=user_display))
                    await interaction.response.send_message(
                        get_supplies_message(interaction.guild.id, "unsubscribed"),
                        ephemeral=True
                    )
                    
        except Exception as e:
            logger.warning("Ошибка при управлении подпиской на поставки: %s", e)
            try:
                await interaction.response.send_message(
                    get_supplies_message(interaction.guild.id, "subscription.error_subscription_processing"),
                    ephemeral=True
                )
            except:
                # If interaction.response is already used, use followup
                await interaction.followup.send(
                    get_supplies_message(interaction.guild.id, "subscription.error_subscription_processing"),
                    ephemeral=True
                )


async def send_supplies_subscription_message(channel: discord.TextChannel):
    """Отправляет сообщение с кнопками подписки на уведомления"""
    try:
        embed = discord.Embed(
            title=get_supplies_message(channel.guild.id, "subscription_title"),
            description=get_supplies_message(channel.guild.id, "subscription_description"),
            color=get_supplies_color(channel.guild.id, "timer_embed")
        )
        embed.set_footer(text=get_supplies_message(channel.guild.id, "subscription_footer"))
        
        view = SuppliesSubscriptionView()
        message = await channel.send(embed=embed, view=view)
        return message
        
    except Exception as e:
        logger.warning("Ошибка отправки сообщения подписки на поставки: %s", e)
        return None