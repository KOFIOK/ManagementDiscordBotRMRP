import os
import asyncio
import signal
import sys
import discord
import logging
from discord.ext import commands
from dotenv import load_dotenv

from utils.config_manager import load_config, create_backup, get_config_status
# from utils.sheets_manager import sheets_manager  # Отключено - используем PostgreSQL
from utils.notification_scheduler import PromotionNotificationScheduler
from utils.logging_setup import setup_logging, get_logger
from forms.dismissal import DismissalReportButton, AutomaticDismissalApprovalView, SimplifiedDismissalApprovalView, send_dismissal_button_message, restore_dismissal_approval_views, restore_dismissal_button_views
from forms.settings import SettingsView
from forms.role_assignment_form import RoleAssignmentView, send_role_assignment_message, restore_role_assignment_views, restore_approval_views
from forms.leave_request_form import LeaveRequestButton, LeaveRequestApprovalView, restore_leave_request_views
from forms.medical_registration import MedicalRegistrationView
from forms.welcome_system import setup_welcome_events

# Load environment variables from .env file
load_dotenv()

# Initialize logging before bot creation
setup_logging()
logger = get_logger(__name__)

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Initialize the bot with a command prefix and intents
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize notification scheduler
notification_scheduler = PromotionNotificationScheduler(bot)

@bot.event
async def on_ready():
    logger.info('Logged in as %s (ID: %s)', bot.user, bot.user.id)
    logger.info('------')
    
    # Create startup backup and check config status
    logger.info("Проверка системы конфигурации...")
    status = get_config_status()
    
    if status['config_exists'] and status['config_valid']:
        backup_path = create_backup("startup")
        if backup_path:
            logger.info("Создан стартовый бэкап: %s", backup_path)
        logger.info("Статус конфигурации: доступно %s бэкапов", status['backup_count'])
    else:
        logger.warning("Обнаружены проблемы конфигурации - проверьте /config-backup")
    
    # Initialize optimized PostgreSQL system
    logger.info("Инициализация оптимизированной PostgreSQL системы...")
    from utils.user_cache import bulk_preload_all_users, print_cache_status
    from utils.postgresql_pool import print_connection_pool_status
    
    try:
        # Предзагрузка пользователей
        preload_result = await bulk_preload_all_users()
        logger.info("Кэш пользователей предзагружен: %s", preload_result.get('users_loaded', 0))
        
        # Показать статистику системы
        print_cache_status()
        print_connection_pool_status()
        
    except Exception as e:
        logger.warning("Предзагрузка кэша не удалась: %s", e)
    
    # Load all extension cogs
    await load_extensions()
    
    # Setup personnel context menu commands
    try:
        from forms.personnel_context.commands_clean import setup_context_commands
        setup_context_commands(bot)
        logger.info('Контекстные команды персонала загружены')
    except Exception as e:
        logger.error('Ошибка загрузки контекстных команд персонала: %s', e)
        import traceback
        traceback.print_exc()
    
    # Sync commands with Discord
    try:
        synced = await bot.tree.sync()
        logger.info('Синхронизировано %s команд(ы) - права обновлены', len(synced))
    except Exception as e:
        logger.error('Не удалось синхронизировать команды: %s', e)
    
    # Load configuration on startup
    try:
        config = load_config()
        logger.info('Конфигурация успешно загружена')
        
        # Rank roles are now initialized manually through the settings interface
        # from forms.settings.rank_roles import initialize_default_ranks
        # if initialize_default_ranks():
        #     print(' Default rank roles initialized')
        
        # Rank data migration is no longer needed (working directly with database)
        # from forms.personnel_context.rank_utils import migrate_old_rank_format
        # migrated = migrate_old_rank_format()
        # if migrated:
        #     print(' Migrated old rank data to hierarchical format')
        # else:
        #     print(' No old rank data to migrate or already migrated')
        
        logger.info('Канал увольнений: %s', config.get('dismissal_channel', 'Not set'))
        logger.info('Канал аудита: %s', config.get('audit_channel', 'Not set'))
        logger.info('Канал черного списка: %s', config.get('blacklist_channel', 'Not set'))
        logger.info('Канал выдачи ролей: %s', config.get('role_assignment_channel', 'Not set'))
        logger.info('Военная роль: %s', config.get('military_role', 'Not set'))
        logger.info('Гражданская роль: %s', config.get('civilian_role', 'Not set'))
    except Exception as e:
        logger.error('Ошибка загрузки конфигурации: %s', e)
        import traceback
        traceback.print_exc()
        return
    
    # ИНИЦИАЛИЗАЦИЯ КЭША ПОЛЬЗОВАТЕЛЕЙ - теперь использует PostgreSQL
    try:
        logger.info('Инициализация кэша пользователей через PostgreSQL...')
        from utils.user_cache import initialize_user_cache
        cache_success = await initialize_user_cache()
        if cache_success:
            logger.info('Кэш пользователей успешно инициализирован с предзагрузкой')
        else:
            logger.warning('Предзагрузка кэша пользователей не удалась - используем резервную загрузку')
    except Exception as e:
        logger.error('Ошибка инициализации кэша пользователей: %s', e)
        import traceback
        traceback.print_exc()
    
    # Create persistent button views
    try:
        logger.info("Добавление постоянных кнопочных представлений...")
        bot.add_view(DismissalReportButton())
        bot.add_view(SettingsView())
        bot.add_view(RoleAssignmentView())
        bot.add_view(LeaveRequestButton())
        bot.add_view(MedicalRegistrationView())
        logger.info("Базовые постоянные представления добавлены")
    except Exception as e:
        logger.error("Ошибка добавления базовых постоянных представлений: %s", e)
        import traceback
        traceback.print_exc()
    
    # Department applications views are created dynamically for specific applications
    # No need to register them globally like other persistent views
    
    # Add generic approval views for persistent buttons
    logger.info("Добавление approval views...")
    bot.add_view(SimplifiedDismissalApprovalView())  # Persistent view for manual dismissals
    bot.add_view(AutomaticDismissalApprovalView(None))  # Persistent view for automatic dismissals
    bot.add_view(LeaveRequestApprovalView("dummy"))  # Dummy ID for persistent view
    logger.info("Approval views добавлены")
      # Add role assignment approval view for persistent buttons
    logger.info("Добавление approval view для выдачи ролей...")
    from forms.role_assignment_form import RoleApplicationApprovalView
    bot.add_view(RoleApplicationApprovalView({}))  # Empty data for persistent view
    logger.info("Approval view для выдачи ролей добавлен")
    
    logger.info("Добавление постоянных представлений склада...")
    try:
        from forms.warehouse import (
            WarehousePinMessageView, WarehousePersistentRequestView, WarehousePersistentMultiRequestView,
            WarehouseStatusView
        )
        logger.info("Warehouse request views импортированы")
    except Exception as e:
        logger.exception("Ошибка импорта warehouse request views: %s", e)
    
    try:
        from forms.warehouse.audit import WarehouseAuditPinMessageView
        logger.info("Warehouse audit view импортирован")
    except Exception as e:
        logger.exception("Ошибка импорта warehouse audit view: %s", e)
    
    try:
        # Add persistent warehouse views - БЕЗ DUMMY ДАННЫХ
        bot.add_view(WarehousePinMessageView())  # Persistent pin message view - БЕЗ ПАРАМЕТРОВ
        logger.info("WarehousePinMessageView добавлен")
        
        bot.add_view(WarehousePersistentRequestView())  # Persistent single request moderation
        logger.info("WarehousePersistentRequestView добавлен")
        bot.add_view(WarehousePersistentMultiRequestView())  # Persistent multi request moderation
        logger.info("WarehousePersistentMultiRequestView добавлен")
        
        # Skip WarehouseStatusView as it requires parameters - it's created dynamically
        # bot.add_view(WarehouseStatusView())  # This requires 'status' parameter
        logger.info("WarehouseStatusView пропущен (требуются параметры)")
        
        bot.add_view(WarehouseAuditPinMessageView())  # Persistent audit pin message view
        logger.info("WarehouseAuditPinMessageView добавлен")
        
        logger.info('Все постоянные представления добавлены в бота')
    except Exception as e:
        logger.exception("Ошибка добавления warehouse views в бота: %s", e)

    # Add safe documents persistent views
    logger.info("Добавление постоянных представлений безопасных документов...")
    try:
        from forms.safe_documents import SafeDocumentsPinView, SafeDocumentsApplicationView, SafeDocumentsApprovedView, SafeDocumentsRejectedView, setup_safe_documents_system
        logger.info("Safe documents views импортированы")
        
        # Add persistent views
        bot.add_view(SafeDocumentsPinView())  # Persistent pin message view
        logger.info("SafeDocumentsPinView добавлен")
        
        # Add SafeDocumentsApplicationView with dummy data for persistent view functionality
        dummy_application_data = {
            'user_id': 0,
            'username': 'dummy',
            'timestamp': '2024-01-01T00:00:00',
            'status': 'pending',
            'name': 'dummy',
            'static': 'dummy',
            'documents': 'dummy',
            'phone': 'dummy',
            'email': 'dummy'
        }
        bot.add_view(SafeDocumentsApplicationView(dummy_application_data))
        logger.info("SafeDocumentsApplicationView добавлен с dummy-данными")
        
        # Add specialized views for different statuses
        bot.add_view(SafeDocumentsApprovedView(dummy_application_data))
        logger.info("SafeDocumentsApprovedView добавлен")
        
        bot.add_view(SafeDocumentsRejectedView(dummy_application_data))
        logger.info("SafeDocumentsRejectedView добавлен")
        
        logger.info('Постоянные представления безопасных документов добавлены в бота')
    except Exception as e:
        logger.exception("Ошибка добавления safe documents views: %s", e)

    # Add supplies persistent views
    logger.info("Добавление постоянных представлений снабжения...")
    try:
        from forms.supplies import SuppliesControlView, SuppliesSubscriptionView
        
        # Add persistent views
        bot.add_view(SuppliesControlView())  # Persistent control view
        logger.info("SuppliesControlView добавлен")
        
        bot.add_view(SuppliesSubscriptionView())  # Persistent subscription view
        logger.info("SuppliesSubscriptionView добавлен")
        
        logger.info('Постоянные представления снабжения добавлены в бота')
    except Exception as e:
        logger.exception("Ошибка добавления supplies views: %s", e)

    # Add safe documents persistent views
    # Setup safe documents system
    logger.info("Настройка системы безопасных документов...")
    try:
        await setup_safe_documents_system(bot)
    except Exception as e:
        logger.exception("Ошибка настройки системы безопасных документов: %s", e)

    # Setup welcome system events
    logger.info("Настройка системы приветствий...")
    setup_welcome_events(bot)
    logger.info("События системы приветствий настроены")
    
    # Department applications views - register base views globally
    logger.info("Добавление постоянных представлений заявок в подразделения...")
    try:
        logger.info(f"Импортируем модули...")
        from forms.department_applications import register_static_views
        logger.info(f"Представления импортированы")
        
        logger.info(f"Регистрируем статические представления...")
        if register_static_views(bot):
            logger.info(f"Статические представления зарегистрированы")
        else:
            logger.warning("  Не удалось зарегистрировать статические представления")
        
        logger.info("Настройка заявок в подразделения завершена")
    except Exception as e:
        logger.error("Ошибка в настройке заявок в подразделения: %s", e)
        import traceback
        traceback.print_exc()
    
    # Start notification scheduler
    try:
        logger.info("Запуск планировщика уведомлений...")
        notification_scheduler.start()
        logger.info("Планировщик уведомлений запущен")
    except Exception as e:
        logger.error("Ошибка запуска планировщика уведомлений: %s", e)
        import traceback
        traceback.print_exc()
    
    # Start supplies scheduler
    try:
        logger.info("Запуск планировщика снабжения...")
        from utils.supplies_scheduler import initialize_supplies_scheduler
        supplies_scheduler = initialize_supplies_scheduler(bot)
        if supplies_scheduler:
            supplies_scheduler.start()
            logger.info("Планировщик снабжения запущен")
        else:
            logger.error("Не удалось инициализировать планировщик снабжения")
    except Exception as e:
        logger.error("Ошибка запуска планировщика снабжения: %s", e)
        import traceback
        traceback.print_exc()
    
    # Start leave requests daily cleanup
    try:
        logger.info("Запуск ежедневной очистки заявок на отгулы...")
        from utils.leave_request_storage import LeaveRequestStorage
        asyncio.create_task(LeaveRequestStorage.start_daily_cleanup_task())
        logger.info("Задача ежедневной очистки заявок запущена")
    except Exception as e:
        logger.error("Ошибка запуска очистки заявок: %s", e)
        import traceback
        traceback.print_exc()
    
    # 🚀 ЗАПУСК СИСТЕМЫ ПРЕДЗАГРУЗКИ КЭША
    try:
        logger.info("Запуск предзагрузчика кэша пользователей...")
        from utils.user_cache import bulk_preload_all_users
        await bulk_preload_all_users()
        logger.info("Предзагрузчик кэша пользователей запущен")
    except Exception as e:
        logger.error("Ошибка запуска предзагрузчика кэша пользователей: %s", e)
        import traceback
        traceback.print_exc()
    
    # Check channels and restore messages if needed
    try:
        logger.info("Восстановление сообщений по каналам...")
        await restore_channel_messages(config)
        logger.info("Восстановление сообщений завершено")
    except Exception as e:
        logger.error("Ошибка при восстановлении сообщений каналов: %s", e)
        import traceback
        traceback.print_exc()
    
    # Restore supplies messages
    try:
        logger.info("Восстановление сообщений системы снабжения...")
        from utils.supplies_restore import initialize_supplies_restore_manager
        supplies_restore = initialize_supplies_restore_manager(bot)
        if supplies_restore:
            await supplies_restore.restore_all_messages()
            logger.info("Восстановление сообщений снабжения завершено")
        else:
            logger.error("Не удалось инициализировать менеджер восстановления снабжения")
    except Exception as e:
        logger.error("Ошибка при восстановлении сообщений снабжения: %s", e)
        import traceback
        traceback.print_exc()

@bot.event
async def on_member_remove(member):
    """Handle member leaving the server and create automatic dismissal if needed."""
    try:
        logger.info("Участник вышел: %s (ID: %s)", member.name, member.id)
        
        # Import here to avoid circular imports
        from forms.dismissal.automatic import should_create_automatic_dismissal, create_automatic_dismissal_report
        
        # Get target role name from config
        config = load_config()
        target_role_name = config.get('military_role_name', 'Сотрудник')
        
        # Check if member should get automatic dismissal
        should_dismiss = await should_create_automatic_dismissal(member, target_role_name)
        
        if should_dismiss:
            logger.warning("Создание автоматического увольнения для %s (роль: %s)", member.name, target_role_name)
            
            # Create automatic dismissal report using member object (has role info)
            success = await create_automatic_dismissal_report(member.guild, member, target_role_name)
            
            if success:
                logger.info("Авто-рапорт об увольнении создан для %s", member.name)
            else:
                logger.error("Не удалось создать авто-рапорт об увольнении для %s", member.name)
        else:
            logger.info("Авто-увольнение не требуется для %s - нет целевой роли", member.name)
            
    except Exception as e:
        logger.error("Ошибка обработки выхода участника %s: %s", member.name, e)

@bot.event
async def on_member_update(before, after):
    """Handle member updates including role changes."""
    try:
        # Проверяем изменения ролей
        if before.roles != after.roles:
            # Получаем добавленные роли
            added_roles = set(after.roles) - set(before.roles)
            
            if added_roles:
                from utils.config_manager import load_config
                config = load_config()
                
                moderator_role_ids = config.get('moderators', {}).get('roles', [])
                administrator_role_ids = config.get('administrators', {}).get('roles', [])
                  # Проверяем, была ли добавлена модераторская/администраторская роль
                from utils.moderator_notifications import (
                    check_if_user_is_moderator, check_if_user_is_administrator,
                    send_moderator_welcome_dm, send_administrator_welcome_dm
                )
                
                # Проверяем статус ДО изменения ролей
                was_moderator = check_if_user_is_moderator(before, config)
                was_administrator = check_if_user_is_administrator(before, config)
                
                became_moderator = False
                became_administrator = False
                
                for role in added_roles:
                    if role.id in administrator_role_ids and not was_administrator:
                        became_administrator = True
                        break
                    elif role.id in moderator_role_ids and not was_moderator and not was_administrator:
                        became_moderator = True
                  # Отправляем уведомления
                if became_administrator:
                    dm_sent = await send_administrator_welcome_dm(after)
                    logger.info("Авто-уведомление администратору %s отправлено: DM %s", after.display_name, 'OK' if dm_sent else 'FAIL')
                    
                elif became_moderator:
                    dm_sent = await send_moderator_welcome_dm(after)
                    logger.info("Авто-уведомление модератору %s отправлено: DM %s", after.display_name, 'OK' if dm_sent else 'FAIL')
            
    except Exception as e:
        logger.error("Ошибка обработки обновления участника %s: %s", after.name, e)

async def restore_channel_messages(config):
    """Check and restore button messages for all configured channels."""    # Restore dismissal channel message
    dismissal_channel_id = config.get('dismissal_channel')
    if dismissal_channel_id:
        channel = bot.get_channel(dismissal_channel_id)
        if channel:
            if not await check_for_button_message(channel, "Рапорты на увольнение"):
                logger.info("Отправляем кнопочное сообщение увольнений в канал %s", channel.name)
                await send_dismissal_button_message(channel)
            
            # Restore dismissal button views for existing dismissal button messages
            logger.info("Восстанавливаем dismissal button views в %s", channel.name)
            await restore_dismissal_button_views(bot, channel)
            
            # Restore approval views for existing dismissal reports
            logger.info("Восстанавливаем approval views для увольнений в %s", channel.name)
            await restore_dismissal_approval_views(bot, channel)
    
    # Restore role assignment channel message
    role_assignment_channel_id = config.get('role_assignment_channel')
    if role_assignment_channel_id:
        channel = bot.get_channel(role_assignment_channel_id)
        if channel:
            if not await check_for_button_message(channel, "Получение ролей"):
                logger.info("Отправляем сообщение выдачи ролей в канал %s", channel.name)
                await send_role_assignment_message(channel)
              # Restore role assignment views
                logger.info("Восстанавливаем role assignment views в %s", channel.name)
            await restore_role_assignment_views(bot, channel)
              # Restore approval views for existing applications
            logger.info("Восстанавливаем approval views для заявок на роли в %s", channel.name)
            await restore_approval_views(bot, channel)
    
    # Restore audit channel message
    audit_channel_id = config.get('audit_channel')
    if audit_channel_id:
        channel = bot.get_channel(audit_channel_id)
      # Restore blacklist channel message
    blacklist_channel_id = config.get('blacklist_channel')
    if blacklist_channel_id:
        channel = bot.get_channel(blacklist_channel_id)
      # Restore leave requests channel message
    leave_requests_channel_id = config.get('leave_requests_channel')
    if leave_requests_channel_id:
        from forms.leave_request_form import send_leave_request_button_message
        channel = bot.get_channel(leave_requests_channel_id)
        if channel:
            if not await check_for_button_message(channel, "Система подачи заявок на отгулы"):
                logger.info("Отправляем сообщение заявок на отгулы в канал %s", channel.name)
                await send_leave_request_button_message(channel)
      # Restore medical registration channel message
    medical_registration_channel_id = config.get('medical_registration_channel')
    if medical_registration_channel_id:
        from forms.medical_registration import send_medical_registration_message
        channel = bot.get_channel(medical_registration_channel_id)
        if channel:
            logger.info("Отправляем сообщение медрегистрации в канал %s", channel.name)
            await send_medical_registration_message(channel)      # Restore warehouse channels - ИСПРАВЛЕННАЯ ВЕРСИЯ
    warehouse_request_channel_id = config.get('warehouse_request_channel')
    if warehouse_request_channel_id:
        from utils.warehouse_utils import send_warehouse_message, restore_warehouse_request_views, restore_warehouse_pinned_message
        channel = bot.get_channel(warehouse_request_channel_id)
        if channel:
            # Сначала пытаемся восстановить существующее закрепленное сообщение
            pinned_restored = await restore_warehouse_pinned_message(channel)
            
            # Если не удалось восстановить, проверяем нужно ли создать новое
            if not pinned_restored and not await check_for_button_message(channel, "Запрос складского имущества"):
                logger.info("Отправляем сообщение склада в канал %s", channel.name)
                try:
                    await send_warehouse_message(channel)
                except Exception as e:
                    logger.error("Ошибка при создании сообщения склада: %s", e)
            
            # Восстанавливаем views для существующих заявок
            logger.info("Восстанавливаем warehouse request views в %s", channel.name)
            await restore_warehouse_request_views(channel)
        else:
            logger.warning("Канал склада не найден (ID: %s)", warehouse_request_channel_id)    # Restore warehouse audit channel
    warehouse_audit_channel_id = config.get('warehouse_audit_channel')
    if warehouse_audit_channel_id:
        from forms.warehouse.audit import send_warehouse_audit_message, restore_warehouse_audit_views, restore_warehouse_audit_pinned_message
        channel = bot.get_channel(warehouse_audit_channel_id)
        if channel:
            # Сначала пытаемся восстановить существующее закрепленное сообщение
            pinned_restored = await restore_warehouse_audit_pinned_message(channel)
            
            # Если не удалось восстановить, проверяем нужно ли создать новое
            if not pinned_restored and not await check_for_button_message(channel, "Аудит склада"):
                logger.info("Отправляем сообщение аудита склада в канал %s", channel.name)
                try:
                    await send_warehouse_audit_message(channel)
                except Exception as e:
                    logger.error("Ошибка при создании сообщения аудита склада: %s", e)
            
            # Восстанавливаем views для аудита
            await restore_warehouse_audit_views(channel)
        else:
            logger.warning("Канал аудита склада не найден (ID: %s)", warehouse_audit_channel_id)
    
    # Restore leave request views
    logger.info("Восстанавливаем leave request views...")
    await restore_leave_request_views(bot)
    
    # Restore department applications messages (direct call for reliability)
    logger.info("Восстанавливаем сообщения заявок в подразделения...")
    try:
        from forms.department_applications.manager import DepartmentApplicationManager
        dept_manager = DepartmentApplicationManager(bot)
        await dept_manager.restore_persistent_views()
    except Exception as e:
        logger.error("Ошибка восстановления заявок в подразделения: %s", e)
        import traceback
        traceback.print_exc()

async def check_for_button_message(channel, title_keyword):
    """Check if a channel already has a button message with the specified title."""
    try:
        async for message in channel.history(limit=10):
            if message.author == bot.user and message.embeds:
                for embed in message.embeds:
                    if embed.title and title_keyword in embed.title:
                        return True
        return False
    except Exception as e:
        logger.error("Ошибка проверки кнопочного сообщения в %s: %s", channel.name, e)
        return False

async def load_extensions():
    """Load all extension cogs from the cogs directory."""
    # Список исключений - cogs которые не нужно загружать
    excluded_cogs = {'warehouse_commands', 'cache_admin', 'department_applications_views'}  # personnel_commands теперь включен
    
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('_'):
            cog_name = filename[:-3]
            if cog_name in excluded_cogs:
                logger.info('Пропущено расширение (исключено): %s', cog_name)
                continue
                
            try:
                await bot.load_extension(f'cogs.{cog_name}')
                logger.info('Загружено расширение: %s', cog_name)
            except Exception as e:
                logger.error('Не удалось загрузить расширение %s: %s', cog_name, e)

@bot.tree.command(name="automatic_report", description="🚨 Создать тестовый автоматический рапорт на увольнение")
async def automatic_report(interaction: discord.Interaction, пользователь: discord.Member):
    """
    Simulate automatic dismissal report for testing purposes.
    
    Args:
        пользователь: User to create automatic dismissal report for
    """
    from utils.config_manager import is_administrator, load_config
    config = load_config()
    
    # Check if user has moderator/admin permissions
    if not is_administrator(interaction.user, config):
        await interaction.response.send_message(
            "❌ У вас нет прав для выполнения этой команды. Требуются права модератора.", 
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Import automatic dismissal creation function
        from forms.dismissal.automatic import create_automatic_dismissal_report
        
        # Create automatic dismissal report using the target member
        success = await create_automatic_dismissal_report(
            guild=interaction.guild,
            member=пользователь,
            target_role_name=config.get('military_role_name', 'Сотрудник')
        )
        
        if success:
            await interaction.followup.send(
                f"✅ Тестовый автоматический рапорт создан для {пользователь.mention}!\n"
                f"📋 Проверьте канал рапортов на увольнение.",
                ephemeral=True
            )
            logger.info("Тестовый авто-рапорт создан %s для %s", interaction.user.display_name, пользователь.display_name)
        else:
            await interaction.followup.send(
                f"❌ Не удалось создать автоматический рапорт для {пользователь.mention}.\n"
                f"⚠️ Проверьте настройку канала и логи бота.",
                ephemeral=True
            )
            logger.error("Не удалось создать тестовый авто-рапорт для %s", пользователь.display_name)
            
    except Exception as e:
        await interaction.followup.send(
            f"❌ Ошибка при создании автоматического рапорта:\n```{str(e)}```",
            ephemeral=True
        )
        logger.error("Ошибка команды automatic_report: %s", e)
        import traceback
        traceback.print_exc()

@bot.tree.command(name="force-sync", description="🔄 Принудительная синхронизация команд (только для администраторов)")
async def force_sync(interaction: discord.Interaction):
    """Force sync commands for debugging permission issues"""
    from utils.config_manager import is_administrator, load_config
    config = load_config()
    
    # Check if user has administrator permissions
    if not (interaction.user.guild_permissions.administrator or is_administrator(interaction.user, config)):
        await interaction.response.send_message(
            "❌ У вас нет прав для выполнения этой команды. Требуются права администратора.", 
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Clear and re-sync commands
        bot.tree.clear_commands(guild=None)
        
        # Re-add personnel context menu commands
        from forms.personnel_context.commands_clean import setup_context_commands
        setup_context_commands(bot)
        
        synced = await bot.tree.sync()
        
        await interaction.followup.send(
            f"✅ Принудительная синхронизация завершена!\n"
            f"🔄 Синхронизировано команд: {len(synced)}\n"
            f"⚡ Контекстные команды должны быть видны всем пользователям",
            ephemeral=True
        )
        logger.info("Force sync выполнен %s: %s команд", interaction.user.display_name, len(synced))
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Ошибка при синхронизации команд:\n```{str(e)}```",
            ephemeral=True
        )
        logger.error("Force sync завершился ошибкой: %s", e)

async def shutdown_handler():
    """Gracefully shutdown the bot."""
    logger.warning("Получен сигнал завершения...")
    logger.info("Завершение работы бота...")
    
    try:
        # Закрываем соединение с Discord
        await bot.close()
        logger.info("Соединение с Discord закрыто")
    except Exception as e:
        logger.error("Ошибка при закрытии соединения: %s", e)
    
    logger.info("Бот успешно завершил работу")

def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.warning("Получен сигнал %s", sig)
    
    # Создаем новый event loop если его нет
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Запускаем graceful shutdown
    if not loop.is_closed():
        task = loop.create_task(shutdown_handler())
        loop.run_until_complete(task)
        loop.close()
    
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Run the bot
if __name__ == '__main__':
    logger.info("Запуск Army Discord Bot...")
    logger.info("Для остановки нажмите Ctrl+C")
    
    # Check for token - first from environment, then try to read from .env file
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        # If we get here, it means dotenv didn't find the token in .env file
        # or the .env file doesn't exist
        logger.warning("DISCORD_TOKEN не найден в переменных окружения или .env.")
        logger.info("Пробуем token.txt как запасной вариант...")
        
        # Try to read from token.txt if exists
        try:
            with open('token.txt', 'r') as f:
                token = f.read().strip()
                logger.info("Токен найден в token.txt")
        except FileNotFoundError:
            raise ValueError(
                "No Discord token found. Please either:\n"
                "1. Set the DISCORD_TOKEN environment variable\n"
                "2. Create a .env file with DISCORD_TOKEN=your_token\n"
                "3. Create a token.txt file containing just your token"
            )
    
    try:
        asyncio.run(bot.start(token))
    except KeyboardInterrupt:
        # Этот блок теперь просто для красоты, основная обработка в signal_handler
        pass
    except Exception as e:
        logger.error("Произошла ошибка при запуске бота: %s", e)
        input("Нажмите Enter для выхода...")