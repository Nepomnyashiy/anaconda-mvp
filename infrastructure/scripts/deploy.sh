#!/bin/bash
# Скрипт для развертывания на production

set -e

ENVIRONMENT=${1:-production}
VERBOSE=${2:-}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

echo "🚀 Развертывание Anaconda MVP - $ENVIRONMENT"
echo "=================================================="

# Проверка Ansible
if ! command -v ansible-playbook &> /dev/null; then
    echo "❌ Ansible не установлен. Установите:"
    echo "   pip install ansible"
    exit 1
fi

# Проверка инвентаря
if [ ! -f "$SCRIPT_DIR/inventory.yml" ]; then
    echo "❌ Файл inventory.yml не найден"
    exit 1
fi

# Подготовка параметров
EXTRA_VARS="-e deploy_target=$ENVIRONMENT"

# Параметры для production
if [ "$ENVIRONMENT" == "production" ]; then
    EXTRA_VARS="$EXTRA_VARS -k"  # Запрос SSH пароля
    echo "⚠️  Production развертывание - потребуется пароль"
fi

# Verbose режим
if [ ! -z "$VERBOSE" ]; then
    VERBOSE_FLAG="-vvv"
else
    VERBOSE_FLAG=""
fi

# Проверка подключения
echo "🔍 Проверка подключения к хостам..."
ansible -i "$SCRIPT_DIR/inventory.yml" "$ENVIRONMENT" -m ping

# Запуск playbook
echo ""
echo "▶️  Запуск развертывания..."
ansible-playbook -i "$SCRIPT_DIR/inventory.yml" "$SCRIPT_DIR/deploy.yml" \
    $EXTRA_VARS $VERBOSE_FLAG

echo ""
echo "✅ Развертывание завершено!"
echo ""
echo "Проверьте здоровье приложения:"
echo "  curl http://$(grep 'ansible_host:' $SCRIPT_DIR/inventory.yml | grep -A1 "$ENVIRONMENT" | tail -1 | awk '{print $2}'):8000/health"
