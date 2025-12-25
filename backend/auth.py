"""
Базовая система аутентификации для онлайн версии.
"""
import secrets
import hashlib
import time
from typing import Optional, Dict
from logger import setup_logger

logger = setup_logger()


class AuthManager:
    """Менеджер аутентификации с простой системой токенов."""
    
    def __init__(self):
        """Инициализирует менеджер аутентификации."""
        self.tokens: Dict[str, Dict] = {}  # token -> {player_id, created_at, expires_at}
        self.token_expiry = 3600 * 24  # 24 часа
    
    def generate_token(self, player_id: str) -> str:
        """
        Генерирует токен для игрока.
        
        Args:
            player_id: ID игрока
            
        Returns:
            Токен доступа
        """
        token = secrets.token_urlsafe(32)
        self.tokens[token] = {
            "player_id": player_id,
            "created_at": time.time(),
            "expires_at": time.time() + self.token_expiry
        }
        logger.debug(f"Токен сгенерирован для игрока {player_id}")
        return token
    
    def validate_token(self, token: str) -> Optional[str]:
        """
        Проверяет токен и возвращает player_id если валиден.
        
        Args:
            token: Токен для проверки
            
        Returns:
            player_id если токен валиден, иначе None
        """
        if token not in self.tokens:
            return None
        
        token_data = self.tokens[token]
        
        # Проверяем срок действия
        if time.time() > token_data["expires_at"]:
            del self.tokens[token]
            logger.debug(f"Токен истёк: {token[:10]}...")
            return None
        
        return token_data["player_id"]
    
    def revoke_token(self, token: str):
        """
        Отзывает токен.
        
        Args:
            token: Токен для отзыва
        """
        if token in self.tokens:
            del self.tokens[token]
            logger.debug(f"Токен отозван: {token[:10]}...")
    
    def cleanup_expired_tokens(self):
        """Удаляет истёкшие токены."""
        current_time = time.time()
        expired = [
            token for token, data in self.tokens.items()
            if current_time > data["expires_at"]
        ]
        for token in expired:
            del self.tokens[token]
        
        if expired:
            logger.debug(f"Удалено {len(expired)} истёкших токенов")


# Глобальный экземпляр менеджера аутентификации
auth_manager = AuthManager()



