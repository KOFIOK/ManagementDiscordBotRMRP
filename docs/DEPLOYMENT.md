# GitHub Secrets Configuration

For the CI/CD pipeline to work properly, you need to configure the following secrets in your GitHub repository:

## Setting up GitHub Secrets

1. Go to your GitHub repository
2. Navigate to Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Add the following secrets:

## Required Secrets

### Production Server
- **SERVER_HOST**: `202.181.188.48`
- **SERVER_USER**: `root`
- **SERVER_PASSWORD**: `&bvWF4oy432&`

### Staging Server (Optional)
- **STAGING_SERVER_HOST**: Your staging server IP
- **STAGING_SERVER_USER**: Your staging server username
- **STAGING_SERVER_PASSWORD**: Your staging server password

### Testing
- **TEST_DISCORD_TOKEN**: A test Discord bot token (for testing only)

## Server Setup Commands

After setting up secrets, you need to prepare your server:

### 1. Connect to server
```bash
ssh root@202.181.188.48
```

### 2. Run setup script (one time only)
```bash
# Download and run setup script
curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/army-discord-bot/main/scripts/setup-server.sh | bash

# Or clone repo first and run locally
git clone https://github.com/YOUR_USERNAME/army-discord-bot.git /opt/army-discord-bot
cd /opt/army-discord-bot
chmod +x scripts/setup-server.sh
./scripts/setup-server.sh
```

### 3. Configure environment
```bash
cd /opt/army-discord-bot

# Create .env file with your actual bot token
echo "DISCORD_TOKEN=your_actual_discord_bot_token_here" > .env

# Configure bot settings
cp data/config.json.example data/config.json
nano data/config.json
```

### 4. Test manual deployment
```bash
# Make deploy script executable
chmod +x scripts/deploy.sh

# Run deployment
./scripts/deploy.sh
```

## GitHub Actions Workflow

The pipeline will automatically:

1. **On Pull Request**: Run tests only
2. **On Push to `develop`**: Run tests + deploy to staging
3. **On Push to `main`**: Run tests + deploy to production

## Monitoring

After deployment, you can monitor the bot:

```bash
# Check if bot is running
screen -list

# View bot logs
tail -f /opt/army-discord-bot/logs/bot.log

# Attach to bot session
screen -r army-bot

# Run health check
/opt/army-discord-bot/scripts/health-check.sh
```

## Security Notes

- Keep your Discord bot token secure
- Use different tokens for testing and production
- Consider using a separate staging server
- Regularly rotate server passwords
- Monitor server access logs

## Troubleshooting

If deployment fails:

1. Check GitHub Actions logs
2. SSH to server and check bot logs
3. Verify server connectivity
4. Check disk space: `df -h`
5. Check memory usage: `free -h`
6. Restart manually if needed: `./scripts/deploy.sh`
