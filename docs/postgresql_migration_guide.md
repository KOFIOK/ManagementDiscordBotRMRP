# 🗄️ PostgreSQL Миграция и База Данных

## 📋 Обзор

Бот полностью мигрировал с Google Sheets на PostgreSQL базу данных, обеспечивая высокую производительность, надёжность и расширенные возможности управления персоналом.

## 🏗️ Архитектура Базы Данных

### 📐 Физическая модель базы данных

![Физическая модель базы данных](./images/db_physical_model.png)

### 👹 Описание сущностей базы данных

> *Сущность* — это «предмет» или «объект» из реального мира, который вы храните в базе данных. Проще: это любой тип данных, про который вам нужно сохранять информацию (например, сотрудник, подразделение, должность). В базе сущность обычно представляется таблицей: каждая строка — это отдельный экземпляр сущности, а столбцы — его свойства (атрибуты).

Ниже приведены основные таблицы физической модели и ключевые поля. Эти описания помогут при подготовке и проверке схемы PostgreSQL.

#### `personnel`
| Атрибут | Тип | Описание |
|---|---|---|
| id | integer (PK) | Внутренний идентификатор сотрудника в реестре personnel |
| discord_id | bigint | Discord ID пользователя (уникальный для связки с Discord) |
| first_name | varchar | Имя сотрудника |
| last_name | varchar | Фамилия сотрудника |
| static | varchar | Статический идентификатор (например 123-456) |
| last_updated | timestamp | Время последнего обновления записи |
| is_dismissal | boolean | Флаг, помечающий уволенных сотрудников |
| join_date | date | Дата принятия на службу |
| dismissal_date | date | Дата увольнения (если есть) |
| dismissal_reason | text | Причина увольнения (опционально) |

#### `employees`
| Атрибут | Тип | Описание |
|---|---|---|
| id | integer (PK) | PK записи сотрудника (employee) |
| rank_id | integer (FK -> ranks.id) | Ссылка на таблицу званий |
| subdivision_id | integer (FK -> subdivisions.id) | Ссылка на подразделение |
| position_subdivision_id | integer (FK -> position_subdivision.id) | Ссылка на привязку должности к подразделению |
| personnel_id | integer (FK -> personnel.id) | Связь с записью в personnel (владелец) |

#### `ranks`
| Атрибут | Тип | Описание |
|---|---|---|
| id | integer (PK) | Идентификатор звания |
| name | varchar | Полное название звания (например 'Ефрейтор') |
| role_id | integer | Discord role id, опционально для автоматизации ролей |
| rank_level | integer | Уровень/приоритет звания (для сортировки) |
| abbreviation | varchar | Краткое обозначение звания |

#### `subdivisions`
| Атрибут | Тип | Описание |
|---|---|---|
| id | integer (PK) | Идентификатор подразделения |
| name | varchar | Полное название подразделения (для UI и embed) |
| abbreviation | varchar | Короткое обозначение подразделения |

#### `positions`
| Атрибут | Тип | Описание |
|---|---|---|
| id | integer (PK) | Идентификатор должности |
| name | varchar | Название должности (например 'Военный комиссар') |
| role_id | integer | Discord role id, опционально |

#### `position_subdivision`
| Атрибут | Тип | Описание |
|---|---|---|
| id | integer (PK) | PK привязки должности к подразделению |
| position_id | integer (FK -> positions.id) | Должность |
| subdivision_id | integer (FK -> subdivisions.id) | Подразделение |

#### `actions`
| Атрибут | Тип | Описание |
|---|---|---|
| id | integer (PK) | Идентификатор действия (лог типа: принят/уволен/повышен) |
| name | varchar | Название действия (например 'Принят на службу') |

#### `history`
| Атрибут | Тип | Описание |
|---|---|---|
| id | integer (PK) | PK записи истории изменений |
| action_date | timestamp | Дата/время действия |
| details | text | Дополнительные детали (сериализованные изменения) |
| performed_by | integer | Discord ID или personnel ID модератора/исполнителя |
| action_id | integer (FK -> actions.id) | Тип действия |
| personnel_id | integer (FK -> personnel.id) | На кого выполнено действие |
| changes | jsonb | Изменения (old/new) в формате JSON |

#### `blacklist`
| Атрибут | Тип | Описание |
|---|---|---|
| id | integer (PK) | PK записи в черном списке |
| reason | text | Причина добавления в чс |
| start_date | date | Дата начала блокировки |
| end_date | date | Дата окончания блокировки (опционально) |
| last_updated | timestamp | Время последнего обновления записи |
| is_active | boolean | Флаг активности записи |
| personnel_id | integer (FK -> personnel.id) | Ссылка на personnel для удобства |

_Примечание:_ это краткий справочник по основным сущностям. Полная схема и дополнительные справочники (например таблицы настроек, audit logs, supplies и т.д.) описаны в `utils/database/models.py`.

---

## 🛡️ Дополнительные меры защиты

### 📃 Авто backup каждые сутки

Инструкция для настройки ежедневных бэкапов базы данных с помощью `pg_dump` и `cron` на сервере Ubuntu. Бэкапы сохраняются в `/opt/PostgreSQL/backups/ManagementDiscordBotRMRP` в 00:00 MSK.
> Перед настройкой убедитесь, что PostgreSQL установлен на ваш сервер.

### 1. Настройка timezone
Убедитесь, что сервер использует московское время:
```bash
sudo timedatectl set-timezone Europe/Moscow
```
Проверьте: `timedatectl` (должно показать `Europe/Moscow (MSK, +0300)`).

### 2. Создание директории для бэкапов
Создайте папку и задайте права:
```bash
sudo mkdir -p /opt/PostgreSQL/backups/ManagementDiscordBotRMRP
sudo chown postgres:postgres /opt/PostgreSQL/backups/ManagementDiscordBotRMRP
sudo chmod 750 /opt/PostgreSQL/backups/ManagementDiscordBotRMRP
```

### 3. Настройка `.pgpass` для аутентификации
Создайте или обновите файл `/var/lib/postgresql/.pgpass` для пользователя PostgreSQL `postgres`:
```bash
echo "127.0.0.1:5432:*:postgres:your_secure_password" | sudo -u postgres tee /var/lib/postgresql/.pgpass
sudo -u postgres chmod 600 /var/lib/postgresql/.pgpass
```
Замените `your_secure_password` на пароль пользователя `postgres`. Если пароль неизвестен, сбросьте:
```bash
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'your_secure_password';"
```

### 4. Создание скрипта бэкапа
Создайте файл `/opt/PostgreSQL/backups/pg_backup.sh`:
```bash
sudo nano /opt/PostgreSQL/backups/pg_backup.sh
```
Вставьте код:
```bash
#!/bin/bash

DB_PORT="5432"
DB_NAME="army_bot_db"
DB_USER="postgres"
BACKUP_DIR="/opt/PostgreSQL/backups/ManagementDiscordBotRMRP"
BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y-%m-%d_%H-%M-%S).dump"
LOG_FILE="$BACKUP_DIR/pg_backup.log"

cd "$BACKUP_DIR" || exit 1

export PGPASSFILE=/var/lib/postgresql/.pgpass

pg_dump -p $DB_PORT -U $DB_USER -d $DB_NAME -F c -f $BACKUP_FILE

gzip $BACKUP_FILE
BACKUP_FILE="$BACKUP_FILE.gz"

find "$BACKUP_DIR" -type f -name "*.dump.gz" -mtime +7 -exec rm {} \;

echo "Backup completed: $BACKUP_FILE" >> "$LOG_FILE"
```
Сделайте исполняемым:
```bash
sudo chmod +x /opt/PostgreSQL/backups/pg_backup.sh
```

### 5. Настройка прав для лога
Создайте лог-файл:
```bash
sudo touch /opt/PostgreSQL/backups/ManagementDiscordBotRMRP/pg_backup.log
sudo chown postgres:postgres /opt/PostgreSQL/backups/ManagementDiscordBotRMRP/pg_backup.log
sudo chmod 664 /opt/PostgreSQL/backups/ManagementDiscordBotRMRP/pg_backup.log
```

### 6. Тестирование скрипта
Запустите вручную:
```bash
sudo -u postgres /opt/PostgreSQL/backups/pg_backup.sh
```
Проверьте:
- Бэкап в `/opt/PostgreSQL/backups/ManagementDiscordBotRMRP/backup_*.dump.gz`.
- Лог в `/opt/PostgreSQL/backups/ManagementDiscordBotRMRP/pg_backup.log`.

### 7. Настройка cron
Настройте запуск в 00:00 MSK:
```bash
sudo -u postgres crontab -e
```
Добавьте:
```
0 0 * * * /opt/PostgreSQL/backups/pg_backup.sh
```
Проверьте: `sudo -u postgres crontab -l`.

### Примечания
- Если pg_dump выдаёт ошибку аутентификации, проверьте `.pgpass` или `pg_hba.conf`:
  ```bash:disable-run
  sudo cat /etc/postgresql/*/main/pg_hba.conf
  ```
  Убедитесь, что для `host all postgres 127.0.0.1/32` стоит `md5` или `trust`.
- Для восстановления: `pg_restore -U postgres -d army_bot_db backup_file.dump`.

---

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
> Предназначена больше для вынесения в один модуль всех отписок в канал кадрового аудита
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
- Используя `ПКМ - Приложения`, все изменения отправляются и в кадровый аудит, и в базу данных
- Автоматическое обновление никнеймов при изменении статуса (повышении / понижении / перевода в подразделение / принятии / увольнения)
  - Настраиваемая система! `/settings - Автозамена никнеймов`
- Сохранение полной истории всех операций в таблице (сущности) history

### 🛡️ **Надёжность и Безопасность**
- Connection pooling для оптимальной производительности
- Транзакции для обеспечения целостности данных
- Валидация всех входных данных
- Автоматические резервные копии базы данных (по желанию и возможности)

### 📈 **Расширенная Аналитика**
- Полная история карьеры каждого сотрудника
- Подсчёт общего времени службы
- Статистика по подразделениям и званиям
- Автоматическое отслеживание чёрного списка (при увольнении все, кто пробыл во фракции менее 5 дней, автоматически попадают в чёрный список)

## 🔧 Настройка и Конфигурация

### 📋 **Требования**
```bash
# Установка PostgreSQL (на Linux)
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

### 🗄️ **Проверка Схемы**
```bash
# Проверка схемы
python db_schema_check.py
```

## 🔮 Планы Развития

### 🚀 **Ближайшие Обновления**
- Расширенные отчёты по персоналу
- ВЕБ-платформа для генерации отчётов
- Горизонтальное масштабирование

---

## ✅ Готов к использованию!

PostgreSQL база данных полностью настроена и интегрирована. Все системы работают стабильно с высокой производительностью и надёжностью.

**📖 Для получения дополнительной информации изучите [руководство по установке](installation_guide.md) и [техническую документацию](../README.md).**
