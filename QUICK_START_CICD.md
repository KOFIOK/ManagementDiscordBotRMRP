# Quick Start CI/CD Guide

This guide will help you set up CI/CD for the Army Discord Bot in just a few steps.

## 🚀 Quick Setup (5 minutes)

### 1. Push your code to GitHub
```powershell
# Initialize git if not already done
git init

# Add all files
git add .

# Commit changes
git commit -m "Add CI/CD pipeline"

# Add your GitHub repository
git remote add origin https://github.com/YOUR_USERNAME/army-discord-bot.git

# Push to main branch
git push -u origin main
```

### 2. Set up your server (First time only)
Connect to your server and run the setup script:

```bash
# Connect to server
ssh root@202.181.188.48

# Create directory and clone repository
mkdir -p /opt/army-discord-bot
cd /opt/army-discord-bot
git clone https://github.com/YOUR_USERNAME/army-discord-bot.git .

# Run setup script
chmod +x scripts/setup-server.sh
./scripts/setup-server.sh

# Create environment file with your bot token
echo "DISCORD_TOKEN=YOUR_ACTUAL_BOT_TOKEN_HERE" > .env

# Configure bot settings (edit with your Discord server IDs)
nano data/config.json
```

### 3. Test local deployment
Test that everything works locally on your computer:

```powershell
# Run local tests (Windows PowerShell)
.\test-local.ps1

# Or use the batch file
.\test-local.bat
```

### 4. Enable automatic deployment
Your GitHub Actions will automatically:
- ✅ Run tests on every push/PR
- 🚀 Deploy to production on push to `main` branch  
- 🧪 Deploy to staging on push to `develop` branch

## 📋 What happens automatically

### When you push to `main`:
1. **Tests run** - Code formatting, linting, unit tests
2. **If tests pass** - Bot deploys to production server
3. **Bot starts** - Automatically starts in screen session
4. **Health check** - Verifies bot started successfully

### When you push to `develop`:
1. **Tests run** - Same as main branch
2. **If tests pass** - Bot deploys to staging server (if configured)

## 🔧 Common Commands

### Local development:
```powershell
# Run tests
pytest tests\ -v

# Format code
black .

# Check linting
flake8 .

# Run all checks
.\test-local.ps1
```

### Server management:
```bash
# Check bot status
screen -list

# View bot logs
tail -f /opt/army-discord-bot/logs/bot.log

# Attach to bot session
screen -r army-bot

# Restart bot manually
cd /opt/army-discord-bot && ./scripts/deploy.sh

# Run health check
./scripts/health-check.sh
```

## 🐛 Troubleshooting

### If deployment fails:
1. Check GitHub Actions logs in your repository
2. SSH to server and check: `tail -f /opt/army-discord-bot/logs/bot.log`
3. Verify server has enough disk space: `df -h`
4. Try manual deployment: `cd /opt/army-discord-bot && ./scripts/deploy.sh`

### If tests fail:
1. Run tests locally: `.\test-local.ps1`
2. Fix any formatting issues: `black .`
3. Fix any import issues: `isort .`
4. Check test output for specific errors

## 🎯 Next Steps

1. **Set up monitoring**: Add the health check to cron:
   ```bash
   # Add to crontab
   crontab -e
   
   # Add this line for health checks every 5 minutes
   */5 * * * * /opt/army-discord-bot/scripts/health-check.sh >/dev/null 2>&1
   ```

2. **Set up staging server** (optional):
   - Use another server or different directory
   - Configure `STAGING_SERVER_*` secrets in GitHub

3. **Monitor logs**: Set up log rotation and monitoring
   ```bash
   # Add to crontab for daily log cleanup
   0 2 * * * find /opt/army-discord-bot/logs -name "*.log" -mtime +7 -delete
   ```

## ✅ Success Indicators

Your CI/CD is working correctly when:
- ✅ Tests pass in GitHub Actions
- ✅ Bot deploys automatically on push to main
- ✅ Bot appears in screen session: `screen -list`
- ✅ Bot logs show successful startup
- ✅ Bot responds to Discord commands

**You're all set! 🎉**

Every time you push to the `main` branch, your bot will automatically update on the server!
