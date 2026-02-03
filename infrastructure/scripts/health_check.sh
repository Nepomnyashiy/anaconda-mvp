#!/bin/bash
# Скрипт для проверки здоровья развернутой системы

ENVIRONMENT=${1:-production}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

echo "🏥 Проверка здоровья системы - $ENVIRONMENT"
echo "=============================================="

# Получение хоста из инвентаря
HOST=$(grep -A 5 "^[ ]*$ENVIRONMENT:" "$SCRIPT_DIR/inventory.yml" | grep "ansible_host:" | awk '{print $2}')

if [ -z "$HOST" ]; then
    echo "❌ Хост не найден в инвентаре для $ENVIRONMENT"
    exit 1
fi

echo "📍 Хост: $HOST"
echo ""

# Проверка API
echo "🔍 Проверка API (port 8000)..."
if curl -s http://$HOST:8000/health | jq . 2>/dev/null; then
    echo "✅ API здоров"
else
    echo "❌ API не отвечает"
fi

echo ""

# Проверка Web
echo "🔍 Проверка Web UI (port 80)..."
if curl -s http://$HOST:80/ > /dev/null 2>&1; then
    echo "✅ Web UI доступен"
else
    echo "❌ Web UI не доступен"
fi

echo ""

# Проверка сообщений
echo "📊 Последние сообщения:"
curl -s http://$HOST:8000/api/messages | jq '.[0:3] | .[] | {id, source, sender}' 2>/dev/null || echo "❌ Ошибка получения сообщений"

echo ""
echo "✓ Проверка завершена"
