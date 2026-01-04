"""
Обработчик WebSocket сообщений для игровых комнат (v2.8).
"""
import time
from typing import Dict, Any
from pydantic import ValidationError
from logger import setup_logger
from schemas import (
    MoveRequest, GetValidMovesRequest, CustomMoveRequest, SaveCardRequest,
    ToggleCardRequest, DeleteCardRequest, ChatRequest, ResignRequest,
    OfferDrawRequest, DrawResponseRequest, RequestUndoRequest, UndoResponseRequest,
    RequestRematchRequest, RematchResponseRequest, SetTimeControlRequest,
    GetPositionAnalysisRequest, ExportPGNRequest, GetRatingRequest
)
from managers import connection_manager
from rating import RatingSystem
from analysis import PositionAnalyzer
from pgn import PGNExporter
from config import config

logger = setup_logger()


def rebuild_custom_moves(room: Dict[str, Any]):
    """Пересобирает custom_moves из включённых карточек."""
    room["custom_moves"] = {"white": {}, "black": {}}
    for color in ["white", "black"]:
        for name, card in room["ability_cards"][color].items():
            if card.get("enabled", True) == False:
                continue
            piece_type = card.get("pieceType")
            if not piece_type:
                continue
            if piece_type not in room["custom_moves"][color]:
                room["custom_moves"][color][piece_type] = {"moves": [], "attacks": []}
            for move in card.get("moves", []):
                if move not in room["custom_moves"][color][piece_type]["moves"]:
                    room["custom_moves"][color][piece_type]["moves"].append(move)
            for attack in card.get("attacks", []):
                if attack not in room["custom_moves"][color][piece_type]["attacks"]:
                    room["custom_moves"][color][piece_type]["attacks"].append(attack)


async def handle_websocket_message(
    room: Dict[str, Any],
    room_id: str,
    player_id: str,
    raw_data: Dict[str, Any]
):
    """
    Обрабатывает WebSocket сообщение от игрока.
    
    Args:
        room: Данные комнаты
        room_id: ID комнаты
        player_id: ID игрока
        raw_data: Сырые данные сообщения
        
    Returns:
        True если сообщение обработано успешно, False если была ошибка
    """
    logger.debug(f"Received message type: {raw_data.get('type')} from {player_id}")
    
    # Валидация данных
    try:
        message_type = raw_data.get("type")
        data = None
        
        # Валидируем сообщение в зависимости от типа
        if message_type == "move":
            data = MoveRequest(**raw_data)
            from_pos = tuple(data.from_pos)
            to_pos = tuple(data.to_pos)
            promotion_piece = data.promotion
        elif message_type == "get_valid_moves":
            data = GetValidMovesRequest(**raw_data)
        elif message_type == "add_custom_move":
            data = CustomMoveRequest(**raw_data)
        elif message_type == "save_card":
            data = SaveCardRequest(**raw_data)
        elif message_type == "toggle_card":
            data = ToggleCardRequest(**raw_data)
        elif message_type == "delete_card":
            data = DeleteCardRequest(**raw_data)
        elif message_type == "chat":
            data = ChatRequest(**raw_data)
        elif message_type == "resign":
            data = ResignRequest(**raw_data)
        elif message_type == "offer_draw":
            data = OfferDrawRequest(**raw_data)
        elif message_type == "draw_response":
            data = DrawResponseRequest(**raw_data)
        elif message_type == "request_undo":
            data = RequestUndoRequest(**raw_data)
        elif message_type == "undo_response":
            data = UndoResponseRequest(**raw_data)
        elif message_type == "request_rematch":
            data = RequestRematchRequest(**raw_data)
        elif message_type == "rematch_response":
            data = RematchResponseRequest(**raw_data)
        elif message_type == "set_time_control":
            data = SetTimeControlRequest(**raw_data)
        elif message_type == "get_position_analysis":
            data = GetPositionAnalysisRequest(**raw_data)
        elif message_type == "export_pgn":
            data = ExportPGNRequest(**raw_data)
        elif message_type == "get_rating":
            data = GetRatingRequest(**raw_data)
        else:
            await connection_manager.send_to_player(room_id, player_id, {
                "type": "error",
                "message": f"Неизвестный тип сообщения: {message_type}"
            })
            return False
            
    except ValidationError as e:
        logger.warning(f"Ошибка валидации данных от {player_id} (тип: {message_type}): {e}")
        await connection_manager.send_to_player(room_id, player_id, {
            "type": "error",
            "message": f"Некорректные данные: {str(e)}"
        })
        return False
    except (KeyError, ValueError, TypeError) as e:
        logger.warning(f"Ошибка формата данных от {player_id} (тип: {message_type}): {e}", exc_info=True)
        await connection_manager.send_to_player(room_id, player_id, {
            "type": "error",
            "message": "Некорректный формат данных"
        })
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обработке сообщения от {player_id} (тип: {message_type}): {e}", exc_info=True)
        await connection_manager.send_to_player(room_id, player_id, {
            "type": "error",
            "message": "Внутренняя ошибка сервера"
        })
        return False
    
    # Обработка конкретных типов сообщений
    # Эта функция будет расширена в routes/game.py с полной логикой обработки
    # Здесь только базовая структура для рефакторинга
    
    return True

