"""
Pydantic схемы для валидации данных WebSocket сообщений.
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional


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

