# Deployment Scripts

This directory contains scripts for server management and deployment of the Army Discord Bot.

## Scripts Overview

### setup-server.sh
Initial server setup script that:
- Updates system packages
- Installs Python, Git, Screen
- Creates application directory
- Sets up systemd service (optional)
- Creates environment template

**Usage:**
```bash
chmod +x scripts/setup-server.sh
sudo ./scripts/setup-server.sh
```

### deploy.sh
Main deployment script that:
- Creates backup of current version
- Stops running bot
- Pulls latest changes from Git
- Updates Python dependencies
- Starts bot in screen session
- Verifies successful startup

**Usage:**
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### health-check.sh
Health monitoring script that:
- Checks if bot is running
- Restarts bot if needed
- Monitors disk space
- Rotates large log files
- Can run continuously with --monitor flag

**Usage:**
```bash
# Single check
chmod +x scripts/health-check.sh
./scripts/health-check.sh

# Continuous monitoring
./scripts/health-check.sh --monitor
```

## Server Management Commands

### Using Screen
```bash
# Start bot
screen -dmS army-bot python3 app.py

# Attach to session
screen -r army-bot

# Detach from session
# Press Ctrl+A, then D

# List sessions
screen -list

# Kill session
screen -S army-bot -X quit
```

### Using Systemd (Alternative)
```bash
# Enable service
sudo systemctl enable army-discord-bot

# Start service
sudo systemctl start army-discord-bot

# Check status
sudo systemctl status army-discord-bot

# View logs
sudo journalctl -u army-discord-bot -f

# Restart service
sudo systemctl restart army-discord-bot
```

## Log Management

### Log Locations
- Bot logs: `/opt/army-discord-bot/logs/bot.log`
- Health check logs: `/opt/army-discord-bot/logs/health.log`
- Error logs: `/opt/army-discord-bot/logs/bot-error.log`

### Useful Log Commands
```bash
# View real-time logs
tail -f logs/bot.log

# View last 100 lines
tail -n 100 logs/bot.log

# Search for errors
grep -i error logs/bot.log

# View logs with timestamps
cat logs/bot.log | grep "$(date '+%Y-%m-%d')"
```

## Cron Jobs Setup

Add health check to cron for automatic monitoring:

```bash
# Edit crontab
crontab -e

# Add line for health check every 5 minutes
*/5 * * * * /opt/army-discord-bot/scripts/health-check.sh >/dev/null 2>&1

# Add line for daily log rotation at 2 AM
0 2 * * * find /opt/army-discord-bot/logs -name "*.log" -mtime +7 -delete
```

## Troubleshooting

### Bot won't start
1. Check logs: `tail -f logs/bot.log`
2. Verify configuration: `cat data/config.json`
3. Check environment variables: `env | grep DISCORD`
4. Test bot manually: `python3 app.py`

### High memory usage
1. Check process: `ps aux | grep python3`
2. Monitor resources: `htop`
3. Check log file sizes: `du -h logs/`
4. Restart bot: `./scripts/deploy.sh`

### Permission issues
1. Check file ownership: `ls -la`
2. Fix permissions: `chmod +x scripts/*.sh`
3. Check directory permissions: `ls -la /opt/`
