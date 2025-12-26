#!/bin/bash
# Скрипт для пересборки Docker образа

echo "========================================"
echo "Пересборка Docker образа"
echo "========================================"
echo

echo "Остановка контейнеров..."
docker-compose down || docker compose down

echo
echo "Пересборка образа без кэша..."
docker-compose build --no-cache || docker compose build --no-cache

if [ $? -ne 0 ]; then
    echo
    echo "ОШИБКА при пересборке!"
    exit 1
fi

echo
echo "Запуск контейнеров..."
docker-compose up -d || docker compose up -d

if [ $? -ne 0 ]; then
    echo
    echo "ОШИБКА при запуске!"
    exit 1
fi

echo
echo "========================================"
echo "Готово! Контейнер пересобран и запущен"
echo "========================================"

