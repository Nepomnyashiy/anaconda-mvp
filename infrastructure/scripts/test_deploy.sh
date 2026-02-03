#!/bin/bash
# Скрипт для тестирования развертывания (dry-run)

set -e

ENVIRONMENT=${1:-localhost_dev}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

echo "🧪 Тестирование развертывания - $ENVIRONMENT (Dry-Run)"
echo "=========================================================="

# Проверка Ansible
if ! command -v ansible-playbook &> /dev/null; then
    echo "❌ Ansible не установлен. Установите:"
    echo "   pip install ansible"
    exit 1
fi

# Запуск playbook в dry-run режиме
ansible-playbook -i "$SCRIPT_DIR/inventory.yml" "$SCRIPT_DIR/deploy.yml" \
    -e "deploy_target=$ENVIRONMENT" \
    -C \
    -v

echo ""
echo "✅ Тест завершен! Команда выше показывает что будет выполнено."
echo ""
echo "Для реального развертывания используйте:"
echo "  cd infrastructure"
echo "  bash scripts/deploy.sh $ENVIRONMENT"
