"""
Department Applications Cog - Restore persistent messages and views in department channels
"""
import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class DepartmentApplicationsCog(commands.Cog):
    """Cog for department applications - restore persistent messages in all department channels"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Restore persistent messages and views in all department channels"""
        # Skip restoration if it's already handled by main app.py
        # This prevents double execution
        logger.info("Department applications restoration handled by main app.py startup process")
        return
    
    @commands.command(name="fix_department_buttons", hidden=True)
    @commands.has_permissions(administrator=True)
    async def fix_department_buttons(self, ctx):
        """Manually fix department application buttons (admin only)"""
        try:
            from forms.department_applications.manager import DepartmentApplicationManager
            
            manager = DepartmentApplicationManager(self.bot)
            
            # Restore persistent views
            await manager.restore_persistent_views()
            
            # Get status of all departments
            results = await manager.setup_all_department_channels(ctx.guild)
            
            embed = discord.Embed(
                title="🔧 Восстановление кнопок подразделений",
                description="Результаты восстановления persistent views:",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            for dept_code, status in results.items():
                embed.add_field(
                    name=f"📋 {dept_code}",
                    value=status,
                    inline=False
                )
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in fix_department_buttons: {e}")
            await ctx.send(f"❌ **Ошибка:** {e}", ephemeral=True)
    
    @commands.command(name="dept_status", hidden=True)
    @commands.has_permissions(administrator=True)
    async def department_status(self, ctx):
        """Check department applications status (admin only)"""
        try:
            from forms.department_applications.manager import DepartmentApplicationManager
            from utils.config_manager import load_config
            
            config = load_config()
            departments = config.get('departments', {})
            
            if not departments:
                await ctx.send("❌ **Нет настроенных подразделений** для заявлений.", ephemeral=True)
                return
                
            manager = DepartmentApplicationManager(self.bot)
            
            embed = discord.Embed(
                title="📊 Статус системы заявлений",
                description=f"Проверка {len(departments)} подразделений:",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            for dept_code, dept_config in departments.items():
                channel_id = dept_config.get('application_channel_id')
                message_id = dept_config.get('persistent_message_id')
                
                if not channel_id:
                    status = "❌ Канал не настроен"
                else:
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        status = f"❌ Канал не найден (ID: {channel_id})"
                    elif not message_id:
                        status = "⚠️ Нет сохранённого message_id"
                    else:
                        try:
                            message = await channel.fetch_message(message_id)
                            if message.pinned:
                                status = "✅ Сообщение найдено и закреплено"
                            else:
                                status = "⚠️ Сообщение найдено, но не закреплено"
                        except discord.NotFound:
                            status = "❌ Сохранённое сообщение не найдено"
                        except discord.Forbidden:
                            status = "❌ Нет доступа к сообщению"
                
                embed.add_field(
                    name=f"📋 {dept_code}",
                    value=status,
                    inline=True
                )
            
            embed.set_footer(
                text="Используйте !fix_department_buttons для восстановления"
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in department_status: {e}")
            await ctx.send(f"❌ **Ошибка:** {e}", ephemeral=True)

async def setup(bot):
    """Setup cog"""
    await bot.add_cog(DepartmentApplicationsCog(bot))
