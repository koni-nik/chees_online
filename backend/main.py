# main.py - FastAPI сервер для онлайн шахмат
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, status, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
import json
import uuid
import time
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import pytz
from game_logic import ChessGame
from rating import RatingSystem
from analysis import PositionAnalyzer
from pgn import PGNExporter, PGNImporter
from tournament import Tournament, tournaments, TournamentType, TournamentStatus
from logger import setup_logger
from schemas import (
    MoveRequest, GetValidMovesRequest, CustomMoveRequest, SaveCardRequest,
    ToggleCardRequest, DeleteCardRequest, ChatRequest, ResignRequest,
    OfferDrawRequest, DrawResponseRequest, RequestUndoRequest, UndoResponseRequest,
    RequestRematchRequest, RematchResponseRequest, SetTimeControlRequest,
    GetPositionAnalysisRequest, ExportPGNRequest, GetRatingRequest,
    CreateTournamentRoomRequest, JoinTournamentRoomRequest,
    validate_player_id, validate_room_id
)
from pydantic import ValidationError
from database import db
from managers import room_manager, tournament_room_manager, connection_manager
from config import config
import aiosqlite
import asyncio

logger = setup_logger()

# Определяем базовый путь в зависимости от окружения
# В Docker: /app, на localhost: родительская директория от backend/
BASE_DIR = Path(__file__).parent.parent  # backend/ -> корень проекта
if os.path.exists("/app"):  # Docker окружение
    FRONTEND_BASE = Path("/app")
else:  # Localhost окружение
    FRONTEND_BASE = BASE_DIR

# Используем конфигурацию для расширяемости
FRONTEND_DIR = FRONTEND_BASE / "frontend"
# Создаём словарь версий для удобного доступа
FRONTEND_VERSIONS = {
    "frontend": FRONTEND_BASE / "frontend",
    "frontend-v2.5": FRONTEND_BASE / "frontend-v2.5",
    "frontend-v2.6": FRONTEND_BASE / "frontend-v2.6",
    "frontend-v2.7": FRONTEND_BASE / "frontend-v2.7",
    "frontend-v2.8": FRONTEND_BASE / "frontend-v2.8"
}
# Для обратной совместимости
FRONTEND_V25_DIR = FRONTEND_VERSIONS["frontend-v2.5"]
FRONTEND_V26_DIR = FRONTEND_VERSIONS["frontend-v2.6"]
FRONTEND_V27_DIR = FRONTEND_VERSIONS["frontend-v2.7"]
FRONTEND_V28_DIR = FRONTEND_VERSIONS["frontend-v2.8"]

app = FastAPI(title="Chess Online")

# Флаг готовности приложения
_app_ready = False

# Middleware для отключения кэширования статических файлов v2.7 и логирования запросов
# ВАЖНО: Этот middleware должен быть добавлен ПЕРВЫМ, чтобы логировать все запросы
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Логируем запросы к API
        if "/api/" in str(request.url.path):
            logger.info(f"API запрос: {request.method} {request.url.path}")
        
        response = await call_next(request)
        
        # Логируем ответ для API запросов
        if "/api/" in str(request.url.path):
            logger.info(f"API ответ: {request.method} {request.url.path} -> {response.status_code}")
        
        # Отключаем кэширование для всех файлов v2.7
        if "/v2.7" in str(request.url):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)

# Настройка CORS - разрешаем запросы с фронтенда
# ВАЖНО: CORS должен быть добавлен ПОСЛЕ других middleware
if config.ENVIRONMENT == "production":
    # В продакшене запрещаем ALLOW_ANY_ORIGIN
    if config.ALLOW_ANY_ORIGIN:
        logger.error("ALLOW_ANY_ORIGIN=true запрещен в продакшене! Используйте конкретные домены в CORS_ORIGINS.")
        raise ValueError("ALLOW_ANY_ORIGIN не может быть True в продакшене")
    cors_origins = config.CORS_ORIGINS
    logger.info(f"CORS настроен для продакшена: {cors_origins}")
elif config.ALLOW_ANY_ORIGIN:
    # Только для разработки - в продакшене использовать конкретные домены
    logger.warning("CORS настроен на разрешение всех доменов - не использовать в продакшене!")
    cors_origins = ["*"]
else:
    cors_origins = config.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ============ API для турнирных комнат (регистрируем рано) ============
# Эти endpoints должны быть зарегистрированы до монтирования статических файлов


@app.get("/health")
@app.get("/ping")
async def health_check():
    """Health check endpoint для проверки работоспособности приложения."""
    # Простой healthcheck для платформы Timeweb Cloud
    # Всегда возвращаем 200 OK, чтобы платформа считала приложение готовым
    # Используем простой Response для максимальной скорости
    return Response(status_code=200, content="ok")

# Тестовый endpoint для проверки регистрации API маршрутов
@app.get("/api/test")
async def test_api():
    """Тестовый endpoint для проверки работы API."""
    return {"status": "ok", "message": "API работает"}

# Подключаем rate limiting
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from middleware.rate_limit import get_rate_limiter
    
    limiter = get_rate_limiter()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Rate limiting подключен")
except ImportError as e:
    logger.warning(f"Не удалось подключить rate limiting: {e}")

# Подключаем auth routes
try:
    from routes.auth import router as auth_router
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    logger.info("Auth routes подключены")
except ImportError as e:
    logger.warning(f"Не удалось подключить auth routes: {e}")

# ВАЖНО: Endpoints для турнирных комнат определены ниже, после определения
# tournament_rooms и manager. Они будут зарегистрированы при загрузке модуля.
# Порядок определения функций не влияет на порядок регистрации маршрутов в FastAPI,
# но важно, чтобы они были определены до монтирования статических файлов.

# ============ API для турнирных комнат ============

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


async def check_tournament_rooms_start_time():
    """Периодическая проверка времени старта турнирных комнат."""
    while True:
        try:
            current_time = datetime.now(pytz.UTC)
            for room_id, room_data in list(tournament_room_manager.tournament_rooms.items()):
                if room_data["status"] == "waiting":
                    start_time_utc = room_data["start_time_utc"]
                    if current_time >= start_time_utc:
                        # Время старта наступило
                        room_data["status"] = "started"
                        # Уведомляем всех участников через WebSocket
                        notification_room_id = f"tournament_{room_id}"
                        if notification_room_id in connection_manager.active_connections:
                            await connection_manager.send_to_room(notification_room_id, {
                                "type": "tournament_room_started",
                                "room_id": room_id,
                                "name": room_data["name"]
                            })
                        logger.info(f"Турнирная комната {room_id} ({room_data['name']}) началась")
        except Exception as e:
            logger.error(f"Ошибка при проверке времени старта турнирных комнат: {e}", exc_info=True)
        
        await asyncio.sleep(10)  # Проверяем каждые 10 секунд


@app.post("/api/tournament-rooms")
async def create_tournament_room(request: CreateTournamentRoomRequest):
    """Создание турнирной комнаты."""
    try:
        # Парсим время старта (ожидаем ISO формат без timezone - интерпретируем как московское время)
        try:
            # Пробуем распарсить как ISO
            if 'T' in request.start_time:
                # Формат: YYYY-MM-DDTHH:MM:SS или YYYY-MM-DDTHH:MM
                parts = request.start_time.split('T')
                date_part = parts[0]
                time_part = parts[1] if len(parts) > 1 else '00:00:00'
                # Добавляем секунды если их нет
                if len(time_part.split(':')) == 2:
                    time_part += ':00'
                datetime_str = f"{date_part}T{time_part}"
                start_time_naive = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")
            else:
                # Формат: YYYY-MM-DD HH:MM:SS
                start_time_naive = datetime.strptime(request.start_time, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"Ошибка парсинга времени: {e}, входные данные: {request.start_time}")
            return JSONResponse(
                status_code=400,
                content={"error": "Неверный формат времени. Используйте формат YYYY-MM-DDTHH:MM:SS (московское время)"}
            )
        
        # Интерпретируем как московское время
        start_time_moscow = MOSCOW_TZ.localize(start_time_naive)
        
        # Конвертируем в UTC для внутреннего хранения
        start_time_utc = start_time_moscow.astimezone(pytz.UTC)
        
        # Проверяем, что время не в прошлом
        current_time_utc = datetime.now(pytz.UTC)
        if start_time_utc < current_time_utc:
            return JSONResponse(
                status_code=400,
                content={"error": "Время старта не может быть в прошлом"}
            )
        
        # Создаём комнату
        room_id = str(uuid.uuid4())[:8]
        tournament_room_manager.create_tournament_room(
            room_id,
            request.name,
            start_time_moscow.isoformat(),
            start_time_utc
        )
        
        logger.info(f"Создана турнирная комната: {room_id} ({request.name}), старт: {start_time_moscow.isoformat()}")
        
        return {
            "id": room_id,
            "name": request.name,
            "start_time": start_time_moscow.isoformat(),
            "players_count": 0,
            "spectators_count": 0,
            "status": "waiting"
        }
    except Exception as e:
        logger.error(f"Ошибка при создании турнирной комнаты: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Внутренняя ошибка сервера"}
        )


@app.get("/api/tournament-rooms")
async def list_tournament_rooms():
    """Получение списка всех турнирных комнат."""
    try:
        rooms_list = []
        current_time_utc = datetime.now(pytz.UTC)
        
        for room_id, room_data in tournament_room_manager.tournament_rooms.items():
            # Проверяем статус на основе времени
            if room_data["status"] == "waiting" and current_time_utc >= room_data["start_time_utc"]:
                room_data["status"] = "started"
            
            rooms_list.append({
                "id": room_data["id"],
                "name": room_data["name"],
                "start_time": room_data["start_time"],
                "players_count": len(room_data["players"]),
                "spectators_count": len(room_data["spectators"]),
                "status": room_data["status"],
                "max_players": 2
            })
        
        # Сортируем по времени создания (новые первыми)
        rooms_list.sort(key=lambda x: tournament_room_manager.tournament_rooms[x["id"]]["created_at"], reverse=True)
        
        return rooms_list
    except Exception as e:
        logger.error(f"Ошибка при получении списка турнирных комнат: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Внутренняя ошибка сервера"}
        )


@app.get("/api/tournament-rooms/{room_id}")
async def get_tournament_room(room_id: str):
    """Получение информации о конкретной турнирной комнате."""
    try:
        # Валидация room_id
        try:
            room_id = validate_room_id(room_id)
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content={"error": str(e)}
            )
        
        room_data = tournament_room_manager.get_tournament_room(room_id)
        if not room_data:
            return JSONResponse(
                status_code=404,
                content={"error": "Комната не найдена"}
            )
        current_time_utc = datetime.now(pytz.UTC)
        
        # Проверяем статус
        if room_data["status"] == "waiting" and current_time_utc >= room_data["start_time_utc"]:
            room_data["status"] = "started"
        
        return {
            "id": room_data["id"],
            "name": room_data["name"],
            "start_time": room_data["start_time"],
            "players": room_data["players"],
            "spectators": room_data["spectators"],
            "players_count": len(room_data["players"]),
            "spectators_count": len(room_data["spectators"]),
            "status": room_data["status"],
            "max_players": 2
        }
    except Exception as e:
        logger.error(f"Ошибка при получении информации о комнате {room_id}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Внутренняя ошибка сервера"}
        )


@app.post("/api/tournament-rooms/{room_id}/join")
async def join_tournament_room(room_id: str, request: JoinTournamentRoomRequest):
    """Присоединение к турнирной комнате."""
    try:
        # Валидация room_id и player_id
        try:
            room_id = validate_room_id(room_id)
            request.player_id = validate_player_id(request.player_id)
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content={"error": str(e)}
            )
        
        room_data = tournament_room_manager.get_tournament_room(room_id)
        if not room_data:
            return JSONResponse(
                status_code=404,
                content={"error": "Комната не найдена"}
            )
        player_id = request.player_id
        
        # Проверяем, не присоединён ли уже игрок
        if player_id in room_data["players"]:
            return {
                "success": True,
                "role": "player",
                "room_id": room_id,
                "message": "Вы уже присоединены как игрок"
            }
        
        if player_id in room_data["spectators"]:
            return {
                "success": True,
                "role": "spectator",
                "room_id": room_id,
                "message": "Вы уже присоединены как зритель"
            }
        
        # Определяем роль
        role = request.role
        if role is None:
            # Автоматически определяем роль
            if len(room_data["players"]) < 2:
                role = "player"
            else:
                role = "spectator"
        
        # Присоединяем
        if role == "player":
            if len(room_data["players"]) >= 2:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Все слоты для игроков заняты. Присоединитесь как зритель"}
                )
            room_data["players"].append(player_id)
        else:  # spectator
            room_data["spectators"].append(player_id)
        
        logger.info(f"Игрок {player_id} присоединился к турнирной комнате {room_id} как {role}")
        
        # Уведомляем других участников через WebSocket (если есть соединения)
        notification_room_id = f"tournament_{room_id}"
        if notification_room_id in connection_manager.active_connections:
            await connection_manager.send_to_room(notification_room_id, {
                "type": "tournament_room_updated",
                "room_id": room_id,
                "players_count": len(room_data["players"]),
                "spectators_count": len(room_data["spectators"])
            })
        
        return {
            "success": True,
            "role": role,
            "room_id": room_id,
            "players_count": len(room_data["players"]),
            "spectators_count": len(room_data["spectators"])
        }
    except Exception as e:
        logger.error(f"Ошибка при присоединении к турнирной комнате {room_id}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Внутренняя ошибка сервера"}
        )

@app.on_event("startup")
async def startup_event():
    """Инициализация базы данных при запуске приложения."""
    global _app_ready
    # Сразу помечаем приложение как готовое для healthcheck
    _app_ready = True
    logger.info("Приложение запускается...")
    
    # Логируем зарегистрированные API маршруты
    api_routes = [r.path for r in app.routes if hasattr(r, 'path') and '/api/' in r.path]
    logger.info(f"Зарегистрировано API маршрутов: {len(api_routes)}")
    
    # Запускаем инициализацию БД в фоне, не блокируя запуск
    try:
        # Используем правильный способ создания задачи в контексте startup
        loop = asyncio.get_event_loop()
        loop.create_task(initialize_db_background())
        # Запускаем фоновую задачу для проверки времени старта турнирных комнат
        loop.create_task(check_tournament_rooms_start_time())
        # Запускаем задачу очистки комнат
        room_manager.start_cleanup_task(loop)
        logger.info("Приложение готово принимать запросы (инициализация БД в фоне)")
    except Exception as e:
        logger.error(f"Ошибка при запуске приложения: {e}", exc_info=True)
        # Не блокируем запуск даже при ошибке

async def initialize_db_background():
    """Инициализация БД в фоновом режиме."""
    try:
        await db.initialize()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}", exc_info=True)

# Хранилище для matchmaking
matchmaking_queue: List[Dict] = []  # [{player_id, websocket, rating, timestamp}]
matchmaking_event: Optional[asyncio.Event] = None  # asyncio.Event для уведомлений


def rebuild_custom_moves(room):
    """Пересобирает custom_moves из включённых карточек"""
    room["custom_moves"] = {"white": {}, "black": {}}
    for color in ["white", "black"]:
        for name, card in room["ability_cards"][color].items():
            if card.get("enabled", True) == False:
                continue
            piece_type = card.get("pieceType")
            if not piece_type:
                continue
            if piece_type not in room["custom_moves"][color]:
                room["custom_moves"][color][piece_type] = {"moves": [], "attacks": []}
            for move in card.get("moves", []):
                if move not in room["custom_moves"][color][piece_type]["moves"]:
                    room["custom_moves"][color][piece_type]["moves"].append(move)
            for attack in card.get("attacks", []):
                if attack not in room["custom_moves"][color][piece_type]["attacks"]:
                    room["custom_moves"][color][piece_type]["attacks"].append(attack)


@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/frontend")
@app.get("/frontend/")
async def frontend():
    """Маршрут для доступа к фронтенду через /frontend/"""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/v2.5")
async def v25_root():
    return FileResponse(str(FRONTEND_V25_DIR / "index.html"))


@app.get("/v2.6")
async def v26_root():
    return FileResponse(str(FRONTEND_V26_DIR / "index.html"))


@app.get("/v2.7")
async def v27_root():
    response = FileResponse(str(FRONTEND_V27_DIR / "index.html"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/v2.8")
async def v28_root():
    response = FileResponse(str(FRONTEND_V28_DIR / "index.html"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


app.mount("/v2.5/static", StaticFiles(directory=str(FRONTEND_V25_DIR)), name="static_v25")
app.mount("/v2.6/static", StaticFiles(directory=str(FRONTEND_V26_DIR)), name="static_v26")
app.mount("/v2.7/static", StaticFiles(directory=str(FRONTEND_V27_DIR / "static")), name="static_v27")
app.mount("/v2.8/static", StaticFiles(directory=str(FRONTEND_V28_DIR / "static")), name="static_v28")

# Монтируем статические файлы для основной версии
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# Маршрут для game.js в v2.7 (находится в корне директории)
@app.get("/v2.7/game.js")
async def v27_game_js():
    response = FileResponse(str(FRONTEND_V27_DIR / "game.js"), media_type="application/javascript")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Маршруты для v2.8 (auth.js и game.js находятся в корне директории)
@app.get("/v2.8/auth.js")
async def v28_auth_js():
    response = FileResponse(str(FRONTEND_V28_DIR / "auth.js"), media_type="application/javascript")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/v2.8/game.js")
async def v28_game_js():
    # Проверяем существование файла, если нет - возвращаем пустой или используем v2.7
    game_js_path = FRONTEND_V28_DIR / "game.js"
    if not game_js_path.exists():
        # Используем game.js из v2.7 как fallback
        game_js_path = FRONTEND_V27_DIR / "game.js"
    response = FileResponse(str(game_js_path), media_type="application/javascript")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# Matchmaking endpoint
@app.websocket("/ws/matchmaking/{player_id}")
async def matchmaking_endpoint(websocket: WebSocket, player_id: str):
    global matchmaking_event
    
    await websocket.accept()
    
    # Получаем рейтинг игрока
    rating = await RatingSystem.get_rating(player_id)
    
    # Создаём событие для уведомлений о новых игроках (если ещё не создано)
    if matchmaking_event is None:
        matchmaking_event = asyncio.Event()
    
    # Добавляем в очередь
    player_entry = {
        "player_id": player_id,
        "websocket": websocket,
        "rating": rating,
        "timestamp": time.time()
    }
    matchmaking_queue.append(player_entry)
    
    # Уведомляем о новом игроке
    matchmaking_event.set()
    
    try:
        # Проверяем состояние соединения перед отправкой
        if websocket.client_state.name != "DISCONNECTED":
            await websocket.send_json({
                "type": "queued",
                "position": len(matchmaking_queue),
                "rating": rating
            })
    except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
        logger.warning(f"Соединение закрыто при отправке начального сообщения: {e}")
        return
    
    try:
        
        # Ищем соперника
        while True:
            # Сортируем очередь по рейтингу для эффективного поиска
            matchmaking_queue.sort(key=lambda x: x["rating"])
            
            # Ищем подходящего соперника (ближайшего по рейтингу)
            best_match = None
            best_diff = float('inf')
            
            for other in matchmaking_queue:
                if other["player_id"] == player_id:
                    continue
                
                rating_diff = abs(other["rating"] - rating)
                wait_time = time.time() - min(player_entry["timestamp"], other["timestamp"])
                
                # Расширяем диапазон поиска со временем
                max_diff = 100 + wait_time * 10
                
                if rating_diff <= max_diff and rating_diff < best_diff:
                    best_match = other
                    best_diff = rating_diff
            
            if best_match:
                # Нашли соперника!
                room_id = str(uuid.uuid4())[:8]
                
                # Удаляем обоих из очереди (с защитой от race condition)
                try:
                    if player_entry in matchmaking_queue:
                        matchmaking_queue.remove(player_entry)
                    if best_match in matchmaking_queue:
                        matchmaking_queue.remove(best_match)
                except (ValueError, KeyError):
                    # Игрок уже удалён из очереди (возможно, отключился)
                    logger.warning(f"Игрок уже удалён из очереди matchmaking")
                    break
                
                # Уведомляем обоих
                try:
                    # Проверяем состояние соединения перед отправкой
                    if websocket.client_state.name != "DISCONNECTED":
                        await websocket.send_json({
                            "type": "match_found",
                            "room_id": room_id,
                            "opponent_rating": best_match["rating"]
                        })
                    
                    # Проверяем состояние соединения соперника
                    if best_match["websocket"].client_state.name != "DISCONNECTED":
                        await best_match["websocket"].send_json({
                            "type": "match_found",
                            "room_id": room_id,
                            "opponent_rating": rating
                        })
                except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
                    logger.warning(f"Соединение закрыто при отправке уведомления о найденном матче: {e}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления о найденном матче: {e}")
                
                return
            
            # Обновляем позицию в очереди
            try:
                pos = matchmaking_queue.index(player_entry) + 1
                # Проверяем состояние соединения перед отправкой
                if websocket.client_state.name != "DISCONNECTED":
                    await websocket.send_json({
                        "type": "queue_update",
                        "position": pos,
                        "queue_size": len(matchmaking_queue)
                    })
            except ValueError:
                break
            except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
                logger.debug(f"Соединение закрыто при отправке обновления очереди: {e}")
                break
            
            # Ждём уведомления о новых игроках или таймаут
            try:
                await asyncio.wait_for(matchmaking_event.wait(), timeout=1.0)
                matchmaking_event.clear()
            except asyncio.TimeoutError:
                pass
    
    except WebSocketDisconnect:
        try:
            if player_entry in matchmaking_queue:
                matchmaking_queue.remove(player_entry)
        except (ValueError, KeyError):
            pass  # Игрок уже удалён


@app.websocket("/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    # Валидация параметров
    try:
        room_id = validate_room_id(room_id)
        player_id = validate_player_id(player_id)
    except ValueError as e:
        await websocket.close(code=4000, reason=str(e))
        return
    
    await connection_manager.connect(websocket, room_id, player_id)
    
    # Создаём комнату если её нет
    room = room_manager.get_room(room_id)
    if not room:
        room = room_manager.create_room(room_id)
    
    # Обновляем активность комнаты
    room_manager.update_activity(room_id)
    
    # Добавляем игрока
    if player_id not in room["players"] and player_id not in room["spectators"]:
        if len(room["players"]) < 2:
            room["players"].append(player_id)
            # Назначаем цвет
            if len(room["players"]) == 1:
                room["colors"][player_id] = "white"
            else:
                room["colors"][player_id] = "black"
        else:
            # Третий+ игрок становится наблюдателем
            room["spectators"].append(player_id)
            room["colors"][player_id] = "spectator"
    
    # Отправляем начальное состояние
    if room["last_move_time"] is None:
        room["last_move_time"] = time.time()
    
    await connection_manager.send_to_player(room_id, player_id, {
        "type": "init",
        "color": room["colors"].get(player_id, "spectator"),
        "board": room["game"].get_board_state(),
        "current_player": room["game"].current_player,
        "players_count": len(room["players"]),
        "spectators_count": len(room["spectators"]),
        "custom_moves": room["custom_moves"],
        "ability_cards": room["ability_cards"],
        "timers": room["timers"],
        "increment": room["increment"],
        "delay": room["delay"],
        "move_history": room["move_history"],
        "en_passant_target": room["game"].en_passant_target
    })
    
    # Уведомляем всех о новом игроке
    await connection_manager.send_to_room(room_id, {
        "type": "player_joined",
        "players_count": len(room["players"])
    })
    
    try:
        while True:
            raw_data = await websocket.receive_json()
            logger.debug(f"Received message type: {raw_data.get('type')} from {player_id}")
            
            # Валидация данных
            try:
                message_type = raw_data.get("type")
                if message_type == "move":
                    data = MoveRequest(**raw_data)
                    from_pos = tuple(data.from_pos)
                    to_pos = tuple(data.to_pos)
                    promotion_piece = data.promotion
                elif message_type == "get_valid_moves":
                    data = GetValidMovesRequest(**raw_data)
                elif message_type == "add_custom_move":
                    data = CustomMoveRequest(**raw_data)
                elif message_type == "save_card":
                    data = SaveCardRequest(**raw_data)
                elif message_type == "toggle_card":
                    data = ToggleCardRequest(**raw_data)
                elif message_type == "delete_card":
                    data = DeleteCardRequest(**raw_data)
                elif message_type == "chat":
                    data = ChatRequest(**raw_data)
                elif message_type == "resign":
                    data = ResignRequest(**raw_data)
                elif message_type == "offer_draw":
                    data = OfferDrawRequest(**raw_data)
                elif message_type == "draw_response":
                    data = DrawResponseRequest(**raw_data)
                elif message_type == "request_undo":
                    data = RequestUndoRequest(**raw_data)
                elif message_type == "undo_response":
                    data = UndoResponseRequest(**raw_data)
                elif message_type == "request_rematch":
                    data = RequestRematchRequest(**raw_data)
                elif message_type == "rematch_response":
                    data = RematchResponseRequest(**raw_data)
                elif message_type == "set_time_control":
                    data = SetTimeControlRequest(**raw_data)
                elif message_type == "get_position_analysis":
                    data = GetPositionAnalysisRequest(**raw_data)
                elif message_type == "export_pgn":
                    data = ExportPGNRequest(**raw_data)
                elif message_type == "get_rating":
                    data = GetRatingRequest(**raw_data)
                else:
                    await connection_manager.send_to_player(room_id, player_id, {
                        "type": "error",
                        "message": f"Неизвестный тип сообщения: {message_type}"
                    })
                    continue
            except ValidationError as e:
                logger.warning(f"Ошибка валидации данных от {player_id} (тип: {message_type}): {e}")
                await connection_manager.send_to_player(room_id, player_id, {
                    "type": "error",
                    "message": f"Некорректные данные: {str(e)}"
                })
                continue
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Ошибка формата данных от {player_id} (тип: {message_type}): {e}", exc_info=True)
                await connection_manager.send_to_player(room_id, player_id, {
                    "type": "error",
                    "message": "Некорректный формат данных"
                })
                continue
            except Exception as e:
                logger.error(f"Неожиданная ошибка при обработке сообщения от {player_id} (тип: {message_type}): {e}", exc_info=True)
                await connection_manager.send_to_player(room_id, player_id, {
                    "type": "error",
                    "message": "Внутренняя ошибка сервера"
                })
                continue
            
            if message_type == "move":
                player_color = room["colors"].get(player_id)
                
                logger.debug(f"Move request from {player_id}: from={from_pos}, to={to_pos}, player_color={player_color}, current_player={room['game'].current_player}")
                
                # Получаем блокировку для комнаты для защиты от race conditions
                room_lock = room_manager.get_room_lock(room_id)
                
                async with room_lock:
                    # Проверяем что ход делает правильный игрок
                    if player_color != room["game"].current_player:
                        logger.warning(f"Wrong turn: player_color={player_color}, current_player={room['game'].current_player}")
                        await connection_manager.send_to_player(room_id, player_id, {
                            "type": "error",
                            "message": "Не ваш ход"
                        })
                        continue
                    
                    # Выполняем ход (с учётом кастомных ходов)
                    result = room["game"].make_move(from_pos, to_pos, room["custom_moves"], promotion_piece)
                    logger.debug(f"Move result: success={result.get('success')}, message={result.get('message')}")
                    
                    if result["success"]:
                        # Обновляем таймеры
                        now = time.time()
                        if room["last_move_time"]:
                            elapsed = now - room["last_move_time"]
                            prev_player = "black" if room["game"].current_player == "white" else "white"
                            room["timers"][prev_player] = max(0, room["timers"][prev_player] - int(elapsed))
                            # Добавляем инкремент
                            room["timers"][prev_player] += room["increment"]
                        room["last_move_time"] = now
                        
                        # Сохраняем ход в историю
                        move_record = {
                            "from": list(from_pos),
                            "to": list(to_pos),
                            "piece": result.get("piece"),
                            "captured": result.get("captured"),
                            "castling": result.get("castling"),
                            "en_passant": result.get("en_passant"),
                            "promotion": result.get("promotion")
                        }
                        room["move_history"].append(move_record)
                        
                        # Анализ позиции (для версии 2.7)
                        position_eval = PositionAnalyzer.evaluate_position(room["game"].board, room["game"].current_player)
                        
                        # Отправляем обновление всем
                        await connection_manager.send_to_room(room_id, {
                            "type": "move",
                            "from": list(from_pos),
                            "to": list(to_pos),
                            "board": room["game"].get_board_state(),
                            "current_player": room["game"].current_player,
                            "check": result.get("check", False),
                            "checkmate": result.get("checkmate", False),
                            "stalemate": result.get("stalemate", False),
                            "captured": result.get("captured"),
                            "castling": result.get("castling"),
                            "en_passant": result.get("en_passant"),
                            "promotion": result.get("promotion"),
                            "en_passant_target": result.get("en_passant_target"),
                            "timers": room["timers"],
                            "position_evaluation": position_eval
                        })
                        
                        # Обновляем рейтинг при завершении игры
                        if result.get("checkmate") or result.get("stalemate"):
                            winner = None
                            if result.get("checkmate"):
                                winner = "black" if room["game"].current_player == "white" else "white"
                            
                            # Обновляем рейтинги
                            if len(room["players"]) == 2:
                                player1_id = room["players"][0]
                                player2_id = room["players"][1]
                                
                                if winner:
                                    if room["colors"][player1_id] == winner:
                                        result_value = 1.0
                                    else:
                                        result_value = 0.0
                                else:
                                    result_value = 0.5  # Ничья
                                
                                rating_update = await RatingSystem.update_rating(player1_id, player2_id, result_value)
                                
                                await connection_manager.send_to_room(room_id, {
                                    "type": "rating_updated",
                                    "ratings": rating_update
                                })
                    else:
                        await connection_manager.send_to_player(room_id, player_id, {
                            "type": "error",
                            "message": result.get("message", "Недопустимый ход")
                        })
            
            elif message_type == "get_valid_moves":
                # Убеждаемся, что data был успешно создан
                if not hasattr(data, 'position'):
                    logger.error(f"GetValidMovesRequest не содержит атрибут position для {player_id}")
                    await connection_manager.send_to_player(room_id, player_id, {
                        "type": "error",
                        "message": "Некорректные данные запроса"
                    })
                    continue
                pos = tuple(data.position)
                moves = room["game"].get_valid_moves(pos)
                
                # Добавляем кастомные ходы из комнаты
                x, y = pos
                piece = room["game"].board[x][y]
                logger.debug(f"get_valid_moves: pos={pos}, custom_moves={room['custom_moves']}")
                if piece:
                    color = piece.color
                    piece_type = piece.type.value  # строка типа "pawn"
                    custom = room["custom_moves"].get(color, {}).get(piece_type, {})
                    logger.debug(f"Piece: {color} {piece_type}, custom for this piece: {custom}")
                    
                    custom_moves_list = custom.get("moves", [])
                    custom_attacks_list = custom.get("attacks", [])
                    
                    # Добавляем кастомные ходы
                    for move in custom_moves_list:
                        dx, dy = move[0], move[1]
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < 8 and 0 <= ny < 8:
                            target = room["game"].board[nx][ny]
                            if not target:
                                if [nx, ny] not in moves["moves"]:
                                    moves["moves"].append([nx, ny])
                    
                    # Добавляем кастомные атаки
                    for attack in custom_attacks_list:
                        dx, dy = attack[0], attack[1]
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < 8 and 0 <= ny < 8:
                            target = room["game"].board[nx][ny]
                            if target and target.color != color:
                                if [nx, ny] not in moves["attacks"]:
                                    moves["attacks"].append([nx, ny])
                
                await connection_manager.send_to_player(room_id, player_id, {
                    "type": "valid_moves",
                    "position": data.position,
                    "moves": moves["moves"],
                    "attacks": moves["attacks"]
                })
            
            elif message_type == "resign":
                winner = "black" if room["colors"].get(player_id) == "white" else "white"
                await connection_manager.send_to_room(room_id, {
                    "type": "game_over",
                    "reason": "resign",
                    "winner": winner
                })
            
            elif message_type == "add_custom_move":
                color = data.color
                piece_type = data.piece_type
                move = data.move
                is_attack = data.is_attack
                
                if color and piece_type and move:
                    if piece_type not in room["custom_moves"][color]:
                        room["custom_moves"][color][piece_type] = {"moves": [], "attacks": []}
                    
                    target = "attacks" if is_attack else "moves"
                    if move not in room["custom_moves"][color][piece_type][target]:
                        room["custom_moves"][color][piece_type][target].append(move)
                    
                    await connection_manager.send_to_room(room_id, {
                        "type": "custom_moves_updated",
                        "custom_moves": room["custom_moves"]
                    })
            
            elif message_type == "save_card":
                color = data.color
                name = data.name
                card_data = data.card_data
                logger.debug(f"Received save_card: {name}, color={color}, card_data={card_data}")
                
                if color and name and card_data:
                    card_data["enabled"] = True
                    room["ability_cards"][color][name] = card_data
                    rebuild_custom_moves(room)
                    
                    logger.debug(f"custom_moves after rebuild: {room['custom_moves']}")
                    await connection_manager.send_to_room(room_id, {
                        "type": "cards_updated",
                        "ability_cards": room["ability_cards"],
                        "custom_moves": room["custom_moves"]
                    })
                else:
                    logger.warning(f"Missing data: color={color}, name={name}, card_data={card_data}")
            
            elif message_type == "delete_card":
                color = data.color
                name = data.name
                
                if color and name and name in room["ability_cards"][color]:
                    del room["ability_cards"][color][name]
                    rebuild_custom_moves(room)
                    
                    await connection_manager.send_to_room(room_id, {
                        "type": "cards_updated",
                        "ability_cards": room["ability_cards"],
                        "custom_moves": room["custom_moves"]
                    })
            
            elif message_type == "toggle_card":
                color = data.color
                name = data.name
                enabled = data.enabled
                logger.debug(f"toggle_card: {name}, enabled={enabled}")
                
                if color and name and name in room["ability_cards"][color]:
                    room["ability_cards"][color][name]["enabled"] = enabled
                    rebuild_custom_moves(room)
                    logger.debug(f"custom_moves after toggle: {room['custom_moves']}")
                    
                    await connection_manager.send_to_room(room_id, {
                        "type": "cards_updated",
                        "ability_cards": room["ability_cards"],
                        "custom_moves": room["custom_moves"]
                    })
            
            elif message_type == "reset_custom_moves":
                room["custom_moves"] = {"white": {}, "black": {}}
                room["ability_cards"] = {"white": {}, "black": {}}
                await connection_manager.send_to_room(room_id, {
                    "type": "cards_updated",
                    "ability_cards": room["ability_cards"],
                    "custom_moves": room["custom_moves"]
                })
            
            elif message_type == "chat":
                message = data.message
                if message:
                    # Отправляем сообщение всем кроме отправителя
                    for pid, ws in connection_manager.active_connections.get(room_id, {}).items():
                        if pid != player_id:
                            await ws.send_json({
                                "type": "chat",
                                "message": message
                            })
            
            elif message_type == "offer_draw":
                # Отправляем предложение ничьей противнику
                for pid, ws in connection_manager.active_connections.get(room_id, {}).items():
                    if pid != player_id:
                        await ws.send_json({"type": "draw_offered"})
            
            elif message_type == "draw_response":
                accept = data.accept
                if accept:
                    await connection_manager.send_to_room(room_id, {
                        "type": "game_over",
                        "reason": "draw",
                        "winner": None
                    })
                else:
                    for pid, ws in connection_manager.active_connections.get(room_id, {}).items():
                        if pid != player_id:
                            await ws.send_json({"type": "draw_declined"})
            
            elif message_type == "request_undo":
                # Запрос на отмену хода
                for pid, ws in connection_manager.active_connections.get(room_id, {}).items():
                    if pid != player_id and pid in room["players"]:
                        await ws.send_json({"type": "undo_requested"})
                        room["undo_requests"][player_id] = True
            
            elif message_type == "undo_response":
                accept = data.accept
                if accept and room["move_history"]:
                    # Отменяем последний ход используя метод undo_move
                    last_move = room["move_history"].pop()
                    room["game"].undo_move(last_move)
                    
                    # Обновляем таймеры (упрощённо - возвращаем время назад)
                    # В реальности нужно хранить время каждого хода
                    
                    await connection_manager.send_to_room(room_id, {
                        "type": "undo_accepted",
                        "board": room["game"].get_board_state(),
                        "current_player": room["game"].current_player,
                        "move_history": room["move_history"]
                    })
                else:
                    for pid, ws in connection_manager.active_connections.get(room_id, {}).items():
                        if pid in room["undo_requests"]:
                            await ws.send_json({"type": "undo_declined"})
                room["undo_requests"] = {}
            
            elif message_type == "request_rematch":
                room["rematch_requests"].add(player_id)
                
                # Если оба игрока согласны
                if len(room["rematch_requests"]) >= 2:
                    # Создаём новую игру
                    room["game"] = ChessGame()
                    room["move_history"] = []
                    room["timers"] = {"white": 600, "black": 600}
                    room["last_move_time"] = None
                    room["rematch_requests"] = set()
                    
                    # Меняем цвета
                    for pid in room["players"]:
                        room["colors"][pid] = "black" if room["colors"][pid] == "white" else "white"
                    
                    await connection_manager.send_to_room(room_id, {
                        "type": "rematch_started",
                        "board": room["game"].get_board_state(),
                        "current_player": room["game"].current_player,
                        "colors": room["colors"],
                        "timers": room["timers"]
                    })
                else:
                    # Уведомляем противника
                    for pid, ws in connection_manager.active_connections.get(room_id, {}).items():
                        if pid != player_id and pid in room["players"]:
                            await ws.send_json({"type": "rematch_requested"})
            
            elif message_type == "rematch_response":
                accept = data.accept
                if accept:
                    room["rematch_requests"].add(player_id)
                    if len(room["rematch_requests"]) >= 2:
                        room["game"] = ChessGame()
                        room["move_history"] = []
                        room["timers"] = {"white": config.DEFAULT_TIME_CONTROL, "black": config.DEFAULT_TIME_CONTROL}
                        room["last_move_time"] = None
                        room["rematch_requests"] = set()
                        
                        for pid in room["players"]:
                            room["colors"][pid] = "black" if room["colors"][pid] == "white" else "white"
                        
                        await connection_manager.send_to_room(room_id, {
                            "type": "rematch_started",
                            "board": room["game"].get_board_state(),
                            "current_player": room["game"].current_player,
                            "colors": room["colors"],
                            "timers": room["timers"]
                        })
                else:
                    room["rematch_requests"] = set()
                    for pid, ws in connection_manager.active_connections.get(room_id, {}).items():
                        if pid != player_id:
                            await ws.send_json({"type": "rematch_declined"})
            
            elif message_type == "set_time_control":
                # Установка контроля времени
                room["timers"]["white"] = data.time
                room["timers"]["black"] = data.time
                room["increment"] = data.increment
                room["delay"] = data.delay
                
                await connection_manager.send_to_room(room_id, {
                    "type": "time_control_updated",
                    "timers": room["timers"],
                    "increment": room["increment"],
                    "delay": room["delay"]
                })
            
            elif message_type == "get_position_analysis":
                # Анализ позиции
                analysis = PositionAnalyzer.analyze_threats(room["game"].board, room["colors"].get(player_id, "white"))
                evaluation = PositionAnalyzer.evaluate_position(room["game"].board, room["colors"].get(player_id, "white"))
                
                await connection_manager.send_to_player(room_id, player_id, {
                    "type": "position_analysis",
                    "evaluation": evaluation,
                    "threats": analysis
                })
            
            elif message_type == "export_pgn":
                # Экспорт партии в PGN
                white_name = data.white_name or "White"
                black_name = data.black_name or "Black"
                result = data.result or "*"
                
                pgn = PGNExporter.export_game(
                    room["move_history"],
                    white_name,
                    black_name,
                    result
                )
                
                await connection_manager.send_to_player(room_id, player_id, {
                    "type": "pgn_exported",
                    "pgn": pgn
                })
            
            elif message_type == "get_rating":
                # Получить рейтинг игрока
                rating = await RatingSystem.get_rating(player_id)
                rank = RatingSystem.get_rank(rating)
                history = await RatingSystem.get_rating_history(player_id, 10)
                
                await connection_manager.send_to_player(room_id, player_id, {
                    "type": "rating_info",
                    "rating": rating,
                    "rank": rank,
                    "history": history
                })
    
    except WebSocketDisconnect:
        logger.info(f"Игрок {player_id} отключился от комнаты {room_id}")
        connection_manager.disconnect(room_id, player_id)
        
        # Сохраняем состояние игры при неожиданном отключении
        if player_id in room.get("players", []):
            room["players"].remove(player_id)
            
            # Если игра была в процессе, сохраняем её
            if room.get("game") and len(room["move_history"]) > 0:
                try:
                    # Правильно определяем white_id и black_id
                    white_id = None
                    black_id = None
                    for pid in room["players"]:
                        color = room["colors"].get(pid)
                        if color == "white":
                            white_id = pid
                        elif color == "black":
                            black_id = pid
                    
                    # Также проверяем отключившегося игрока
                    disconnected_color = room["colors"].get(player_id)
                    if disconnected_color == "white":
                        white_id = player_id
                    elif disconnected_color == "black":
                        black_id = player_id
                    
                    if white_id and black_id:
                        await db.save_game(
                            white_id, black_id,
                            result="*",  # Незавершённая игра
                            move_history=room["move_history"]
                        )
                        logger.info(f"Игра сохранена при отключении игрока {player_id}")
                except Exception as e:
                    logger.error(f"Ошибка при сохранении игры при отключении: {e}", exc_info=True)
        
        # Уведомляем остальных игроков
        try:
            await connection_manager.send_to_room(room_id, {
                "type": "player_left",
                "players_count": len(room.get("players", [])),
                "player_id": player_id
            })
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об отключении: {e}", exc_info=True)
        
        # Удаляем комнату если она пуста
        if len(room.get("players", [])) == 0 and len(room.get("spectators", [])) == 0:
            room_manager.delete_room(room_id)
            logger.info(f"Комната {room_id} удалена (пуста)")
    except Exception as e:
        logger.error(f"Неожиданная ошибка в WebSocket соединении {player_id} (комната: {room_id}): {e}", exc_info=True)
        try:
            connection_manager.disconnect(room_id, player_id)
        except Exception as disconnect_error:
            logger.debug(f"Ошибка при отключении игрока {player_id}: {disconnect_error}")



# Для совместимости со старыми ссылками /v2 -> /v2.5
@app.get("/v2")
async def v2_redirect():
    return FileResponse(str(FRONTEND_V25_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
