"""
Slash-команды администратора для управления системой кэширования пользователей
"""

import discord
import time
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.user_cache import (
    get_cache_statistics, clear_user_cache, invalidate_user_cache,
    get_cached_user_info, preload_user_data, get_user_name_fast,
    get_user_department_fast, get_user_rank_fast
)


class CacheAdminSlashCommands(commands.Cog):
    """Slash-команды администратора для управления кэшем"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='cache_stats', description='Показать статистику использования кэша пользователей')
    @app_commands.default_permissions(administrator=True)
    async def cache_statistics(self, interaction: discord.Interaction):
        """Показать статистику использования кэша пользователей"""
        try:
            stats = get_cache_statistics()
            
            embed = discord.Embed(
                title="📊 Статистика кэша пользователей",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Основная статистика
            embed.add_field(
                name="📈 Производительность",
                value=f"**Hit Rate:** {stats['hit_rate_percent']}%\n"
                      f"**Всего запросов:** {stats['total_requests']}\n"
                      f"**Cache Hits:** {stats['hits']}\n"
                      f"**Cache Misses:** {stats['misses']}",
                inline=True
            )
            
            # Размер кэша
            embed.add_field(
                name="💾 Размер кэша",
                value=f"**Записей в кэше:** {stats['cache_size']}\n"
                      f"**Истекших записей:** {stats['expired_entries']}\n"
                      f"**Память (примерно):** {stats['memory_usage_estimate']} байт",
                inline=True
            )
            
            # Время последней очистки
            last_cleanup = stats['last_cleanup'].strftime('%H:%M:%S %d.%m.%Y')
            embed.add_field(
                name="🧹 Обслуживание",
                value=f"**Последняя очистка:** {last_cleanup}",
                inline=False
            )
            
            # Рекомендации
            recommendations = []
            if stats['hit_rate_percent'] < 70:
                recommendations.append("🔸 Низкий Hit Rate - рассмотрите увеличение TTL кэша")
            if stats['expired_entries'] > stats['cache_size'] * 0.3:
                recommendations.append("🔸 Много истекших записей - выполните очистку")
            if stats['cache_size'] > 500:
                recommendations.append("🔸 Большой размер кэша - проверьте память сервера")
            
            if recommendations:
                embed.add_field(
                    name="💡 Рекомендации",
                    value="\n".join(recommendations),
                    inline=False
                )
            
            embed.set_footer(text="Используйте /cache_clear для очистки кэша")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Не удалось получить статистику кэша: {e}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='cache_clear', description='Полностью очистить кэш пользователей')
    @app_commands.default_permissions(administrator=True)
    async def clear_cache(self, interaction: discord.Interaction):
        """Полностью очистить кэш пользователей"""
        try:
            stats_before = get_cache_statistics()
            clear_user_cache()
            
            embed = discord.Embed(
                title="🧹 Кэш очищен",
                description=f"Удалено {stats_before['cache_size']} записей из кэша",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Не удалось очистить кэш: {e}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='cache_invalidate', description='Удалить конкретного пользователя из кэша')
    @app_commands.describe(user='Пользователь для удаления из кэша')
    @app_commands.default_permissions(administrator=True)
    async def invalidate_user(self, interaction: discord.Interaction, user: discord.Member):
        """Удалить конкретного пользователя из кэша"""
        try:
            invalidate_user_cache(user.id)
            
            embed = discord.Embed(
                title="🗑️ Пользователь удален из кэша",
                description=f"Данные пользователя {user.mention} удалены из кэша",
                color=discord.Color.orange()
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Не удалось удалить пользователя из кэша: {e}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='cache_test_user', description='Протестировать получение данных пользователя через кэш')
    @app_commands.describe(user='Пользователь для тестирования')
    @app_commands.default_permissions(administrator=True)
    async def test_user_cache(self, interaction: discord.Interaction, user: discord.Member):
        """Тестирование получения данных пользователя через кэш"""
        try:
            await interaction.response.defer()
            
            # Очищаем кэш пользователя для чистого теста
            invalidate_user_cache(user.id)
            
            embed = discord.Embed(
                title="🧪 Тест кэширования пользователя",
                description=f"Тестирование данных для {user.mention}",
                color=discord.Color.blue()
            )
            
            # Первый запрос (должен быть MISS)
            start_time = time.time()
            user_data_1 = await get_cached_user_info(user.id)
            first_request_time = time.time() - start_time
            
            # Второй запрос (должен быть HIT)
            start_time = time.time()
            user_data_2 = await get_cached_user_info(user.id)
            second_request_time = time.time() - start_time
            
            if user_data_1:
                embed.add_field(
                    name="👤 Найденные данные",
                    value=f"**Имя:** {user_data_1.get('full_name', 'Не указано')}\n"
                          f"**Статик:** {user_data_1.get('static', 'Не указано')}\n"
                          f"**Звание:** {user_data_1.get('rank', 'Не указано')}\n"
                          f"**Подразделение:** {user_data_1.get('department', 'Не указано')}\n"
                          f"**Должность:** {user_data_1.get('position', 'Не указано')}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="❌ Результат",
                    value="Пользователь не найден в базе данных",
                    inline=False
                )
            
            speedup_text = f"{first_request_time/second_request_time:.1f}x" if second_request_time > 0 else "∞x"
            embed.add_field(
                name="⚡ Производительность",
                value=f"**1-й запрос (MISS):** {first_request_time:.3f}с\n"
                      f"**2-й запрос (HIT):** {second_request_time:.3f}с\n"
                      f"**Ускорение:** {speedup_text}",
                inline=False
            )
            
            # Тест быстрых функций
            name_fast = await get_user_name_fast(user.id)
            dept_fast = await get_user_department_fast(user.id)
            rank_fast = await get_user_rank_fast(user.id)
            
            embed.add_field(
                name="🚀 Быстрые функции",
                value=f"**get_user_name_fast:** {name_fast}\n"
                      f"**get_user_department_fast:** {dept_fast}\n"
                      f"**get_user_rank_fast:** {rank_fast}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ Ошибка тестирования пользователя: {e}")
            else:
                await interaction.response.send_message(f"❌ Ошибка тестирования пользователя: {e}")

    @app_commands.command(name='global_cache_status', description='Показать полный статус универсальной системы кэширования')
    @app_commands.default_permissions(administrator=True)
    async def global_cache_status(self, interaction: discord.Interaction):
        """Показать полный статус универсальной системы кэширования"""
        try:
            stats = get_cache_statistics()
            
            embed = discord.Embed(
                title="🌐 Универсальная система кэширования",
                description="Статус кэширования для всех модулей бота",
                color=discord.Color.blue()
            )
            
            # Основная статистика
            embed.add_field(
                name="📊 Общая статистика",
                value=f"**Размер кэша:** {stats['cache_size']} записей\n"
                      f"**Всего запросов:** {stats['total_requests']}\n"
                      f"**Попадания:** {stats['hits']}\n"
                      f"**Промахи:** {stats['misses']}\n"
                      f"**Hit Rate:** {stats['hit_rate_percent']:.1f}%",
                inline=True
            )
            
            # Производительность
            if stats['total_requests'] > 0:
                avg_hit_rate = stats['hit_rate_percent']
                if avg_hit_rate >= 70:
                    performance_status = "🟢 Отлично"
                elif avg_hit_rate >= 50:
                    performance_status = "🟡 Хорошо"
                else:
                    performance_status = "🔴 Требует внимания"
            else:
                performance_status = "⚪ Нет данных"
            
            embed.add_field(
                name="⚡ Производительность",
                value=f"**Статус:** {performance_status}\n"
                      f"**Истекших записей:** {stats['expired_entries']}\n"
                      f"**Примерное потребление памяти:** {stats['memory_usage_estimate']} байт\n"
                      f"**Последняя очистка:** {stats['last_cleanup'].strftime('%H:%M:%S')}",
                inline=True
            )
            
            # Модули, использующие кэш
            cache_modules = [
                "✅ Система склада (warehouse)",
                "✅ UserDatabase (универсальный)",
                "✅ Медицинская регистрация (migrated)",
                "✅ Система увольнений (migrated)",
                "✅ Заявки на отпуск (migrated)"
            ]
            
            embed.add_field(
                name="🎯 Модули с кэшированием",
                value="\n".join(cache_modules),
                inline=False
            )
            
            # Рекомендации
            recommendations = []
            if stats['total_requests'] > 0:
                if avg_hit_rate < 50:
                    recommendations.append("💡 Рекомендуется предзагрузка активных пользователей")
                if stats['expired_entries'] > stats['cache_size'] * 0.3:
                    recommendations.append("🧹 Рекомендуется очистка кэша")
            if not recommendations:
                recommendations.append("✅ Система работает оптимально")
            
            embed.add_field(
                name="💡 Рекомендации",
                value="\n".join(recommendations),
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка получения статуса: {e}")

    @app_commands.command(name='warehouse_test_user', description='Протестировать получение данных пользователя для системы склада')
    @app_commands.describe(user='Пользователь для тестирования (по умолчанию - вы)')
    @app_commands.default_permissions(administrator=True)
    async def test_warehouse_user_data(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Протестировать получение данных пользователя для системы склада"""
        target_user = user if user else interaction.user
        
        try:
            await interaction.response.defer()
            
            from utils.warehouse_user_data import get_warehouse_user_data, prepare_modal_data
            
            # Тест 1: Полные данные пользователя
            start_time = time.time()
            user_data = await get_warehouse_user_data(target_user.id)
            full_data_time = time.time() - start_time
            
            # Тест 2: Данные для модального окна
            start_time = time.time()
            modal_data = await prepare_modal_data(target_user.id)
            modal_data_time = time.time() - start_time
            
            embed = discord.Embed(
                title="🧪 Тест данных пользователя",
                description=f"Результаты тестирования для {target_user.mention}",
                color=discord.Color.blue()
            )
            
            # Полные данные
            embed.add_field(
                name="📋 Полные данные пользователя",
                value=f"**Имя:** {user_data['full_name'] or 'Не найдено'}\n"
                      f"**Статик:** {user_data['static'] or 'Не найден'}\n"
                      f"**Должность:** {user_data['position']}\n"
                      f"**Звание:** {user_data['rank']}\n"
                      f"**Подразделение:** {user_data['department']}\n"
                      f"**Источник:** {user_data['source']}\n"
                      f"**Время загрузки:** {full_data_time:.3f}с",
                inline=False
            )
            
            # Данные модального окна
            embed.add_field(
                name="🔤 Данные для автозаполнения",
                value=f"**Имя (значение):** {modal_data['name_value'] or 'Пусто'}\n"
                      f"**Статик (значение):** {modal_data['static_value'] or 'Пусто'}\n"
                      f"**Имеет данные:** {'Да' if modal_data['has_data'] else 'Нет'}\n"
                      f"**Источник:** {modal_data['source']}\n"
                      f"**Время загрузки:** {modal_data_time:.3f}с",
                inline=False
            )
            
            # Анализ производительности
            status_emoji = "🟢" if full_data_time < 1.0 else "🟡" if full_data_time < 3.0 else "🔴"
            embed.add_field(
                name=f"{status_emoji} Анализ производительности",
                value=f"**Статус:** {'Отлично' if full_data_time < 1.0 else 'Приемлемо' if full_data_time < 3.0 else 'Медленно'}\n"
                      f"**Риск таймаута Discord:** {'Низкий' if full_data_time < 2.0 else 'Средний' if full_data_time < 3.0 else 'Высокий'}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ Ошибка тестирования: {e}")
            else:
                await interaction.response.send_message(f"❌ Ошибка тестирования: {e}")


async def setup(bot):
    """Загрузка Cog"""
    await bot.add_cog(CacheAdminSlashCommands(bot))
