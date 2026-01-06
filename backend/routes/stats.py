"""
API endpoints для статистики игрока.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict
from logger import setup_logger
from auth import auth_manager
from database import db
from rating import RatingSystem

logger = setup_logger()

router = APIRouter()
security = HTTPBearer()


async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """Получает ID текущего пользователя из токена."""
    token = credentials.credentials
    user = await auth_manager.get_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен"
        )
    return user["id"]


@router.get("/stats")
async def get_player_stats(user_id: int = Depends(get_current_user_id)):
    """
    Получает статистику игрока.
    """
    try:
        # Получаем player_id для пользователя
        async with db._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT player_id FROM players WHERE user_id = ? LIMIT 1",
                (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                # Если нет player_id, создаём его
                player_id = f"user_{user_id}"
                await db.get_or_create_player(player_id)
                await db.link_player_to_user(player_id, user_id)
            else:
                player_id = row[0]
        
        # Получаем игры игрока
        games = await db.get_player_games(player_id, limit=1000)
        
        # Подсчитываем статистику
        total = len(games)
        white_wins = 0
        black_wins = 0
        draws = 0
        
        for game in games:
            result = game.get("result")
            if result == "1-0":
                if game["white_player_id"] == player_id:
                    white_wins += 1
                else:
                    black_wins += 1
            elif result == "0-1":
                if game["black_player_id"] == player_id:
                    black_wins += 1
                else:
                    white_wins += 1
            elif result == "1/2-1/2":
                draws += 1
        
        # Получаем рейтинг
        rating = await RatingSystem.get_rating(player_id)
        rank = RatingSystem.get_rank(rating)
        
        return {
            "total": total,
            "white_wins": white_wins,
            "black_wins": black_wins,
            "draws": draws,
            "rating": rating,
            "rank": rank
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения статистики"
        )

