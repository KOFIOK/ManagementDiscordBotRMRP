import discord
from discord import ui
import re
from utils.config_manager import load_config

# Define the dismissal report form
class DismissalReportModal(ui.Modal, title="Рапорт на увольнение"):
    name = ui.TextInput(
        label="Имя Фамилия",
        placeholder="Введите имя и фамилию через пробел",
        min_length=3,
        max_length=50,
        required=True
    )
    
    static = ui.TextInput(
        label="Статик (6 цифр, 123-456)",
        placeholder="Формат: 123-456",
        min_length=6,
        max_length=7,
        required=True
    )
    
    reason = ui.TextInput(
        label="Причина увольнения",
        placeholder="Укажите причину увольнения...",
        style=discord.TextStyle.paragraph,
        min_length=3,
        max_length=1000,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate name format (должно быть 2 слова)
            name_parts = self.name.value.strip().split()
            if len(name_parts) != 2:
                await interaction.response.send_message(
                    "Ошибка: Имя и фамилия должны состоять из 2 слов, разделенных пробелом.", 
                    ephemeral=True
                )
                return
            
            # Validate static format (5 цифр: 12-345)
            if not re.match(r'^\d{2}-\d{3}$|^\d{3}-\d{3}$', self.static.value):
                await interaction.response.send_message(
                    "Ошибка: Статик должен быть в формате 123-456 (3 цифры, тире, 3 цифры).", 
                    ephemeral=True
                )
                return
            
            # Get the channel where reports should be sent
            config = load_config()
            channel_id = config.get('dismissal_channel')
            
            if not channel_id:
                await interaction.response.send_message(
                    "Ошибка: канал для рапортов не настроен. Обратитесь к администратору.", 
                    ephemeral=True
                )
                return
            
            channel = interaction.client.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "Ошибка: не удалось найти канал для рапортов. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Create an embed for the report
            embed = discord.Embed(
                title="Новый рапорт на увольнение",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="Имя Фамилия", value=self.name.value, inline=False)
            embed.add_field(name="Статик", value=self.static.value, inline=False)
            embed.add_field(name="Причина", value=self.reason.value, inline=False)
            embed.add_field(name="Статус", value="⏳ Рассматривается", inline=False)
            
            embed.set_footer(text=f"Отправлено: {interaction.user.name}")
            
            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)
            
            # Send the report to the dismissal channel
            await channel.send(embed=embed)
            
            await interaction.response.send_message(
                "Ваш рапорт на увольнение был успешно отправлен и будет рассмотрен.", 
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error in form submission: {e}")
            await interaction.response.send_message(
                f"Произошла ошибка при отправке рапорта: {e}", 
                ephemeral=True
            )
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Modal error: {error}")
        await interaction.response.send_message(
            "Произошла ошибка при обработке формы. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
            ephemeral=True
        )

# Button for dismissal report
class DismissalReportButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Отправить рапорт на увольнение", style=discord.ButtonStyle.red, custom_id="dismissal_report")
    async def dismissal_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DismissalReportModal())

# Message with button for the dismissal channel
async def send_dismissal_button_message(channel):
    embed = discord.Embed(
        title="Рапорты на увольнение",
        description="Нажмите на кнопку ниже, чтобы отправить рапорт на увольнение.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Инструкция", 
        value="1. Нажмите на кнопку\n2. Заполните открывшуюся форму\n3. Нажмите 'Submit'", 
        inline=False
    )
    
    embed.add_field(
        name="Требования",
        value="• Имя и фамилия - 2 слова через пробел\n• Статик в формате 12-345\n• Причина увольнения (мин. 3 символа)",
        inline=False
    )
    
    view = DismissalReportButton()
    await channel.send(embed=embed, view=view)
