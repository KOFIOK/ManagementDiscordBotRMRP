import os
import asyncio
import signal
import sys
import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.config_manager import load_config, create_backup, get_config_status
# from utils.sheets_manager import sheets_manager  # Отключено - используем PostgreSQL
from utils.notification_scheduler import PromotionNotificationScheduler
from forms.dismissal import DismissalReportButton, AutomaticDismissalApprovalView, SimplifiedDismissalApprovalView, send_dismissal_button_message, restore_dismissal_approval_views, restore_dismissal_button_views
from forms.settings import SettingsView
from forms.role_assignment_form import RoleAssignmentView, send_role_assignment_message, restore_role_assignment_views, restore_approval_views
from forms.leave_request_form import LeaveRequestButton, LeaveRequestApprovalView, restore_leave_request_views
from forms.medical_registration import MedicalRegistrationView
from forms.welcome_system import setup_welcome_events

# Load environment variables from .env file
load_dotenv()

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
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    
    # Create startup backup and check config status
    print("🔄 Checking configuration system...")
    status = get_config_status()
    
    if status['config_exists'] and status['config_valid']:
        backup_path = create_backup("startup")
        if backup_path:
            print(f"✅ Startup backup created: {backup_path}")
        print(f"📊 Config status: {status['backup_count']} backups available")
    else:
        print("⚠️  Configuration issues detected - check /config-backup status")
    
    # Initialize optimized PostgreSQL system
    print("\n🚀 Initializing optimized PostgreSQL system...")
    from utils.user_cache import bulk_preload_all_users, print_cache_status
    from utils.postgresql_pool import print_connection_pool_status
    
    try:
        # Предзагрузка пользователей
        preload_result = await bulk_preload_all_users()
        print(f"✅ User cache preloaded: {preload_result.get('users_loaded', 0)} users")
        
        # Показать статистику системы
        print_cache_status()
        print_connection_pool_status()
        
    except Exception as e:
        print(f"⚠️ Warning: Cache preload failed: {e}")
    
    # Load all extension cogs
    await load_extensions()
    
    # Setup personnel context menu commands
    try:
        from forms.personnel_context.commands_clean import setup_context_commands
        setup_context_commands(bot)
        print('✅ Personnel context menu commands loaded')
    except Exception as e:
        print(f'❌ Error loading personnel context commands: {e}')
        import traceback
        traceback.print_exc()
    
    # Sync commands with Discord
    try:
        synced = await bot.tree.sync()
        print(f'🔄 Synced {len(synced)} command(s) - updated permissions')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
    
    # Load configuration on startup
    try:
        config = load_config()
        print('✅ Configuration loaded successfully')
        
        # Initialize default rank roles if not present
        from forms.settings.rank_roles import initialize_default_ranks
        if initialize_default_ranks():
            print('✅ Default rank roles initialized')
        
        # Migrate old rank data to hierarchical format
        from forms.personnel_context.rank_utils import migrate_old_rank_format
        migrated = migrate_old_rank_format()
        if migrated:
            print('✅ Migrated old rank data to hierarchical format')
        else:
            print('ℹ️ No old rank data to migrate or already migrated')
        
        print(f'Dismissal channel: {config.get("dismissal_channel", "Not set")}')
        print(f'Audit channel: {config.get("audit_channel", "Not set")}')
        print(f'Blacklist channel: {config.get("blacklist_channel", "Not set")}')
        print(f'Role assignment channel: {config.get("role_assignment_channel", "Not set")}')
        print(f'Military role: {config.get("military_role", "Not set")}')
        print(f'Civilian role: {config.get("civilian_role", "Not set")}')
    except Exception as e:
        print(f'❌ Error loading configuration: {e}')
        import traceback
        traceback.print_exc()
        return
    
    # ИНИЦИАЛИЗАЦИЯ КЭША ПОЛЬЗОВАТЕЛЕЙ - теперь использует PostgreSQL
    try:
        print('🚀 Initializing user cache with PostgreSQL...')
        from utils.user_cache import initialize_user_cache
        cache_success = await initialize_user_cache()
        if cache_success:
            print('✅ User cache initialized successfully with bulk preload')
        else:
            print('⚠️ User cache bulk preload failed - will use fallback loading')
    except Exception as e:
        print(f'❌ Error initializing user cache: {e}')
        import traceback
        traceback.print_exc()
    
    # Create persistent button views
    try:
        print("🔄 Adding persistent button views...")
        bot.add_view(DismissalReportButton())
        bot.add_view(SettingsView())
        bot.add_view(RoleAssignmentView())
        bot.add_view(LeaveRequestButton())
        bot.add_view(MedicalRegistrationView())
        print("✅ Basic persistent views added")
    except Exception as e:
        print(f"❌ Error adding basic persistent views: {e}")
        import traceback
        traceback.print_exc()
    
    # Department applications views are created dynamically for specific applications
    # No need to register them globally like other persistent views
    
    # Add generic approval views for persistent buttons
    print("🔄 Adding approval views...")
    bot.add_view(SimplifiedDismissalApprovalView())  # Persistent view for manual dismissals
    bot.add_view(AutomaticDismissalApprovalView(None))  # Persistent view for automatic dismissals
    bot.add_view(LeaveRequestApprovalView("dummy"))  # Dummy ID for persistent view
    print("✅ Approval views added")
      # Add role assignment approval view for persistent buttons
    print("🔄 Adding role assignment approval view...")
    from forms.role_assignment_form import RoleApplicationApprovalView
    bot.add_view(RoleApplicationApprovalView({}))  # Empty data for persistent view
    print("✅ Role assignment approval view added")
    
    print("🔄 Adding warehouse persistent views...")
    try:
        from forms.warehouse import (
            WarehousePinMessageView, WarehousePersistentRequestView, WarehousePersistentMultiRequestView,
            WarehouseStatusView
        )
        print("✅ Warehouse request views imported successfully")
    except Exception as e:
        print(f"❌ Error importing warehouse request views: {e}")
        import traceback
        print(f"🔍 Import traceback: {traceback.format_exc()}")
    
    try:
        from forms.warehouse.audit import WarehouseAuditPinMessageView
        print("✅ Warehouse audit view imported successfully")
    except Exception as e:
        print(f"❌ Error importing warehouse audit view: {e}")
        import traceback
        print(f"🔍 Import traceback: {traceback.format_exc()}")
    
    try:
        # Add persistent warehouse views - БЕЗ DUMMY ДАННЫХ
        bot.add_view(WarehousePinMessageView())  # Persistent pin message view - БЕЗ ПАРАМЕТРОВ
        print("✅ WarehousePinMessageView added")
        
        bot.add_view(WarehousePersistentRequestView())  # Persistent single request moderation
        print("✅ WarehousePersistentRequestView added")
        bot.add_view(WarehousePersistentMultiRequestView())  # Persistent multi request moderation
        print("✅ WarehousePersistentMultiRequestView added")
        
        # Skip WarehouseStatusView as it requires parameters - it's created dynamically
        # bot.add_view(WarehouseStatusView())  # This requires 'status' parameter
        print("ℹ️ WarehouseStatusView skipped (requires parameters)")
        
        bot.add_view(WarehouseAuditPinMessageView())  # Persistent audit pin message view
        print("✅ WarehouseAuditPinMessageView added")
        
        print('✅ All persistent views added to bot')
    except Exception as e:
        print(f"❌ Error adding warehouse views to bot: {e}")
        import traceback
        print(f"🔍 Add view traceback: {traceback.format_exc()}")

    # Add safe documents persistent views
    print("🔄 Adding safe documents persistent views...")
    try:
        from forms.safe_documents import SafeDocumentsPinView, SafeDocumentsApplicationView, SafeDocumentsApprovedView, SafeDocumentsRejectedView, setup_safe_documents_system
        print("✅ Safe documents views imported successfully")
        
        # Add persistent views
        bot.add_view(SafeDocumentsPinView())  # Persistent pin message view
        print("✅ SafeDocumentsPinView added")
        
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
        print("✅ SafeDocumentsApplicationView added with dummy data")
        
        # Add specialized views for different statuses
        bot.add_view(SafeDocumentsApprovedView(dummy_application_data))
        print("✅ SafeDocumentsApprovedView added")
        
        bot.add_view(SafeDocumentsRejectedView(dummy_application_data))
        print("✅ SafeDocumentsRejectedView added")
        
        print('✅ Safe documents persistent views added to bot')
    except Exception as e:
        print(f"❌ Error adding safe documents views to bot: {e}")
        import traceback
        print(f"🔍 Safe documents traceback: {traceback.format_exc()}")

    # Add supplies persistent views
    print("🔄 Adding supplies persistent views...")
    try:
        from forms.supplies import SuppliesControlView, SuppliesSubscriptionView
        
        # Add persistent views
        bot.add_view(SuppliesControlView())  # Persistent control view
        print("✅ SuppliesControlView added")
        
        bot.add_view(SuppliesSubscriptionView())  # Persistent subscription view
        print("✅ SuppliesSubscriptionView added")
        
        print('✅ Supplies persistent views added to bot')
    except Exception as e:
        print(f"❌ Error adding supplies views to bot: {e}")
        import traceback
        print(f"🔍 Supplies traceback: {traceback.format_exc()}")

    # Add safe documents persistent views
    print("🔄 Adding safe documents persistent views...")
    try:
        from forms.safe_documents import SafeDocumentsPinView, SafeDocumentsApplicationView, SafeDocumentsApprovedView, SafeDocumentsRejectedView, setup_safe_documents_system
        print("✅ Safe documents views imported successfully")
        
        # Add persistent views
        bot.add_view(SafeDocumentsPinView())  # Persistent pin message view
        print("✅ SafeDocumentsPinView added")
        
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
        print("✅ SafeDocumentsApplicationView added with dummy data")
        
        # Add specialized views for different statuses
        bot.add_view(SafeDocumentsApprovedView(dummy_application_data))
        print("✅ SafeDocumentsApprovedView added")
        
        bot.add_view(SafeDocumentsRejectedView(dummy_application_data))
        print("✅ SafeDocumentsRejectedView added")
        
        print('✅ Safe documents persistent views added to bot')
    except Exception as e:
        print(f"❌ Error adding safe documents views to bot: {e}")
        import traceback
        print(f"🔍 Safe documents traceback: {traceback.format_exc()}")

    # Setup safe documents system
    print("🔄 Setting up safe documents system...")
    try:
        await setup_safe_documents_system(bot)
    except Exception as e:
        print(f"❌ Error setting up safe documents system: {e}")
        import traceback
        print(f"🔍 Safe documents setup traceback: {traceback.format_exc()}")
      # Setup welcome system events
    print("🔄 Setting up welcome system...")
    setup_welcome_events(bot)
    print("✅ Welcome system events setup complete")
    
    # Department applications views - register base views globally
    print("🔄 Adding department applications persistent views...")
    try:
        print("   📦 Importing modules...")
        from forms.department_applications import register_static_views
        print("   ✅ Views imported successfully")
        
        print("   � Registering static views...")
        if register_static_views(bot):
            print("   ✅ Static views registered successfully")
        else:
            print("   ❌ Failed to register static views")
        
        print("✅ Department applications setup complete")
    except Exception as e:
        print(f"❌ Error in department applications setup: {e}")
        import traceback
        traceback.print_exc()
    
    # Start notification scheduler
    try:
        print("🔄 Starting notification scheduler...")
        notification_scheduler.start()
        print("✅ Notification scheduler started")
    except Exception as e:
        print(f"❌ Error starting notification scheduler: {e}")
        import traceback
        traceback.print_exc()
    
    # Start supplies scheduler
    try:
        print("🔄 Starting supplies scheduler...")
        from utils.supplies_scheduler import initialize_supplies_scheduler
        supplies_scheduler = initialize_supplies_scheduler(bot)
        if supplies_scheduler:
            supplies_scheduler.start()
            print("✅ Supplies scheduler started")
        else:
            print("❌ Failed to initialize supplies scheduler")
    except Exception as e:
        print(f"❌ Error starting supplies scheduler: {e}")
        import traceback
        traceback.print_exc()
    
    # Start leave requests daily cleanup
    try:
        print("🔄 Starting leave requests cleanup...")
        from utils.leave_request_storage import LeaveRequestStorage
        asyncio.create_task(LeaveRequestStorage.start_daily_cleanup_task())
        print("🧹 Leave requests daily cleanup task started")
    except Exception as e:
        print(f"❌ Error starting leave requests cleanup: {e}")
        import traceback
        traceback.print_exc()
    
    # 🚀 ЗАПУСК СИСТЕМЫ ПРЕДЗАГРУЗКИ КЭША
    try:
        print("🔄 Starting user cache preloader...")
        from utils.user_cache import bulk_preload_all_users
        await bulk_preload_all_users()
        print("🚀 User cache preloader started")
    except Exception as e:
        print(f"❌ Error starting user cache preloader: {e}")
        import traceback
        traceback.print_exc()
    
    # Check channels and restore messages if needed
    try:
        print("🔄 Starting channel messages restoration...")
        await restore_channel_messages(config)
        print("✅ Channel messages restoration complete")
    except Exception as e:
        print(f"❌ Error during channel messages restoration: {e}")
        import traceback
        traceback.print_exc()
    
    # Restore supplies messages
    try:
        print("🔄 Starting supplies messages restoration...")
        from utils.supplies_restore import initialize_supplies_restore_manager
        supplies_restore = initialize_supplies_restore_manager(bot)
        if supplies_restore:
            await supplies_restore.restore_all_messages()
            print("✅ Supplies messages restoration complete")
        else:
            print("❌ Failed to initialize supplies restore manager")
    except Exception as e:
        print(f"❌ Error during supplies messages restoration: {e}")
        import traceback
        traceback.print_exc()

@bot.event
async def on_member_remove(member):
    """Handle member leaving the server and create automatic dismissal if needed."""
    try:
        print(f"👋 Member left: {member.name} (ID: {member.id})")
        
        # Import here to avoid circular imports
        from forms.dismissal.automatic import should_create_automatic_dismissal, create_automatic_dismissal_report
        
        # Get target role name from config
        config = load_config()
        target_role_name = config.get('military_role_name', 'Военнослужащий ВС РФ')
        
        # Check if member should get automatic dismissal
        should_dismiss = await should_create_automatic_dismissal(member, target_role_name)
        
        if should_dismiss:
            print(f"🚨 Creating automatic dismissal for {member.name} - had role '{target_role_name}'")
            
            # Create automatic dismissal report using member object (has role info)
            success = await create_automatic_dismissal_report(member.guild, member, target_role_name)
            
            if success:
                print(f"✅ Automatic dismissal report created for {member.name}")
            else:
                print(f"❌ Failed to create automatic dismissal report for {member.name}")
        else:
            print(f"ℹ️ No automatic dismissal needed for {member.name} - didn't have target role")
            
    except Exception as e:
        print(f"❌ Error handling member removal for {member.name}: {e}")

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
                    print(f"📢 Авто-уведомление администратору {after.display_name} (роль выдана): DM {'✅' if dm_sent else '❌'}")
                    
                elif became_moderator:
                    dm_sent = await send_moderator_welcome_dm(after)
                    print(f"📢 Авто-уведомление модератору {after.display_name} (роль выдана): DM {'✅' if dm_sent else '❌'}")
            
    except Exception as e:
        print(f"❌ Error handling member update for {after.name}: {e}")

async def restore_channel_messages(config):
    """Check and restore button messages for all configured channels."""    # Restore dismissal channel message
    dismissal_channel_id = config.get('dismissal_channel')
    if dismissal_channel_id:
        channel = bot.get_channel(dismissal_channel_id)
        if channel:
            if not await check_for_button_message(channel, "Рапорты на увольнение"):
                print(f"Sending dismissal button message to channel {channel.name}")
                await send_dismissal_button_message(channel)
            
            # Restore dismissal button views for existing dismissal button messages
            print(f"Restoring dismissal button views in {channel.name}")
            await restore_dismissal_button_views(bot, channel)
            
            # Restore approval views for existing dismissal reports
            print(f"Restoring approval views for dismissal reports in {channel.name}")
            await restore_dismissal_approval_views(bot, channel)
    
    # Restore role assignment channel message
    role_assignment_channel_id = config.get('role_assignment_channel')
    if role_assignment_channel_id:
        channel = bot.get_channel(role_assignment_channel_id)
        if channel:
            if not await check_for_button_message(channel, "Получение ролей"):
                print(f"Sending role assignment message to channel {channel.name}")
                await send_role_assignment_message(channel)
              # Restore role assignment views
            print(f"Restoring role assignment views in {channel.name}")
            await restore_role_assignment_views(bot, channel)
              # Restore approval views for existing applications
            print(f"Restoring approval views for role applications in {channel.name}")
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
                print(f"Sending leave request button message to channel {channel.name}")
                await send_leave_request_button_message(channel)
      # Restore medical registration channel message
    medical_registration_channel_id = config.get('medical_registration_channel')
    if medical_registration_channel_id:
        from forms.medical_registration import send_medical_registration_message
        channel = bot.get_channel(medical_registration_channel_id)
        if channel:
            print(f"Sending medical registration message to channel {channel.name}")
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
                print(f"Sending warehouse message to channel {channel.name}")
                try:
                    await send_warehouse_message(channel)
                except Exception as e:
                    print(f"❌ Ошибка при создании сообщения склада: {e}")
            
            # Восстанавливаем views для существующих заявок
            print(f"Restoring warehouse request views in {channel.name}")
            await restore_warehouse_request_views(channel)
        else:
            print(f"⚠️ Канал склада не найден (ID: {warehouse_request_channel_id})")    # Restore warehouse audit channel
    warehouse_audit_channel_id = config.get('warehouse_audit_channel')
    if warehouse_audit_channel_id:
        from forms.warehouse.audit import send_warehouse_audit_message, restore_warehouse_audit_views, restore_warehouse_audit_pinned_message
        channel = bot.get_channel(warehouse_audit_channel_id)
        if channel:
            # Сначала пытаемся восстановить существующее закрепленное сообщение
            pinned_restored = await restore_warehouse_audit_pinned_message(channel)
            
            # Если не удалось восстановить, проверяем нужно ли создать новое
            if not pinned_restored and not await check_for_button_message(channel, "Аудит склада"):
                print(f"Sending warehouse audit message to channel #{channel.name}")
                try:
                    await send_warehouse_audit_message(channel)
                except Exception as e:
                    print(f"❌ Ошибка при создании сообщения аудита склада: {e}")
            
            # Восстанавливаем views для аудита
            await restore_warehouse_audit_views(channel)
        else:
            print(f"⚠️ Канал аудита склада не найден (ID: {warehouse_audit_channel_id})")
    
    # Restore leave request views
    print("Restoring leave request views...")
    await restore_leave_request_views(bot)
    
    # Restore department applications messages (direct call for reliability)
    print("Restoring department applications messages...")
    try:
        from forms.department_applications.manager import DepartmentApplicationManager
        dept_manager = DepartmentApplicationManager(bot)
        await dept_manager.restore_persistent_views()
    except Exception as e:
        print(f"❌ Error restoring department applications: {e}")
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
        print(f"Error checking for button message in {channel.name}: {e}")
        return False

async def load_extensions():
    """Load all extension cogs from the cogs directory."""
    # Список исключений - cogs которые не нужно загружать
    excluded_cogs = {'warehouse_commands', 'cache_admin', 'department_applications_views'}  # personnel_commands теперь включен
    
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('_'):
            cog_name = filename[:-3]
            if cog_name in excluded_cogs:
                print(f'Skipped extension (excluded): {cog_name}')
                continue
                
            try:
                await bot.load_extension(f'cogs.{cog_name}')
                print(f'Loaded extension: {cog_name}')
            except Exception as e:
                print(f'Failed to load extension {cog_name}: {e}')

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
            target_role_name=config.get('military_role_name', 'Военнослужащий ВС РФ')
        )
        
        if success:
            await interaction.followup.send(
                f"✅ Тестовый автоматический рапорт создан для {пользователь.mention}!\n"
                f"📋 Проверьте канал рапортов на увольнение.",
                ephemeral=True
            )
            print(f"🚨 Test automatic dismissal created by {interaction.user.display_name} for {пользователь.display_name}")
        else:
            await interaction.followup.send(
                f"❌ Не удалось создать автоматический рапорт для {пользователь.mention}.\n"
                f"⚠️ Проверьте настройку канала и логи бота.",
                ephemeral=True
            )
            print(f"❌ Failed to create test automatic dismissal for {пользователь.display_name}")
            
    except Exception as e:
        await interaction.followup.send(
            f"❌ Ошибка при создании автоматического рапорта:\n```{str(e)}```",
            ephemeral=True
        )
        print(f"❌ Error in automatic_report command: {e}")
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
        print(f"🔄 Force sync completed by {interaction.user.display_name}: {len(synced)} commands")
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Ошибка при синхронизации команд:\n```{str(e)}```",
            ephemeral=True
        )
        print(f"❌ Force sync failed: {e}")

async def shutdown_handler():
    """Gracefully shutdown the bot."""
    print("\n⚠️  Получен сигнал завершения...")
    print("🔄 Завершение работы бота...")
    
    try:
        # Закрываем соединение с Discord
        await bot.close()
        print("✅ Соединение с Discord закрыто")
    except Exception as e:
        print(f"❌ Ошибка при закрытии соединения: {e}")
    
    print("✅ Бот успешно завершил работу")

def signal_handler(sig, frame):
    """Handle shutdown signals."""
    print(f"\n⚠️  Получен сигнал {sig}")
    
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
    print("🤖 Запуск Army Discord Bot...")
    print("💡 Для остановки нажмите Ctrl+C")
    
    # Check for token - first from environment, then try to read from .env file
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        # If we get here, it means dotenv didn't find the token in .env file
        # or the .env file doesn't exist
        print("Warning: DISCORD_TOKEN not found in environment variables or .env file.")
        print("Checking for token.txt as a fallback...")
        
        # Try to read from token.txt if exists
        try:
            with open('token.txt', 'r') as f:
                token = f.read().strip()
                print("Token found in token.txt")
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
        print(f"❌ Произошла ошибка при запуске бота: {e}")
        input("Нажмите Enter для выхода...")
