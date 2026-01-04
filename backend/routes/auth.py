"""
Auth routes для версии 2.8.
Базовая реализация для работы системы аккаунтов.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
from logger import setup_logger
from auth import auth_manager

logger = setup_logger()

router = APIRouter()
security = HTTPBearer()


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """
    Регистрация нового пользователя.
    В упрощенной версии создает токен на основе email.
    """
    try:
        # В упрощенной версии используем email как player_id
        player_id = request.email.split("@")[0]  # Используем часть до @ как ID
        
        # Генерируем токены
        access_token = auth_manager.generate_token(player_id)
        refresh_token = auth_manager.generate_token(f"{player_id}_refresh")
        
        logger.info(f"Пользователь зарегистрирован: {request.email}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )
    except Exception as e:
        logger.error(f"Ошибка регистрации: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка регистрации"
        )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Вход в систему.
    В упрощенной версии создает токен на основе email.
    """
    try:
        # В упрощенной версии используем email как player_id
        player_id = request.email.split("@")[0]
        
        # Генерируем токены
        access_token = auth_manager.generate_token(player_id)
        refresh_token = auth_manager.generate_token(f"{player_id}_refresh")
        
        logger.info(f"Пользователь вошел: {request.email}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )
    except Exception as e:
        logger.error(f"Ошибка входа: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка входа"
        )


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Выход из системы - отзыв токена."""
    try:
        token = credentials.credentials
        auth_manager.revoke_token(token)
        logger.info("Пользователь вышел из системы")
        return {"message": "Выход выполнен успешно"}
    except Exception as e:
        logger.error(f"Ошибка выхода: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка выхода"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Обновление токена."""
    try:
        refresh_token = credentials.credentials
        player_id = auth_manager.validate_token(refresh_token)
        
        if not player_id or not player_id.endswith("_refresh"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный refresh token"
            )
        
        # Убираем суффикс _refresh
        base_player_id = player_id.replace("_refresh", "")
        
        # Генерируем новые токены
        new_access_token = auth_manager.generate_token(base_player_id)
        new_refresh_token = auth_manager.generate_token(f"{base_player_id}_refresh")
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token
        )
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
        player_id = auth_manager.validate_token(token)
        
        if not player_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный токен"
            )
        
        # В упрощенной версии возвращаем базовую информацию
        return {
            "player_id": player_id,
            "username": player_id,
            "email": f"{player_id}@example.com"  # Заглушка
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
    """Верификация email (заглушка)."""
    return {"message": "Email верификация пока не реализована"}


@router.post("/forgot-password")
async def forgot_password(email: EmailStr):
    """Запрос сброса пароля (заглушка)."""
    return {"message": "Восстановление пароля пока не реализовано"}


@router.post("/reset-password")
async def reset_password(token: str, new_password: str):
    """Сброс пароля (заглушка)."""
    return {"message": "Сброс пароля пока не реализован"}

