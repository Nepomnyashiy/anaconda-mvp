# Infrastructure Directory - Ansible Deployment

Быстрая справка по развертыванию системы с помощью Ansible.

## 📋 Быстрый старт

### 1️⃣ Подготовка SSH ключей

```bash
cd infrastructure
bash scripts/setup_ssh.sh
```

### 2️⃣ Настройка inventory и переменных

```bash
# Отредактируйте инвентарь
nano inventory.yml

# Обновите переменные хостов
nano host_vars/production.yml
```

### 3️⃣ Тест развертывания (Dry-Run)

```bash
bash scripts/test_deploy.sh localhost_dev
```

### 4️⃣ Развертывание

```bash
# Development (локально)
bash scripts/deploy.sh localhost_dev

# Production
bash scripts/deploy.sh production
```

### 5️⃣ Проверка здоровья

```bash
bash scripts/health_check.sh production
```

## 📁 Структура файлов

| Файл | Описание |
|------|---------|
| `ansible.cfg` | Конфигурация Ansible |
| `inventory.yml` | Список хостов и переменные |
| `deploy.yml` | Основной playbook |
| `roles/docker/` | Установка Docker |
| `roles/project/` | Развертывание проекта |
| `roles/ssl/` | SSL сертификаты |
| `group_vars/` | Переменные для групп хостов |
| `host_vars/` | Переменные для конкретных хостов |
| `scripts/` | Вспомогательные скрипты |

## 🔑 Переменные

### Обязательные

- `ansible_host` - IP адрес целевого хоста
- `ansible_user` - пользователь SSH (обычно root)
- `project_dir` - путь проекта на целевом хосте
- `postgres_password` - пароль БД

### Опциональные

- `telegram_bot_token` - Telegram токен
- `email_imap_user` - Email для IMAP
- `domain_name` - Домен для SSL (production)

## 🚀 Примеры команд

```bash
# Прямой запуск playbook
ansible-playbook -i inventory.yml deploy.yml -e "deploy_target=production"

# С запросом пароля
ansible-playbook -i inventory.yml deploy.yml -e "deploy_target=production" -k

# Только определенные теги
ansible-playbook -i inventory.yml deploy.yml -t docker

# Verbose вывод
ansible-playbook -i inventory.yml deploy.yml -vvv

# Проверка подключения
ansible -i inventory.yml all -m ping
```

## 🔐 Безопасность

### Для production используйте Vault:

```bash
# Создать зашифрованный файл с секретами
ansible-vault create group_vars/webservers_vault.yml

# Запуск с Vault паролем
ansible-playbook -i inventory.yml deploy.yml --ask-vault-pass
```

## ❌ Troubleshooting

| Проблема | Решение |
|----------|---------|
| "ansible-playbook not found" | `pip install ansible` |
| SSH: "Permission denied" | Проверьте SSH ключи, используйте `-k` флаг |
| "Python not found" | На целевом хосте установите python3 |
| "Docker not running" | `ssh root@host "systemctl restart docker"` |

## 📖 Документация

- [Ansible Documentation](https://docs.ansible.com/)
- [README.md](README.md) - Полная документация
- [host_vars/production.yml](host_vars/production.yml) - Пример конфигурации

## 📞 Поддержка

Полная документация находится в [README.md](README.md)

Скрипты:
- `setup_ssh.sh` - Подготовка SSH ключей
- `deploy.sh` - Запуск развертывания
- `test_deploy.sh` - Тест в режиме dry-run
- `health_check.sh` - Проверка здоровья системы
