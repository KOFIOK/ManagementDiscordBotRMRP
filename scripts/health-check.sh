#!/bin/bash

# Health check script for Army Discord Bot
# This script monitors the bot's health and can restart it if needed

APP_DIR="/opt/army-discord-bot"
LOG_DIR="$APP_DIR/logs"
SCREEN_SESSION="army-bot"
HEALTH_LOG="$LOG_DIR/health.log"

# Function to log with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a $HEALTH_LOG
}

# Function to check if bot is running
is_bot_running() {
    screen -list | grep -q "$SCREEN_SESSION"
}

# Function to restart bot
restart_bot() {
    log_message "🔄 Restarting bot..."
    
    # Stop existing session
    screen -S $SCREEN_SESSION -X quit 2>/dev/null || true
    sleep 3
    
    # Start new session
    cd $APP_DIR
    screen -dmS $SCREEN_SESSION bash -c "python3 app.py 2>&1 | tee $LOG_DIR/bot.log"
    sleep 5
    
    if is_bot_running; then
        log_message "✅ Bot restarted successfully"
        return 0
    else
        log_message "❌ Failed to restart bot"
        return 1
    fi
}

# Function to check disk space
check_disk_space() {
    local usage=$(df $APP_DIR | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ $usage -gt 90 ]; then
        log_message "⚠️  Disk space warning: ${usage}% used"
        
        # Clean old logs if disk space is critical
        if [ $usage -gt 95 ]; then
            log_message "🧹 Cleaning old logs..."
            find $LOG_DIR -name "*.log" -mtime +7 -delete
        fi
    fi
}

# Function to check log file size
check_log_size() {
    local log_file="$LOG_DIR/bot.log"
    if [ -f "$log_file" ]; then
        local size=$(du -m "$log_file" | cut -f1)
        if [ $size -gt 100 ]; then
            log_message "📄 Rotating large log file (${size}MB)"
            mv "$log_file" "$log_file.$(date +%Y%m%d-%H%M%S)"
            touch "$log_file"
        fi
    fi
}

# Main health check
main() {
    log_message "🔍 Starting health check..."
    
    # Check if bot is running
    if ! is_bot_running; then
        log_message "❌ Bot is not running!"
        
        if restart_bot; then
            log_message "✅ Health check completed - bot restarted"
        else
            log_message "❌ Health check failed - could not restart bot"
            exit 1
        fi
    else
        log_message "✅ Bot is running normally"
    fi
    
    # Perform additional checks
    check_disk_space
    check_log_size
    
    log_message "✅ Health check completed successfully"
}

# Create logs directory if not exists
mkdir -p $LOG_DIR

# Run main function
main

# If --monitor flag is passed, run continuously
if [ "$1" = "--monitor" ]; then
    log_message "🔄 Starting continuous monitoring (every 5 minutes)..."
    while true; do
        sleep 300  # 5 minutes
        main
    done
fi
