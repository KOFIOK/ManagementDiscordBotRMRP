#!/bin/bash

# Server Setup Script for Army Discord Bot
# This script prepares the Ubuntu server for the Discord bot deployment

set -e  # Exit on any error

echo "🚀 Setting up Army Discord Bot on Ubuntu Server..."

# Update system packages
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install required packages
echo "🔧 Installing required packages..."
apt install -y python3 python3-pip git screen curl nano htop

# Create application directory
echo "📁 Creating application directory..."
mkdir -p /opt/army-discord-bot
cd /opt/army-discord-bot

# Set up git repository (if not already cloned)
if [ ! -d ".git" ]; then
    echo "📥 Cloning repository..."
    git clone https://github.com/YOUR_USERNAME/army-discord-bot.git .
else
    echo "📥 Updating repository..."
    git pull origin main
fi

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip3 install -r requirements.txt

# Create logs directory
echo "📄 Creating logs directory..."
mkdir -p logs

# Create systemd service file (alternative to screen)
echo "⚙️  Creating systemd service..."
cat > /etc/systemd/system/army-discord-bot.service << EOF
[Unit]
Description=Army Discord Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/army-discord-bot
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=5
StandardOutput=append:/opt/army-discord-bot/logs/bot.log
StandardError=append:/opt/army-discord-bot/logs/bot-error.log

[Install]
WantedBy=multi-user.target
EOF

# Set up environment variables (create template)
echo "🔐 Creating environment template..."
cat > .env.template << EOF
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token_here

# Google Sheets Configuration (if used)
GOOGLE_SHEETS_CREDENTIALS=path_to_credentials.json

# Other environment variables
ENVIRONMENT=production
EOF

echo "✅ Server setup completed!"
echo ""
echo "📝 Next steps:"
echo "1. Copy your .env file or set environment variables"
echo "2. Configure data/config.json with your Discord server settings"
echo "3. Run: systemctl enable army-discord-bot"
echo "4. Run: systemctl start army-discord-bot"
echo ""
echo "🔍 Useful commands:"
echo "- Check status: systemctl status army-discord-bot"
echo "- View logs: tail -f logs/bot.log"
echo "- Restart bot: systemctl restart army-discord-bot"
echo "- Stop bot: systemctl stop army-discord-bot"
echo ""
echo "📺 Using screen instead:"
echo "- Start: screen -dmS army-bot python3 app.py"
echo "- Attach: screen -r army-bot"
echo "- Detach: Ctrl+A, then D"
echo "- List: screen -list"
