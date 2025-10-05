#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка структуры таблицы personnel
"""

from utils.postgresql_pool import get_db_cursor

def check_personnel_table():
    """Проверяем структуру таблицы personnel"""
    try:
        with get_db_cursor() as cursor:
            # Проверяем структуру таблицы
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'personnel' 
                ORDER BY ordinal_position;
            """)
            
            columns = cursor.fetchall()
            
            if columns:
                print("📋 Структура таблицы personnel:")
                print("-" * 50)
                for col in columns:
                    print(f"  {col['column_name']}: {col['data_type']} ({'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'})")
                    
                # Проверяем есть ли данные
                cursor.execute("SELECT COUNT(*) as count FROM personnel;")
                count = cursor.fetchone()['count']
                print(f"\n📊 Количество записей: {count}")
                
                if count > 0:
                    cursor.execute("""
                        SELECT discord_id, first_name, last_name, static 
                        FROM personnel 
                        WHERE is_dismissal = false
                        LIMIT 3;
                    """)
                    samples = cursor.fetchall()
                    print("\n📄 Примеры записей (активные):")
                    for sample in samples:
                        print(f"  Discord ID: {sample['discord_id']}, Имя: {sample.get('first_name', 'N/A')}, Фамилия: {sample.get('last_name', 'N/A')}, Static: {sample.get('static', 'N/A')}")
                        
            else:
                print("❌ Таблица personnel не найдена или пуста")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    check_personnel_table()