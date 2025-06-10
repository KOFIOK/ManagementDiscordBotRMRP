#!/bin/bash

# Army Discord Bot Management Script
# Convenient commands for managing the bot on Ubuntu server

APP_DIR="/opt/army-discord-bot"
SCREEN_SESSION="army-bot"
SERVICE_NAME="army-discord-bot"

show_help() {
    echo "🤖 Army Discord Bot Management Commands:"
    echo ""
    echo "📊 Status Commands:"
    echo "  ./manage.sh status     - Show bot status"
    echo "  ./manage.sh logs       - Show recent logs"
    echo "  ./manage.sh screen     - Connect to screen session"
    echo ""
    echo "🔄 Control Commands:"
    echo "  ./manage.sh start      - Start the bot"
    echo "  ./manage.sh stop       - Stop the bot"
    echo "  ./manage.sh restart    - Restart the bot"
    echo "  ./manage.sh kill       - Force kill the bot"
    echo ""
    echo "⚙️ Service Management (systemd):"
    echo "  ./manage.sh service-start   - Start via systemd"
    echo "  ./manage.sh service-stop    - Stop via systemd"
    echo "  ./manage.sh service-restart - Restart via systemd"
    echo "  ./manage.sh service-status  - Check systemd status"
    echo ""
    echo "🧹 Maintenance:"
    echo "  ./manage.sh deploy     - Run deployment script"
    echo "  ./manage.sh backup     - Create backup"
    echo "  ./manage.sh cleanup    - Clean old logs"
}

show_status() {
    echo "🔍 Bot Status Check:"
    echo ""
    
    # Check screen session
    if screen -list | grep -q "$SCREEN_SESSION"; then
        echo "✅ Screen session '$SCREEN_SESSION' is running"
    else
        echo "❌ Screen session '$SCREEN_SESSION' is not running"
    fi
    
    # Check Python process
    if pgrep -f "python3 app.py" > /dev/null; then
        echo "✅ Python bot process is running"
        echo "📋 Process info:"
        ps aux | grep "python3 app.py" | grep -v grep
    else
        echo "❌ Python bot process is not running"
    fi
    
    # Check systemd service if exists
    if systemctl list-units --full -all | grep -q "$SERVICE_NAME.service"; then
        echo ""
        echo "⚙️ Systemd service status:"
        systemctl status "$SERVICE_NAME" --no-pager -l
    fi
}

start_bot() {
    echo "▶️ Starting bot via screen..."
    if screen -list | grep -q "$SCREEN_SESSION"; then
        echo "⚠️ Bot is already running in screen session"
        return 1
    fi
    
    cd "$APP_DIR"
    screen -dmS "$SCREEN_SESSION" bash -c "python3 app.py 2>&1 | tee logs/bot.log"
    sleep 3
    
    if screen -list | grep -q "$SCREEN_SESSION"; then
        echo "✅ Bot started successfully!"
    else
        echo "❌ Failed to start bot"
        return 1
    fi
}

stop_bot() {
    echo "🛑 Stopping bot..."
    
    # Stop screen session
    if screen -list | grep -q "$SCREEN_SESSION"; then
        screen -S "$SCREEN_SESSION" -X quit
        echo "✅ Screen session terminated"
    fi
    
    # Stop any remaining Python processes
    if pgrep -f "python3 app.py" > /dev/null; then
        pkill -f "python3 app.py"
        echo "✅ Python processes terminated"
    fi
    
    sleep 2
    echo "✅ Bot stopped"
}

kill_bot() {
    echo "💀 Force killing bot..."
    
    # Force kill screen session
    screen -S "$SCREEN_SESSION" -X quit 2>/dev/null || true
    
    # Force kill Python processes
    pkill -9 -f "python3 app.py" 2>/dev/null || true
    
    echo "✅ Bot force killed"
}

restart_bot() {
    echo "🔄 Restarting bot..."
    stop_bot
    sleep 3
    start_bot
}

show_logs() {
    echo "📄 Recent bot logs:"
    echo "=================="
    if [ -f "$APP_DIR/logs/bot.log" ]; then
        tail -50 "$APP_DIR/logs/bot.log"
    else
        echo "❌ Log file not found"
    fi
}

connect_screen() {
    echo "📺 Connecting to screen session..."
    echo "💡 To detach from screen: Ctrl+A, then D"
    echo "💡 To stop bot: Ctrl+C"
    echo ""
    screen -r "$SCREEN_SESSION"
}

case "$1" in
    "status")
        show_status
        ;;
    "start")
        start_bot
        ;;
    "stop")
        stop_bot
        ;;
    "restart")
        restart_bot
        ;;
    "kill")
        kill_bot
        ;;
    "logs")
        show_logs
        ;;
    "screen")
        connect_screen
        ;;
    "service-start")
        echo "▶️ Starting via systemd..."
        systemctl start "$SERVICE_NAME"
        systemctl status "$SERVICE_NAME" --no-pager
        ;;
    "service-stop")
        echo "🛑 Stopping via systemd..."
        systemctl stop "$SERVICE_NAME"
        ;;
    "service-restart")
        echo "🔄 Restarting via systemd..."
        systemctl restart "$SERVICE_NAME"
        systemctl status "$SERVICE_NAME" --no-pager
        ;;
    "service-status")
        systemctl status "$SERVICE_NAME" --no-pager -l
        ;;
    "deploy")
        echo "🚀 Running deployment..."
        if [ -f "$APP_DIR/scripts/deploy.sh" ]; then
            bash "$APP_DIR/scripts/deploy.sh"
        else
            echo "❌ Deploy script not found"
        fi
        ;;
    "backup")
        echo "💾 Creating backup..."
        if [ -f "/usr/local/bin/army-bot-backup" ]; then
            /usr/local/bin/army-bot-backup
        else
            echo "❌ Backup script not found"
        fi
        ;;
    "cleanup")
        echo "🧹 Cleaning old logs..."
        find "$APP_DIR/logs" -name "*.log" -mtime +7 -delete
        echo "✅ Old logs cleaned"
        ;;
    *)
        show_help
        ;;
esac
