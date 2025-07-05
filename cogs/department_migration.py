"""
Department Applications Migration - Only migration command
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging

from utils.config_manager import load_config, save_config
from utils.ping_manager import ping_manager

logger = logging.getLogger(__name__)

class DepartmentMigrationCog(commands.Cog):
    """Cog for department migration utilities"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="migrate-ping-settings", description="Мигрировать старые настройки пингов в новую систему")
    @app_commands.default_permissions(administrator=True)
    async def migrate_ping_settings(self, interaction: discord.Interaction):
        """Migrate legacy ping settings to new system"""
        try:
            await interaction.response.defer()
            
            config = load_config()
            ping_settings = config.get('ping_settings', {})
            departments = config.get('departments', {})
            
            if not ping_settings:
                embed = discord.Embed(
                    title="ℹ️ Миграция не требуется",
                    description="Старые настройки пингов не найдены.",
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=embed)
                return
            
            migrated_count = 0
            migration_log = []
            
            # Migrate old ping settings to new department structure
            for dept_pattern, role_ids in ping_settings.items():
                # Find matching department
                dept_code = None
                for code, patterns in ping_manager.DEPARTMENT_PATTERNS.items():
                    if dept_pattern.lower() in [p.lower() for p in patterns]:
                        dept_code = code
                        break
                
                if dept_code and dept_code in departments:
                    if 'ping_contexts' not in departments[dept_code]:
                        departments[dept_code]['ping_contexts'] = {}
                    
                    # Migrate to applications context
                    departments[dept_code]['ping_contexts']['applications'] = role_ids
                    migrated_count += 1
                    migration_log.append(f"✅ {dept_pattern} → {dept_code} (applications): {len(role_ids)} ролей")
                else:
                    migration_log.append(f"❌ {dept_pattern}: подразделение не найдено")
            
            if migrated_count > 0:
                # Save updated config
                save_config(config)
                
                # Auto-reload config
                try:
                    ping_manager.reload_config()
                except:
                    pass
                
                embed = discord.Embed(
                    title="✅ Миграция завершена",
                    description=f"Мигрировано {migrated_count} настроек пингов",
                    color=discord.Color.green()
                )
                
                log_text = "\n".join(migration_log[:15])
                if len(migration_log) > 15:
                    log_text += f"\n... и еще {len(migration_log) - 15} записей"
                
                embed.add_field(
                    name="📝 Детали миграции",
                    value=log_text,
                    inline=False
                )
                
                embed.add_field(
                    name="💡 Информация",
                    value="Старые настройки остались в конфигурации для совместимости.\n"
                          "Новая система использует структуру ping_contexts.",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="⚠️ Миграция не выполнена",
                    description="Не удалось сопоставить старые настройки с подразделениями.",
                    color=discord.Color.orange()
                )
                
                embed.add_field(
                    name="📝 Проблемы",
                    value="\n".join(migration_log[:10]),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in ping settings migration: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка миграции",
                description=f"Произошла ошибка при миграции настроек: {e}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed)

async def setup(bot):
    """Загрузка Cog"""
    await bot.add_cog(DepartmentMigrationCog(bot))
