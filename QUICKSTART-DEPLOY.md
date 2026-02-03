# Quick Start: GitHub Actions Deployment

## За 5 минут готовый CI/CD 🚀

### Шаг 1: На сервере (один раз)

```bash
# Клонируйте репо и запустите скрипт
cd ~
bash ./kip-service/anaconda_mvp/infrastructure/setup-deploy.sh

# Скрипт покажет SSH ключ для GitHub
# Скопируйте ВЕСЬ вывод между ====
```

### Шаг 2: На GitHub

1. Перейдите: **Settings → Secrets and variables → Actions**
2. **New repository secret** и добавьте:

| Secret | Значение |
|--------|----------|
| `DEPLOY_HOST` | IP или домен сервера (192.168.x.x или anaconda.domain.com) |
| `DEPLOY_USER` | Имя пользователя на сервере (nsadmin) |
| `DEPLOY_SSH_KEY` | Приватный ключ из setup-deploy.sh вывода |
| `DEPLOY_PORT` | SSH порт (опционально, по умолчанию 22) |

### Шаг 3: Тестирование

```bash
# На ПК, в папке проекта
git add .
git commit -m "test: enable CI/CD"
git push origin main

# Перейдите на GitHub → Actions
# Смотрите логи деплоя в реальном времени ✨
```

---

## Что происходит при каждом push в main:

```
Push to main
    ↓
GitHub Actions triggered
    ↓
SSH в сервер
    ↓
git pull (обновление кода)
    ↓
docker-compose build (пересборка образов)
    ↓
docker-compose up -d (запуск)
    ↓
Health check (проверка доступности)
    ↓
✅ Deployment complete
```

---

## Полезные команды

```bash
# Смотреть статус контейнеров
docker-compose ps

# Смотреть логи
docker-compose logs -f

# Остановить
docker-compose down

# Перезапустить
docker-compose restart

# Провести обновление вручную
cd /home/nsadmin/kip-service/anaconda_mvp
git pull
docker-compose up -d --build
```

---

## Troubleshooting

### ❌ "fatal: unable to access 'https://github.com/...': Could not resolve host"
Проверьте интернет соединение на сервере.

### ❌ "docker: command not found"
```bash
sudo apt-get install docker.io docker-compose
```

### ❌ "Permission denied (publickey)"
Скопируйте SSH ключ полностью в GitHub Secret (включая `-----BEGIN` и `-----END`).

### ❌ "docker-compose: Permission denied"
```bash
sudo usermod -aG docker $USER
newgrp docker
```

---

## Откат версии

```bash
ssh nsadmin@DEPLOY_HOST
cd /home/nsadmin/kip-service/anaconda_mvp
git log --oneline
git reset --hard <COMMIT_HASH>
docker-compose up -d --build
```

---

## Интеграция с Slack (опционально)

Если нужны уведомления о деплое:

1. Создайте webhook в Slack workspace
2. Добавьте secret `SLACK_WEBHOOK_URL` на GitHub
3. Раскомментируйте блок в `.github/workflows/deploy.yml`

---

**Готово! 🎉 Непрерывная интеграция и деплой настроены.**
