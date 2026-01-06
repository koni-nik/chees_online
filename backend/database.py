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
        self._connection = None  # Переиспользуемое соединение
    
    async def initialize(self):
        """Инициализирует базу данных и создаёт таблицы."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей (v2.8+)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    is_guest INTEGER DEFAULT 0,
                    is_email_verified INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица игроков (обновлена для связи с users)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    player_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    rating INTEGER NOT NULL DEFAULT 1200,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Таблица сессий пользователей (для refresh токенов)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    refresh_token TEXT NOT NULL UNIQUE,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Таблица токенов верификации email
            await db.execute("""
                CREATE TABLE IF NOT EXISTS email_verification_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Таблица токенов сброса пароля
            await db.execute("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
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
                CREATE INDEX IF NOT EXISTS idx_users_email 
                ON users(email)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_username 
                ON users(username)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_players_user_id 
                ON players(user_id)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id 
                ON user_sessions(user_id)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_sessions_token 
                ON user_sessions(refresh_token)
            """)
            
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
    
    async def _get_connection(self):
        """Получает или создает соединение с БД."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(
                self.db_path,
                check_same_thread=False
            )
            self._connection.row_factory = aiosqlite.Row
        return self._connection
    
    async def get_or_create_player(self, player_id: str) -> Dict:
        """
        Получает или создаёт игрока.
        
        Args:
            player_id: ID игрока
            
        Returns:
            Словарь с данными игрока
        """
        db = await self._get_connection()
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
        db = await self._get_connection()
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
        db = await self._get_connection()
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
        db = await self._get_connection()
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
        db = await self._get_connection()
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
        db = await self._get_connection()
        cursor = await db.execute("""
            SELECT * FROM games 
            WHERE white_player_id = ? OR black_player_id = ?
            ORDER BY created_at DESC 
            LIMIT ?
        """, (player_id, player_id, limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    # ============ Методы для работы с пользователями (v2.8+) ============
    
    async def create_user(self, username: str, email: str, password_hash: str, is_guest: bool = False) -> int:
        """
        Создаёт нового пользователя.
        
        Args:
            username: Имя пользователя
            email: Email
            password_hash: Хеш пароля
            is_guest: Является ли гостем
            
        Returns:
            ID созданного пользователя
        """
        db = await self._get_connection()
        cursor = await db.execute("""
            INSERT INTO users (username, email, password_hash, is_guest)
            VALUES (?, ?, ?, ?)
        """, (username, email, password_hash, 1 if is_guest else 0))
        await db.commit()
        user_id = cursor.lastrowid
        logger.info(f"Создан пользователь: {username} (ID: {user_id})")
        return user_id
    
    async def get_user_by_email(self, email: str) -> Optional[Dict]:
        """
        Получает пользователя по email.
        
        Args:
            email: Email пользователя
            
        Returns:
            Данные пользователя или None
        """
        db = await self._get_connection()
        cursor = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """
        Получает пользователя по ID.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Данные пользователя или None
        """
        db = await self._get_connection()
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    
    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """
        Получает пользователя по username.
        
        Args:
            username: Имя пользователя
            
        Returns:
            Данные пользователя или None
        """
        db = await self._get_connection()
        cursor = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    
    async def update_user_last_login(self, user_id: int):
        """
        Обновляет время последнего входа пользователя.
        
        Args:
            user_id: ID пользователя
        """
        db = await self._get_connection()
        await db.execute("""
            UPDATE users SET last_login = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user_id,))
        await db.commit()
    
    async def verify_user_email(self, user_id: int):
        """
        Отмечает email пользователя как верифицированный.
        
        Args:
            user_id: ID пользователя
        """
        db = await self._get_connection()
        await db.execute("""
            UPDATE users SET is_email_verified = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user_id,))
        await db.commit()
        logger.info(f"Email пользователя {user_id} верифицирован")
    
    async def save_refresh_token(self, user_id: int, refresh_token: str, expires_at: datetime):
        """
        Сохраняет refresh токен в БД.
        
        Args:
            user_id: ID пользователя
            refresh_token: Refresh токен
            expires_at: Время истечения
        """
        db = await self._get_connection()
        await db.execute("""
            INSERT INTO user_sessions (user_id, refresh_token, expires_at)
            VALUES (?, ?, ?)
        """, (user_id, refresh_token, expires_at))
        await db.commit()
    
    async def get_refresh_token(self, refresh_token: str) -> Optional[Dict]:
        """
        Получает данные сессии по refresh токену.
        
        Args:
            refresh_token: Refresh токен
            
        Returns:
            Данные сессии или None
        """
        db = await self._get_connection()
        cursor = await db.execute("""
            SELECT * FROM user_sessions 
            WHERE refresh_token = ? AND expires_at > datetime('now')
        """, (refresh_token,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    
    async def revoke_refresh_token(self, refresh_token: str):
        """
        Отзывает refresh токен.
        
        Args:
            refresh_token: Refresh токен для отзыва
        """
        db = await self._get_connection()
        await db.execute("""
            DELETE FROM user_sessions WHERE refresh_token = ?
        """, (refresh_token,))
        await db.commit()
    
    async def revoke_all_user_sessions(self, user_id: int):
        """
        Отзывает все сессии пользователя.
        
        Args:
            user_id: ID пользователя
        """
        db = await self._get_connection()
        await db.execute("""
            DELETE FROM user_sessions WHERE user_id = ?
        """, (user_id,))
        await db.commit()
        logger.info(f"Все сессии пользователя {user_id} отозваны")
    
    async def save_email_verification_token(self, user_id: int, token: str, expires_at: datetime):
        """
        Сохраняет токен верификации email.
        
        Args:
            user_id: ID пользователя
            token: Токен верификации
            expires_at: Время истечения
        """
        db = await self._get_connection()
        await db.execute("""
            INSERT INTO email_verification_tokens (user_id, token, expires_at)
            VALUES (?, ?, ?)
        """, (user_id, token, expires_at))
        await db.commit()
    
    async def get_email_verification_token(self, token: str) -> Optional[Dict]:
        """
        Получает токен верификации email.
        
        Args:
            token: Токен верификации
            
        Returns:
            Данные токена или None
        """
        db = await self._get_connection()
        cursor = await db.execute("""
            SELECT * FROM email_verification_tokens 
            WHERE token = ? AND expires_at > datetime('now')
        """, (token,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    
    async def delete_email_verification_token(self, token: str):
        """
        Удаляет токен верификации email.
        
        Args:
            token: Токен для удаления
        """
        db = await self._get_connection()
        await db.execute("""
            DELETE FROM email_verification_tokens WHERE token = ?
        """, (token,))
        await db.commit()
    
    async def save_password_reset_token(self, user_id: int, token: str, expires_at: datetime):
        """
        Сохраняет токен сброса пароля.
        
        Args:
            user_id: ID пользователя
            token: Токен сброса пароля
            expires_at: Время истечения
        """
        db = await self._get_connection()
        await db.execute("""
            INSERT INTO password_reset_tokens (user_id, token, expires_at)
            VALUES (?, ?, ?)
        """, (user_id, token, expires_at))
        await db.commit()
    
    async def get_password_reset_token(self, token: str) -> Optional[Dict]:
        """
        Получает токен сброса пароля.
        
        Args:
            token: Токен сброса пароля
            
        Returns:
            Данные токена или None
        """
        db = await self._get_connection()
        cursor = await db.execute("""
            SELECT * FROM password_reset_tokens 
            WHERE token = ? AND expires_at > datetime('now')
        """, (token,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    
    async def delete_password_reset_token(self, token: str):
        """
        Удаляет токен сброса пароля.
        
        Args:
            token: Токен для удаления
        """
        db = await self._get_connection()
        await db.execute("""
            DELETE FROM password_reset_tokens WHERE token = ?
        """, (token,))
        await db.commit()
    
    async def update_user_password(self, user_id: int, new_password_hash: str):
        """
        Обновляет пароль пользователя.
        
        Args:
            user_id: ID пользователя
            new_password_hash: Новый хеш пароля
        """
        db = await self._get_connection()
        await db.execute("""
            UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_password_hash, user_id))
        await db.commit()
        logger.info(f"Пароль пользователя {user_id} обновлён")
    
    async def link_player_to_user(self, player_id: str, user_id: int):
        """
        Связывает player_id с user_id.
        
        Args:
            player_id: ID игрока
            user_id: ID пользователя
        """
        db = await self._get_connection()
        await db.execute("""
            UPDATE players SET user_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE player_id = ?
        """, (user_id, player_id))
        await db.commit()
        logger.debug(f"Игрок {player_id} связан с пользователем {user_id}")


# Глобальный экземпляр базы данных
db = Database()



