"""
Rank synchronization commands
"""
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.config_manager import load_config, is_moderator_or_admin
from utils.rank_sync import sync_ranks_for_guild, sync_ranks_for_member, rank_sync_manager


class RankSyncCog(commands.Cog):
    """Commands for rank synchronization system"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="rank-sync", description="Синхронизировать звания с игровой активностью")
    @app_commands.describe(
        target="Пользователь для синхронизации (оставьте пустым для всех)",
        force="Принудительная синхронизация (игнорировать кэш)"
    )
    async def rank_sync(
        self, 
        interaction: discord.Interaction, 
        target: Optional[discord.Member] = None,
        force: bool = False
    ):
        """Sync ranks based on Discord activity"""
        
        # Check permissions
        config = load_config()
        if not is_moderator_or_admin(interaction.user, config):
            await interaction.response.send_message(
                "❌ **Доступ запрещён**\n"
                "Эта команда доступна только модераторам и администраторам.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            if target:
                # Sync specific member
                embed = discord.Embed(
                    title="🔄 Синхронизация звания",
                    description=f"Проверяю активность пользователя {target.mention}...",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                success = await sync_ranks_for_member(target)
                
                if success:
                    embed.description = f"✅ Синхронизация для {target.mention} завершена"
                    embed.color = discord.Color.green()
                else:
                    embed.description = f"⚠️ Не удалось синхронизировать звание для {target.mention}"
                    embed.color = discord.Color.orange()
                
            else:
                # Sync all members
                embed = discord.Embed(
                    title="🔄 Массовая синхронизация званий",
                    description="Начинаю проверку активности всех участников сервера...",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # Use optimized sync if available
                try:
                    from utils.optimized_rank_sync import optimized_rank_sync
                    if optimized_rank_sync:
                        synced_count, checked_count = await optimized_rank_sync.manual_sync_all()
                    else:
                        synced_count, checked_count = await sync_ranks_for_guild(interaction.guild)
                except ImportError:
                    synced_count, checked_count = await sync_ranks_for_guild(interaction.guild)
                
                embed = discord.Embed(
                    title="✅ Синхронизация завершена",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                embed.add_field(
                    name="📊 Результаты:",
                    value=(
                        f"**Проверено участников:** {checked_count}\n"
                        f"**Синхронизировано:** {synced_count}\n"
                        f"**Успешность:** {(synced_count/checked_count*100):.1f}%" if checked_count > 0 else "**Успешность:** 0%"
                    ),
                    inline=False
                )
                
                if synced_count > 0:
                    embed.add_field(
                        name="ℹ️ Информация:",
                        value="Все изменения ролей зафиксированы в канале аудита.",
                        inline=False
                    )
            
            await interaction.edit_original_response(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка синхронизации",
                description=f"Произошла ошибка при синхронизации званий: {e}",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            await interaction.edit_original_response(embed=error_embed)
            print(f"❌ Error in rank sync command: {e}")
    
    @app_commands.command(name="rank-test", description="Тестировать определение звания из активности")
    @app_commands.describe(
        activity_text="Текст активности для тестирования (например: '1553-326 | Капитан (1153 из 5000)')"
    )
    async def rank_test(self, interaction: discord.Interaction, activity_text: str):
        """Test rank detection from activity text"""
        
        # Check permissions
        config = load_config()
        if not is_moderator_or_admin(interaction.user, config):
            await interaction.response.send_message(
                "❌ **Доступ запрещён**\n"
                "Эта команда доступна только модераторам и администраторам.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🧪 Тест определения звания",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📝 Тестируемый текст:",
            value=f"```{activity_text}```",
            inline=False
        )
        
        if not rank_sync_manager:
            embed.add_field(
                name="❌ Ошибка:",
                value="Система синхронизации не инициализирована",
                inline=False
            )
            embed.color = discord.Color.red()
        else:
            # Test server detection
            is_rmrp = rank_sync_manager.is_rmrp_arbat_server(activity_text)
            embed.add_field(
                name="🎮 Сервер RMRP Арбат:",
                value="✅ Обнаружен" if is_rmrp else "❌ Не обнаружен",
                inline=True
            )
            
            # Test rank extraction
            detected_rank = rank_sync_manager.extract_rank_from_activity(activity_text)
            
            if detected_rank:
                embed.add_field(
                    name="🎖️ Обнаруженное звание:",
                    value=f"`{detected_rank}`",
                    inline=True
                )
                
                # Check if rank has corresponding role
                config = load_config()
                rank_roles = config.get('rank_roles', {})
                
                if detected_rank in rank_roles:
                    role_id = rank_roles[detected_rank]
                    role = interaction.guild.get_role(role_id)
                    
                    embed.add_field(
                        name="🏷️ Соответствующая роль:",
                        value=role.mention if role else f"❌ Роль не найдена (ID: {role_id})",
                        inline=True
                    )
                    
                    embed.color = discord.Color.green()
                else:
                    embed.add_field(
                        name="⚠️ Роль:",
                        value="Не настроена в конфигурации",
                        inline=True
                    )
                    embed.color = discord.Color.orange()
            else:
                embed.add_field(
                    name="❌ Звание:",
                    value="Не обнаружено",
                    inline=True
                )
                embed.color = discord.Color.red()
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="rank-status", description="Показать статус системы синхронизации званий")
    async def rank_status(self, interaction: discord.Interaction):
        """Show rank synchronization system status"""
        
        # Check permissions
        config = load_config()
        if not is_moderator_or_admin(interaction.user, config):
            await interaction.response.send_message(
                "❌ **Доступ запрещён**\n"
                "Эта команда доступна только модераторам и администраторам.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📊 Статус системы синхронизации званий",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # System status
        if rank_sync_manager:
            embed.add_field(
                name="🤖 Система:",
                value="✅ Активна",
                inline=True
            )
        else:
            embed.add_field(
                name="🤖 Система:",
                value="❌ Не инициализирована",
                inline=True
            )
        
        # Configured ranks count
        rank_roles = config.get('rank_roles', {})
        embed.add_field(
            name="🎖️ Настроено званий:",
            value=str(len(rank_roles)),
            inline=True
        )
        
        # Supported server patterns
        if rank_sync_manager:
            server_patterns = rank_sync_manager.server_patterns
            embed.add_field(
                name="🎮 Поддерживаемые серверы:",
                value="\n".join([f"• `{pattern}`" for pattern in server_patterns[:3]]),
                inline=False
            )
            
            # Sample rank variations
            sample_ranks = ["капитан", "мл. лейтенант", "ст. сержант"]
            variations_text = []
            
            for rank in sample_ranks:
                if rank in rank_sync_manager.rank_variations:
                    variations = rank_sync_manager.rank_variations[rank][:3]  # First 3
                    variations_text.append(f"**{rank}**: {', '.join(variations)}")
            
            if variations_text:
                embed.add_field(
                    name="🔤 Примеры вариаций званий:",
                    value="\n".join(variations_text),
                    inline=False
                )
        
        embed.add_field(
            name="🛠️ Доступные команды:",
            value=(
                "• `/rank-sync` - запустить синхронизацию\n"
                "• `/rank-test` - протестировать определение звания\n"
                "• `/rank-status` - показать этот статус\n"
                "• `/rank-stats` - статистика оптимизированной системы"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="rank-stats", description="Показать статистику оптимизированной системы синхронизации")
    async def rank_stats(self, interaction: discord.Interaction):
        """Show optimized rank sync statistics"""
        
        # Check permissions
        config = load_config()
        if not is_moderator_or_admin(interaction.user, config):
            await interaction.response.send_message(
                "❌ **Доступ запрещён**\n"
                "Эта команда доступна только модераторам и администраторам.",
                ephemeral=True
            )
            return
        
        try:
            from utils.optimized_rank_sync import optimized_rank_sync
            
            if not optimized_rank_sync:
                await interaction.response.send_message(
                    "❌ Оптимизированная система синхронизации не инициализирована",
                    ephemeral=True
                )
                return
            
            stats = await optimized_rank_sync.get_sync_stats()
            
            embed = discord.Embed(
                title="📊 Статистика оптимизированной системы синхронизации",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Server stats
            embed.add_field(
                name="🏛️ Статистика сервера:",
                value=(
                    f"**Всего участников:** {stats.get('total_members', 'N/A')}\n"
                    f"**С ключевой ролью:** {stats.get('key_role_members', 'N/A')}\n"
                    f"**Активных игроков RMRP:** {stats.get('active_rmrp_players', 'N/A')}\n"
                    f"**В кэше активностей:** {stats.get('cached_activities', 'N/A')}\n"
                    f"**Синхронизировано:** {stats.get('synced_members', 'N/A')}"
                ),
                inline=False
            )
            
            # Key role info
            key_role_name = stats.get('key_role_name')
            key_role_configured = stats.get('key_role_configured', False)
            
            if key_role_configured and key_role_name:
                embed.add_field(
                    name="🔑 Ключевая роль:",
                    value=f"✅ **{key_role_name}** ({stats.get('key_role_members', 0)} участников)",
                    inline=False
                )
            elif key_role_configured:
                embed.add_field(
                    name="🔑 Ключевая роль:",
                    value="❌ **Роль не найдена** (проверьте настройки)",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚠️ Ключевая роль:",
                    value="**Не настроена** - проверяются все участники сервера",
                    inline=False
                )
            
            # System settings
            mode_status = []
            if stats.get('realtime_enabled'):
                mode_status.append("🔴 **Real-time** (высокая нагрузка)")
            if stats.get('periodic_enabled'):
                mode_status.append("🟢 **Periodic** (оптимально)")
            if not mode_status:
                mode_status.append("🟡 **Manual only**")
            
            embed.add_field(
                name="⚙️ Настройки системы:",
                value=(
                    f"**Режимы:** {', '.join(mode_status)}\n"
                    f"**Размер батча:** {stats.get('batch_size', 'N/A')}\n"
                    f"**Интервал проверки:** {stats.get('check_interval', 'N/A')}с\n"
                    f"**Очередь активностей:** {stats.get('queue_size', 'N/A')}"
                ),
                inline=False
            )
            
            # Performance recommendations
            active_players = stats.get('active_rmrp_players', 0)
            total_members = stats.get('total_members', 0)
            key_role_members = stats.get('key_role_members', 0)
            key_role_configured = stats.get('key_role_configured', False)
            
            if total_members > 1000:
                if not key_role_configured:
                    embed.add_field(
                        name="⚠️ Важная рекомендация:",
                        value=(
                            "**Настройте ключевую роль!**\n"
                            f"• Сейчас проверяется до {total_members} участников\n"
                            "• Настройте ключевую роль для военнослужащих\n"
                            "• Это повысит производительность в разы\n"
                            "• `/settings` → `Роли званий` → `🔑 Настроить ключевую роль`"
                        ),
                        inline=False
                    )
                elif stats.get('realtime_enabled'):
                    embed.add_field(
                        name="⚠️ Рекомендации по производительности:",
                        value=(
                            "**Real-time режим включен на большом сервере!**\n"
                            "• Рекомендуется отключить real-time режим\n"
                            "• Используйте periodic режим (каждые 5 минут)\n"
                            f"• Активных игроков: {active_players} из {key_role_members} военнослужащих"
                        ),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="✅ Оптимизация:",
                        value=(
                            "Система настроена оптимально для большого сервера.\n"
                            f"Обрабатывается только {active_players} активных игроков из {key_role_members} военнослужащих."
                        ),
                        inline=False
                    )
            else:
                embed.add_field(
                    name="ℹ️ Статус:",
                    value=f"Сервер среднего размера. Обрабатывается {active_players} активных игроков.",
                    inline=False
                )
            
            embed.add_field(
                name="🔧 Управление режимами:",
                value="Для изменения режимов обратитесь к разработчику.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка получения статистики",
                description=f"Произошла ошибка: {e}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(RankSyncCog(bot))
