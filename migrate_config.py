"""
🔄 СКРИПТ МИГРАЦИИ КОНФИГУРАЦИИ
===============================

Преобразует старый config.json в новый формат с учетом модернизированной архитектуры:

ИЗМЕНЕНИЯ:
• Удаляет устаревшие поля rank_roles (ранги теперь в PostgreSQL)
• Удаляет position_role_ids и assignable_position_role_ids из departments 
• Удаляет устаревшие лимиты склада в старом формате
• Обновляет структуру departments согласно новой архитектуре
• Сохраняет все Discord-специфичные настройки

ИСПОЛЬЗОВАНИЕ:
python migrate_config.py --input old_config.json --output new_config.json
"""

import json
import argparse
import os
import shutil
from datetime import datetime
from typing import Dict, Any

def backup_file(filepath: str) -> str:
    """Создать резервную копию файла"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.backup_{timestamp}"
    if os.path.exists(filepath):
        shutil.copy2(filepath, backup_path)
        print(f"✅ Создана резервная копия: {backup_path}")
        return backup_path
    return ""

def migrate_departments(old_departments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Миграция секции departments: удаляем position_role_ids и assignable_position_role_ids
    """
    new_departments = {}
    
    print("🏛️ МИГРАЦИЯ ПОДРАЗДЕЛЕНИЙ:")
    
    for dept_key, dept_data in old_departments.items():
        print(f"  📁 {dept_key} ({dept_data.get('name', 'Без названия')})")
        
        # Копируем все данные кроме устаревших полей
        new_dept = {}
        
        for key, value in dept_data.items():
            if key in ['position_role_ids', 'assignable_position_role_ids']:
                print(f"    ❌ Удаляем устаревшее поле: {key}")
                continue
            else:
                new_dept[key] = value
        
        # Проверяем и исправляем цвета если они в текстовом формате
        if 'color' in new_dept and isinstance(new_dept['color'], str):
            if new_dept['color'] == "синий":
                new_dept['color'] = 3447003  # Стандартный синий цвет
                print(f"    🎨 Конвертирован цвет 'синий' -> {new_dept['color']}")
        
        new_departments[dept_key] = new_dept
        print(f"    ✅ Подразделение мигрировано")
    
    return new_departments

def remove_warehouse_legacy_fields(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Удаляет устаревшие поля лимитов склада в старом формате
    """
    fields_to_remove = []
    
    print("🏪 ОЧИСТКА УСТАРЕВШИХ ПОЛЕЙ СКЛАДА:")
    
    # Ищем поля с именами званий/должностей в корне конфигурации
    for key in config.keys():
        if isinstance(config[key], dict) and any(
            subkey in config[key] 
            for subkey in ['оружие', 'бронежилеты', 'аптечки', 'обезболивающее', 'дефибрилляторы']
        ):
            fields_to_remove.append(key)
            print(f"  ❌ Удаляем устаревшее поле лимитов: {key}")
    
    # Удаляем найденные поля
    for field in fields_to_remove:
        del config[field]
    
    return config

def migrate_config(old_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Основная функция миграции конфигурации
    """
    print("🔄 НАЧАЛО МИГРАЦИИ КОНФИГУРАЦИИ")
    print("=" * 50)
    
    new_config = old_config.copy()
    
    # 1. Удаляем секцию rank_roles (ранги теперь в PostgreSQL)
    if 'rank_roles' in new_config:
        print("🏆 МИГРАЦИЯ РАНГОВ:")
        print(f"  ❌ Удаляем секцию rank_roles ({len(new_config['rank_roles'])} рангов)")
        print("  📊 Ранги теперь управляются через PostgreSQL")
        del new_config['rank_roles']
    
    # 2. Удаляем rank_sync_key_role если есть
    if 'rank_sync_key_role' in new_config:
        print(f"  ❌ Удаляем устаревшее поле rank_sync_key_role")
        del new_config['rank_sync_key_role']
    
    # 3. Мигрируем подразделения
    if 'departments' in new_config:
        new_config['departments'] = migrate_departments(new_config['departments'])
    
    # 4. Удаляем устаревшие поля лимитов склада
    new_config = remove_warehouse_legacy_fields(new_config)
    
    # 5. Обновляем supplies секцию если нужно
    if 'supplies' in new_config:
        print("📦 ПРОВЕРКА НАСТРОЕК ПОСТАВОК:")
        supplies = new_config['supplies']
        
        # Добавляем недостающие поля если их нет
        if 'timer_duration_hours' not in supplies:
            supplies['timer_duration_hours'] = 4
            print("  ✅ Добавлено timer_duration_hours: 4")
        
        if 'timer_duration_minutes' not in supplies:
            supplies['timer_duration_minutes'] = 2  
            print("  ✅ Добавлено timer_duration_minutes: 2")
    
    # 6. Инициализируем настройки автозамены никнеймов
    if 'nickname_auto_replacement' not in new_config:
        print("🏷️ ИНИЦИАЛИЗАЦИЯ НАСТРОЕК АВТОЗАМЕНЫ НИКНЕЙМОВ:")
        new_config['nickname_auto_replacement'] = {
            'enabled': True,
            'departments': {},
            'modules': {
                'dismissal': True,
                'transfer': True,
                'promotion': True,
                'demotion': True
            }
        }
        print("  ✅ Добавлены настройки автозамены никнеймов")
        print("  ✅ Глобально включена: True")
        print("  ✅ Все модули включены: dismissal, transfer, promotion, demotion")
    else:
        print("🏷️ ПРОВЕРКА НАСТРОЕК АВТОЗАМЕНЫ НИКНЕЙМОВ:")
        nickname_settings = new_config['nickname_auto_replacement']
        
        # Проверяем структуру
        if 'enabled' not in nickname_settings:
            nickname_settings['enabled'] = True
            print("  ✅ Добавлено enabled: True")
        
        if 'departments' not in nickname_settings:
            nickname_settings['departments'] = {}
            print("  ✅ Добавлена секция departments")
        
        if 'modules' not in nickname_settings:
            nickname_settings['modules'] = {
                'dismissal': True,
                'transfer': True,
                'promotion': True,
                'demotion': True
            }
            print("  ✅ Добавлена секция modules")
        else:
            modules = nickname_settings['modules']
            required_modules = ['dismissal', 'transfer', 'promotion', 'demotion']
            for module in required_modules:
                if module not in modules:
                    modules[module] = True
                    print(f"  ✅ Добавлен модуль {module}: True")
    
    print("\n🎯 МИГРАЦИЯ ЗАВЕРШЕНА!")
    return new_config

def validate_migrated_config(config: Dict[str, Any]) -> bool:
    """
    Проверяет корректность мигрированной конфигурации
    """
    print("\n🔍 ВАЛИДАЦИЯ МИГРИРОВАННОЙ КОНФИГУРАЦИИ:")
    print("-" * 40)
    
    issues = []
    
    # Проверяем что удалены устаревшие поля
    if 'rank_roles' in config:
        issues.append("❌ rank_roles не удалена")
    else:
        print("✅ rank_roles успешно удалена")
    
    # Проверяем departments
    if 'departments' in config:
        print(f"📁 Подразделений: {len(config['departments'])}")
        
        for dept_key, dept_data in config['departments'].items():
            if 'position_role_ids' in dept_data:
                issues.append(f"❌ {dept_key} содержит устаревшее поле position_role_ids")
            if 'assignable_position_role_ids' in dept_data:
                issues.append(f"❌ {dept_key} содержит устаревшее поле assignable_position_role_ids")
        
        if not issues:
            print("✅ Все подразделения очищены от устаревших полей")
    
    # Проверяем наличие обязательных полей
    required_fields = [
        'dismissal_channel', 'audit_channel', 'role_assignment_channel',
        'departments', 'moderators', 'administrators', 'nickname_auto_replacement'
    ]
    
    for field in required_fields:
        if field not in config:
            issues.append(f"❌ Отсутствует обязательное поле: {field}")
        else:
            print(f"✅ {field}: присутствует")
    
    # Проверяем структуру настроек автозамены никнеймов
    if 'nickname_auto_replacement' in config:
        print("🏷️ ПРОВЕРКА НАСТРОЕК АВТОЗАМЕНЫ НИКНЕЙМОВ:")
        nickname_settings = config['nickname_auto_replacement']
        
        required_nickname_fields = ['enabled', 'departments', 'modules']
        for field in required_nickname_fields:
            if field not in nickname_settings:
                issues.append(f"❌ nickname_auto_replacement.{field} отсутствует")
            else:
                print(f"  ✅ {field}: присутствует")
        
        if 'modules' in nickname_settings:
            required_modules = ['dismissal', 'transfer', 'promotion', 'demotion']
            modules = nickname_settings['modules']
            for module in required_modules:
                if module not in modules:
                    issues.append(f"❌ nickname_auto_replacement.modules.{module} отсутствует")
                else:
                    print(f"  ✅ модуль {module}: присутствует")
    
    if issues:
        print(f"\n⚠️  НАЙДЕНО {len(issues)} ПРОБЛЕМ:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n🎉 КОНФИГУРАЦИЯ ВАЛИДНА!")
        return True

def print_migration_summary(old_config: Dict[str, Any], new_config: Dict[str, Any]):
    """
    Печатает сводку изменений
    """
    print("\n📊 СВОДКА МИГРАЦИИ:")
    print("=" * 50)
    
    # Подсчет удаленных полей
    old_fields = set(old_config.keys())
    new_fields = set(new_config.keys())
    removed_fields = old_fields - new_fields
    
    if removed_fields:
        print(f"🗑️  Удалено полей: {len(removed_fields)}")
        for field in sorted(removed_fields):
            print(f"  • {field}")
    
    # Подразделения
    if 'departments' in old_config and 'departments' in new_config:
        old_dept_count = len(old_config['departments'])
        new_dept_count = len(new_config['departments'])
        print(f"\n🏛️ Подразделения: {old_dept_count} -> {new_dept_count}")
        
        # Подсчет удаленных полей в подразделениях
        total_removed_dept_fields = 0
        for dept_key in old_config['departments']:
            if dept_key in new_config['departments']:
                old_dept_fields = set(old_config['departments'][dept_key].keys())
                new_dept_fields = set(new_config['departments'][dept_key].keys())
                total_removed_dept_fields += len(old_dept_fields - new_dept_fields)
        
        if total_removed_dept_fields > 0:
            print(f"  • Удалено полей из подразделений: {total_removed_dept_fields}")
    
    print(f"\n💾 Размер конфигурации:")
    print(f"  • До: {len(json.dumps(old_config))} символов")
    print(f"  • После: {len(json.dumps(new_config))} символов")

def main():
    parser = argparse.ArgumentParser(description='Миграция config.json в новый формат')
    parser.add_argument('--input', '-i', default='old_config.json', 
                       help='Путь к старому config.json')
    parser.add_argument('--output', '-o', default='data/config.json',
                       help='Путь для нового config.json')
    parser.add_argument('--backup', '-b', action='store_true',
                       help='Создать резервную копию выходного файла')
    parser.add_argument('--validate-only', action='store_true',
                       help='Только валидация, без сохранения')
    
    args = parser.parse_args()
    
    # Проверяем существование входного файла
    if not os.path.exists(args.input):
        print(f"❌ Файл не найден: {args.input}")
        return
    
    # Создаем резервную копию выходного файла если требуется
    if args.backup and os.path.exists(args.output):
        backup_file(args.output)
    
    # Загружаем старую конфигурацию
    print(f"📂 Загрузка конфигурации из: {args.input}")
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            old_config = json.load(f)
        print(f"✅ Конфигурация загружена ({len(old_config)} полей)")
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return
    
    # Выполняем миграцию
    try:
        new_config = migrate_config(old_config)
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        return
    
    # Валидация
    if not validate_migrated_config(new_config):
        print("❌ Миграция завершилась с ошибками")
        return
    
    # Печатаем сводку
    print_migration_summary(old_config, new_config)
    
    # Сохраняем если не только валидация
    if not args.validate_only:
        try:
            # Создаем директорию если нужно
            os.makedirs(os.path.dirname(args.output), exist_ok=True)
            
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=4, ensure_ascii=False)
            
            print(f"\n💾 Новая конфигурация сохранена: {args.output}")
            print("🎯 Миграция успешно завершена!")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
    else:
        print("\n🔍 Режим валидации - файл не сохранен")

if __name__ == "__main__":
    main()