# 🗄️ PostgreSQL Миграция и База Данных

## 📋 Обзор

Бот полностью мигрировал с Google Sheets на PostgreSQL базу данных, обеспечивая высокую производительность, надёжность и расширенные возможности управления персоналом.

## 🏗️ Архитектура Базы Данных

### Основные таблицы:

#### 👥 **personnel** - Основная таблица персонала
```sql
- id (serial) - Уникальный идентификатор
- discord_id (bigint) - Discord ID пользователя
- first_name (varchar) - Имя
- last_name (varchar) - Фамилия
- static (varchar) - Статический номер (XX-XXX или XXX-XXX)
- join_date (date) - Дата поступления
- dismissal_date (date) - Дата увольнения (если есть)
- is_dismissal (boolean) - Статус увольнения
- last_updated (timestamp) - Последнее обновление
```

#### 💼 **employees** - Активные сотрудники
```sql
- id (serial) - Уникальный идентификатор
- personnel_id (int) - Связь с personnel
- rank_id (int) - Связь с ranks
- subdivision_id (int) - Связь с subdivisions
- position_subdivision_id (int) - Связь с position_subdivision
- assigned_date (date) - Дата назначения
- last_updated (timestamp) - Последнее обновление
```

#### 🎖️ **ranks** - Воинские звания
```sql
- id (serial) - Уникальный идентификатор
- name (varchar) - Название звания
- abbreviation (varchar) - Аббревиатура
- hierarchy_level (int) - Уровень в иерархии
```

#### 🏢 **subdivisions** - Подразделения
```sql
- id (serial) - Уникальный идентификатор
- name (varchar) - Название подразделения
- abbreviation (varchar) - Аббревиатура
- parent_id (int) - Родительское подразделение
```

#### 💺 **positions** - Должности
```sql
- id (serial) - Уникальный идентификатор
- name (varchar) - Название должности
- description (text) - Описание должности
```

#### 📊 **history** - История изменений
```sql
- id (serial) - Уникальный идентификатор
- personnel_id (int) - Связь с personnel
- action_id (int) - Тип действия (из actions)
- action_date (timestamp) - Дата действия
- performed_by (varchar) - Кто выполнил
- details (text) - Подробности
- changes (jsonb) - Изменения в формате JSON
```

#### 🚫 **blacklist** - Чёрный список
```sql
- id (serial) - Уникальный идентификатор
- personnel_id (int) - Связь с personnel
- reason (text) - Причина занесения
- start_date (date) - Дата начала
- end_date (date) - Дата окончания
- added_by (varchar) - Кто добавил
- is_active (boolean) - Активность записи
```

## 🔧 Ключевые Компоненты

### 📊 **PersonnelManager** - Основной менеджер персонала
```python
from utils.database_manager import PersonnelManager

pm = PersonnelManager()

# Основные операции
await pm.process_role_application_approval(...)
await pm.process_department_join(...)
await pm.process_personnel_dismissal(...)
await pm.get_personnel_summary(discord_id)
```

### 🗄️ **Connection Pool** - Пул соединений
```python
from utils.postgresql_pool import get_db_cursor, get_connection_pool

# Использование курсора
with get_db_cursor() as cursor:
    cursor.execute("SELECT * FROM personnel WHERE discord_id = %s", (user_id,))
    result = cursor.fetchone()
```

### 📝 **Audit Logger** - Система аудита
```python
from utils.audit_logger import audit_logger, AuditAction

# Отправка записи аудита
await audit_logger.send_personnel_audit(
    guild=interaction.guild,
    action=await AuditAction.HIRING(),
    target_user=user,
    moderator=interaction.user,
    personnel_data=data
)
```

## ⚙️ Основные Возможности

### 🔄 **Автоматическая Синхронизация**
- Все изменения Discord ролей отражаются в базе данных
- Автоматическое обновление никнеймов при изменении статуса
- Сохранение полной истории всех операций

### 🛡️ **Надёжность и Безопасность**
- Connection pooling для оптимальной производительности
- Транзакции для обеспечения целостности данных
- Валидация всех входных данных
- Автоматические резервные копии

### 📈 **Расширенная Аналитика**
- Полная история карьеры каждого сотрудника
- Подсчёт общего времени службы
- Статистика по подразделениям и званиям
- Автоматическое отслеживание чёрного списка

## 🚀 Преимущества над Google Sheets

### ⚡ **Производительность**
- Мгновенные запросы благодаря индексам
- Одновременная работа множества пользователей
- Отсутствие лимитов API

### 🔐 **Безопасность**
- Локальная база данных - полный контроль
- Нет зависимости от внешних сервисов
- Расширенные права доступа

### 🎯 **Функциональность**
- Сложные запросы с JOIN
- JSONB поля для гибкого хранения данных
- Триггеры и хранимые процедуры
- Полнотекстовый поиск

## 🔧 Настройка и Конфигурация

### 📋 **Требования**
```bash
# Установка PostgreSQL
sudo apt install postgresql postgresql-contrib

# Python зависимости
pip install psycopg2-binary
```

### ⚙️ **Переменные Окружения**
```bash
# .env файл
DATABASE_URL="postgresql://username:password@localhost:5432/army_bot"
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"
POSTGRES_DB="army_bot"
POSTGRES_USER="username"
POSTGRES_PASSWORD="password"
```

### 🗄️ **Инициализация Схемы**
```bash
# Создание схемы из файлов sql/
python db_schema_check.py
```

## 📊 Миграционный Процесс

### 🔄 **Автоматическая Миграция**
Бот автоматически:
1. Создаёт необходимые таблицы при первом запуске
2. Проверяет схему на соответствие
3. Выполняет обновления структуры при необходимости
4. Мигрирует данные из существующих источников

### 🛠️ **Инструменты Миграции**
- `migrate_config.py` - Миграция конфигурации
- `db_schema_check.py` - Проверка схемы базы данных
- `validate_bot.py` - Валидация системы после миграции

## 🔍 Мониторинг и Диагностика

### 📊 **Команды Диагностики**
```bash
# Проверка состояния базы данных
python check_personnel_table.py

# Валидация системы
python validate_bot.py

# Статистика подключений
/admin database-stats
```

### 📈 **Метрики Performance**
- Время выполнения запросов
- Количество активных соединений
- Статистика операций CRUD
- Мониторинг ошибок подключения

## 🔮 Планы Развития

### 🚀 **Ближайшие Обновления**
- Интеграция с аналитическими дашбордами
- Расширенные отчёты по персоналу
- API для внешних интеграций
- Горизонтальное масштабирование

### 💡 **Новые Возможности**
- Автоматические бэкапы в облако
- Репликация для отказоустойчивости
- Интеграция с системами мониторинга
- Машинное обучение для прогнозирования

---

## ✅ Готов к использованию!

PostgreSQL база данных полностью настроена и интегрирована. Все системы работают стабильно с высокой производительностью и надёжностью.

**📖 Для получения дополнительной информации изучите [руководство по установке](installation_guide.md) и [техническую документацию](README.md).**