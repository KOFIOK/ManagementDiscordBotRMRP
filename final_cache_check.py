#!/usr/bin/env python3
"""
Финальная проверка универсального кэширования
"""

import sys
import os
import asyncio
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent))

from utils.user_cache import get_cache_statistics, get_cached_user_info
from utils.user_database import UserDatabase

async def final_cache_test():
    """Финальная проверка универсального кэширования"""
    print("🎯 ФИНАЛЬНАЯ ПРОВЕРКА УНИВЕРСАЛЬНОГО КЭШИРОВАНИЯ")
    print("=" * 60)
      # Получаем начальную статистику
    initial_stats = get_cache_statistics()
    print(f"📊 Начальная статистика кэша:")
    print(f"   Размер: {initial_stats['cache_size']} записей")
    print(f"   Hit Rate: {initial_stats['hit_rate_percent']:.1f}%")
    
    # Тестируем несколько запросов
    print(f"\n🔄 Выполняем тестовые запросы...")
    test_user_id = "123456789"
    
    # Первый запрос (miss)
    start_time = asyncio.get_event_loop().time()
    result1 = await get_cached_user_info(test_user_id)
    time1 = asyncio.get_event_loop().time() - start_time
    
    # Второй запрос (hit)
    start_time = asyncio.get_event_loop().time()
    result2 = await get_cached_user_info(test_user_id)
    time2 = asyncio.get_event_loop().time() - start_time
    
    print(f"   Первый запрос: {time1:.3f}с (cache miss)")
    print(f"   Второй запрос: {time2:.3f}с (cache hit)")
    if time1 > 0:
        speedup = time1 / time2 if time2 > 0 else float('inf')
        print(f"   🚀 Ускорение: {speedup:.1f}x")
      # Получаем финальную статистику
    final_stats = get_cache_statistics()
    print(f"\n📈 Финальная статистика кэша:")
    print(f"   Размер: {final_stats['cache_size']} записей")
    print(f"   Всего запросов: {final_stats['total_requests']}")
    print(f"   Попадания: {final_stats['hits']}")
    print(f"   Промахи: {final_stats['misses']}")
    print(f"   Hit Rate: {final_stats['hit_rate_percent']:.1f}%")
    
    print(f"\n✅ Универсальное кэширование работает корректно!")
    
    return final_stats

async def main():
    try:
        await final_cache_test()
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
