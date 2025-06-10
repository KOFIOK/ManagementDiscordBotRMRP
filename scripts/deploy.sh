#!/bin/bash

# Deployment script for Army Discord Bot
# This script handles the deployment process on the production server

set -e

APP_DIR="/opt/army-discord-bot"
LOG_DIR="$APP_DIR/logs"
SCREEN_SESSION="army-bot"

echo "🚀 Starting deployment process..."

# Navigate to application directory
cd $APP_DIR

# Create backup of current version
echo "💾 Creating backup..."
if [ -d "backup" ]; then
    rm -rf backup
fi
mkdir backup
cp -r . backup/ 2>/dev/null || true

# Stop existing bot instance
echo "🛑 Stopping existing bot..."
# Use our bot control script if available
if [ -f "$APP_DIR/scripts/bot.sh" ]; then
    bash "$APP_DIR/scripts/bot.sh" stop
else
    # Fallback to manual stop
    screen -S $SCREEN_SESSION -p 0 -X stuff "^C" 2>/dev/null || true
    sleep 3
    screen -S $SCREEN_SESSION -X quit 2>/dev/null || true
    pkill -f "python3 app.py" 2>/dev/null || true
fi
sleep 3

# Double-check that bot is stopped
if pgrep -f "python3 app.py" > /dev/null; then
    echo "⚠️ Bot still running, force killing..."
    pkill -9 -f "python3 app.py"
    sleep 2
fi

# Pull latest changes
echo "📥 Pulling latest changes..."
git fetch origin
git reset --hard origin/main

# Update dependencies
echo "📦 Updating dependencies..."
pip3 install -r requirements.txt

# Create logs directory if not exists
mkdir -p $LOG_DIR

# Verify configuration
echo "🔍 Verifying configuration..."
if [ ! -f "data/config.json" ]; then
    echo "⚠️  Warning: config.json not found"
fi

if [ ! -f ".env" ] && [ -z "$DISCORD_TOKEN" ]; then
    echo "⚠️  Warning: No .env file or DISCORD_TOKEN environment variable found"
fi

# Start bot in screen session
echo "▶️  Starting bot..."
if [ -f "$APP_DIR/scripts/bot.sh" ]; then
    bash "$APP_DIR/scripts/bot.sh" start
else
    # Fallback to direct start
    screen -dmS $SCREEN_SESSION bash -c "cd $APP_DIR && python3 app.py 2>&1 | tee $LOG_DIR/bot.log"
fi

# Wait and verify startup
echo "⏳ Waiting for bot to start..."
sleep 5

if screen -list | grep -q "$SCREEN_SESSION"; then
    echo "✅ Bot deployed and started successfully!"
    echo ""
    echo "📋 Управление ботом:"
    echo "  ./scripts/bot.sh status   - статус бота"
    echo "  ./scripts/bot.sh stop     - остановить бота"
    echo "  ./scripts/bot.sh logs     - показать логи"
    echo "  ./scripts/bot.sh watch    - следить за логами"
else
    echo "❌ Bot failed to start!"
    echo "📄 Check logs: cat $LOG_DIR/bot.log"
    exit 1
fi

echo "🎉 Deployment completed successfully!"
