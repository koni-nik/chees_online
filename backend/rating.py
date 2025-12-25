# rating.py - Система рейтинга Elo
from typing import Dict, Tuple
from database import db
from logger import setup_logger

logger = setup_logger()


class RatingSystem:
    """Система расчёта рейтинга Elo"""
    
    K_FACTOR = 32  # Коэффициент K для Elo
    
    @staticmethod
    async def get_rating(player_id: str) -> int:
        """
        Получить текущий рейтинг игрока.
        
        Args:
            player_id: ID игрока
            
        Returns:
            Текущий рейтинг игрока
        """
        player = await db.get_or_create_player(player_id)
        return player.get("rating", 1200)
    
    @staticmethod
    def get_rank(rating: int) -> str:
        """Определить ранг по рейтингу"""
        if rating < 1000:
            return "Новичок"
        elif rating < 1200:
            return "Любитель"
        elif rating < 1400:
            return "Разрядник"
        elif rating < 1600:
            return "Кандидат"
        elif rating < 1800:
            return "Мастер"
        elif rating < 2000:
            return "Гроссмейстер"
        elif rating < 2200:
            return "Международный мастер"
        else:
            return "Гранд-мастер"
    
    @staticmethod
    def calculate_elo(player_rating: int, opponent_rating: int, result: float) -> Tuple[int, int]:
        """
        Рассчитать новый рейтинг по формуле Elo
        
        Args:
            player_rating: Текущий рейтинг игрока
            opponent_rating: Рейтинг соперника
            result: Результат (1.0 - победа, 0.5 - ничья, 0.0 - поражение)
        
        Returns:
            Tuple[новый_рейтинг_игрока, новый_рейтинг_соперника]
        """
        # Ожидаемый результат
        expected_player = 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))
        expected_opponent = 1 - expected_player
        
        # Новый рейтинг
        new_player_rating = round(player_rating + RatingSystem.K_FACTOR * (result - expected_player))
        new_opponent_rating = round(opponent_rating + RatingSystem.K_FACTOR * ((1 - result) - expected_opponent))
        
        return new_player_rating, new_opponent_rating
    
    @staticmethod
    async def update_rating(player_id: str, opponent_id: str, result: float):
        """
        Обновить рейтинг после игры.
        
        Args:
            player_id: ID игрока
            opponent_id: ID соперника
            result: Результат для player_id (1.0 - победа, 0.5 - ничья, 0.0 - поражение)
            
        Returns:
            Словарь с новыми рейтингами и изменениями
        """
        player_rating = await RatingSystem.get_rating(player_id)
        opponent_rating = await RatingSystem.get_rating(opponent_id)
        
        new_player_rating, new_opponent_rating = RatingSystem.calculate_elo(
            player_rating, opponent_rating, result
        )
        
        # Обновляем рейтинги в БД
        await db.update_player_rating(player_id, new_player_rating)
        await db.update_player_rating(opponent_id, new_opponent_rating)
        
        # Сохраняем историю
        await db.add_rating_history(
            player_id, player_rating, new_player_rating,
            opponent_id, opponent_rating, result
        )
        await db.add_rating_history(
            opponent_id, opponent_rating, new_opponent_rating,
            player_id, player_rating, 1 - result
        )
        
        return {
            "player_rating": new_player_rating,
            "opponent_rating": new_opponent_rating,
            "player_change": new_player_rating - player_rating,
            "opponent_change": new_opponent_rating - opponent_rating
        }
    
    @staticmethod
    async def get_rating_history(player_id: str, limit: int = 10) -> list:
        """
        Получить историю изменения рейтинга.
        
        Args:
            player_id: ID игрока
            limit: Максимальное количество записей
            
        Returns:
            Список записей истории рейтинга
        """
        history = await db.get_rating_history(player_id, limit)
        # Преобразуем в формат, совместимый со старым API
        return [
            {
                "old_rating": h["old_rating"],
                "new_rating": h["new_rating"],
                "opponent": h["opponent_id"],
                "opponent_rating": h["opponent_rating"],
                "result": h["result"]
            }
            for h in history
        ]


