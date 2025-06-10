#!/bin/bash

# Simple Bot Control Script
# Управление ботом на Ubuntu сервере без входа в screen сессию

SCREEN_SESSION="army-bot"
APP_DIR="/opt/army-discord-bot"

case "$1" in
    "status")
        echo "🔍 Статус бота:"
        if screen -list | grep -q "$SCREEN_SESSION"; then
            echo "✅ Бот запущен в screen сессии '$SCREEN_SESSION'"
            echo "📊 Процессы Python:"
            ps aux | grep "python3 app.py" | grep -v grep || echo "❌ Python процесс не найден"
        else
            echo "❌ Screen сессия '$SCREEN_SESSION' не найдена"
            if pgrep -f "python3 app.py" > /dev/null; then
                echo "⚠️ Но Python процесс работает вне screen"
                ps aux | grep "python3 app.py" | grep -v grep
            fi
        fi
        ;;
        
    "stop")
        echo "🛑 Остановка бота..."
        
        # Отправляем Ctrl+C в screen сессию
        if screen -list | grep -q "$SCREEN_SESSION"; then
            echo "📨 Отправка Ctrl+C в screen сессию..."
            screen -S "$SCREEN_SESSION" -p 0 -X stuff "^C"
            sleep 3
            
            # Проверяем, остановился ли процесс
            if screen -list | grep -q "$SCREEN_SESSION"; then
                echo "⏳ Ожидание завершения..."
                sleep 5
                
                # Если всё ещё работает, убиваем сессию
                if screen -list | grep -q "$SCREEN_SESSION"; then
                    echo "🔨 Принудительное завершение screen сессии..."
                    screen -S "$SCREEN_SESSION" -X quit
                fi
            fi
        fi
        
        # Убиваем оставшиеся Python процессы
        if pgrep -f "python3 app.py" > /dev/null; then
            echo "🔨 Завершение Python процессов..."
            pkill -f "python3 app.py"
            sleep 2
        fi
        
        echo "✅ Бот остановлен"
        ;;
        
    "start")
        echo "▶️ Запуск бота..."
        
        if screen -list | grep -q "$SCREEN_SESSION"; then
            echo "⚠️ Бот уже запущен в screen сессии"
            exit 1
        fi
        
        if pgrep -f "python3 app.py" > /dev/null; then
            echo "⚠️ Python процесс уже запущен"
            exit 1
        fi
        
        cd "$APP_DIR"
        screen -dmS "$SCREEN_SESSION" bash -c "python3 app.py 2>&1 | tee logs/bot.log"
        sleep 3
        
        if screen -list | grep -q "$SCREEN_SESSION"; then
            echo "✅ Бот запущен в screen сессии '$SCREEN_SESSION'"
        else
            echo "❌ Не удалось запустить бота"
            exit 1
        fi
        ;;
        
    "restart")
        echo "🔄 Перезапуск бота..."
        $0 stop
        sleep 3
        $0 start
        ;;
        
    "kill")
        echo "💀 Принудительное завершение бота..."
        screen -S "$SCREEN_SESSION" -X quit 2>/dev/null || true
        pkill -9 -f "python3 app.py" 2>/dev/null || true
        echo "✅ Все процессы убиты"
        ;;
        
    "logs")
        echo "📄 Последние 50 строк логов:"
        echo "=============================="
        if [ -f "$APP_DIR/logs/bot.log" ]; then
            tail -50 "$APP_DIR/logs/bot.log"
        else
            echo "❌ Лог файл не найден"
        fi
        ;;
        
    "watch")
        echo "👀 Мониторинг логов (Ctrl+C для выхода):"
        echo "========================================"
        if [ -f "$APP_DIR/logs/bot.log" ]; then
            tail -f "$APP_DIR/logs/bot.log"
        else
            echo "❌ Лог файл не найден"
        fi
        ;;
        
    *)
        echo "🤖 Управление Army Discord Bot"
        echo ""
        echo "Использование: $0 {command}"
        echo ""
        echo "Команды:"
        echo "  status   - Показать статус бота"
        echo "  start    - Запустить бота"
        echo "  stop     - Остановить бота (эмуляция Ctrl+C)"
        echo "  restart  - Перезапустить бота"
        echo "  kill     - Принудительно убить все процессы"
        echo "  logs     - Показать последние логи"
        echo "  watch    - Следить за логами в реальном времени"
        echo ""
        echo "Примеры:"
        echo "  $0 status"
        echo "  $0 stop"
        echo "  $0 start"
        ;;
esac
