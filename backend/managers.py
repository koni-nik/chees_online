"""
Менеджеры для управления состоянием приложения.
"""
from typing import Dict, Optional
from fastapi import WebSocket
import time
import asyncio
from logger import setup_logger
from game_logic import ChessGame
from config import config

logger = setup_logger()


class RoomManager:
    """Менеджер для управления игровыми комнатами."""
    
    def __init__(self):
        self.rooms: Dict[str, Dict] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def create_room(self, room_id: str) -> Dict:
        """Создаёт новую комнату."""
        if room_id not in self.rooms:
            self.rooms[room_id] = {
                "players": [],
                "spectators": [],
                "game": ChessGame(),
                "colors": {},
                "custom_moves": {"white": {}, "black": {}},
                "ability_cards": {"white": {}, "black": {}},
                "timers": {"white": config.DEFAULT_TIME_CONTROL, "black": config.DEFAULT_TIME_CONTROL},
                "increment": config.DEFAULT_TIME_INCREMENT,
                "delay": config.DEFAULT_TIME_DELAY,
                "last_move_time": None,
                "move_history": [],
                "undo_requests": {},
                "rematch_requests": set(),
                "created_at": time.time(),
                "last_activity": time.time()
            }
            logger.debug(f"Создана комната {room_id}")
        return self.rooms[room_id]
    
    def get_room(self, room_id: str) -> Optional[Dict]:
        """Получает комнату по ID."""
        return self.rooms.get(room_id)
    
    def delete_room(self, room_id: str):
        """Удаляет комнату."""
        if room_id in self.rooms:
            del self.rooms[room_id]
            logger.debug(f"Удалена комната {room_id}")
    
    def update_activity(self, room_id: str):
        """Обновляет время последней активности комнаты."""
        if room_id in self.rooms:
            self.rooms[room_id]["last_activity"] = time.time()
    
    async def cleanup_empty_rooms(self):
        """Периодическая очистка пустых комнат."""
        while True:
            try:
                current_time = time.time()
                rooms_to_delete = []
                
                for room_id, room_data in list(self.rooms.items()):
                    # Удаляем комнаты без игроков и наблюдателей, которые неактивны более 1 часа
                    if (len(room_data.get("players", [])) == 0 and 
                        len(room_data.get("spectators", [])) == 0 and
                        current_time - room_data.get("last_activity", 0) > 3600):
                        rooms_to_delete.append(room_id)
                
                for room_id in rooms_to_delete:
                    self.delete_room(room_id)
                    logger.info(f"Удалена неактивная комната {room_id}")
                
            except Exception as e:
                logger.error(f"Ошибка при очистке комнат: {e}", exc_info=True)
            
            await asyncio.sleep(config.ROOM_CLEANUP_INTERVAL)
    
    def start_cleanup_task(self, loop: asyncio.AbstractEventLoop):
        """Запускает задачу очистки."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = loop.create_task(self.cleanup_empty_rooms())


class TournamentRoomManager:
    """Менеджер для управления турнирными комнатами."""
    
    def __init__(self):
        self.tournament_rooms: Dict[str, Dict] = {}
    
    def create_tournament_room(self, room_id: str, name: str, start_time: str, start_time_utc) -> Dict:
        """Создаёт турнирную комнату."""
        self.tournament_rooms[room_id] = {
            "id": room_id,
            "name": name,
            "start_time": start_time,
            "start_time_utc": start_time_utc,
            "players": [],
            "spectators": [],
            "created_at": time.time(),
            "status": "waiting"
        }
        return self.tournament_rooms[room_id]
    
    def get_tournament_room(self, room_id: str) -> Optional[Dict]:
        """Получает турнирную комнату по ID."""
        return self.tournament_rooms.get(room_id)
    
    def delete_tournament_room(self, room_id: str):
        """Удаляет турнирную комнату."""
        if room_id in self.tournament_rooms:
            del self.tournament_rooms[room_id]
    
    def cleanup_old_rooms(self, max_age_hours: int = 24):
        """Очищает старые турнирные комнаты."""
        current_time = time.time()
        max_age = max_age_hours * 3600
        
        rooms_to_delete = [
            room_id for room_id, room_data in self.tournament_rooms.items()
            if current_time - room_data.get("created_at", 0) > max_age
        ]
        
        for room_id in rooms_to_delete:
            self.delete_tournament_room(room_id)
            logger.info(f"Удалена старая турнирная комната {room_id}")


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


# Глобальные экземпляры менеджеров
room_manager = RoomManager()
tournament_room_manager = TournamentRoomManager()
connection_manager = ConnectionManager()

