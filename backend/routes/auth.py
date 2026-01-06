"""
Auth routes для версии 2.8.
Реализация системы аккаунтов с JWT и bcrypt.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.requests import Request as StarletteRequest  # Для slowapi
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime, timedelta
from logger import setup_logger
from auth import auth_manager
from database import db
from config import config
from middleware.rate_limit import get_rate_limiter

logger = setup_logger()

router = APIRouter()
security = HTTPBearer()
limiter = get_rate_limiter()


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError('Username must be between 3 and 50 characters')
        if not v.isalnum() and '_' not in v and '-' not in v:
            raise ValueError('Username can only contain letters, numbers, underscores and hyphens')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register(request: RegisterRequest, req: StarletteRequest = None):
    """
    Регистрация нового пользователя.
    """
    try:
        # Создаём пользователя
        user_id = await auth_manager.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            is_guest=False
        )
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email или username уже существует"
            )
        
        # Генерируем токены
        tokens = await auth_manager.generate_tokens_for_user(user_id)
        
        # Создаём player_id для пользователя
        player_id = f"user_{user_id}"
        await db.get_or_create_player(player_id)
        await db.link_player_to_user(player_id, user_id)
        
        # Генерируем токен верификации email (пока не отправляем)
        verification_token = auth_manager.generate_verification_token()
        expires_at = datetime.utcnow() + timedelta(days=7)
        await db.save_email_verification_token(user_id, verification_token, expires_at)
        
        logger.info(f"Пользователь зарегистрирован: {request.email} (ID: {user_id})")
        
        return TokenResponse(**tokens)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка регистрации: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка регистрации"
        )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: LoginRequest, req: StarletteRequest = None):
    """
    Вход в систему.
    """
    try:
        # Аутентифицируем пользователя
        user = await auth_manager.authenticate_user(request.email, request.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль"
            )
        
        # Генерируем токены
        tokens = await auth_manager.generate_tokens_for_user(user["id"])
        
        logger.info(f"Пользователь вошел: {request.email} (ID: {user['id']})")
        
        return TokenResponse(**tokens)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка входа: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка входа"
        )


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Выход из системы - отзыв refresh токена."""
    try:
        token = credentials.credentials
        
        # Получаем refresh токен из запроса (в реальности нужно передавать его отдельно)
        # Пока просто отзываем все сессии пользователя
        user = await auth_manager.get_user_from_token(token)
        if user:
            await db.revoke_all_user_sessions(user["id"])
            logger.info(f"Пользователь {user['id']} вышел из системы")
        
        return {"message": "Выход выполнен успешно"}
    except Exception as e:
        logger.error(f"Ошибка выхода: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка выхода"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """Обновление access токена."""
    try:
        tokens = await auth_manager.refresh_access_token(request.refresh_token)
        
        if not tokens:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный refresh token"
            )
        
        return TokenResponse(**tokens)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления токена: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обновления токена"
        )


@router.get("/me")
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Получение информации о текущем пользователе."""
    try:
        token = credentials.credentials
        user = await auth_manager.get_user_from_token(token)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный токен"
            )
        
        # Получаем player_id для пользователя
        player_id = None
        async with db._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT player_id FROM players WHERE user_id = ? LIMIT 1",
                (user["id"],)
            )
            row = await cursor.fetchone()
            if row:
                player_id = row[0]
        
        return {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "is_guest": bool(user["is_guest"]),
            "is_email_verified": bool(user["is_email_verified"]),
            "player_id": player_id,
            "created_at": user["created_at"],
            "last_login": user["last_login"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения пользователя: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения пользователя"
        )


@router.get("/verify-email")
async def verify_email(token: str):
    """Верификация email."""
    try:
        # Получаем токен из БД
        token_data = await db.get_email_verification_token(token)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недействительный или истёкший токен верификации"
            )
        
        # Верифицируем email
        await db.verify_user_email(token_data["user_id"])
        
        # Удаляем токен
        await db.delete_email_verification_token(token)
        
        logger.info(f"Email пользователя {token_data['user_id']} верифицирован")
        
        return {"message": "Email успешно верифицирован"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка верификации email: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка верификации email"
        )


@router.post("/forgot-password")
@limiter.limit("3/hour")
async def forgot_password(request: ForgotPasswordRequest, req: StarletteRequest = None):
    """Запрос сброса пароля."""
    try:
        # Получаем пользователя
        user = await db.get_user_by_email(request.email)
        if not user:
            # Не раскрываем, существует ли пользователь
            return {"message": "Если пользователь с таким email существует, на него отправлена ссылка для сброса пароля"}
        
        # Генерируем токен сброса пароля
        reset_token = auth_manager.generate_password_reset_token()
        expires_at = datetime.utcnow() + timedelta(hours=24)
        await db.save_password_reset_token(user["id"], reset_token, expires_at)
        
        # TODO: Отправить email с токеном
        # Пока просто логируем
        logger.info(f"Токен сброса пароля для {request.email}: {reset_token}")
        
        return {"message": "Если пользователь с таким email существует, на него отправлена ссылка для сброса пароля"}
    except Exception as e:
        logger.error(f"Ошибка запроса сброса пароля: {e}", exc_info=True)
        # Не раскрываем ошибку пользователю
        return {"message": "Если пользователь с таким email существует, на него отправлена ссылка для сброса пароля"}


@router.post("/reset-password")
@limiter.limit("5/hour")
async def reset_password(request: ResetPasswordRequest, req: StarletteRequest = None):
    """Сброс пароля по токену."""
    try:
        # Получаем токен из БД
        token_data = await db.get_password_reset_token(request.token)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недействительный или истёкший токен сброса пароля"
            )
        
        # Хешируем новый пароль
        password_hash = auth_manager.hash_password(request.new_password)
        
        # Обновляем пароль
        await db.update_user_password(token_data["user_id"], password_hash)
        
        # Отзываем все сессии пользователя
        await db.revoke_all_user_sessions(token_data["user_id"])
        
        # Удаляем токен
        await db.delete_password_reset_token(request.token)
        
        logger.info(f"Пароль пользователя {token_data['user_id']} сброшен")
        
        return {"message": "Пароль успешно изменён"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка сброса пароля: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка сброса пароля"
        )
