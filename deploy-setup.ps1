# Army Discord Bot - Final Deployment Script
# Run this script to complete the CI/CD setup

Write-Host "Army Discord Bot - Final CI/CD Deployment" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green

# Check current status
Write-Host "`n1. Checking current status..." -ForegroundColor Yellow
$currentBranch = git branch --show-current
Write-Host "Current branch: $currentBranch" -ForegroundColor Cyan

# Validate environment
Write-Host "`n2. Validating environment..." -ForegroundColor Yellow

if (Test-Path ".env") {
    Write-Host "✅ .env file exists" -ForegroundColor Green
} else {
    Write-Host "⚠️  .env file missing - you'll need to configure this on the server" -ForegroundColor Yellow
}

if (Test-Path "requirements.txt") {
    Write-Host "✅ requirements.txt exists" -ForegroundColor Green
} else {
    Write-Host "❌ requirements.txt missing" -ForegroundColor Red
    exit 1
}

# Check git status
Write-Host "`n3. Checking git status..." -ForegroundColor Yellow
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "⚠️  Uncommitted changes detected:" -ForegroundColor Yellow
    git status --short
    
    $commit = Read-Host "Commit changes? (y/n)"
    if ($commit -eq "y" -or $commit -eq "yes") {
        git add .
        $message = Read-Host "Commit message (or press Enter for default)"
        if ([string]::IsNullOrWhiteSpace($message)) {
            $message = "Final CI/CD setup and deployment preparation"
        }
        git commit -m $message
        Write-Host "✅ Changes committed" -ForegroundColor Green
    }
} else {
    Write-Host "✅ Working directory clean" -ForegroundColor Green
}

# Push current branch
Write-Host "`n4. Pushing current branch..." -ForegroundColor Yellow
git push origin $currentBranch
Write-Host "✅ Pushed $currentBranch to GitHub" -ForegroundColor Green

# Create and push main branch if needed
Write-Host "`n5. Setting up main branch..." -ForegroundColor Yellow
$mainExists = git show-ref --verify --quiet refs/heads/main
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Main branch already exists" -ForegroundColor Green
} else {
    Write-Host "Creating main branch..." -ForegroundColor Cyan
    git checkout -b main
    git push origin main
    git checkout $currentBranch
    Write-Host "✅ Main branch created and pushed" -ForegroundColor Green
}

# Instructions for GitHub secrets
Write-Host "`n6. GitHub Secrets Setup Required" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Yellow
Write-Host "You need to add your Discord bot token to GitHub secrets:" -ForegroundColor White
Write-Host ""
Write-Host "1. Go to: https://github.com/KOFIOK/armyDiscordBot/settings/secrets/actions" -ForegroundColor Cyan
Write-Host "2. Click 'New repository secret'" -ForegroundColor Cyan
Write-Host "3. Name: DISCORD_TOKEN" -ForegroundColor Cyan
Write-Host "4. Value: [Your Discord Bot Token]" -ForegroundColor Cyan
Write-Host "5. Click 'Add secret'" -ForegroundColor Cyan

# Server setup instructions
Write-Host "`n7. Production Server Setup" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Yellow
Write-Host "To set up your production server (202.181.188.48):" -ForegroundColor White
Write-Host ""
Write-Host "SSH to server and run:" -ForegroundColor Cyan
Write-Host "sudo bash scripts/setup-production-server.sh" -ForegroundColor White
Write-Host ""
Write-Host "Then clone your repository:" -ForegroundColor Cyan
Write-Host "cd /opt/army-discord-bot" -ForegroundColor White
Write-Host "git clone https://github.com/KOFIOK/armyDiscordBot.git ." -ForegroundColor White

# Deployment instructions
Write-Host "`n8. Deployment Process" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Yellow
Write-Host "After setting up GitHub secrets and server:" -ForegroundColor White
Write-Host ""
Write-Host "Option A - Automatic (Recommended):" -ForegroundColor Cyan
Write-Host "git push origin main" -ForegroundColor White
Write-Host "→ This triggers automatic deployment via GitHub Actions" -ForegroundColor Gray
Write-Host ""
Write-Host "Option B - Manual:" -ForegroundColor Cyan
Write-Host "SSH to server and run: bash /opt/army-discord-bot/deploy-production.sh" -ForegroundColor White

# Monitoring
Write-Host "`n9. Monitoring & Management" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Yellow
Write-Host "Server management commands:" -ForegroundColor White
Write-Host "• Check status: army-bot-status" -ForegroundColor Cyan
Write-Host "• View logs: journalctl -u army-discord-bot -f" -ForegroundColor Cyan
Write-Host "• Manual health check: army-bot-health" -ForegroundColor Cyan
Write-Host "• Create backup: army-bot-backup" -ForegroundColor Cyan

# Final status
Write-Host "`n✅ CI/CD Setup Complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host "Your bot is ready for production deployment!" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Add DISCORD_TOKEN to GitHub secrets" -ForegroundColor White
Write-Host "2. Set up production server" -ForegroundColor White
Write-Host "3. Push to main branch for deployment" -ForegroundColor White
Write-Host ""
Write-Host "GitHub Actions will handle the rest automatically! 🚀" -ForegroundColor Green

# Open browser to GitHub if requested
$openGitHub = Read-Host "`nOpen GitHub repository? (y/n)"
if ($openGitHub -eq "y" -or $openGitHub -eq "yes") {
    Start-Process "https://github.com/KOFIOK/armyDiscordBot"
}
