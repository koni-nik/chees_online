"""
Конфигурация приложения.
Поддерживает переменные окружения для гибкой настройки.
"""
import os
from typing import List

class Config:
    """Класс конфигурации приложения."""
    
    # CORS настройки
    CORS_ORIGINS: List[str] = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    
    # Безопасность
    ALLOW_ANY_ORIGIN: bool = os.getenv("ALLOW_ANY_ORIGIN", "false").lower() == "true"
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    
    # База данных
    DB_PATH: str = os.getenv("DB_PATH", "chess_online.db")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    
    # WebSocket
    WS_TIMEOUT: float = float(os.getenv("WS_TIMEOUT", "300.0"))
    MAX_RECONNECT_ATTEMPTS: int = int(os.getenv("MAX_RECONNECT_ATTEMPTS", "5"))
    
    # Matchmaking
    MATCHMAKING_TIMEOUT: float = float(os.getenv("MATCHMAKING_TIMEOUT", "60.0"))
    MATCHMAKING_RATING_RANGE: int = int(os.getenv("MATCHMAKING_RATING_RANGE", "100"))
    
    # Время по умолчанию
    DEFAULT_TIME_CONTROL: int = int(os.getenv("DEFAULT_TIME_CONTROL", "600"))
    DEFAULT_TIME_INCREMENT: int = int(os.getenv("DEFAULT_TIME_INCREMENT", "0"))
    DEFAULT_TIME_DELAY: int = int(os.getenv("DEFAULT_TIME_DELAY", "0"))
    
    # Рейтинг и Elo
    INITIAL_RATING: int = int(os.getenv("INITIAL_RATING", "1200"))
    ELO_K_FACTOR: int = int(os.getenv("ELO_K_FACTOR", "32"))
    
    # Окружение
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")  # development или production
    
    # Очистка ресурсов
    ROOM_CLEANUP_INTERVAL: int = int(os.getenv("ROOM_CLEANUP_INTERVAL", "300"))  # 5 минут
    TOKEN_CLEANUP_INTERVAL: int = int(os.getenv("TOKEN_CLEANUP_INTERVAL", "3600"))  # 1 час
    
    # JWT настройки
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    
    # Расширяемость: список доступных версий фронтенда
    FRONTEND_VERSIONS: List[str] = [
        "frontend",
        "frontend-v2.5",
        "frontend-v2.6",
        "frontend-v2.7"
    ]
    
    # Расширяемость: список доступных тем (для будущего использования)
    AVAILABLE_THEMES: List[str] = [
        "default",
        "dark",
        "classic"
    ]


config = Config()

