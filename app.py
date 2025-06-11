import os
import asyncio
import signal
import sys
import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.config_manager import load_config, create_backup, get_config_status
from utils.google_sheets import sheets_manager
from forms.dismissal_form import DismissalReportButton, DismissalApprovalView, send_dismissal_button_message, restore_dismissal_approval_views, restore_dismissal_button_views
from forms.settings_form import SettingsView
from forms.role_assignment_form import RoleAssignmentView, send_role_assignment_message, restore_role_assignment_views, restore_approval_views
from forms.welcome_system import setup_welcome_events, WelcomeButtonsView

# Load environment variables from .env file
load_dotenv()

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Initialize the bot with a command prefix and intents
bot = commands.Bot(command_prefix='!', intents=intents)

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
    
    # Load all extension cogs
    await load_extensions()
      # Sync commands with Discord
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
      # Load configuration on startup
    config = load_config()
    print('Configuration loaded successfully')
    print(f'Dismissal channel: {config.get("dismissal_channel", "Not set")}')
    print(f'Audit channel: {config.get("audit_channel", "Not set")}')
    print(f'Blacklist channel: {config.get("blacklist_channel", "Not set")}')
    print(f'Role assignment channel: {config.get("role_assignment_channel", "Not set")}')
    print(f'Military role: {config.get("military_role", "Not set")}')
    print(f'Civilian role: {config.get("civilian_role", "Not set")}')
      # Initialize Google Sheets
    print('Initializing Google Sheets...')
    sheets_success = sheets_manager.initialize()
    if sheets_success:
        print('✅ Google Sheets initialized successfully')
    else:
        print('⚠️ Google Sheets initialization failed - dismissal logging will not work')    # Create persistent button views
    bot.add_view(DismissalReportButton())
    bot.add_view(SettingsView())
    bot.add_view(RoleAssignmentView())
    bot.add_view(WelcomeButtonsView())
    
    # Add a generic DismissalApprovalView for persistent approval buttons
    bot.add_view(DismissalApprovalView())
    
    print('Persistent views added to bot')
    
    # Setup welcome system events
    setup_welcome_events(bot)
    
    # Check channels and restore messages if needed
    await restore_channel_messages(config)

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
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('_'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded extension: {filename[:-3]}')
            except Exception as e:
                print(f'Failed to load extension {filename[:-3]}: {e}')

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
