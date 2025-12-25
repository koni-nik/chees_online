"""
Кастомные исключения для шахматного движка.
"""


class ChessException(Exception):
    """Базовое исключение для всех ошибок шахматного движка."""
    pass


class InvalidMoveException(ChessException):
    """Исключение для недопустимых ходов."""
    pass


class InvalidPositionException(ChessException):
    """Исключение для недопустимых позиций."""
    pass


class GameOverException(ChessException):
    """Исключение когда игра уже завершена."""
    pass


class InvalidPieceException(ChessException):
    """Исключение для недопустимых фигур."""
    pass



