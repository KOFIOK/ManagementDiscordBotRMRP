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
    get_user_department_fast, get_user_rank_fast, refresh_user_cache, 
    is_cache_initialized, initialize_user_cache
)


class CacheAdminSlashCommands(commands.Cog):
    """Slash-команды администратора для управления кэшем"""
    
    def __init__(self, bot):
        self.bot = bot
    
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
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Не удалось очистить кэш: {e}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
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
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Не удалось удалить пользователя из кэша: {e}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
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
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ Ошибка тестирования пользователя: {e}")
            else:
                await interaction.response.send_message(f"❌ Ошибка тестирования пользователя: {e}", ephemeral=True)

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
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка получения статуса: {e}", ephemeral=True)

    @app_commands.command(name='warehouse_test_user', description='Протестировать получение данных пользователя для системы склада')
    @app_commands.describe(user='Пользователь для тестирования (по умолчанию - вы)')
    @app_commands.default_permissions(administrator=True)
    async def test_warehouse_user_data(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Протестировать получение данных пользователя для системы склада"""
        target_user = user if user else interaction.user
        
        try:
            await interaction.response.defer()
            
            from utils.user_cache import get_warehouse_user_data, prepare_modal_data
            
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
                await interaction.response.send_message(f"❌ Ошибка тестирования: {e}", ephemeral=True)
    
    @app_commands.command(name='reload_config', description='Перезагрузить конфигурацию бота без перезапуска')
    @app_commands.default_permissions(administrator=True)
    async def reload_config(self, interaction: discord.Interaction):
        """Перезагрузить конфигурацию бота"""
        try:
            await interaction.response.defer()
            
            # Импорт необходимых модулей
            from utils.config_manager import load_config
            from utils.ping_manager import ping_manager
            
            # Получаем старую конфигурацию для сравнения
            old_departments = ping_manager.get_departments_config()
            
            # Перезагружаем конфигурацию в ping_manager
            ping_manager.config = load_config()
            
            # Получаем новую конфигурацию
            new_departments = ping_manager.get_departments_config()
            
            # Анализируем изменения
            changes = []
            
            # Проверяем новые подразделения
            for dept_code, dept_config in new_departments.items():
                if dept_code not in old_departments:
                    changes.append(f"➕ Добавлено подразделение: **{dept_code}** ({dept_config.get('name', 'Без названия')})")
                else:
                    # Проверяем изменения в ролях должностей
                    old_positions = set(old_departments[dept_code].get('position_role_ids', []))
                    new_positions = set(dept_config.get('position_role_ids', []))
                    
                    old_assignable = set(old_departments[dept_code].get('assignable_position_role_ids', []))
                    new_assignable = set(dept_config.get('assignable_position_role_ids', []))
                    
                    if old_positions != new_positions:
                        added_pos = new_positions - old_positions
                        removed_pos = old_positions - new_positions
                        if added_pos:
                            changes.append(f"🔧 {dept_code}: добавлены роли должностей: {list(added_pos)}")
                        if removed_pos:
                            changes.append(f"🔧 {dept_code}: удалены роли должностей: {list(removed_pos)}")
                    
                    if old_assignable != new_assignable:
                        added_assign = new_assignable - old_assignable
                        removed_assign = old_assignable - new_assignable
                        if added_assign:
                            changes.append(f"✅ {dept_code}: добавлены выдаваемые роли: {list(added_assign)}")
                        if removed_assign:
                            changes.append(f"❌ {dept_code}: удалены выдаваемые роли: {list(removed_assign)}")
            
            # Проверяем удаленные подразделения  
            for dept_code in old_departments:
                if dept_code not in new_departments:
                    changes.append(f"➖ Удалено подразделение: **{dept_code}**")
            
            # Создаем embed с результатами
            embed = discord.Embed(
                title="🔄 Конфигурация перезагружена",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="📊 Статистика",
                value=f"**Подразделений:** {len(new_departments)}\n"
                      f"**Обнаружено изменений:** {len(changes)}",
                inline=True
            )
            
            if changes:
                # Ограничиваем количество изменений для отображения
                display_changes = changes[:10]
                if len(changes) > 10:
                    display_changes.append(f"... и еще {len(changes) - 10} изменений")
                
                embed.add_field(
                    name="📝 Обнаруженные изменения",
                    value="\n".join(display_changes),
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ Статус",
                    value="Изменений в конфигурации не обнаружено",
                    inline=False
                )
            
            embed.add_field(
                name="💡 Информация",
                value="Конфигурация успешно перезагружена.\n"
                      "Новые роли должностей теперь доступны без перезапуска бота.",
                inline=False
            )
            
            embed.set_footer(text="Изменения применены мгновенно")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка перезагрузки",
                description=f"Не удалось перезагрузить конфигурацию: {e}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed)

    @app_commands.command(name='cache_refresh', description='Принудительное обновление кэша пользователей')
    @app_commands.default_permissions(administrator=True)
    async def cache_refresh(self, interaction: discord.Interaction):
        """Принудительное обновление кэша пользователей"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Получаем статистику до обновления
            old_stats = get_cache_statistics()
            
            print(f"🔄 MANUAL CACHE REFRESH: Запрос от {interaction.user}")
            success = await refresh_user_cache()
            
            # Получаем статистику после обновления
            new_stats = get_cache_statistics()
            
            if success:
                await interaction.followup.send(
                    f"✅ **Кэш успешно обновлен**\n\n"
                    f"📊 **Статистика:**\n"
                    f"• Пользователей в кэше: {new_stats['cache_size']}\n"
                    f"• Hit rate: {new_stats['hit_rate_percent']}%\n"
                    f"• Всего запросов: {new_stats['total_requests']}\n"
                    f"• Попаданий: {new_stats['hits']}\n"
                    f"• Промахов: {new_stats['misses']}\n\n"
                    f"📦 **Предзагрузка:**\n"
                    f"• Пользователей предзагружено: {new_stats['bulk_preload_count']}\n"
                    f"• Время предзагрузки: {new_stats['bulk_preload_time']}\n\n"
                    f"💾 **Память:**\n"
                    f"• Примерное использование: {new_stats['memory_usage_estimate']} байт",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ **Ошибка при обновлении кэша**\n\n"
                    "Проверьте логи бота для деталей.",
                    ephemeral=True
                )
        
        except Exception as e:
            print(f"❌ Error in cache refresh command: {e}")
            try:
                await interaction.followup.send(
                    f"❌ Произошла ошибка: {str(e)}",
                    ephemeral=True
                )
            except:
                pass

    @app_commands.command(name='cache_stats', description='Показать статистику кэша пользователей')
    @app_commands.default_permissions(administrator=True)
    async def cache_stats(self, interaction: discord.Interaction):
        """Показать статистику кэша пользователей"""
        try:
            stats = get_cache_statistics()
            is_initialized = is_cache_initialized()
            
            # Рассчитываем время работы
            if stats.get('bulk_preload_time'):
                import datetime
                preload_time = stats['bulk_preload_time']
                if isinstance(preload_time, str):
                    try:
                        preload_time = datetime.datetime.fromisoformat(preload_time)
                    except:
                        preload_time = "Неизвестно"
                
                if isinstance(preload_time, datetime.datetime):
                    age = datetime.datetime.now() - preload_time
                    age_text = f"{age.total_seconds():.0f} секунд назад"
                else:
                    age_text = "Неизвестно"
            else:
                age_text = "Не выполнена"
            
            status_emoji = "✅" if is_initialized else "⚠️"
            status_text = "Активен" if is_initialized else "Требует инициализации"
            
            await interaction.response.send_message(
                f"{status_emoji} **Статистика кэша пользователей**\n\n"
                f"🔄 **Статус:** {status_text}\n"
                f"📊 **Размер кэша:** {stats['cache_size']} записей\n"
                f"📈 **Hit rate:** {stats['hit_rate_percent']}%\n"
                f"📋 **Всего запросов:** {stats['total_requests']}\n"
                f"✅ **Попаданий:** {stats['hits']}\n"
                f"❌ **Промахов:** {stats['misses']}\n\n"
                f"📦 **Предзагрузка:**\n"
                f"• Пользователей: {stats.get('bulk_preload_count', 0)}\n"
                f"• Последняя: {age_text}\n\n"
                f"💾 **Память:** ~{stats['memory_usage_estimate']} байт\n"
                f"🧹 **Истекших записей:** {stats['expired_entries']}",
                ephemeral=True
            )
        
        except Exception as e:
            print(f"❌ Error in cache stats command: {e}")
            await interaction.response.send_message(
                f"❌ Ошибка получения статистики: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name='cache_bulk_init', description='Принудительная инициализация кэша с массовой предзагрузкой')
    @app_commands.default_permissions(administrator=True)
    async def cache_bulk_init(self, interaction: discord.Interaction):
        """Принудительная инициализация кэша с массовой предзагрузкой"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            print(f"🚀 MANUAL BULK INIT: Запрос от {interaction.user}")
            
            import time
            start_time = time.time()
            
            success = await initialize_user_cache(force_refresh=True)
            
            load_time = time.time() - start_time
            stats = get_cache_statistics()
            
            if success:
                await interaction.followup.send(
                    f"✅ **Массовая предзагрузка завершена**\n\n"
                    f"⏱️ **Время выполнения:** {load_time:.2f} секунд\n"
                    f"📦 **Результат:**\n"
                    f"• Пользователей загружено: {stats.get('bulk_preload_count', 0)}\n"
                    f"• Размер кэша: {stats['cache_size']} записей\n"
                    f"• Статус: {'Активен' if is_cache_initialized() else 'Ошибка'}\n\n"
                    f"🚀 **Эффект:**\n"
                    f"• Мгновенное автозаполнение форм\n"
                    f"• Отсутствие ошибок PostgreSQL\n"
                    f"• Быстрая работа всех систем",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ **Ошибка массовой предзагрузки**\n\n"
                    f"⏱️ Время выполнения: {load_time:.2f} секунд\n"
                    f"📝 Проверьте логи бота для деталей\n"
                    f"💡 Возможные причины:\n"
                    f"• Проблемы с PostgreSQL подключением\n"
                    f"• Превышение лимитов запросов\n"
                    f"• Недоступность листа 'Личный Состав'",
                    ephemeral=True
                )
        
        except Exception as e:
            print(f"❌ Error in bulk init command: {e}")
            try:
                await interaction.followup.send(
                    f"❌ Произошла ошибка: {str(e)}",
                    ephemeral=True
                )
            except:
                pass

async def setup(bot):
    """Загрузка Cog"""
    await bot.add_cog(CacheAdminSlashCommands(bot))
