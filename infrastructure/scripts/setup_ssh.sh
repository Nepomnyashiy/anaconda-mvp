#!/bin/bash
# Скрипт для подготовки SSH ключей для Ansible развертывания

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
KEY_DIR="$HOME/.ssh"
KEY_NAME="ansible_key"

echo "🔐 Подготовка SSH ключей для Ansible"
echo "========================================"

# Создание ~/.ssh если не существует
if [ ! -d "$KEY_DIR" ]; then
    echo "📁 Создание директории $KEY_DIR"
    mkdir -p "$KEY_DIR"
    chmod 700 "$KEY_DIR"
fi

# Генерирование ключа
if [ ! -f "$KEY_DIR/$KEY_NAME" ]; then
    echo "🔑 Генерирование SSH ключа: $KEY_DIR/$KEY_NAME"
    ssh-keygen -t rsa -b 4096 -N "" -f "$KEY_DIR/$KEY_NAME" -C "ansible@localhost"
    chmod 600 "$KEY_DIR/$KEY_NAME"
    chmod 644 "$KEY_DIR/$KEY_NAME.pub"
    echo "✓ Ключ создан"
else
    echo "✓ Ключ уже существует: $KEY_DIR/$KEY_NAME"
fi

# Вывод инструкций
echo ""
echo "📝 Скопируйте следующую команду на целевой хост (root):"
echo ""
echo "ssh-copy-id -i $KEY_DIR/$KEY_NAME.pub root@YOUR_HOST_IP"
echo ""
echo "Или вручную добавьте содержимое в /root/.ssh/authorized_keys:"
cat "$KEY_DIR/$KEY_NAME.pub"
echo ""
echo "✓ SSH ключи готовы!"
