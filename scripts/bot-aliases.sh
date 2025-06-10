#!/bin/bash

# Quick Bot Management Aliases
# Source this file in your ~/.bashrc for instant commands

alias bot-status='cd /opt/army-discord-bot && ./scripts/manage.sh status'
alias bot-start='cd /opt/army-discord-bot && ./scripts/manage.sh start'
alias bot-stop='cd /opt/army-discord-bot && ./scripts/manage.sh stop'
alias bot-restart='cd /opt/army-discord-bot && ./scripts/manage.sh restart'
alias bot-kill='cd /opt/army-discord-bot && ./scripts/manage.sh kill'
alias bot-logs='cd /opt/army-discord-bot && ./scripts/manage.sh logs'
alias bot-screen='cd /opt/army-discord-bot && ./scripts/manage.sh screen'
alias bot-deploy='cd /opt/army-discord-bot && ./scripts/manage.sh deploy'

# Quick status check
alias bot='bot-status'

echo "🤖 Bot management aliases loaded!"
echo "Available commands:"
echo "  bot-status  (or just 'bot')"
echo "  bot-start"
echo "  bot-stop" 
echo "  bot-restart"
echo "  bot-kill"
echo "  bot-logs"
echo "  bot-screen"
echo "  bot-deploy"
