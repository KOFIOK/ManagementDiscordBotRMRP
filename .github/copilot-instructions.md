# AI Coding Assistant Instructions for Army Discord Bot

## Project Overview
This is a comprehensive Discord bot for military personnel management built with Discord.py 2.0+, featuring PostgreSQL database integration, hierarchical permissions, and complex form-based interactions.

## Communication Guidelines

**IMPORTANT**: All responses must be in Russian language. The user communicates in Russian, so all explanations, comments, and documentation should be provided in Russian. This includes:
- Code comments and docstrings
- Error messages and logging
- User-facing messages and responses
- Documentation and instructions

## Architecture & Key Components

### Core Structure
- **`app.py`**: Main entry point with complex async initialization sequence
- **`cogs/`**: Modular command extensions loaded dynamically
- **`forms/`**: Discord UI components (persistent views, modals, buttons)
- **`utils/`**: Core utilities (database, config, caching, notifications)
- **`data/config.json`**: Centralized configuration with automatic backups

### Database Layer
- **PostgreSQL** with **SQLAlchemy** async models (`utils/database/models.py`)
- **Connection pooling** via `utils/postgresql_pool.py`
- **PersonnelManager** class for all database operations (`utils/database_manager/manager.py`)
- **Audit logging** for all personnel changes

### Database Schema Overview
**Core Tables:**
- `personnel`: Main personnel records (discord_id, names, static ID, dismissal status)
- `employees`: Links personnel to ranks, subdivisions, positions
- `ranks`: Military ranks with hierarchy levels and Discord role IDs
- `subdivisions`: Departments/divisions with Discord role IDs
- `positions`: Job positions
- `position_subdivision`: Junction table for position-department relationships
- `history`: Complete audit trail with JSON change tracking
- `blacklist`: Personnel blacklist with reasons and date ranges

**Key Relationships:**
- Personnel → Employees (1:many)
- Employees → Ranks, Subdivisions, PositionSubdivision
- PositionSubdivision → Positions + Subdivisions

### Messaging System
- **YAML-based templates**: `data/messages/messages-default.yml` is the authoritative source
- **Wrapper functions**: `get_message`, `get_private_messages`, `get_system_message`, `get_systems_message`
- **Namespace mapping**: Each wrapper maps to a YAML namespace (e.g., `get_supplies_message` → `systems.supplies`)
- **Template references**: Messages can reference other templates via `{templates.base.error_prefix}` syntax
- **Per-guild customization**: Guild-specific overrides in `messages-{guild_id}.yml`

**Message Key Patterns:**
```python
# Direct access
get_message(guild_id, "templates.errors.validation", default)

# Wrapper access with namespace prefix
get_supplies_message(guild_id, "main_embed_title")  # → systems.supplies.main_embed_title
get_private_messages(guild_id, "dismissal.approval.title")  # → private_messages.dismissal.approval.title
get_ui_button(guild_id, "approve")  # → ui.buttons.approve

# Role audit reasons
get_role_reason(guild_id, "role_assignment.approved")  # → role_reasons.role_assignment.approved
```

**CRITICAL**: Always verify message keys exist in YAML before using them. Run `python tests/test_messages_all_keys.py` to validate all keys.

### Permission System
Hierarchical access control with Discord admin override:
```python
administrators > moderators > users
# Check permissions with:
from utils.config_manager import is_administrator, is_moderator_or_admin
```

## Critical Patterns & Conventions

### Persistent Views Pattern
**CRITICAL**: Views must survive bot restarts. Register in `app.py` `on_ready()` with dummy data:
```python
# Register views in app.py on_ready() for buttons that survive restarts
bot.add_view(DismissalReportButton())
bot.add_view(RoleAssignmentView())

# Views require dummy data for persistence
dummy_data = {'user_id': 0, 'status': 'pending'}
bot.add_view(SomeApprovalView(dummy_data))
```

### Database Operations
Always use PersonnelManager for data access with context managers:
```python
# Always use PersonnelManager for data access
from utils.database_manager import PersonnelManager
manager = PersonnelManager()

# Core operations
await manager.process_role_application_approval(...)
await manager.process_department_join(...)
await manager.process_personnel_dismissal(...)
personnel_data = await manager.get_personnel_summary(discord_id)
```

### Connection Pool Usage
Use connection pool for direct database access:
```python
from utils.postgresql_pool import get_db_cursor

# Always use context manager for connections
with get_db_cursor() as cursor:
    cursor.execute("SELECT * FROM personnel WHERE discord_id = %s", (user_id,))
    result = cursor.fetchone()
```

### Audit Logging
Log all personnel changes with audit system:
```python
from utils.audit_logger import audit_logger, AuditAction

await audit_logger.send_personnel_audit(
    guild=guild,
    action=await AuditAction.HIRING(),
    target_user=user,
    moderator=moderator,
    personnel_data=data
)
```

### Configuration Management
Load config with validation and automatic backups:
```python
# Load config with validation
from utils.config_manager import load_config
config = load_config()

# Automatic backups created on every save
# Check config status: get_config_status()
```

### Async Initialization Sequence
Follow this order in `app.py`:
1. Load extensions (cogs)
2. Initialize PostgreSQL cache (`bulk_preload_all_users`)
3. Register persistent views with dummy data
4. Setup notification schedulers
5. Sync slash commands (`bot.tree.sync()`)

### Error Handling
Comprehensive try/catch with emoji prefixes:
```python
try:
    # operation
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
```

## Developer Workflows

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set token (PowerShell)
$env:DISCORD_TOKEN = "your_token"

# Run bot
python app.py
```

### Testing
```bash
# Database validation
python tests/test_database_comprehensive.py

# Message key validation
python tests/test_messages_all_keys.py

# Bot validation (imports, config, messages)
python validate_bot.py
```

### Production Deployment
```bash
# Use deployment scripts
./scripts/bot.sh start|stop|status
./scripts/deploy.sh
```

## Key Files & Patterns

### Architecture Understanding
- `app.py` (lines 30-150): Complex initialization sequence with view registration
- `utils/database/models.py`: SQLAlchemy data models with relationships
- `utils/config_manager.py`: Configuration patterns with backup system
- `cogs/personnel_commands.py`: Command structure examples

### UI Patterns
- `forms/role_assignment/views.py`: Persistent view patterns with timeout=None
- `forms/dismissal/`: Approval workflow examples
- `forms/settings/`: Settings UI patterns

### Database Integration
- `utils/database_manager/manager.py`: PersonnelManager usage patterns
- `utils/postgresql_pool.py`: Connection management with asyncpg
- `utils/user_cache.py`: Caching patterns with bulk preload
- `utils/audit_logger.py`: Audit logging for all personnel changes
- `forms/settings/positions/`: Hierarchical position management with pagination
  - `navigation.py`: Subdivision selection with pagination
  - `management.py`: Position management within subdivisions
  - `detailed_management.py`: Individual position configuration
  - `ui_components.py`: Reusable Discord UI components

### Message System Integration
- `utils/message_manager.py`: Core message retrieval functions
- `utils/message_service.py`: High-level message sending (DMs, embeds)
- `data/messages/messages-default.yml`: Authoritative message templates
- `tests/test_messages_all_keys.py`: Comprehensive message key validation

### Position Management System
**New Hierarchical System (2025)**:
- `forms/settings/positions/`: Complete hierarchical position management
- `utils/database_manager/position_service.py`: Service layer with proper employees table integration
- **Features**: Subdivision-based navigation, pagination for 300+ positions, Discord role assignment
- **Database**: Uses `position_subdivision` junction table instead of deprecated `user_data`
- **UI**: Persistent views with timeout=None, paginated selects, search functionality

**Migration Notes**:
- Old system: `forms/settings/position_roles.py` (deprecated)
- New system: `forms/settings/positions/` (current)
- Automatic integration in main settings menu

## Common Pitfalls

### View Registration
- **Always** register persistent views in `app.py` `on_ready()` with dummy data
- **Never** create views dynamically without registration
- Views must handle button clicks after bot restarts

### Message Keys
- **Always** verify keys exist in `messages-default.yml` before adding new `get_*_message()` calls
- **Run validation**: `python tests/test_messages_all_keys.py` after adding message references
- **Use wrappers**: Prefer `get_supplies_message()` over `get_message("systems.supplies.*")` for consistency
- **Template references**: Use `{templates.*}` for common patterns to avoid duplication

### Database Security
- **Daily Automated Backups**: pg_dump with cron scheduling to `/opt/PostgreSQL/backups/`
- **Connection Pooling**: Optimized performance with connection reuse
- **Transaction Safety**: Data integrity through proper transaction handling
- **Input Validation**: Comprehensive validation of all input data

### Configuration
- Config changes trigger automatic backups to `data/backups/`
- Use `create_backup()` before manual config edits
- Validate config with `get_config_status()`

### Database Features
- **Automatic Synchronization**: All changes via context menus sync to audit channel and database
- **Auto Nickname Updates**: Automatic nickname updates on status changes (promotions, transfers, hiring, dismissal)
- **Complete History Tracking**: Full operation history in `history` table with JSON changes
- **Advanced Analytics**: Career history, service time calculation, department/rank statistics
- **Auto Blacklist**: Automatic blacklist addition for personnel serving less than 5 days

## Code Style & Patterns

### Imports
```python
# Standard library first
import os
import asyncio

# Third-party
import discord
from discord.ext import commands

# Local imports
from utils.config_manager import load_config
```

### Error Messages
Use emoji prefixes for consistency:
- `❌` Errors
- `✅` Success
- `⚠️` Warnings
- `🔄` Progress/Loading
- `🔍` Debugging/Inspection

### Logging
```python
# Use audit_logger for personnel changes
from utils.audit_logger import audit_logger, AuditAction
await audit_logger.log_action(AuditAction.UPDATE_PERSONNEL, user_id, details)
```

## Testing & Validation

### Pre-commit Checks
```bash
# Validate database schema
python db_schema_check.py

# Run comprehensive tests
python tests/test_database_comprehensive.py

# Validate all message keys
python tests/test_messages_all_keys.py

# Validate bot configuration
python validate_bot.py
```

### Cache Management
```bash
# Clear cache: /cache_clear
# Bulk reload: /cache_bulk_init
# Check status: print_cache_status()
```

## Deployment Considerations

### Environment Variables
Required for production:
- `DISCORD_TOKEN`
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- Optional: `DATABASE_URL`

### Persistent Data
- Config automatically backed up on changes
- Database handles all personnel data
- Cache rebuilds from database on startup
- Daily automated PostgreSQL backups to `/opt/PostgreSQL/backups/`

### Monitoring
- Use `/performance_monitoring` for system stats
- Check logs for errors during startup sequence
- Monitor database connection pool status</content>
<parameter name="filePath">g:\GitHub\repos\army discord bot\.github\copilot-instructions.md