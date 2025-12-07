#!/bin/bash

# Скрипт для обновления файлов на сервере
# Использование: ./deploy.sh [user@server:/path/to/Conspect]

# Если аргумент не передан, используем дефолтный сервер
if [ -z "$1" ]; then
    SERVER_PATH="root@77.73.232.142:/root/Conspect"
    echo "Используется сервер по умолчанию: $SERVER_PATH"
else
    SERVER_PATH="$1"
fi

echo "Копирование файлов на сервер..."

# Копируем необходимые файлы
scp docker-compose.yml "$SERVER_PATH/"
scp Dockerfile "$SERVER_PATH/"
scp main.py "$SERVER_PATH/"
scp requirements.txt "$SERVER_PATH/"

echo "Файлы скопированы!"
echo ""
echo "Подключаюсь к серверу для пересборки..."

# Извлекаем хост из SERVER_PATH
SERVER_HOST=$(echo "$SERVER_PATH" | cut -d: -f1)
SERVER_DIR=$(echo "$SERVER_PATH" | cut -d: -f2)

# Подключаемся к серверу и пересобираем
ssh "$SERVER_HOST" "cd $SERVER_DIR && docker-compose down && docker-compose build --no-cache && docker-compose up -d && echo 'Бот пересобран и запущен! Проверьте логи:' && docker-compose logs --tail=20 bot"

