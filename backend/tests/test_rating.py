"""
Unit-тесты для рейтинговой системы.
"""
import pytest
import asyncio
import sys
from pathlib import Path
import os

# Добавляем путь к backend модулю
sys.path.insert(0, str(Path(__file__).parent.parent))

from rating import RatingSystem
from database import Database


@pytest.fixture
async def test_db():
    """Создаёт тестовую базу данных."""
    db = Database("test_chess.db")
    await db.initialize()
    yield db
    # Очистка после тестов
    if os.path.exists("test_chess.db"):
        os.remove("test_chess.db")


@pytest.mark.asyncio
async def test_get_rating_default(test_db):
    """Тест получения рейтинга по умолчанию."""
    from database import db
    db.db_path = "test_chess.db"
    await db.initialize()
    
    rating = await RatingSystem.get_rating("test_player_1")
    assert rating == 1200


@pytest.mark.asyncio
async def test_calculate_elo():
    """Тест расчёта Elo рейтинга."""
    # Игрок с рейтингом 1200 побеждает игрока с рейтингом 1200
    new_rating_1, new_rating_2 = RatingSystem.calculate_elo(1200, 1200, 1.0)
    
    assert new_rating_1 > 1200  # Победитель получает рейтинг
    assert new_rating_2 < 1200  # Проигравший теряет рейтинг
    assert new_rating_1 + new_rating_2 == 2400  # Сумма рейтингов сохраняется
    
    # Ничья
    new_rating_1, new_rating_2 = RatingSystem.calculate_elo(1200, 1200, 0.5)
    assert new_rating_1 == 1200
    assert new_rating_2 == 1200


@pytest.mark.asyncio
async def test_update_rating(test_db):
    """Тест обновления рейтинга."""
    from database import db
    db.db_path = "test_chess.db"
    await db.initialize()
    
    # Создаём игроков
    await RatingSystem.get_rating("player1")
    await RatingSystem.get_rating("player2")
    
    # Игрок 1 побеждает игрока 2
    result = await RatingSystem.update_rating("player1", "player2", 1.0)
    
    assert result["player_rating"] > 1200
    assert result["opponent_rating"] < 1200
    assert result["player_change"] > 0
    assert result["opponent_change"] < 0


@pytest.mark.asyncio
async def test_get_rating_history(test_db):
    """Тест получения истории рейтинга."""
    from database import db
    db.db_path = "test_chess.db"
    await db.initialize()
    
    # Создаём игроков и обновляем рейтинг
    await RatingSystem.get_rating("player3")
    await RatingSystem.get_rating("player4")
    await RatingSystem.update_rating("player3", "player4", 1.0)
    
    # Получаем историю
    history = await RatingSystem.get_rating_history("player3", 10)
    
    assert len(history) > 0
    assert history[0]["old_rating"] == 1200
    assert history[0]["new_rating"] > 1200


def test_get_rank():
    """Тест определения ранга."""
    assert RatingSystem.get_rank(800) == "Новичок"
    assert RatingSystem.get_rank(1100) == "Любитель"
    assert RatingSystem.get_rank(1300) == "Разрядник"
    assert RatingSystem.get_rank(1500) == "Кандидат"
    assert RatingSystem.get_rank(1700) == "Мастер"
    assert RatingSystem.get_rank(1900) == "Гроссмейстер"
    assert RatingSystem.get_rank(2100) == "Международный мастер"
    assert RatingSystem.get_rank(2300) == "Гранд-мастер"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


