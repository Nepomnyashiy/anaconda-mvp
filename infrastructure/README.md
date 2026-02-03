# Ansible Развертывание Anaconda MVP

Этот каталог содержит Ansible конфигурацию для развертывания платформы Anaconda MVP по SSH.

## Структура

```
infrastructure/
├── ansible.cfg              # Конфигурация Ansible
├── inventory.yml            # Инвентарь хостов
├── deploy.yml               # Основной playbook
├── roles/
│   ├── docker/              # Роль для установки Docker
│   ├── project/             # Роль для развертывания проекта
│   └── ssl/                 # Роль для SSL сертификатов
├── group_vars/              # Переменные для групп хостов
│   ├── all.yml              # Глобальные переменные
│   ├── webservers.yml       # Production хосты
│   └── dev_machines.yml     # Development машины
├── host_vars/               # Переменные для конкретных хостов
│   ├── production.yml       # Production хост
│   └── staging.yml          # Staging хост
└── scripts/                 # Вспомогательные скрипты
```

## Требования

### На управляющей машине (откуда запускаете Ansible)

```bash
# Установка Ansible
pip install ansible>=2.9

# Или через apt (Ubuntu/Debian)
sudo apt-get install ansible
```

### На целевых хостах

- SSH доступ (обычно port 22)
- Python 3.6+ (для Ansible)
- sudo доступ или root пользователь
- Ubuntu/Debian система

## Быстрый старт

### 1. Подготовка инвентаря

Отредактируйте `inventory.yml` с вашими IP адресами:

```yaml
all:
  hosts:
    production:
      ansible_host: YOUR_PRODUCTION_IP
      ansible_user: root  # или sudo пользователь
```

### 2. Подготовка переменных

Заполните `host_vars/production.yml`:

```yaml
ansible_user: root
project_dir: /opt/anaconda_mvp
git_repo: "https://github.com/your-org/kip-service.git"
```

### 3. Тестирование подключения

```bash
cd infrastructure

# Проверка подключения к хостам
ansible -i inventory.yml all -m ping
```

### 4. Запуск развертывания

```bash
# Development машина (локально)
ansible-playbook -i inventory.yml deploy.yml -e "deploy_target=localhost_dev"

# Staging
ansible-playbook -i inventory.yml deploy.yml -e "deploy_target=staging"

# Production (осторожно!)
ansible-playbook -i inventory.yml deploy.yml -e "deploy_target=production" -k

# С повышением привилегий
ansible-playbook -i inventory.yml deploy.yml -e "deploy_target=production" -K
```

### 5. Мониторинг развертывания

```bash
# Просмотр логов
tail -f ansible.log

# Только определенные теги
ansible-playbook -i inventory.yml deploy.yml -t docker

# Проверка перед запуском (dry-run)
ansible-playbook -i inventory.yml deploy.yml -C
```

## Теги (Tags)

Разные части развертывания помечены тегами:

```bash
# Установка Docker только
ansible-playbook -i inventory.yml deploy.yml -t docker

# Развертывание проекта
ansible-playbook -i inventory.yml deploy.yml -t project

# SSL сертификаты
ansible-playbook -i inventory.yml deploy.yml -t ssl

# Проверка здоровья
ansible-playbook -i inventory.yml deploy.yml -t verify
```

## Переменные среды

### Production

```bash
# Безопасные переменные в Ansible Vault
ansible-vault create infrastructure/group_vars/webservers_vault.yml

# Использование Vault при запуске
ansible-playbook -i inventory.yml deploy.yml --ask-vault-pass
```

### Development

```bash
# Для локального тестирования
ansible-playbook -i inventory.yml deploy.yml -e "deploy_target=localhost_dev" -v
```

## SSH Настройка

### Без пароля (рекомендуется)

```bash
# На управляющей машине
ssh-keygen -t rsa -N "" -f ~/.ssh/ansible_key

# На целевом хосте
ssh-copy-id -i ~/.ssh/ansible_key.pub root@31.59.106.120

# В inventory.yml
all:
  vars:
    ansible_ssh_private_key_file: ~/.ssh/ansible_key
```

### С паролем

```bash
# Интерактивно запросит пароль
ansible-playbook -i inventory.yml deploy.yml -k
```

## Troubleshooting

### Ошибка подключения

```bash
# Проверка SSH подключения
ssh -i ~/.ssh/ansible_key root@31.59.106.120

# Тестирование с verbose
ansible -i inventory.yml production -m ping -vvv
```

### Python не найден

```bash
# Установка Python на целевом хосте
ssh root@31.59.106.120 "apt-get update && apt-get install -y python3"
```

### Docker не запускается

```bash
# На целевом хосте
ssh root@31.59.106.120 "systemctl restart docker"
docker-compose ps
```

## Примеры команд

```bash
# Проверка конкретного хоста
ansible-playbook -i inventory.yml deploy.yml -l production

# С дополнительным выводом
ansible-playbook -i inventory.yml deploy.yml -vvv

# Только handlers (перезагрузка сервисов)
ansible-playbook -i inventory.yml deploy.yml -t handlers

# Пропуск определенных тегов
ansible-playbook -i inventory.yml deploy.yml --skip-tags ssl

# Запуск с кастомными переменными
ansible-playbook -i inventory.yml deploy.yml \
  -e "postgres_password=my_secure_password" \
  -e "telegram_bot_token=123456:ABC..."
```

## Файлы логов

```bash
# Ansible логи
tail -f infrastructure/ansible.log

# Логи контейнеров на хосте
ssh root@31.59.106.120 "docker-compose -f /opt/anaconda_mvp logs -f"
```

## Безопасность

### 1. Используйте Vault для секретов

```bash
ansible-vault create infrastructure/group_vars/vault.yml
```

### 2. Ограничьте SSH доступ

```bash
# На целевом хосте - только для SSH ключа
PermitRootLogin without-password
PasswordAuthentication no
```

### 3. Используйте become для sudo

```bash
# В inventory.yml
all:
  vars:
    ansible_become: yes
    ansible_become_method: sudo
```

## Последующие развертывания

После первоначального развертывания, для обновления:

```bash
# Обновить код и перезагрузить контейнеры
ansible-playbook -i inventory.yml deploy.yml -e "deploy_target=production" -t project

# Обновить только .env файл
ansible-playbook -i inventory.yml roles/project/tasks/main.yml \
  -e "deploy_target=production" \
  -e "postgres_password=new_password"
```

## Документация

- [Ansible Documentation](https://docs.ansible.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
