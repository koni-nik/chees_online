"""
Модель базы данных SQLite для онлайн версии шахмат.
"""
import aiosqlite
import json
from typing import Optional, List, Dict
from datetime import datetime
from logger import setup_logger

logger = setup_logger()


class Database:
    """Класс для работы с базой данных SQLite."""
    
    def __init__(self, db_path: str = "chess_online.db"):
        """
        Инициализирует подключение к базе данных.
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self._initialized = False
    
    async def initialize(self):
        """Инициализирует базу данных и создаёт таблицы."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица игроков
            await db.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    player_id TEXT PRIMARY KEY,
                    rating INTEGER NOT NULL DEFAULT 1200,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица истории рейтингов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS rating_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id TEXT NOT NULL,
                    old_rating INTEGER NOT NULL,
                    new_rating INTEGER NOT NULL,
                    opponent_id TEXT,
                    opponent_rating INTEGER,
                    result REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (player_id) REFERENCES players(player_id)
                )
            """)
            
            # Таблица завершенных игр
            await db.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    white_player_id TEXT NOT NULL,
                    black_player_id TEXT NOT NULL,
                    result TEXT,
                    move_history TEXT,
                    pgn TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (white_player_id) REFERENCES players(player_id),
                    FOREIGN KEY (black_player_id) REFERENCES players(player_id)
                )
            """)
            
            # Индексы для быстрого поиска
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_rating_history_player 
                ON rating_history(player_id, created_at DESC)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_games_player 
                ON games(white_player_id, black_player_id, created_at DESC)
            """)
            
            await db.commit()
            self._initialized = True
            logger.info("База данных инициализирована")
    
    async def get_or_create_player(self, player_id: str) -> Dict:
        """
        Получает или создаёт игрока.
        
        Args:
            player_id: ID игрока
            
        Returns:
            Словарь с данными игрока
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM players WHERE player_id = ?",
                (player_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return dict(row)
            
            # Создаём нового игрока
            await db.execute(
                "INSERT INTO players (player_id, rating) VALUES (?, ?)",
                (player_id, 1200)
            )
            await db.commit()
            
            cursor = await db.execute(
                "SELECT * FROM players WHERE player_id = ?",
                (player_id,)
            )
            row = await cursor.fetchone()
            return dict(row)
    
    async def update_player_rating(self, player_id: str, new_rating: int):
        """
        Обновляет рейтинг игрока.
        
        Args:
            player_id: ID игрока
            new_rating: Новый рейтинг
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE players SET rating = ?, updated_at = CURRENT_TIMESTAMP WHERE player_id = ?",
                (new_rating, player_id)
            )
            await db.commit()
            logger.debug(f"Рейтинг игрока {player_id} обновлён до {new_rating}")
    
    async def add_rating_history(
        self,
        player_id: str,
        old_rating: int,
        new_rating: int,
        opponent_id: Optional[str] = None,
        opponent_rating: Optional[int] = None,
        result: float = 0.0
    ):
        """
        Добавляет запись в историю рейтингов.
        
        Args:
            player_id: ID игрока
            old_rating: Старый рейтинг
            new_rating: Новый рейтинг
            opponent_id: ID соперника
            opponent_rating: Рейтинг соперника
            result: Результат (1.0 - победа, 0.5 - ничья, 0.0 - поражение)
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO rating_history 
                (player_id, old_rating, new_rating, opponent_id, opponent_rating, result)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (player_id, old_rating, new_rating, opponent_id, opponent_rating, result))
            await db.commit()
            logger.debug(f"Добавлена запись в историю рейтинга для {player_id}")
    
    async def get_rating_history(self, player_id: str, limit: int = 10) -> List[Dict]:
        """
        Получает историю изменения рейтинга игрока.
        
        Args:
            player_id: ID игрока
            limit: Максимальное количество записей
            
        Returns:
            Список записей истории рейтинга
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM rating_history 
                WHERE player_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (player_id, limit))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def save_game(
        self,
        white_player_id: str,
        black_player_id: str,
        result: Optional[str] = None,
        move_history: Optional[List] = None,
        pgn: Optional[str] = None
    ) -> int:
        """
        Сохраняет завершенную игру.
        
        Args:
            white_player_id: ID игрока белыми
            black_player_id: ID игрока чёрными
            result: Результат игры ("1-0", "0-1", "1/2-1/2")
            move_history: История ходов
            pgn: PGN запись партии
            
        Returns:
            ID сохранённой игры
        """
        async with aiosqlite.connect(self.db_path) as db:
            move_history_json = json.dumps(move_history) if move_history else None
            cursor = await db.execute("""
                INSERT INTO games (white_player_id, black_player_id, result, move_history, pgn)
                VALUES (?, ?, ?, ?, ?)
            """, (white_player_id, black_player_id, result, move_history_json, pgn))
            await db.commit()
            game_id = cursor.lastrowid
            logger.info(f"Игра сохранена: ID={game_id}, white={white_player_id}, black={black_player_id}")
            return game_id
    
    async def get_player_games(self, player_id: str, limit: int = 10) -> List[Dict]:
        """
        Получает последние игры игрока.
        
        Args:
            player_id: ID игрока
            limit: Максимальное количество игр
            
        Returns:
            Список игр
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM games 
                WHERE white_player_id = ? OR black_player_id = ?
                ORDER BY created_at DESC 
                LIMIT ?
            """, (player_id, player_id, limit))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# Глобальный экземпляр базы данных
db = Database()



