# Шахматы Онлайн

Веб-приложение для игры в шахматы онлайн с поддержкой мультиплеера.

## Архитектура

### Структура проекта
```
chess-online/
├── backend/           # Backend сервер (FastAPI)
│   ├── main.py       # Основной файл сервера с WebSocket endpoints
│   ├── game_logic.py # Логика шахматной игры
│   ├── rating.py     # Система рейтинга Elo
│   ├── database.py   # Модель базы данных SQLite
│   ├── auth.py       # Система аутентификации
│   ├── schemas.py    # Pydantic схемы для валидации
│   └── logger.py     # Система логирования
├── shared/           # Общий код для обеих версий
│   ├── chess_engine.py # Общий шахматный движок
│   ├── exceptions.py  # Кастомные исключения
│   └── constants.py  # Общие константы
└── frontend/         # Frontend приложение
```

### Основные компоненты

#### Backend (FastAPI)
- **main.py**: WebSocket сервер для реального времени, управление комнатами, matchmaking
- **game_logic.py**: Логика шахматной игры (использует общий движок из shared/)
- **database.py**: Работа с SQLite (игроки, рейтинги, история игр)
- **rating.py**: Система рейтинга Elo с персистентным хранением
- **schemas.py**: Валидация всех WebSocket сообщений через Pydantic
- **auth.py**: JWT-аутентификация с хешированием паролей (v2.8+)
- **routes/**: HTTP endpoints (auth, game, tournament, matchmaking)
- **services/**: Бизнес-логика (email, matchmaking)
- **middleware/**: Промежуточное ПО (auth, rate limiting)
- **handlers/**: Обработчики WebSocket сообщений

#### Shared модули
- **chess_engine.py**: Общий шахматный движок с оптимизированной проверкой шаха
- **exceptions.py**: Кастомные исключения для обработки ошибок
- **constants.py**: Централизованные константы

### API Endpoints

#### WebSocket
- `/ws/{room_id}/{player_id}` - Подключение к игровой комнате
- `/ws/matchmaking/{player_id}` - Поиск соперника

#### HTTP
- `/` - Главная страница (frontend/index.html)
- `/v2.5`, `/v2.6`, `/v2.7`, `/v2.8` - Различные версии frontend
- `/api/auth/*` - Endpoints аутентификации (v2.8+)
  - `POST /api/auth/register` - Регистрация
  - `POST /api/auth/login` - Вход
  - `POST /api/auth/logout` - Выход
  - `POST /api/auth/refresh` - Обновление токена
  - `GET /api/auth/verify-email` - Верификация email
  - `POST /api/auth/forgot-password` - Запрос сброса пароля
  - `POST /api/auth/reset-password` - Сброс пароля
  - `GET /api/auth/me` - Текущий пользователь

### Типы WebSocket сообщений

Все сообщения валидируются через Pydantic схемы:
- `move` - Выполнение хода
- `get_valid_moves` - Получение допустимых ходов
- `resign` - Сдача
- `offer_draw` - Предложение ничьей
- `request_undo` - Запрос отмены хода
- `get_rating` - Получение рейтинга
- И другие...

## Локальный запуск

### С Python
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```
Откройте http://localhost:8000

### С Docker
```bash
docker-compose up --build
```

## Тестирование

```bash
# Тесты шахматного движка
cd shared/tests
pytest test_chess_engine.py -v

# Тесты рейтинговой системы
cd backend/tests
pytest test_rating.py -v
```

## База данных

Используется SQLite для хранения:
- **users**: Аккаунты пользователей (v2.8+)
- **user_sessions**: JWT refresh токены (v2.8+)
- **email_verification_tokens**: Токены верификации email (v2.8+)
- **password_reset_tokens**: Токены сброса пароля (v2.8+)
- **players**: Игроки и их рейтинги (связь с users через user_id в v2.8+)
- **rating_history**: История изменения рейтингов
- **games**: Завершенные игры

База данных автоматически инициализируется при первом запуске.

### Миграция к версии 2.8

Для миграции существующих игроков к новой системе аккаунтов:
```bash
cd backend
python migrations/migrate_to_v2_8.py
```

## Логирование

Логи сохраняются в директории `logs/`:
- `chess_online.log` - Основной лог с ротацией (10 MB, 5 файлов)

## Безопасность

- Валидация всех WebSocket сообщений через Pydantic
- JWT-аутентификация с access и refresh токенами (v2.8+)
- Хеширование паролей с bcrypt (v2.8+)
- Rate limiting для auth endpoints (v2.8+)
- Защита WebSocket соединений через JWT (v2.8+)
- Санитизация входных данных
- Верификация email (v2.8+)

## Производительность

- Оптимизированная проверка шаха с кэшированием атакованных клеток
- Эффективный matchmaking с приоритетной очередью
- Асинхронная работа с базой данных (aiosqlite)

## Деплой на Timeweb Cloud

### 1. Создание приложения
1. Войдите в панель Timeweb Cloud
2. Создайте новое приложение (App Platform или Docker)
3. Подключите репозиторий или загрузите файлы

### 2. Настройка
- Порт: 8000
- Команда запуска: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`

### 3. Переменные окружения (опционально)
- `PORT` - порт приложения (по умолчанию 8000)

## Как играть
1. Откройте приложение в браузере
2. Введите ID комнаты или нажмите "Новая игра"
3. Отправьте ID комнаты другу
4. Играйте!

## Технологии
- Backend: FastAPI + WebSockets + SQLite
- Frontend: HTML5 Canvas + JavaScript
- Валидация: Pydantic
- Тестирование: pytest
- Деплой: Docker

