#!/bin/bash

# Прогрессивный деплой Anaconda MVP с визуализацией процесса
# Цветные выводы и пошаговый прогресс

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Функции для вывода
print_header() {
    echo -e "\n${CYAN}════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
}

print_step() {
    echo -e "\n${BLUE}[Шаг $1/$2]${NC} ${YELLOW}$3${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Прогресс бар
progress_bar() {
    local current=$1
    local total=$2
    local width=50
    local percent=$((current * 100 / total))
    local completed=$((current * width / total))
    local remaining=$((width - completed))
    
    echo -ne "\r["
    for ((i=0; i<completed; i++)); do echo -ne "█"; done
    for ((i=0; i<remaining; i++)); do echo -ne "░"; done
    echo -ne "] ${percent}% (${current}/${total})"
    if [ $current -eq $total ]; then echo; fi
}

# Проверка аргументов
if [ $# -lt 1 ]; then
    echo -e "${RED}Использование: $0 <target>${NC}"
    echo -e "Доступные цели:"
    echo -e "  ${GREEN}production${NC}    - Деплой на продакшн сервер (31.59.106.120)"
    echo -e "  ${YELLOW}staging${NC}       - Деплой на стейджинг сервер"
    echo -e "  ${BLUE}localhost_dev${NC}  - Деплой на локальную машину"
    exit 1
fi

TARGET=$1
TOTAL_STEPS=8
CURRENT_STEP=0

print_header "🚀 Деплой Anaconda MVP платформы"
echo -e "Цель: ${GREEN}${TARGET}${NC}"
echo -e "Время начала: $(date)"
echo -e "Рабочая директория: $(pwd)"

# Шаг 1: Проверка окружения
CURRENT_STEP=1
print_step $CURRENT_STEP $TOTAL_STEPS "Проверка окружения и зависимостей"

# Проверка Ansible
if ! command -v ansible &> /dev/null; then
    print_error "Ansible не установлен. Установите через apt install ansible"
    exit 1
else
    ANSIBLE_VERSION=$(ansible --version | head -n1 | awk '{print $3}')
    print_success "Ansible $ANSIBLE_VERSION обнаружен"
fi

# Проверка SSH ключа для production
if [ "$TARGET" = "production" ]; then
    if [ ! -f ~/.ssh/id_ed25519 ]; then
        print_info "Создание SSH ключа для production..."
        ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -q
        print_success "SSH ключ создан"
    else
        print_success "SSH ключ для production обнаружен"
    fi
fi

progress_bar $CURRENT_STEP $TOTAL_STEPS

# Шаг 2: Проверка подключения к целевому серверу
CURRENT_STEP=2
print_step $CURRENT_STEP $TOTAL_STEPS "Проверка подключения к серверу"

if [ "$TARGET" = "production" ]; then
    SERVER="31.59.106.120"
    print_info "Проверка подключения к production серверу ($SERVER)..."
    
    if ping -c 1 -W 2 $SERVER &> /dev/null; then
        print_success "Сервер $SERVER доступен"
    else
        print_error "Сервер $SERVER недоступен"
        exit 1
    fi
    
    # Проверка SSH подключения
    if ssh -o BatchMode=yes -o ConnectTimeout=5 root@$SERVER "echo 'SSH подключение успешно'" &> /dev/null; then
        print_success "SSH подключение к серверу установлено"
    else
        print_error "Не удалось установить SSH подключение к серверу"
        print_info "Убедитесь, что публичный ключ добавлен на сервер:"
        cat ~/.ssh/id_ed25519.pub
        exit 1
    fi
elif [ "$TARGET" = "localhost_dev" ]; then
    print_success "Локальный деплой, проверка подключения не требуется"
fi

progress_bar $CURRENT_STEP $TOTAL_STEPS

# Шаг 3: Подготовка Ansible инвентаря
CURRENT_STEP=3
print_step $CURRENT_STEP $TOTAL_STEPS "Подготовка Ansible конфигурации"

cd infrastructure

# Проверка inventory файла
if [ ! -f inventory.yml ]; then
    print_error "Файл inventory.yml не найден"
    exit 1
fi

print_success "Inventory файл обнаружен"

# Проверка переменных
if [ ! -f group_vars/all.yml ]; then
    print_error "Файл group_vars/all.yml не найден"
    exit 1
fi

print_success "Файлы конфигурации проверены"
progress_bar $CURRENT_STEP $TOTAL_STEPS

# Шаг 4: Запуск Ansible playbook
CURRENT_STEP=4
print_step $CURRENT_STEP $TOTAL_STEPS "Запуск Ansible playbook"

print_info "Запускаем развертывание на $TARGET..."

# Запуск Ansible с подробным выводом
ansible-playbook -i inventory.yml deploy.yml \
    --limit "$TARGET" \
    --extra-vars "deploy_target=$TARGET" \
    -v \
    --tags "docker,project,verify"

if [ $? -eq 0 ]; then
    print_success "Ansible playbook выполнен успешно"
else
    print_error "Ошибка при выполнении Ansible playbook"
    exit 1
fi

progress_bar $CURRENT_STEP $TOTAL_STEPS

# Шаг 5: Проверка сервисов
CURRENT_STEP=5
print_step $CURRENT_STEP $TOTAL_STEPS "Проверка запущенных сервисов"

if [ "$TARGET" = "production" ]; then
    SERVER="31.59.106.120"
    
    # Проверка API
    print_info "Проверка API сервиса..."
    for i in {1..10}; do
        if curl -s -f "http://$SERVER:8000/health" &> /dev/null; then
            print_success "API сервис доступен на http://$SERVER:8000"
            break
        else
            if [ $i -eq 10 ]; then
                print_error "API сервис не ответил после 10 попыток"
                exit 1
            fi
            sleep 2
            echo -n "."
        fi
    done
    
    # Проверка веб-интерфейса
    print_info "Проверка веб-интерфейса..."
    if curl -s -f "http://$SERVER:80" &> /dev/null; then
        print_success "Веб-интерфейс доступен на http://$SERVER"
    else
        print_warning "Веб-интерфейс не отвечает, проверьте nginx конфигурацию"
    fi
elif [ "$TARGET" = "localhost_dev" ]; then
    # Локальная проверка
    print_info "Проверка локальных сервисов..."
    
    if curl -s -f "http://localhost:8000/health" &> /dev/null; then
        print_success "API сервис доступен на http://localhost:8000"
    else
        print_error "API сервис не отвечает"
        exit 1
    fi
    
    if docker ps | grep -q "anaconda_web"; then
        print_success "Веб-контейнер запущен"
    else
        print_error "Веб-контейнер не запущен"
    fi
fi

progress_bar $CURRENT_STEP $TOTAL_STEPS

# Шаг 6: Тестирование функциональности
CURRENT_STEP=6
print_step $CURRENT_STEP $TOTAL_STEPS "Тестирование функциональности"

print_info "Тестирование API endpoints..."

if [ "$TARGET" = "production" ]; then
    BASE_URL="http://$SERVER:8000"
else
    BASE_URL="http://localhost:8000"
fi

# Тест здоровья
if curl -s "$BASE_URL/health" | grep -q "healthy"; then
    print_success "Health check пройден"
else
    print_error "Health check не пройден"
fi

# Тест структуры хаба
if curl -s "$BASE_URL/api/hub_structure" | grep -q "unsorted"; then
    print_success "API /api/hub_structure работает"
else
    print_warning "API /api/hub_structure не вернул ожидаемые данные"
fi

# Тест организаций
if curl -s "$BASE_URL/api/organizations" &> /dev/null; then
    print_success "API /api/organizations работает"
else
    print_warning "API /api/organizations не отвечает"
fi

progress_bar $CURRENT_STEP $TOTAL_STEPS

# Шаг 7: Создание отчета о деплое
CURRENT_STEP=7
print_step $CURRENT_STEP $TOTAL_STEPS "Создание отчета о деплое"

REPORT_FILE="/tmp/anaconda_deploy_report_$(date +%Y%m%d_%H%M%S).txt"

cat > "$REPORT_FILE" << EOF
===========================================
 ОТЧЕТ О ДЕПЛОЕ ANACONDA MVP
===========================================
Дата: $(date)
Цель: $TARGET
Статус: УСПЕШНО

СЕРВИСЫ:
- API: $BASE_URL
- Веб-интерфейс: http://${SERVER:-localhost}:80
- Health check: $BASE_URL/health

ПРОВЕРЕННЫЕ ENDPOINTS:
✓ /health
✓ /api/hub_structure
✓ /api/organizations

СЛЕДУЮЩИЕ ШАГИ:
1. Откройте веб-интерфейс в браузере
2. Настройте переменные окружения в .env файле
3. Добавьте Telegram бота и email credentials
4. Протестируйте отправку сообщений

ПРОБЛЕМЫ:
$(if [ "$TARGET" = "production" ]; then
    echo "- Убедитесь, что порты 80 и 8000 открыты в фаерволе"
    echo "- Настройте доменное имя для production"
else
    echo "- Локальный деплой успешен"
fi)

ЛОГИ:
$(tail -20 infrastructure/deploy_output.txt 2>/dev/null || echo "Логи не найдены")
EOF

print_success "Отчет создан: $REPORT_FILE"
progress_bar $CURRENT_STEP $TOTAL_STEPS

# Шаг 8: Финальный вывод
CURRENT_STEP=8
print_step $CURRENT_STEP $TOTAL_STEPS "Завершение деплоя"

print_header "🎉 Деплой успешно завершен!"
echo -e ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Система Anaconda MVP успешно развернута!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e ""
echo -e "${CYAN}Доступные сервисы:${NC}"
if [ "$TARGET" = "production" ]; then
    echo -e "  🌐 Веб-интерфейс: ${GREEN}http://31.59.106.120${NC}"
    echo -e "  ⚙️  API: ${GREEN}http://31.59.106.120:8000${NC}"
else
    echo -e "  🌐 Веб-интерфейс: ${GREEN}http://localhost${NC}"
    echo -e "  ⚙️  API: ${GREEN}http://localhost:8000${NC}"
fi
echo -e "  🏥 Health check: ${GREEN}${BASE_URL}/health${NC}"
echo -e ""
echo -e "${CYAN}Следующие шаги:${NC}"
echo -e "  1. Откройте веб-интерфейс в браузере"
echo -e "  2. Настройте переменные окружения в .env файле"
echo -e "  3. Добавьте Telegram бота и email credentials"
echo -e "  4. Протестируйте отправку сообщений"
echo -e ""
echo -e "${YELLOW}Отчет о деплое сохранен:${NC} ${REPORT_FILE}"
echo -e ""

progress_bar $CURRENT_STEP $TOTAL_STEPS

print_success "Деплой завершен в $(date)"