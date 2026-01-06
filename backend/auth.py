"""
Система аутентификации с JWT токенами и bcrypt для версии 2.8+.
"""
import bcrypt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from logger import setup_logger
from config import config
from database import db

logger = setup_logger()


class AuthManager:
    """Менеджер аутентификации с JWT токенами и bcrypt."""
    
    def __init__(self):
        """Инициализирует менеджер аутентификации."""
        self.secret_key = config.JWT_SECRET_KEY
        self.algorithm = config.JWT_ALGORITHM
        self.access_token_expire_minutes = config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = config.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    
    def hash_password(self, password: str) -> str:
        """
        Хеширует пароль с использованием bcrypt.
        
        Args:
            password: Пароль в открытом виде
            
        Returns:
            Хеш пароля
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Проверяет пароль против хеша.
        
        Args:
            plain_password: Пароль в открытом виде
            hashed_password: Хеш пароля
            
        Returns:
            True если пароль верный, иначе False
        """
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Ошибка проверки пароля: {e}")
            return False
    
    def create_access_token(self, data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Создаёт JWT access токен.
        
        Args:
            data: Данные для включения в токен (например, {"sub": user_id})
            expires_delta: Время жизни токена (опционально)
            
        Returns:
            JWT токен
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict) -> str:
        """
        Создаёт JWT refresh токен.
        
        Args:
            data: Данные для включения в токен
            
        Returns:
            JWT refresh токен
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def decode_token(self, token: str, token_type: str = "access") -> Optional[Dict]:
        """
        Декодирует и проверяет JWT токен.
        
        Args:
            token: JWT токен
            token_type: Тип токена ("access" или "refresh")
            
        Returns:
            Данные токена или None если токен невалиден
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Проверяем тип токена
            if payload.get("type") != token_type:
                logger.warning(f"Неверный тип токена: ожидался {token_type}, получен {payload.get('type')}")
                return None
            
            return payload
        except JWTError as e:
            logger.debug(f"Ошибка декодирования токена: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при декодировании токена: {e}")
            return None
    
    async def create_user(self, username: str, email: str, password: str, is_guest: bool = False) -> Optional[int]:
        """
        Создаёт нового пользователя.
        
        Args:
            username: Имя пользователя
            email: Email
            password: Пароль в открытом виде
            is_guest: Является ли гостем
            
        Returns:
            ID созданного пользователя или None при ошибке
        """
        try:
            # Проверяем, не существует ли уже пользователь с таким email или username
            existing_user = await db.get_user_by_email(email)
            if existing_user:
                logger.warning(f"Пользователь с email {email} уже существует")
                return None
            
            existing_user = await db.get_user_by_username(username)
            if existing_user:
                logger.warning(f"Пользователь с username {username} уже существует")
                return None
            
            # Хешируем пароль
            password_hash = self.hash_password(password)
            
            # Создаём пользователя
            user_id = await db.create_user(username, email, password_hash, is_guest)
            
            logger.info(f"Создан пользователь: {username} (ID: {user_id})")
            return user_id
        except Exception as e:
            logger.error(f"Ошибка создания пользователя: {e}", exc_info=True)
            return None
    
    async def authenticate_user(self, email: str, password: str) -> Optional[Dict]:
        """
        Аутентифицирует пользователя по email и паролю.
        
        Args:
            email: Email пользователя
            password: Пароль в открытом виде
            
        Returns:
            Данные пользователя или None если аутентификация не удалась
        """
        try:
            # Получаем пользователя из БД
            user = await db.get_user_by_email(email)
            if not user:
                logger.warning(f"Попытка входа с несуществующим email: {email}")
                return None
            
            # Проверяем пароль
            if not self.verify_password(password, user["password_hash"]):
                logger.warning(f"Неверный пароль для пользователя {email}")
                return None
            
            # Обновляем время последнего входа
            await db.update_user_last_login(user["id"])
            
            logger.info(f"Пользователь {email} успешно аутентифицирован")
            return user
        except Exception as e:
            logger.error(f"Ошибка аутентификации пользователя: {e}", exc_info=True)
            return None
    
    async def generate_tokens_for_user(self, user_id: int) -> Dict[str, str]:
        """
        Генерирует access и refresh токены для пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь с access_token и refresh_token
        """
        # Создаём токены
        access_token = self.create_access_token(data={"sub": str(user_id)})
        refresh_token = self.create_refresh_token(data={"sub": str(user_id)})
        
        # Сохраняем refresh токен в БД
        expires_at = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        await db.save_refresh_token(user_id, refresh_token, expires_at)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    async def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """
        Обновляет access токен используя refresh токен.
        
        Args:
            refresh_token: Refresh токен
            
        Returns:
            Новые токены или None если refresh токен невалиден
        """
        try:
            # Проверяем refresh токен в БД
            session = await db.get_refresh_token(refresh_token)
            if not session:
                logger.warning("Попытка обновления токена с невалидным refresh токеном")
                return None
            
            # Декодируем токен
            payload = self.decode_token(refresh_token, token_type="refresh")
            if not payload:
                return None
            
            user_id = int(payload.get("sub"))
            
            # Проверяем, что user_id совпадает с сессией
            if session["user_id"] != user_id:
                logger.warning(f"Несоответствие user_id в токене и сессии")
                return None
            
            # Генерируем новые токены
            return await self.generate_tokens_for_user(user_id)
        except Exception as e:
            logger.error(f"Ошибка обновления токена: {e}", exc_info=True)
            return None
    
    async def revoke_refresh_token(self, refresh_token: str):
        """
        Отзывает refresh токен.
        
        Args:
            refresh_token: Refresh токен для отзыва
        """
        await db.revoke_refresh_token(refresh_token)
        logger.debug("Refresh токен отозван")
    
    async def get_user_from_token(self, token: str) -> Optional[Dict]:
        """
        Получает пользователя из access токена.
        
        Args:
            token: Access токен
            
        Returns:
            Данные пользователя или None
        """
        try:
            payload = self.decode_token(token, token_type="access")
            if not payload:
                return None
            
            user_id = int(payload.get("sub"))
            user = await db.get_user_by_id(user_id)
            return user
        except Exception as e:
            logger.error(f"Ошибка получения пользователя из токена: {e}", exc_info=True)
            return None
    
    def generate_verification_token(self) -> str:
        """Генерирует токен для верификации email."""
        return secrets.token_urlsafe(32)
    
    def generate_password_reset_token(self) -> str:
        """Генерирует токен для сброса пароля."""
        return secrets.token_urlsafe(32)


# Глобальный экземпляр менеджера аутентификации
auth_manager = AuthManager()
