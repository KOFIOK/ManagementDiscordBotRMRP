"""
Medical Registration Cog for Discord bot
Handles medical appointments and registration forms
"""

import discord
from discord.ext import commands
from utils.config_manager import load_config
from forms.medical_registration import MedicalRegistrationView, send_medical_registration_message


class MedicalRegistration(commands.Cog):
    """Cog for medical registration system"""
    
    def __init__(self, bot):
        self.bot = bot
        print("[DEBUG] MedicalRegistration cog initialized")
        # Add persistent view
        self.bot.add_view(MedicalRegistrationView())
        print("[DEBUG] MedicalRegistrationView added to bot")

    @commands.Cog.listener()
    async def on_ready(self):
        """Ensure medical registration message exists in configured channel"""
        try:
            print("[DEBUG] Medical registration on_ready called")
            config = load_config()
            channel_id = config.get('medical_registration_channel')
            
            print(f"[DEBUG] Medical registration channel ID from config: {channel_id}")
            
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                print(f"[DEBUG] Channel object: {channel}")
                if channel:
                    print(f"[DEBUG] Calling send_medical_registration_message for channel: {channel.name}")
                    await send_medical_registration_message(channel)
                    print(f"[DEBUG] send_medical_registration_message completed")
                else:
                    print(f"[DEBUG] Channel with ID {channel_id} not found")
            else:
                print("[DEBUG] No medical registration channel configured")
        except Exception as e:
            print(f"Error in medical registration on_ready: {e}")
            import traceback
            traceback.print_exc()

    @commands.command(name="test_medical_message")
    @commands.has_permissions(administrator=True)
    async def test_medical_message(self, ctx):
        """Test command to manually send medical registration message"""
        try:
            config = load_config()
            channel_id = config.get('medical_registration_channel')
            
            if not channel_id:
                await ctx.send("❌ Канал медицинской роты не настроен в конфигурации.")
                return
            
            channel = self.bot.get_channel(channel_id)
            if not channel:
                await ctx.send(f"❌ Канал с ID {channel_id} не найден.")
                return
            
            await send_medical_registration_message(channel)
            await ctx.send(f"✅ Сообщение медицинской роты отправлено в {channel.mention}")
            
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {str(e)}")
            print(f"Error in test_medical_message: {e}")


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(MedicalRegistration(bot))
