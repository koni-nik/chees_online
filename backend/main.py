# main.py - FastAPI сервер для онлайн шахмат
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
import json
import uuid
import time
from typing import Dict, List, Optional
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
    GetPositionAnalysisRequest, ExportPGNRequest, GetRatingRequest
)
from pydantic import ValidationError
from database import db
import aiosqlite

logger = setup_logger()

app = FastAPI(title="Chess Online")

# Флаг готовности приложения
_app_ready = False

# Middleware для отключения кэширования статических файлов v2.7
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Отключаем кэширование для всех файлов v2.7
        if "/v2.7" in str(request.url):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)


@app.get("/health")
async def health_check():
    """Health check endpoint для проверки работоспособности приложения."""
    # Простой healthcheck для платформы Timeweb Cloud
    # Всегда возвращаем 200 OK, чтобы платформа считала приложение готовым
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ok"}
    )

#xtu

@app.on_event("startup")
async def startup_event():
    """Инициализация базы данных при запуске приложения."""
    global _app_ready
    try:
        logger.info("Приложение запускается...")
        # Запускаем инициализацию в фоне, чтобы не блокировать запуск приложения
        import asyncio
        asyncio.create_task(initialize_db_background())
        logger.info("Приложение готово принимать запросы (инициализация БД в фоне)")
    except Exception as e:
        logger.error(f"Ошибка при запуске приложения: {e}", exc_info=True)
        # Не блокируем запуск даже при ошибке

async def initialize_db_background():
    """Инициализация БД в фоновом режиме."""
    global _app_ready
    try:
        await db.initialize()
        _app_ready = True
        logger.info("Приложение запущено, база данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}", exc_info=True)
        _app_ready = False

# Хранилище активных игр и соединений
games: Dict[str, ChessGame] = {}
rooms: Dict[str, Dict] = {}  # room_id -> {players: [], game: ChessGame}
waiting_players: List[WebSocket] = []  # Очередь для matchmaking
matchmaking_queue: List[Dict] = []  # [{player_id, websocket, rating, timestamp}]
matchmaking_event = None  # asyncio.Event для уведомлений
connections: Dict[str, WebSocket] = {}  # player_id -> websocket

# Рейтинги игроков теперь в rating.py


class ConnectionManager:
    """Менеджер WebSocket соединений с обработкой ошибок и retry механизмом."""
    
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}  # room_id -> {player_id: ws}
        self.connection_timestamps: Dict[str, Dict[str, float]] = {}  # room_id -> {player_id: timestamp}
    
    async def connect(self, websocket: WebSocket, room_id: str, player_id: str):
        """Подключает WebSocket соединение."""
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = {}
            self.connection_timestamps[room_id] = {}
        self.active_connections[room_id][player_id] = websocket
        self.connection_timestamps[room_id][player_id] = time.time()
        logger.debug(f"Игрок {player_id} подключён к комнате {room_id}")
    
    def disconnect(self, room_id: str, player_id: str):
        """Отключает WebSocket соединение."""
        if room_id in self.active_connections:
            self.active_connections[room_id].pop(player_id, None)
            if room_id in self.connection_timestamps:
                self.connection_timestamps[room_id].pop(player_id, None)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
                if room_id in self.connection_timestamps:
                    del self.connection_timestamps[room_id]
        logger.debug(f"Игрок {player_id} отключён от комнаты {room_id}")
    
    async def send_to_room(self, room_id: str, message: dict, max_retries: int = 3):
        """Отправляет сообщение всем игрокам в комнате с retry механизмом."""
        if room_id not in self.active_connections:
            return
        
        failed_connections = []
        for player_id, ws in list(self.active_connections[room_id].items()):
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Ошибка отправки сообщения игроку {player_id}: {e}")
                failed_connections.append(player_id)
        
        # Удаляем неработающие соединения
        for player_id in failed_connections:
            if player_id in self.active_connections[room_id]:
                try:
                    await self.active_connections[room_id][player_id].close()
                except:
                    pass
                self.disconnect(room_id, player_id)
    
    async def send_to_player(self, room_id: str, player_id: str, message: dict, max_retries: int = 3):
        """Отправляет сообщение конкретному игроку с retry механизмом."""
        if room_id not in self.active_connections or player_id not in self.active_connections[room_id]:
            return
        
        for attempt in range(max_retries):
            try:
                await self.active_connections[room_id][player_id].send_json(message)
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Попытка {attempt + 1} отправки сообщения игроку {player_id} не удалась: {e}")
                    await asyncio.sleep(0.1)
                else:
                    logger.error(f"Не удалось отправить сообщение игроку {player_id} после {max_retries} попыток: {e}")
                    self.disconnect(room_id, player_id)


manager = ConnectionManager()


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
    return FileResponse("/app/frontend/index.html")


@app.get("/frontend")
@app.get("/frontend/")
async def frontend():
    """Маршрут для доступа к фронтенду через /frontend/"""
    return FileResponse("/app/frontend/index.html")


@app.get("/v2.5")
async def v25_root():
    return FileResponse("/app/frontend-v2.5/index.html")


@app.get("/v2.6")
async def v26_root():
    return FileResponse("/app/frontend-v2.6/index.html")


@app.get("/v2.7")
async def v27_root():
    response = FileResponse("/app/frontend-v2.7/index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


app.mount("/v2.5/static", StaticFiles(directory="/app/frontend-v2.5"), name="static_v25")
app.mount("/v2.6/static", StaticFiles(directory="/app/frontend-v2.6"), name="static_v26")
app.mount("/v2.7/static", StaticFiles(directory="/app/frontend-v2.7/static"), name="static_v27")

# Маршрут для game.js в v2.7 (находится в корне директории)
@app.get("/v2.7/game.js")
async def v27_game_js():
    response = FileResponse("/app/frontend-v2.7/game.js", media_type="application/javascript")
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
    
    await websocket.send_json({
        "type": "queued",
        "position": len(matchmaking_queue),
        "rating": rating
    })
    
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
                
                # Удаляем обоих из очереди
                matchmaking_queue.remove(player_entry)
                matchmaking_queue.remove(best_match)
                
                # Уведомляем обоих
                await websocket.send_json({
                    "type": "match_found",
                    "room_id": room_id,
                    "opponent_rating": best_match["rating"]
                })
                
                await best_match["websocket"].send_json({
                    "type": "match_found",
                    "room_id": room_id,
                    "opponent_rating": rating
                })
                
                return
            
            # Обновляем позицию в очереди
            try:
                pos = matchmaking_queue.index(player_entry) + 1
                await websocket.send_json({
                    "type": "queue_update",
                    "position": pos,
                    "queue_size": len(matchmaking_queue)
                })
            except ValueError:
                break
            
            # Ждём уведомления о новых игроках или таймаут
            try:
                await asyncio.wait_for(matchmaking_event.wait(), timeout=1.0)
                matchmaking_event.clear()
            except asyncio.TimeoutError:
                pass
    
    except WebSocketDisconnect:
        if player_entry in matchmaking_queue:
            matchmaking_queue.remove(player_entry)


import asyncio
import heapq


@app.websocket("/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    await manager.connect(websocket, room_id, player_id)
    
    # Создаём комнату если её нет
    if room_id not in rooms:
        rooms[room_id] = {
            "players": [],
            "spectators": [],
            "game": ChessGame(),
            "colors": {},
            "custom_moves": {"white": {}, "black": {}},
            "ability_cards": {"white": {}, "black": {}},
            "timers": {"white": 600, "black": 600},
            "increment": 0,  # Инкремент времени
            "delay": 0,  # Задержка
            "last_move_time": None,
            "move_history": [],
            "undo_requests": {},
            "rematch_requests": set()
        }
    
    room = rooms[room_id]
    
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
    import time
    if room["last_move_time"] is None:
        room["last_move_time"] = time.time()
    
    await manager.send_to_player(room_id, player_id, {
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
    await manager.send_to_room(room_id, {
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
                    await manager.send_to_player(room_id, player_id, {
                        "type": "error",
                        "message": f"Неизвестный тип сообщения: {message_type}"
                    })
                    continue
            except ValidationError as e:
                logger.warning(f"Ошибка валидации данных от {player_id}: {e}")
                await manager.send_to_player(room_id, player_id, {
                    "type": "error",
                    "message": f"Некорректные данные: {str(e)}"
                })
                continue
            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения от {player_id}: {e}", exc_info=True)
                await manager.send_to_player(room_id, player_id, {
                    "type": "error",
                    "message": "Внутренняя ошибка сервера"
                })
                continue
            
            if message_type == "move":
                player_color = room["colors"].get(player_id)
                
                # Проверяем что ход делает правильный игрок
                if player_color != room["game"].current_player:
                    await manager.send_to_player(room_id, player_id, {
                        "type": "error",
                        "message": "Не ваш ход"
                    })
                    continue
                
                # Выполняем ход (с учётом кастомных ходов)
                result = room["game"].make_move(from_pos, to_pos, room["custom_moves"], promotion_piece)
                
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
                    await manager.send_to_room(room_id, {
                        "type": "move",
                        "from": data["from"],
                        "to": data["to"],
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
                            
                            await manager.send_to_room(room_id, {
                                "type": "rating_updated",
                                "ratings": rating_update
                            })
                else:
                    await manager.send_to_player(room_id, player_id, {
                        "type": "error",
                        "message": result.get("message", "Недопустимый ход")
                    })
            
            elif message_type == "get_valid_moves":
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
                
                await manager.send_to_player(room_id, player_id, {
                    "type": "valid_moves",
                    "position": data["position"],
                    "moves": moves["moves"],
                    "attacks": moves["attacks"]
                })
            
            elif message_type == "resign":
                winner = "black" if room["colors"].get(player_id) == "white" else "white"
                await manager.send_to_room(room_id, {
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
                    
                    await manager.send_to_room(room_id, {
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
                    await manager.send_to_room(room_id, {
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
                    
                    await manager.send_to_room(room_id, {
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
                    
                    await manager.send_to_room(room_id, {
                        "type": "cards_updated",
                        "ability_cards": room["ability_cards"],
                        "custom_moves": room["custom_moves"]
                    })
            
            elif message_type == "reset_custom_moves":
                room["custom_moves"] = {"white": {}, "black": {}}
                room["ability_cards"] = {"white": {}, "black": {}}
                await manager.send_to_room(room_id, {
                    "type": "cards_updated",
                    "ability_cards": room["ability_cards"],
                    "custom_moves": room["custom_moves"]
                })
            
            elif message_type == "chat":
                message = data.message
                if message:
                    # Отправляем сообщение всем кроме отправителя
                    for pid, ws in manager.active_connections.get(room_id, {}).items():
                        if pid != player_id:
                            await ws.send_json({
                                "type": "chat",
                                "message": message
                            })
            
            elif message_type == "offer_draw":
                # Отправляем предложение ничьей противнику
                for pid, ws in manager.active_connections.get(room_id, {}).items():
                    if pid != player_id:
                        await ws.send_json({"type": "draw_offered"})
            
            elif message_type == "draw_response":
                accept = data.accept
                if accept:
                    await manager.send_to_room(room_id, {
                        "type": "game_over",
                        "reason": "draw",
                        "winner": None
                    })
                else:
                    for pid, ws in manager.active_connections.get(room_id, {}).items():
                        if pid != player_id:
                            await ws.send_json({"type": "draw_declined"})
            
            elif message_type == "request_undo":
                # Запрос на отмену хода
                for pid, ws in manager.active_connections.get(room_id, {}).items():
                    if pid != player_id and pid in room["players"]:
                        await ws.send_json({"type": "undo_requested"})
                        room["undo_requests"][player_id] = True
            
            elif message_type == "undo_response":
                accept = data.accept
                if accept and room["move_history"]:
                    # Отменяем последний ход
                    last_move = room["move_history"].pop()
                    room["game"] = ChessGame()  # Пересоздаём игру
                    # Воспроизводим все ходы кроме последнего
                    for move in room["move_history"]:
                        room["game"].make_move(
                            tuple(move["from"]), 
                            tuple(move["to"]), 
                            room["custom_moves"],
                            move.get("promotion")
                        )
                    
                    await manager.send_to_room(room_id, {
                        "type": "undo_accepted",
                        "board": room["game"].get_board_state(),
                        "current_player": room["game"].current_player,
                        "move_history": room["move_history"]
                    })
                else:
                    for pid, ws in manager.active_connections.get(room_id, {}).items():
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
                    
                    await manager.send_to_room(room_id, {
                        "type": "rematch_started",
                        "board": room["game"].get_board_state(),
                        "current_player": room["game"].current_player,
                        "colors": room["colors"],
                        "timers": room["timers"]
                    })
                else:
                    # Уведомляем противника
                    for pid, ws in manager.active_connections.get(room_id, {}).items():
                        if pid != player_id and pid in room["players"]:
                            await ws.send_json({"type": "rematch_requested"})
            
            elif message_type == "rematch_response":
                accept = data.accept
                if accept:
                    room["rematch_requests"].add(player_id)
                    if len(room["rematch_requests"]) >= 2:
                        room["game"] = ChessGame()
                        room["move_history"] = []
                        room["timers"] = {"white": 600, "black": 600}
                        room["last_move_time"] = None
                        room["rematch_requests"] = set()
                        
                        for pid in room["players"]:
                            room["colors"][pid] = "black" if room["colors"][pid] == "white" else "white"
                        
                        await manager.send_to_room(room_id, {
                            "type": "rematch_started",
                            "board": room["game"].get_board_state(),
                            "current_player": room["game"].current_player,
                            "colors": room["colors"],
                            "timers": room["timers"]
                        })
                else:
                    room["rematch_requests"] = set()
                    for pid, ws in manager.active_connections.get(room_id, {}).items():
                        if pid != player_id:
                            await ws.send_json({"type": "rematch_declined"})
            
            elif message_type == "set_time_control":
                # Установка контроля времени
                room["timers"]["white"] = data.time
                room["timers"]["black"] = data.time
                room["increment"] = data.increment
                room["delay"] = data.delay
                
                await manager.send_to_room(room_id, {
                    "type": "time_control_updated",
                    "timers": room["timers"],
                    "increment": room["increment"],
                    "delay": room["delay"]
                })
            
            elif message_type == "get_position_analysis":
                # Анализ позиции
                analysis = PositionAnalyzer.analyze_threats(room["game"].board, room["colors"].get(player_id, "white"))
                evaluation = PositionAnalyzer.evaluate_position(room["game"].board, room["colors"].get(player_id, "white"))
                
                await manager.send_to_player(room_id, player_id, {
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
                
                await manager.send_to_player(room_id, player_id, {
                    "type": "pgn_exported",
                    "pgn": pgn
                })
            
            elif message_type == "get_rating":
                # Получить рейтинг игрока
                rating = await RatingSystem.get_rating(player_id)
                rank = RatingSystem.get_rank(rating)
                history = await RatingSystem.get_rating_history(player_id, 10)
                
                await manager.send_to_player(room_id, player_id, {
                    "type": "rating_info",
                    "rating": rating,
                    "rank": rank,
                    "history": history
                })
    
    except WebSocketDisconnect:
        logger.info(f"Игрок {player_id} отключился от комнаты {room_id}")
        manager.disconnect(room_id, player_id)
        
        # Сохраняем состояние игры при неожиданном отключении
        if player_id in room.get("players", []):
            room["players"].remove(player_id)
            
            # Если игра была в процессе, сохраняем её
            if room.get("game") and len(room["move_history"]) > 0:
                try:
                    white_id = room["players"][0] if len(room["players"]) > 0 and room["colors"].get(room["players"][0]) == "white" else None
                    black_id = room["players"][0] if len(room["players"]) > 0 and room["colors"].get(room["players"][0]) == "black" else None
                    
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
            await manager.send_to_room(room_id, {
                "type": "player_left",
                "players_count": len(room.get("players", [])),
                "player_id": player_id
            })
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об отключении: {e}", exc_info=True)
        
        # Удаляем комнату если она пуста
        if len(room.get("players", [])) == 0 and len(room.get("spectators", [])) == 0:
            if room_id in rooms:
                del rooms[room_id]
                logger.info(f"Комната {room_id} удалена (пуста)")
    except Exception as e:
        logger.error(f"Неожиданная ошибка в WebSocket соединении {player_id}: {e}", exc_info=True)
        try:
            manager.disconnect(room_id, player_id)
        except:
            pass


# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="/app/frontend"), name="static")

# Для совместимости со старыми ссылками /v2 -> /v2.5
@app.get("/v2")
async def v2_redirect():
    return FileResponse("/app/frontend-v2.5/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

