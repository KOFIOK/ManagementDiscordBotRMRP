"""
Comprehensive performance monitoring command for PostgreSQL migration

Этот модуль предоставляет команды мониторинга для оценки производительности
системы после миграции на PostgreSQL с кэшированием и connection pooling.
"""

import discord
from discord.ext import commands
from discord import app_commands
import time
from utils.user_cache import get_cache_statistics, get_cached_user_info
from utils.database_manager import personnel_manager

class PerformanceMonitoringCog(commands.Cog):
    """Cog for monitoring PostgreSQL migration performance"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="perf-test", description="🧪 Провести тест производительности системы")
    async def performance_test(self, interaction: discord.Interaction):
        """Провести тест производительности с реальными данными"""
        
        # Проверка прав
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ У вас нет прав для проведения тестов производительности.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Получаем список пользователей для тестирования
        try:
            # Получаем всех активных пользователей из personnel таблицы
            all_users_raw = await personnel_manager.get_all_personnel()
            all_users = [{'discord_id': user.get('discord_id')} for user in all_users_raw if user.get('discord_id')]
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка получения пользователей: {e}")
            return
        if not all_users:
            await interaction.followup.send("❌ Не удалось получить список пользователей для тестирования.")
            return
        
        test_users = all_users[:20]  # Первые 20 пользователей для теста
        
        embed = discord.Embed(
            title="🧪 Тест производительности PostgreSQL системы",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Тест 1: Прямые запросы к PostgreSQL
        print(f"🧪 PERFORMANCE TEST: Тестирование {len(test_users)} пользователей...")
        
        start_time = time.time()
        direct_successes = 0
        for user in test_users:
            try:
                user_info = personnel_manager.get_personnel_by_discord_id(user['discord_id'])
                if user_info:
                    direct_successes += 1
            except Exception:
                pass
        direct_time = time.time() - start_time
        
        # Тест 2: Кэшированные запросы
        start_time = time.time()
        cache_successes = 0
        for user in test_users:
            try:
                user_info = await get_cached_user_info(user['discord_id'])
                if user_info:
                    cache_successes += 1
            except Exception:
                pass
        cache_time = time.time() - start_time
        
        # Тест 3: Повторные кэшированные запросы (все должны быть в кэше)
        start_time = time.time()
        cache_hit_successes = 0
        for user in test_users:
            try:
                user_info = await get_cached_user_info(user['discord_id'])
                if user_info:
                    cache_hit_successes += 1
            except Exception:
                pass
        cache_hit_time = time.time() - start_time
        
        # Расчет метрик
        speedup_first = direct_time / cache_time if cache_time > 0 else 0
        speedup_cached = direct_time / cache_hit_time if cache_hit_time > 0 else 0
        
        embed.add_field(
            name="📊 Результаты теста",
            value=f"""
**Тестировано пользователей:** {len(test_users)}
            
**🔗 Прямые запросы PostgreSQL:**
• Время: {direct_time:.3f}s
• Успешных: {direct_successes}/{len(test_users)}
• Среднее время: {(direct_time/len(test_users)*1000):.1f}ms

**🔄 Первые кэшированные запросы:**
• Время: {cache_time:.3f}s  
• Успешных: {cache_successes}/{len(test_users)}
• Среднее время: {(cache_time/len(test_users)*1000):.1f}ms
• Ускорение: {speedup_first:.1f}x

**⚡ Повторные кэшированные запросы:**
• Время: {cache_hit_time:.3f}s
• Успешных: {cache_hit_successes}/{len(test_users)}  
• Среднее время: {(cache_hit_time/len(test_users)*1000):.1f}ms
• Ускорение: {speedup_cached:.0f}x
            """.strip(),
            inline=False
        )
        
        # Рекомендации
        recommendations = []
        if direct_time > 2.0:
            recommendations.append("⚠️ Медленные прямые запросы - рассмотрите индексацию БД")
        if speedup_cached < 50:
            recommendations.append("⚠️ Низкое ускорение кэша - проверьте настройки")
        if cache_hit_successes < len(test_users):
            recommendations.append("⚠️ Не все запросы попадают в кэш")
        
        if not recommendations:
            recommendations.append("✅ Система работает оптимально!")
        
        embed.add_field(
            name="💡 Рекомендации",
            value="\n".join(recommendations),
            inline=False
        )
        
        embed.set_footer(text=f"Тест завершен • Общее время: {direct_time + cache_time + cache_hit_time:.2f}s")
        
        await interaction.followup.send(embed=embed)
    

async def setup(bot):
    """Добавить cog к боту"""
    await bot.add_cog(PerformanceMonitoringCog(bot))