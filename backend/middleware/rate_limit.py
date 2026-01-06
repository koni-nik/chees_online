"""
Rate limiting middleware для защиты от злоупотреблений.
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request  # Используем starlette.requests.Request для slowapi
from logger import setup_logger
from config import config

logger = setup_logger()

# Создаём лимитер
limiter = Limiter(key_func=get_remote_address)

# Получаем функцию обработки ошибок rate limit
rate_limit_handler = _rate_limit_exceeded_handler


def get_rate_limiter() -> Limiter:
    """Возвращает экземпляр лимитера."""
    return limiter

