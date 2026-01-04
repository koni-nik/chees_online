"""
Сервис для matchmaking игроков (v2.8).
"""
import heapq
import time
import uuid
import asyncio
from typing import Dict, List, Optional, Tuple
from fastapi import WebSocket, WebSocketDisconnect
from logger import setup_logger
from rating import RatingSystem

logger = setup_logger()


class MatchmakingService:
    """Сервис для подбора соперников."""
    
    def __init__(self):
        """Инициализирует сервис matchmaking."""
        # Очередь игроков: [(rating, timestamp, player_entry), ...]
        # Используем heap для эффективной сортировки
        self._queue: List[Tuple[int, float, Dict]] = []
        self._queue_lock = asyncio.Lock()
        self._event: Optional[asyncio.Event] = None
    
    def _get_event(self) -> asyncio.Event:
        """Получает или создаёт событие для уведомлений."""
        if self._event is None:
            self._event = asyncio.Event()
        return self._event
    
    async def add_player(self, player_id: str, websocket: WebSocket) -> int:
        """
        Добавляет игрока в очередь matchmaking.
        
        Args:
            player_id: ID игрока
            websocket: WebSocket соединение
            
        Returns:
            Позиция в очереди
        """
        async with self._queue_lock:
            # Получаем рейтинг игрока
            rating = await RatingSystem.get_rating(player_id)
            timestamp = time.time()
            
            player_entry = {
                "player_id": player_id,
                "websocket": websocket,
                "rating": rating,
                "timestamp": timestamp
            }
            
            # Добавляем в heap (сортируем по rating, затем по timestamp)
            heapq.heappush(self._queue, (rating, timestamp, player_entry))
            
            # Уведомляем о новом игроке
            self._get_event().set()
            
            position = len(self._queue)
            logger.debug(f"Игрок {player_id} добавлен в очередь matchmaking (позиция: {position})")
            return position
    
    async def remove_player(self, player_id: str):
        """
        Удаляет игрока из очереди.
        
        Args:
            player_id: ID игрока
        """
        async with self._queue_lock:
            # Создаём новую очередь без указанного игрока
            new_queue = [
                item for item in self._queue
                if item[2]["player_id"] != player_id
            ]
            heapq.heapify(new_queue)
            self._queue = new_queue
    
    async def find_match(self, player_id: str, max_rating_diff: int = 100, max_wait_time: float = 60.0) -> Optional[Tuple[str, Dict]]:
        """
        Ищет соперника для игрока.
        
        Args:
            player_id: ID игрока
            max_rating_diff: Максимальная разница в рейтинге (базовая)
            max_wait_time: Максимальное время ожидания в секундах
            
        Returns:
            Tuple (room_id, opponent_entry) если соперник найден, иначе None
        """
        async with self._queue_lock:
            # Находим игрока в очереди
            player_entry = None
            player_index = None
            
            for i, (rating, timestamp, entry) in enumerate(self._queue):
                if entry["player_id"] == player_id:
                    player_entry = entry
                    player_index = i
                    break
            
            if not player_entry:
                return None
            
            player_rating = player_entry["rating"]
            wait_time = time.time() - player_entry["timestamp"]
            
            # Расширяем диапазон поиска со временем
            current_max_diff = max_rating_diff + int(wait_time * 10)
            
            # Ищем лучшего соперника
            best_match = None
            best_diff = float('inf')
            best_index = None
            
            for i, (rating, timestamp, entry) in enumerate(self._queue):
                if i == player_index:
                    continue
                
                rating_diff = abs(rating - player_rating)
                
                if rating_diff <= current_max_diff and rating_diff < best_diff:
                    best_match = entry
                    best_diff = rating_diff
                    best_index = i
            
            if best_match:
                # Удаляем обоих игроков из очереди
                indices_to_remove = sorted([player_index, best_index], reverse=True)
                for idx in indices_to_remove:
                    self._queue.pop(idx)
                heapq.heapify(self._queue)
                
                # Создаём room_id
                room_id = str(uuid.uuid4())[:8]
                
                logger.info(f"Найден матч: {player_id} vs {best_match['player_id']} (комната: {room_id})")
                return room_id, best_match
            
            return None
    
    async def get_queue_position(self, player_id: str) -> Optional[int]:
        """
        Получает позицию игрока в очереди.
        
        Args:
            player_id: ID игрока
            
        Returns:
            Позиция в очереди (1-based) или None
        """
        async with self._queue_lock:
            for i, (rating, timestamp, entry) in enumerate(self._queue):
                if entry["player_id"] == player_id:
                    return i + 1
            return None
    
    def get_queue_size(self) -> int:
        """Возвращает размер очереди."""
        return len(self._queue)
    
    async def wait_for_match(self, timeout: float = 1.0):
        """
        Ожидает уведомления о новых игроках.
        
        Args:
            timeout: Таймаут в секундах
        """
        event = self._get_event()
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            event.clear()
        except asyncio.TimeoutError:
            pass


# Глобальный экземпляр сервиса matchmaking
matchmaking_service = MatchmakingService()

