# ✅ Pre-Push Checklist

## Before Running `git push origin main`:

### 1. GitHub Secrets Configuration ⚠️
**CRITICAL**: Ensure these secrets are configured in GitHub repository settings:

- [ ] `SERVER_HOST` = `202.181.188.48`
- [ ] `SERVER_USER` = `root` 
- [ ] `SERVER_PASSWORD` = `&bvWF4oy432&`

**Where to add**: GitHub Repository → Settings → Secrets and variables → Actions

### 2. Repository Settings
- [ ] Default branch is set to `main`
- [ ] Actions are enabled for the repository

### 3. Bot Configuration
- [ ] Discord bot token is properly set in your bot's environment
- [ ] Bot has necessary permissions on your Discord server

### 4. Final Push Command
```bash
git push origin main
```

## After Push:
1. 🔍 Go to GitHub → Actions tab
2. 📊 Watch "Deploy Bot" workflow execution
3. ✅ Verify successful deployment
4. 🤖 Test bot functionality in Discord

## Emergency Stop (if needed):
```bash
# SSH to server
ssh root@202.181.188.48

# Stop bot
screen -S army-bot -X quit

# Check status
screen -list
```

**⚡ Ready for deployment!**
