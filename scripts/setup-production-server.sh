#!/bin/bash

# Production Server Setup Script for Army Discord Bot
# Run this script on your Ubuntu server to prepare for deployment

set -e

echo "🚀 Setting up Army Discord Bot production server..."

# Update system packages
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install required packages
echo "📥 Installing required packages..."
apt install -y python3 python3-pip git screen htop curl wget

# Create application directory
APP_DIR="/opt/army-discord-bot"
echo "📁 Setting up application directory: $APP_DIR"

if [ ! -d "$APP_DIR" ]; then
    mkdir -p "$APP_DIR"
    echo "✅ Created $APP_DIR"
else
    echo "✅ Directory $APP_DIR already exists"
fi

# Create logs directory
mkdir -p "$APP_DIR/logs"
mkdir -p "$APP_DIR/backups"

# Set up log rotation
echo "📝 Setting up log rotation..."
cat > /etc/logrotate.d/army-discord-bot << EOF
$APP_DIR/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    copytruncate
}
EOF

# Create systemd service (alternative to screen for production)
echo "⚙️ Creating systemd service..."
cat > /etc/systemd/system/army-discord-bot.service << EOF
[Unit]
Description=Army Discord Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=10
StandardOutput=append:$APP_DIR/logs/bot.log
StandardError=append:$APP_DIR/logs/error.log

[Install]
WantedBy=multi-user.target
EOF

# Create health check script
echo "🏥 Setting up health monitoring..."
cat > /usr/local/bin/army-bot-health << 'EOF'
#!/bin/bash

APP_DIR="/opt/army-discord-bot"
LOG_FILE="$APP_DIR/logs/bot.log"
HEALTH_LOG="$APP_DIR/logs/health.log"

echo "$(date): Checking bot health..." >> "$HEALTH_LOG"

# Check if service is running
if systemctl is-active --quiet army-discord-bot; then
    echo "$(date): ✅ Service is running" >> "$HEALTH_LOG"
else
    echo "$(date): ❌ Service is not running, attempting restart..." >> "$HEALTH_LOG"
    systemctl restart army-discord-bot
    sleep 10
    if systemctl is-active --quiet army-discord-bot; then
        echo "$(date): ✅ Service restarted successfully" >> "$HEALTH_LOG"
    else
        echo "$(date): ❌ Service restart failed" >> "$HEALTH_LOG"
    fi
fi

# Check log file for recent activity
if [ -f "$LOG_FILE" ]; then
    RECENT_LOGS=$(tail -n 20 "$LOG_FILE" | grep -c "$(date +%Y-%m-%d)" || echo "0")
    echo "$(date): Recent log entries: $RECENT_LOGS" >> "$HEALTH_LOG"
else
    echo "$(date): ⚠️ Log file not found" >> "$HEALTH_LOG"
fi
EOF

chmod +x /usr/local/bin/army-bot-health

# Set up cron job for health checks
echo "⏰ Setting up automated health checks..."
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/army-bot-health") | crontab -

# Create backup script
cat > /usr/local/bin/army-bot-backup << 'EOF'
#!/bin/bash

APP_DIR="/opt/army-discord-bot"
BACKUP_DIR="$APP_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "📦 Creating backup: backup_$TIMESTAMP"

# Create backup
cd "$APP_DIR"
tar -czf "$BACKUP_DIR/backup_$TIMESTAMP.tar.gz" \
    --exclude="backups" \
    --exclude="logs" \
    --exclude=".git" \
    --exclude="__pycache__" \
    .

# Keep only last 7 backups
cd "$BACKUP_DIR"
ls -t backup_*.tar.gz | tail -n +8 | xargs -r rm

echo "✅ Backup completed: backup_$TIMESTAMP.tar.gz"
EOF

chmod +x /usr/local/bin/army-bot-backup

# Set up daily backups
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/army-bot-backup") | crontab -

# Create deployment script
cat > "$APP_DIR/deploy-production.sh" << 'EOF'
#!/bin/bash

set -e

APP_DIR="/opt/army-discord-bot"
echo "🚀 Starting production deployment..."

cd "$APP_DIR"

# Create backup before deployment
echo "📦 Creating pre-deployment backup..."
/usr/local/bin/army-bot-backup

# Stop the service
echo "🛑 Stopping bot service..."
systemctl stop army-discord-bot

# Pull latest changes
echo "📥 Pulling latest changes..."
git fetch origin
git reset --hard origin/main

# Install/update dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

# Validate configuration
if [ -f "validate_config.py" ]; then
    echo "🔍 Validating configuration..."
    python3 validate_config.py
fi

# Start the service
echo "🚀 Starting bot service..."
systemctl start army-discord-bot

# Wait and check if it started successfully
sleep 5
if systemctl is-active --quiet army-discord-bot; then
    echo "✅ Bot deployed and started successfully!"
    systemctl status army-discord-bot
else
    echo "❌ Bot failed to start. Checking logs..."
    systemctl status army-discord-bot
    tail -n 20 logs/bot.log
    exit 1
fi

echo "🎉 Deployment completed successfully!"
EOF

chmod +x "$APP_DIR/deploy-production.sh"

# Enable and start the service (if app.py exists)
if [ -f "$APP_DIR/app.py" ]; then
    echo "🔧 Enabling and starting service..."
    systemctl daemon-reload
    systemctl enable army-discord-bot
    # Note: Don't start yet, wait for first deployment
else
    echo "⚠️ app.py not found. Service will be started after first deployment."
fi

# Set up firewall (basic security)
echo "🔒 Setting up basic firewall..."
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 22

# Create monitoring dashboard script
cat > /usr/local/bin/army-bot-status << 'EOF'
#!/bin/bash

APP_DIR="/opt/army-discord-bot"

echo "🤖 Army Discord Bot Status Dashboard"
echo "=================================="

# Service status
echo "📊 Service Status:"
systemctl status army-discord-bot --no-pager -l

echo -e "\n📝 Recent Logs (last 10 lines):"
if [ -f "$APP_DIR/logs/bot.log" ]; then
    tail -n 10 "$APP_DIR/logs/bot.log"
else
    echo "No logs found"
fi

echo -e "\n💾 Disk Usage:"
df -h "$APP_DIR"

echo -e "\n🧠 Memory Usage:"
free -h

echo -e "\n⏰ Uptime:"
uptime

echo -e "\n🔄 Last Deployment:"
if [ -f "$APP_DIR/.git/FETCH_HEAD" ]; then
    echo "Last fetch: $(stat -c %y "$APP_DIR/.git/FETCH_HEAD")"
    echo "Current commit: $(cd "$APP_DIR" && git rev-parse --short HEAD)"
    echo "Current branch: $(cd "$APP_DIR" && git branch --show-current)"
else
    echo "No deployment information found"
fi
EOF

chmod +x /usr/local/bin/army-bot-status

echo ""
echo "🎉 Server setup completed successfully!"
echo ""
echo "📋 Summary:"
echo "   • Application directory: $APP_DIR"
echo "   • Systemd service: army-discord-bot"
echo "   • Log rotation configured"
echo "   • Health monitoring every 5 minutes"
echo "   • Daily backups at 2 AM"
echo "   • Basic firewall enabled"
echo ""
echo "🚀 Next steps:"
echo "   1. Clone your repository to $APP_DIR"
echo "   2. Configure your .env file with Discord token"
echo "   3. Run the first deployment: $APP_DIR/deploy-production.sh"
echo ""
echo "🔧 Useful commands:"
echo "   • Check status: army-bot-status"
echo "   • View logs: journalctl -u army-discord-bot -f"
echo "   • Manual health check: army-bot-health"
echo "   • Create backup: army-bot-backup"
echo ""
EOF
