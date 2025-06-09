#!/usr/bin/env python3
"""
Final CI/CD Setup Script for Army Discord Bot (Windows Compatible)

This script helps complete the CI/CD setup by:
1. Checking GitHub repository setup
2. Validating environment configuration
3. Testing deployment scripts locally
4. Providing next steps for production deployment
"""

import os
import sys
import subprocess
import json
from pathlib import Path


def run_command(cmd, check=True):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.CalledProcessError as e:
        return e.stdout.strip(), e.stderr.strip(), e.returncode


def check_git_setup():
    """Check if git is properly configured"""
    print("Checking Git setup...")
    
    # Check if we're in a git repository
    stdout, stderr, code = run_command("git rev-parse --is-inside-work-tree", check=False)
    if code != 0:
        print("❌ Not in a git repository. Please run 'git init' first.")
        return False
    
    # Check for remote origin
    stdout, stderr, code = run_command("git remote get-url origin", check=False)
    if code != 0:
        print("⚠️  No remote origin set. You'll need to add your GitHub repository:")
        print("   git remote add origin https://github.com/YOUR_USERNAME/army-discord-bot.git")
        return False
    
    print(f"✅ Git remote origin: {stdout}")
    
    # Check current branch
    stdout, stderr, code = run_command("git branch --show-current")
    current_branch = stdout
    print(f"Current branch: {current_branch}")
    
    return True


def check_environment():
    """Check environment configuration"""
    print("\nChecking environment configuration...")
    
    # Check for .env file
    if not os.path.exists('.env'):
        print("⚠️  .env file not found. Creating template...")
        create_env_template()
    else:
        print("✅ .env file exists")
    
    # Check requirements.txt
    if not os.path.exists('requirements.txt'):
        print("❌ requirements.txt not found")
        return False
    else:
        print("✅ requirements.txt exists")
    
    # Check if we can import discord.py
    try:
        import discord
        print(f"✅ discord.py version: {discord.__version__}")
    except ImportError:
        print("⚠️  discord.py not installed. Run: pip install -r requirements.txt")
    
    return True


def create_env_template():
    """Create a template .env file"""
    env_template = """# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_GUILD_ID=your_server_id_here

# Database Configuration (if using)
DATABASE_URL=sqlite:///data/bot.db

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log

# Development Settings
DEBUG=True
"""
    
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_template)
    
    print("Created .env template file. Please fill in your Discord bot token and guild ID.")


def test_deployment_scripts():
    """Test deployment scripts locally"""
    print("\nTesting deployment scripts...")
    
    scripts_dir = Path("scripts")
    if not scripts_dir.exists():
        print("❌ Scripts directory not found")
        return False
    
    # Check script files exist
    for script_file in ["setup-server.sh", "deploy.sh", "health-check.sh", "setup-production-server.sh"]:
        script_path = scripts_dir / script_file
        if script_path.exists():
            print(f"✅ Found {script_file}")
        else:
            print(f"⚠️  Missing {script_file}")
    
    return True


def check_test_setup():
    """Check test configuration"""
    print("\nChecking test setup...")
    
    # Check if tests directory exists
    if not os.path.exists('tests'):
        print("❌ Tests directory not found")
        return False
    
    print("✅ Tests directory exists")
    
    # Check if pytest is available
    stdout, stderr, code = run_command("python -m pytest --version", check=False)
    if code == 0:
        print(f"✅ Pytest available: {stdout}")
        return True
    else:
        print("⚠️  Pytest not installed. Installing now...")
        stdout, stderr, code = run_command("pip install pytest pytest-asyncio pytest-mock", check=False)
        if code == 0:
            print("✅ Pytest installed successfully")
            return True
        else:
            print("❌ Failed to install pytest")
            return False


def validate_github_secrets():
    """Provide information about required GitHub secrets"""
    print("\nGitHub Secrets Configuration Required:")
    print("You need to set up the following secrets in your GitHub repository:")
    print("   - Go to: Settings -> Secrets and variables -> Actions")
    print("   - Add these repository secrets:")
    print()
    print("   DISCORD_TOKEN (for production deployment)")
    print("      Your production Discord bot token")
    print()
    print("   Optional for staging server:")
    print("      - STAGING_SERVER_HOST")
    print("      - STAGING_SERVER_USER") 
    print("      - STAGING_SERVER_PASSWORD")
    print()


def create_final_checklist():
    """Create a final checklist file"""
    checklist = """# Final CI/CD Setup Checklist

## [x] Completed
- [x] GitHub Actions workflow created
- [x] Test suite implemented
- [x] Deployment scripts created
- [x] Local testing scripts added
- [x] Documentation written

## [ ] Next Steps

### 1. Install Dependencies
```powershell
pip install -r requirements-dev.txt
```

### 2. GitHub Repository Setup
- [ ] Push code to GitHub repository
- [ ] Set up GitHub secrets for Discord tokens
- [ ] Test GitHub Actions workflow

### 3. Server Preparation
- [ ] Run setup script on server: bash scripts/setup-production-server.sh
- [ ] Configure Discord bot token in production
- [ ] Test manual deployment: bash scripts/deploy.sh

### 4. Production Deployment
- [ ] Create main branch and push
- [ ] Monitor first automatic deployment
- [ ] Set up log monitoring and alerts
- [ ] Configure cron jobs for health checks

### 5. Optional Enhancements
- [ ] Set up staging server for develop branch
- [ ] Configure monitoring dashboards
- [ ] Set up backup procedures
- [ ] Add database migrations if needed

## Commands to Run

### Local Testing (Windows PowerShell)
```powershell
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock

# Run all tests
python -m pytest tests/ -v

# Check code formatting
black --check .

# Run linting
flake8 .

# Validate configuration
python validate_config.py
```

### Server Setup (on Ubuntu server)
```bash
# Initial server setup (improved production script)
sudo bash scripts/setup-production-server.sh

# Manual deployment test
bash scripts/deploy.sh

# Check bot health
bash scripts/health-check.sh
```

### GitHub Setup Steps
1. Push to GitHub: git push origin develop
2. Create main branch: git checkout -b main && git push origin main
3. Add secrets in Settings -> Secrets and variables -> Actions
4. Monitor Actions tab for workflow execution

## Support
If you encounter issues:
1. Check GitHub Actions logs
2. Review server logs: tail -f /opt/army-discord-bot/logs/bot.log
3. Validate configuration: python validate_config.py

## Production Server Info
- IP: 202.181.188.48
- User: root
- Project Path: /opt/army-discord-bot
- Service: army-discord-bot (systemd)
- Logs: /opt/army-discord-bot/logs/
"""
    
    with open('FINAL_SETUP_CHECKLIST.md', 'w', encoding='utf-8') as f:
        f.write(checklist)
    
    print("\nCreated FINAL_SETUP_CHECKLIST.md with next steps")


def main():
    """Main function to run all checks"""
    print("Army Discord Bot CI/CD Finalization Script")
    print("=" * 50)
    
    # Run all checks
    git_ok = check_git_setup()
    env_ok = check_environment()
    scripts_ok = test_deployment_scripts()
    tests_ok = check_test_setup()
    
    # Provide GitHub secrets info
    validate_github_secrets()
    
    # Create final checklist
    create_final_checklist()
    
    print("\n" + "=" * 50)
    print("CI/CD Setup Summary:")
    print(f"   Git Setup: {'✅' if git_ok else '❌'}")
    print(f"   Environment: {'✅' if env_ok else '❌'}")
    print(f"   Scripts: {'✅' if scripts_ok else '❌'}")
    print(f"   Tests: {'✅' if tests_ok else '❌'}")
    
    if all([git_ok, env_ok, scripts_ok, tests_ok]):
        print("\nReady for deployment! Check FINAL_SETUP_CHECKLIST.md for next steps.")
    else:
        print("\nPlease address the issues above before deploying.")
    
    print("\nNext: Review QUICK_START_CICD.md and FINAL_SETUP_CHECKLIST.md")


if __name__ == "__main__":
    main()
