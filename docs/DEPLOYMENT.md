# GitHub Actions Deployment Guide

## Быстрая настройка CI/CD

Этот гайд описывает как настроить автоматический деплой на сервер при push в `main` ветку.

---

## 1. Генерация SSH ключей (на сервере)

Если ключ уже есть, пропустите этот шаг.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/anaconda_deploy -N ""
cat ~/.ssh/anaconda_deploy.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

---

## 2. Добавление GitHub Secrets

Перейдите на GitHub → Settings → Secrets and variables → Actions

Добавьте следующие секреты:

### DEPLOY_HOST
**Значение:** IP адрес или домен сервера (например: `192.168.1.100` или `anaconda.kip-service.ru`)

### DEPLOY_USER
**Значение:** пользователь для SSH (например: `nsadmin`)

### DEPLOY_SSH_KEY
**Значение:** приватный SSH ключ (содержимое `~/.ssh/anaconda_deploy`)

```bash
cat ~/.ssh/anaconda_deploy
```

Скопируйте весь вывод в GitHub Secret.

### DEPLOY_PORT (опционально)
**Значение:** SSH порт (по умолчанию `22`)

---

## 3. Тестирование локально (опционально)

Убедитесь что с вашего ПК SSH доступен:

```bash
ssh -i ~/.ssh/anaconda_deploy nsadmin@DEPLOY_HOST "cd /home/nsadmin/kip-service/anaconda_mvp && git status"
```

---

## 4. Первый деплой

Просто сделайте commit и push:

```bash
git add .
git commit -m "feat: enable GitHub Actions deployment"
git push origin main
```

Перейдите на GitHub → Actions → Deploy to Production и смотрите логи.

---

## Workflow шаги

1. **Checkout** — клонирование кода
2. **Pull latest** — обновление с GitHub
3. **Stop containers** — остановка старых контейнеров
4. **Build images** — сборка Docker образов
5. **Start containers** — запуск новых контейнеров
6. **Health check** — проверка доступности API

---

## Ручной триггер деплоя (без commit)

На странице Actions → Deploy to Production → "Run workflow" → выберите `main` branch.

---

## Troubleshooting

### Ошибка: "Permission denied (publickey)"
- Проверьте что приватный ключ скопирован полностью (включая `-----BEGIN` и `-----END`)
- Убедитесь что публичный ключ добавлен в `~/.ssh/authorized_keys` на сервере

### Ошибка: "docker-compose: command not found"
- Установите docker-compose на сервер:
  ```bash
  sudo apt-get install docker-compose
  ```

### Ошибка: "Could not resolve hostname"
- Проверьте DEPLOY_HOST — должен быть IP или валидный домен

### Health check не прошла
- Проверьте логи контейнера:
  ```bash
  docker-compose logs -f anaconda_api
  ```

---

## Продвинутая конфигурация

### Деплой только при изменении кода (не документации)

Отредактируйте `.github/workflows/deploy.yml`:

```yaml
on:
  push:
    branches:
      - main
    paths:
      - 'anaconda_api/**'
      - 'anaconda_web/**'
      - 'docker-compose.yml'
      - '.github/workflows/deploy.yml'
```

### Слэк уведомления

```yaml
- name: Notify Slack on deployment
  if: always()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "Deployment ${{ job.status }}",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Anaconda Deployment* → ${{ job.status }}\nBranch: main\nCommit: ${{ github.sha }}"
            }
          }
        ]
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

---

## Откат (Rollback)

Если деплой сломал сервер:

```bash
ssh nsadmin@DEPLOY_HOST
cd /home/nsadmin/kip-service/anaconda_mvp
git log --oneline | head -5
git reset --hard <commit-hash>
docker-compose up -d
```

---

## Мониторинг деплоев

```bash
# Смотреть статус контейнеров
docker-compose ps

# Смотреть логи API
docker-compose logs -f anaconda_api

# Смотреть логи веба
docker-compose logs -f anaconda_web

# Проверить здоровье
curl http://localhost:8000/health
```

---

**Готово! 🚀 Теперь каждый push в `main` автоматически деплоится на сервер.**
