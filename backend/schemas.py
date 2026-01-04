"""
Pydantic схемы для валидации данных WebSocket сообщений.
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional
import re


class Position(BaseModel):
    """Позиция на доске."""
    x: int = Field(..., ge=0, le=7, description="Координата X (0-7)")
    y: int = Field(..., ge=0, le=7, description="Координата Y (0-7)")


class MoveRequest(BaseModel):
    """Запрос на выполнение хода."""
    model_config = ConfigDict(populate_by_name=True)
    
    type: str = Field(..., pattern="^move$")
    from_pos: List[int] = Field(..., min_length=2, max_length=2, alias="from")
    to_pos: List[int] = Field(..., min_length=2, max_length=2, alias="to")
    promotion: Optional[str] = Field(None, pattern="^(queen|rook|bishop|knight)$")
    
    @field_validator('from_pos', 'to_pos')
    @classmethod
    def validate_position(cls, v):
        """Проверяет, что координаты в пределах доски."""
        if len(v) != 2:
            raise ValueError("Позиция должна содержать 2 координаты")
        x, y = v
        if not (0 <= x <= 7 and 0 <= y <= 7):
            raise ValueError(f"Координаты вне доски: ({x}, {y})")
        return v


class GetValidMovesRequest(BaseModel):
    """Запрос на получение допустимых ходов."""
    type: str = Field(..., pattern="^get_valid_moves$")
    position: List[int] = Field(..., min_length=2, max_length=2)
    
    @field_validator('position')
    @classmethod
    def validate_position(cls, v):
        """Проверяет, что координаты в пределах доски."""
        if len(v) != 2:
            raise ValueError("Позиция должна содержать 2 координаты")
        x, y = v
        if not (0 <= x <= 7 and 0 <= y <= 7):
            raise ValueError(f"Координаты вне доски: ({x}, {y})")
        return v


class CustomMoveRequest(BaseModel):
    """Запрос на добавление кастомного хода."""
    type: str = Field(..., pattern="^add_custom_move$")
    color: str = Field(..., pattern="^(white|black)$")
    piece_type: str = Field(..., pattern="^(pawn|rook|knight|bishop|queen|king)$")
    move: List[int] = Field(..., min_length=2, max_length=2)
    is_attack: bool = False
    
    @field_validator('move')
    @classmethod
    def validate_move(cls, v):
        """Проверяет формат хода."""
        if len(v) != 2:
            raise ValueError("Ход должен содержать 2 координаты (dx, dy)")
        return v


class SaveCardRequest(BaseModel):
    """Запрос на сохранение карточки способностей."""
    type: str = Field(..., pattern="^save_card$")
    color: str = Field(..., pattern="^(white|black)$")
    name: str = Field(..., min_length=1, max_length=100)
    card_data: dict


class ToggleCardRequest(BaseModel):
    """Запрос на переключение карточки."""
    type: str = Field(..., pattern="^toggle_card$")
    color: str = Field(..., pattern="^(white|black)$")
    name: str = Field(..., min_length=1, max_length=100)
    enabled: bool = True


class DeleteCardRequest(BaseModel):
    """Запрос на удаление карточки."""
    type: str = Field(..., pattern="^delete_card$")
    color: str = Field(..., pattern="^(white|black)$")
    name: str = Field(..., min_length=1, max_length=100)


class ChatRequest(BaseModel):
    """Запрос на отправку сообщения в чат."""
    type: str = Field(..., pattern="^chat$")
    message: str = Field(..., min_length=1, max_length=500)


class ResignRequest(BaseModel):
    """Запрос на сдачу."""
    type: str = Field(..., pattern="^resign$")


class OfferDrawRequest(BaseModel):
    """Запрос на предложение ничьей."""
    type: str = Field(..., pattern="^offer_draw$")


class DrawResponseRequest(BaseModel):
    """Ответ на предложение ничьей."""
    type: str = Field(..., pattern="^draw_response$")
    accept: bool


class RequestUndoRequest(BaseModel):
    """Запрос на отмену хода."""
    type: str = Field(..., pattern="^request_undo$")


class UndoResponseRequest(BaseModel):
    """Ответ на запрос отмены хода."""
    type: str = Field(..., pattern="^undo_response$")
    accept: bool


class RequestRematchRequest(BaseModel):
    """Запрос на реванш."""
    type: str = Field(..., pattern="^request_rematch$")


class RematchResponseRequest(BaseModel):
    """Ответ на запрос реванша."""
    type: str = Field(..., pattern="^rematch_response$")
    accept: bool


class SetTimeControlRequest(BaseModel):
    """Запрос на установку контроля времени."""
    type: str = Field(..., pattern="^set_time_control$")
    time: int = Field(..., ge=1, le=3600, description="Время в секундах")
    increment: int = Field(0, ge=0, le=60, description="Инкремент в секундах")
    delay: int = Field(0, ge=0, le=60, description="Задержка в секундах")


class GetPositionAnalysisRequest(BaseModel):
    """Запрос на анализ позиции."""
    type: str = Field(..., pattern="^get_position_analysis$")


class ExportPGNRequest(BaseModel):
    """Запрос на экспорт PGN."""
    type: str = Field(..., pattern="^export_pgn$")
    white_name: Optional[str] = Field(None, max_length=100)
    black_name: Optional[str] = Field(None, max_length=100)
    result: Optional[str] = Field("*", pattern="^(1-0|0-1|1/2-1/2|\\*)$")


class GetRatingRequest(BaseModel):
    """Запрос на получение рейтинга."""
    type: str = Field(..., pattern="^get_rating$")


class CreateTournamentRoomRequest(BaseModel):
    """Запрос на создание турнирной комнаты."""
    name: str = Field(..., min_length=1, max_length=100, description="Название комнаты")
    start_time: str = Field(..., description="Время старта в формате ISO (московское время)")


class JoinTournamentRoomRequest(BaseModel):
    """Запрос на присоединение к турнирной комнате."""
    player_id: str = Field(..., min_length=1, max_length=50, description="ID игрока")
    role: Optional[str] = Field(None, pattern="^(player|spectator)$", description="Роль: player или spectator")
    
    @field_validator('player_id')
    @classmethod
    def validate_player_id(cls, v):
        """Валидация player_id для безопасности."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("player_id может содержать только буквы, цифры, дефисы и подчеркивания")
        return v


# Валидаторы для path параметров
def validate_player_id(player_id: str) -> str:
    """Валидация player_id из path параметра."""
    if not player_id or len(player_id) > 50:
        raise ValueError("Некорректный player_id")
    if not re.match(r'^[a-zA-Z0-9_-]+$', player_id):
        raise ValueError("player_id может содержать только буквы, цифры, дефисы и подчеркивания")
    return player_id


def validate_room_id(room_id: str) -> str:
    """Валидация room_id из path параметра."""
    if not room_id or len(room_id) > 50:
        raise ValueError("Некорректный room_id")
    if not re.match(r'^[a-zA-Z0-9_-]+$', room_id):
        raise ValueError("room_id может содержать только буквы, цифры, дефисы и подчеркивания")
    return room_id

