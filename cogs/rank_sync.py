import discord
from discord.ext import commands
from utils.rank_sync import RankSync
from utils.config_manager import load_config


class RankSyncCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rank_sync = RankSync(bot)
    
    @discord.app_commands.command(name="rank-sync", description="Синхронизировать звания пользователей")
    @discord.app_commands.describe(
        target="Пользователь для синхронизации званий (оставьте пустым для всех)",
        force="Игнорировать проверки ключевой роли"
    )
    async def rank_sync_command(self, interaction: discord.Interaction, target: discord.Member = None, force: bool = False):
        """Синхронизировать звания пользователей"""
        # Проверяем права доступа
        config = load_config()
        key_role_id = config.get("rank_sync", {}).get("key_role_id")
        
        if not force and key_role_id:
            if not any(role.id == key_role_id for role in interaction.user.roles):
                await interaction.response.send_message("❌ У вас нет прав для использования этой команды.", ephemeral=True)
                return
        
        await interaction.response.defer()
        
        if target:
            # Синхронизировать одного пользователя
            result = await self.rank_sync.sync_user(target, force=force)
            if result["success"]:
                message = f"✅ Синхронизация пользователя {target.display_name} завершена успешно"
                if result.get("rank_detected"):
                    message += f"\n🎖️ Обнаружено звание: {result['rank_detected']}"
                if result.get("roles_added"):
                    message += f"\n📝 Добавлены роли: {', '.join(result['roles_added'])}"
                if result.get("roles_removed"):
                    message += f"\n🗑️ Удалены роли: {', '.join(result['roles_removed'])}"
            else:
                message = f"❌ Ошибка синхронизации пользователя {target.display_name}: {result.get('error', 'Неизвестная ошибка')}"
        else:
            # Синхронизировать всех пользователей
            message = "🔄 Начинается массовая синхронизация званий...\n"
            await interaction.followup.send(message)
            
            total = 0
            success = 0
            members = [member for member in interaction.guild.members if not member.bot]
            
            for member in members:
                result = await self.rank_sync.sync_user(member, force=force)
                total += 1
                if result["success"]:
                    success += 1
            
            message = f"✅ Массовая синхронизация завершена:\n📊 Успешно: {success}/{total}"
        
        await interaction.followup.send(message)
    
    @discord.app_commands.command(name="rank-test", description="Тестирование системы синхронизации званий")
    async def rank_test_command(self, interaction: discord.Interaction, target: discord.Member = None):
        """Тестировать систему синхронизации званий"""
        await interaction.response.defer()
        
        if not target:
            target = interaction.user
        
        # Проверяем активности пользователя
        activities = target.activities
        message = f"🔍 Тестирование синхронизации для {target.display_name}:\n\n"
        
        if not activities:
            message += "❌ У пользователя нет активных активностей"
        else:
            message += "📱 Активности пользователя:\n"
            for i, activity in enumerate(activities, 1):
                message += f"{i}. **{activity.name}**\n"
                if hasattr(activity, 'details') and activity.details:
                    message += f"   Details: {activity.details}\n"
                if hasattr(activity, 'state') and activity.state:
                    message += f"   State: {activity.state}\n"
                message += "\n"
            
            # Пытаемся найти RMRP активность
            rmrp_activity = self.rank_sync._find_rmrp_activity(target)
            if rmrp_activity:
                message += f"✅ Найдена RMRP активность: **{rmrp_activity.name}**\n"
                if hasattr(rmrp_activity, 'details'):
                    message += f"   Details: {rmrp_activity.details}\n"
                if hasattr(rmrp_activity, 'state'):
                    message += f"   State: {rmrp_activity.state}\n"
                
                # Пытаемся извлечь звание
                rank = self.rank_sync._extract_rank(rmrp_activity)
                if rank:
                    message += f"🎖️ Обнаружено звание: **{rank}**\n"
                else:
                    message += "❌ Звание не обнаружено в активности\n"
            else:
                message += "❌ RMRP активность не найдена\n"
        
        await interaction.followup.send(message)


async def setup(bot):
    """Required setup function for discord.py cog loading"""
    await bot.add_cog(RankSyncCog(bot))
    print("✅ Rank sync cog loaded successfully")