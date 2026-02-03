# Пользователь Anaconda

Для безопасности и управления проектом создан отдельный пользователь `anaconda`.

## 📋 Информация о пользователе

```
Имя: anaconda
Группа: anaconda
Home директория: /home/anaconda
Shell: /bin/bash
```

## 🔐 Права доступа

### Docker права
- Пользователь `anaconda` добавлен в группу `docker`
- Может запускать docker контейнеры без sudo
- Может использовать docker-compose

### Sudo права
Файл: `/etc/sudoers.d/anaconda`

```bash
# Команды, доступные без пароля:
- /usr/bin/docker          # Docker CLI
- /usr/bin/docker-compose  # Docker Compose
- /bin/systemctl           # Systemctl (управление сервисами)
```

### Права доступа на файлы
- Директория проекта: `/opt/anaconda_mvp`
- Владелец: `anaconda:anaconda`
- Права: `755` на директории, `644` на файлы
- `.env` файл: `600` (только для чтения пользователем)

## 🚀 Команды для работы с проектом

```bash
# Под пользователем anaconda:

# Запуск docker-compose
cd /opt/anaconda_mvp
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка контейнеров
docker-compose down

# Проверка статуса контейнеров
docker-compose ps

# Перезагрузка API контейнера
docker-compose restart anaconda-api
```

## 🔄 SSH доступ для anaconda

```bash
# Добавьте SSH ключ для пользователя anaconda
ssh-copy-id -i ~/.ssh/id_rsa anaconda@31.59.106.120

# Подключитесь под пользователем anaconda
ssh anaconda@31.59.106.120

# Проверьте права
id
# uid=1000(anaconda) gid=1000(anaconda) groups=1000(anaconda),999(docker)
```

## 📝 Пример работы проекта

```bash
# SSH на сервер
ssh anaconda@31.59.106.120

# Перейти в директорию проекта
cd /opt/anaconda_mvp

# Запустить контейнеры
docker-compose up -d

# Проверить статус
docker-compose ps

# Просмотреть логи API
docker-compose logs anaconda-api

# Проверить здоровье API
curl http://localhost:8000/health

# Получить список сообщений
curl http://localhost:8000/api/messages | jq
```

## 🔒 Безопасность

1. **Sudo без пароля** - ограничены только необходимые команды
2. **Docker группа** - позволяет работать с контейнерами без sudo
3. **Домашняя директория** - отдельное место для хранения конфигов
4. **Обычный пользователь** - не root, что снижает риски

## ⚠️ Важно

- Пользователь `anaconda` НЕ может запускать привилегированные команды
- Может только управлять docker и systemctl для сервисов
- Файл `.env` защищен от чтения другими пользователями
- Для смены пароля используйте: `sudo passwd anaconda`

## 🆘 Troubleshooting

### Пользователь не может запустить docker

```bash
# Проверьте, что пользователь в группе docker
id anaconda

# Если нет - добавьте:
sudo usermod -aG docker anaconda

# Перезагрузитесь или выполните:
newgrp docker
```

### Sudo требует пароль

```bash
# Проверьте файл sudoers
sudo visudo -f /etc/sudoers.d/anaconda

# Должна быть строка:
# anaconda ALL=(ALL) NOPASSWD: /usr/bin/docker, /usr/bin/docker-compose, /bin/systemctl
```

### Нет прав на директорию проекта

```bash
# Переустановите права (от root):
sudo chown -R anaconda:anaconda /opt/anaconda_mvp
sudo chmod -R u+rwx,g+rx,o+rx /opt/anaconda_mvp
```
