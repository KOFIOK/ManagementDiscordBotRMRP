"""
Система предварительного кэширования для оптимизации складских операций
"""

import asyncio
from datetime import datetime
from typing import List
from utils.user_cache import preload_user_data
from utils.config_manager import load_config


class WarehouseCachePreloader:
    """Система предварительной загрузки кэша для склада"""
    
    def __init__(self, bot):
        self.bot = bot
        self.preload_task = None
        self.is_preloading = False
    
    async def start_preloading(self):
        """Запустить предварительную загрузку кэша"""
        if self.is_preloading:
            print("🔄 Предзагрузка кэша уже выполняется")
            return
        
        self.is_preloading = True
        self.preload_task = asyncio.create_task(self._preload_active_users())
    
    async def _preload_active_users(self):
        """Предзагрузить данные активных пользователей"""
        try:
            print("🚀 CACHE PRELOADER: Начинаем предзагрузку кэша...")
            
            # Ждем полной инициализации бота
            await asyncio.sleep(10)
            
            # Получаем список всех гильдий
            guilds = self.bot.guilds
            if not guilds:
                print("⚠️ CACHE PRELOADER: Нет доступных серверов")
                return
            
            # Собираем активных пользователей (не ботов)
            active_users = []
            for guild in guilds:
                for member in guild.members:
                    if not member.bot and member.id not in active_users:
                        active_users.append(member.id)
            
            # Ограничиваем количество для первоначальной загрузки
            preload_count = min(50, len(active_users))  # Максимум 50 пользователей
            users_to_preload = active_users[:preload_count]
            
            print(f"📦 CACHE PRELOADER: Предзагружаем данные для {preload_count} пользователей")
            
            # Выполняем предзагрузку батчами по 10 пользователей
            batch_size = 10
            successful_loads = 0
            
            for i in range(0, len(users_to_preload), batch_size):
                batch = users_to_preload[i:i + batch_size]
                
                try:
                    results = await preload_user_data(batch)
                    batch_success = sum(1 for result in results.values() if result is not None)
                    successful_loads += batch_success
                    
                    print(f"✅ CACHE PRELOADER: Батч {i//batch_size + 1}: {batch_success}/{len(batch)} успешно")
                    
                    # Небольшая пауза между батчами, чтобы не перегружать API
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    print(f"❌ CACHE PRELOADER: Ошибка в батче {i//batch_size + 1}: {e}")
                    continue
            
            print(f"✅ CACHE PRELOADER: Завершено! Предзагружено {successful_loads}/{preload_count} пользователей")
            
            # Планируем следующую предзагрузку через час
            await asyncio.sleep(3600)  # 1 час
            await self._periodic_cache_refresh()
            
        except Exception as e:
            print(f"❌ CACHE PRELOADER: Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_preloading = False
    
    async def _periodic_cache_refresh(self):
        """Периодическое обновление кэша"""
        try:
            print("🔄 CACHE PRELOADER: Периодическое обновление кэша")
            
            # Получаем статистику кэша
            from utils.user_cache import get_cache_statistics
            stats = get_cache_statistics()
            
            # Если hit rate низкий, делаем дополнительную предзагрузку
            if stats['hit_rate_percent'] < 60:
                print(f"📈 CACHE PRELOADER: Hit Rate низкий ({stats['hit_rate_percent']}%), выполняем дополнительную предзагрузку")
                
                # Предзагружаем еще 20 случайных пользователей
                import random
                all_users = []
                for guild in self.bot.guilds:
                    for member in guild.members:
                        if not member.bot:
                            all_users.append(member.id)
                
                if all_users:
                    random_users = random.sample(all_users, min(20, len(all_users)))
                    await preload_user_data(random_users)
                    print(f"✅ CACHE PRELOADER: Дополнительно предзагружено {len(random_users)} пользователей")
            
            # Планируем следующее обновление
            await asyncio.sleep(3600)  # Еще через час
            if not self.is_preloading:  # Защита от множественных задач
                self.preload_task = asyncio.create_task(self._periodic_cache_refresh())
                
        except Exception as e:
            print(f"❌ CACHE PRELOADER: Ошибка периодического обновления: {e}")
    
    def stop_preloading(self):
        """Остановить предзагрузку"""
        if self.preload_task and not self.preload_task.done():
            self.preload_task.cancel()
            print("🛑 CACHE PRELOADER: Предзагрузка остановлена")
        self.is_preloading = False


# Глобальный экземпляр предзагрузчика
cache_preloader = None


def setup_cache_preloader(bot):
    """Настроить предзагрузчик кэша"""
    global cache_preloader
    cache_preloader = WarehouseCachePreloader(bot)
    return cache_preloader


def start_cache_preloading(bot):
    """Запустить предзагрузку кэша"""
    global cache_preloader
    if not cache_preloader:
        cache_preloader = setup_cache_preloader(bot)
    
    # Запускаем предзагрузку асинхронно
    asyncio.create_task(cache_preloader.start_preloading())
    print("🚀 CACHE PRELOADER: Система предзагрузки запущена")


def stop_cache_preloading():
    """Остановить предзагрузку кэша"""
    global cache_preloader
    if cache_preloader:
        cache_preloader.stop_preloading()
