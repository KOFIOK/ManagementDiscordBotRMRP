# filepath: g:\GitHub\repos\army discord bot\app.py
import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration file to store channel IDs
CONFIG_FILE = 'config.json'

# Default configuration
default_config = {
    'dismissal_channel': None,
    'audit_channel': None,
    'blacklist_channel': None
}

# Load configuration
def load_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Create default config file if it doesn't exist
        save_config(default_config)
        return default_config.copy()

# Save configuration
def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    
    # Sync commands with Discord
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

    # Load configuration on startup
    config = load_config()
    print('Configuration loaded successfully')
    print(f'Dismissal channel: {config["dismissal_channel"]}')
    print(f'Audit channel: {config["audit_channel"]}')
    print(f'Blacklist channel: {config["blacklist_channel"]}')

@bot.tree.command(name="set-dismissal-channel", description="Установить канал для рапортов на увольнение")
@app_commands.checks.has_permissions(administrator=True)
async def set_dismissal_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    config = load_config()
    config['dismissal_channel'] = channel.id
    save_config(config)
    await interaction.response.send_message(
        f"Канал для рапортов на увольнение установлен: {channel.mention}", 
        ephemeral=True
    )

@bot.tree.command(name="set-audit-channel", description="Установить канал для кадрового аудита")
@app_commands.checks.has_permissions(administrator=True)
async def set_audit_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    config = load_config()
    config['audit_channel'] = channel.id
    save_config(config)
    await interaction.response.send_message(
        f"Канал для кадрового аудита установлен: {channel.mention}", 
        ephemeral=True
    )

@bot.tree.command(name="set-blacklist-channel", description="Установить канал для чёрного списка")
@app_commands.checks.has_permissions(administrator=True)
async def set_blacklist_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    config = load_config()
    config['blacklist_channel'] = channel.id
    save_config(config)
    await interaction.response.send_message(
        f"Канал для чёрного списка установлен: {channel.mention}", 
        ephemeral=True
    )

@bot.tree.command(name="show-channels", description="Показать настроенные каналы")
@app_commands.checks.has_permissions(administrator=True)
async def show_channels(interaction: discord.Interaction):
    config = load_config()
    
    # Create response message
    response = "**Настроенные каналы:**\n"
    
    # Add dismissal channel info
    if config['dismissal_channel']:
        channel = bot.get_channel(config['dismissal_channel'])
        response += f"Рапорт на увольнение: {channel.mention if channel else 'Канал не найден'}\n"
    else:
        response += "Рапорт на увольнение: Не настроен\n"
    
    # Add audit channel info
    if config['audit_channel']:
        channel = bot.get_channel(config['audit_channel'])
        response += f"Кадровый аудит: {channel.mention if channel else 'Канал не найден'}\n"
    else:
        response += "Кадровый аудит: Не настроен\n"
    
    # Add blacklist channel info
    if config['blacklist_channel']:
        channel = bot.get_channel(config['blacklist_channel'])
        response += f"Чёрный список: {channel.mention if channel else 'Канал не найден'}\n"
    else:
        response += "Чёрный список: Не настроен\n"
    
    await interaction.response.send_message(response, ephemeral=True)

# Error handling for commands
@set_dismissal_channel.error
@set_audit_channel.error
@set_blacklist_channel.error
@show_channels.error
async def channel_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("У вас нет прав для выполнения этой команды.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Произошла ошибка: {error}", ephemeral=True)
        print(f"Command error: {error}")

# Run the bot
if __name__ == '__main__':
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
        bot.run(token)
    except Exception as e:
        print(f"Произошла ошибка при запуске бота: {e}")
        input("Нажмите Enter для выхода...")