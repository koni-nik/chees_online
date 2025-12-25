"""
Шахматный движок - общие классы для логики игры.
"""
from enum import Enum
from typing import List, Tuple, Optional


class PieceType(Enum):
    """Типы шахматных фигур."""
    PAWN = "pawn"
    ROOK = "rook"
    KNIGHT = "knight"
    BISHOP = "bishop"
    QUEEN = "queen"
    KING = "king"


class ChessPiece:
    """
    Базовый класс шахматной фигуры.
    
    Attributes:
        color: Цвет фигуры ("white" или "black")
        type: Тип фигуры (PieceType)
        position: Позиция на доске (x, y)
        moved: Флаг, была ли фигура перемещена
    """
    
    def __init__(self, color: str, piece_type: PieceType, position: Tuple[int, int]):
        """
        Инициализирует шахматную фигуру.
        
        Args:
            color: Цвет фигуры ("white" или "black")
            piece_type: Тип фигуры
            position: Позиция на доске (x, y)
        """
        self.color = color
        self.type = piece_type
        self.position = position
        self.moved = False
    
    def get_valid_moves(self, board: List[List[Optional['ChessPiece']]], 
                       en_passant_target: Optional[Tuple[int, int]] = None,
                       check_castling_safety: callable = None) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
        """
        Возвращает допустимые ходы и атаки для фигуры.
        
        Args:
            board: Доска 8x8 с фигурами
            en_passant_target: Целевая клетка для взятия на проходе (опционально)
            check_castling_safety: Функция проверки безопасности рокировки (опционально)
            
        Returns:
            Кортеж (moves, attacks) где:
            - moves: Список позиций для обычных ходов
            - attacks: Список позиций для атак
        """
        x, y = self.position
        moves = []
        attacks = []
        
        if self.type == PieceType.PAWN:
            direction = -1 if self.color == "white" else 1
            # Ход вперёд
            if 0 <= y + direction < 8 and not board[x][y + direction]:
                moves.append((x, y + direction))
                # Двойной ход
                if not self.moved and 0 <= y + 2 * direction < 8 and not board[x][y + 2 * direction]:
                    moves.append((x, y + 2 * direction))
            # Атаки по диагонали
            for dx in [-1, 1]:
                nx, ny = x + dx, y + direction
                if 0 <= nx < 8 and 0 <= ny < 8:
                    target = board[nx][ny]
                    if target and target.color != self.color:
                        attacks.append((nx, ny))
                    # Взятие на проходе
                    elif en_passant_target and (nx, ny) == en_passant_target:
                        attacks.append((nx, ny))
        
        elif self.type == PieceType.ROOK:
            directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            moves, attacks = self._get_linear_moves(board, directions)
        
        elif self.type == PieceType.KNIGHT:
            offsets = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
            moves, attacks = self._get_jump_moves(board, offsets)
        
        elif self.type == PieceType.BISHOP:
            directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
            moves, attacks = self._get_linear_moves(board, directions)
        
        elif self.type == PieceType.QUEEN:
            directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
            moves, attacks = self._get_linear_moves(board, directions)
        
        elif self.type == PieceType.KING:
            offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
            moves, attacks = self._get_jump_moves(board, offsets)
            # Рокировка
            if not self.moved:
                if self._can_castle(board, 'kingside', check_castling_safety):
                    moves.append((x + 2, y))
                if self._can_castle(board, 'queenside', check_castling_safety):
                    moves.append((x - 2, y))
        
        return moves, attacks
    
    def _get_linear_moves(self, board, directions):
        """Вспомогательный метод для линейных ходов (ладья, слон, ферзь)."""
        x, y = self.position
        moves = []
        attacks = []
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            while 0 <= nx < 8 and 0 <= ny < 8:
                if board[nx][ny]:
                    if board[nx][ny].color != self.color:
                        attacks.append((nx, ny))
                    break
                moves.append((nx, ny))
                nx += dx
                ny += dy
        return moves, attacks
    
    def _get_jump_moves(self, board, offsets):
        """Вспомогательный метод для прыжковых ходов (конь, король)."""
        x, y = self.position
        moves = []
        attacks = []
        for dx, dy in offsets:
            nx, ny = x + dx, y + dy
            if 0 <= nx < 8 and 0 <= ny < 8:
                if board[nx][ny]:
                    if board[nx][ny].color != self.color:
                        attacks.append((nx, ny))
                else:
                    moves.append((nx, ny))
        return moves, attacks
    
    def _can_castle(self, board, side, check_castling_safety=None):
        """Проверяет возможность рокировки."""
        x, y = self.position
        rook_x = 7 if side == 'kingside' else 0
        step = 1 if side == 'kingside' else -1
        
        rook = board[rook_x][y]
        if not rook or rook.type != PieceType.ROOK or rook.moved:
            return False
        
        # Проверяем что клетки между королём и ладьёй свободны
        current = x + step
        while current != rook_x:
            if board[current][y] is not None:
                return False
            current += step
        
        # Проверяем что король не под шахом и не проходит через атакованные клетки
        if check_castling_safety:
            squares_to_check = [(x, y), (x + step, y), (x + 2 * step, y)]
            for sq in squares_to_check:
                if check_castling_safety(sq, self.color):
                    return False
        
        return True


class ChessBoard:
    """Класс для работы с шахматной доской."""
    
    @staticmethod
    def init_board() -> List[List[Optional[ChessPiece]]]:
        """
        Инициализирует доску с фигурами в начальных позициях.
        
        Returns:
            Двумерный массив 8x8 с ChessPiece объектами или None
        """
        board: List[List[Optional[ChessPiece]]] = [[None for _ in range(8)] for _ in range(8)]
        
        # Расставляем фигуры
        back_row = [
            (0, PieceType.ROOK), (1, PieceType.KNIGHT), (2, PieceType.BISHOP),
            (3, PieceType.QUEEN), (4, PieceType.KING),
            (5, PieceType.BISHOP), (6, PieceType.KNIGHT), (7, PieceType.ROOK)
        ]
        
        # Чёрные фигуры (верх доски, y=0-1)
        for x, piece_type in back_row:
            board[x][0] = ChessPiece("black", piece_type, (x, 0))
        for x in range(8):
            board[x][1] = ChessPiece("black", PieceType.PAWN, (x, 1))
        
        # Белые фигуры (низ доски, y=6-7)
        for x, piece_type in back_row:
            board[x][7] = ChessPiece("white", piece_type, (x, 7))
        for x in range(8):
            board[x][6] = ChessPiece("white", PieceType.PAWN, (x, 6))
        
        return board
    
    @staticmethod
    def validate_position(position: Tuple[int, int]) -> bool:
        """
        Проверяет, является ли позиция валидной (в пределах доски).
        
        Args:
            position: Позиция (x, y)
            
        Returns:
            True если позиция валидна
        """
        x, y = position
        return 0 <= x < 8 and 0 <= y < 8
    
    @staticmethod
    def get_piece_at(board: List[List[Optional[ChessPiece]]], position: Tuple[int, int]) -> Optional[ChessPiece]:
        """
        Получает фигуру на указанной позиции.
        
        Args:
            board: Доска 8x8
            position: Позиция (x, y)
            
        Returns:
            ChessPiece или None если клетка пуста
        """
        x, y = position
        if not ChessBoard.validate_position(position):
            return None
        return board[x][y]


class ChessRules:
    """Класс для проверки шахматных правил."""
    
    @staticmethod
    def is_square_attacked(square: Tuple[int, int], by_color: str, 
                          board: List[List[Optional[ChessPiece]]]) -> bool:
        """
        Проверяет, атакована ли клетка фигурами указанного цвета.
        
        Args:
            square: Позиция для проверки (x, y)
            by_color: Цвет атакующих фигур
            board: Доска 8x8
            
        Returns:
            True если клетка атакована
        """
        x, y = square
        if not ChessBoard.validate_position(square):
            return False
        
        # Проверяем все фигуры противоположного цвета
        for px in range(8):
            for py in range(8):
                piece = board[px][py]
                if piece and piece.color == by_color:
                    moves, attacks = piece.get_valid_moves(board)
                    if square in moves or square in attacks:
                        return True
        
        return False
    
    @staticmethod
    def is_in_check(color: str, board: List[List[Optional[ChessPiece]]]) -> bool:
        """
        Проверяет, под шахом ли король указанного цвета.
        
        Args:
            color: Цвет короля для проверки
            board: Доска 8x8
            
        Returns:
            True если король под шахом
        """
        # Находим короля
        king_pos = None
        for x in range(8):
            for y in range(8):
                piece = board[x][y]
                if piece and piece.color == color and piece.type == PieceType.KING:
                    king_pos = (x, y)
                    break
            if king_pos:
                break
        
        if not king_pos:
            return False
        
        # Проверяем, атакована ли позиция короля
        opponent = "black" if color == "white" else "white"
        return ChessRules.is_square_attacked(king_pos, opponent, board)
    
    @staticmethod
    def is_checkmate(color: str, board: List[List[Optional[ChessPiece]]], 
                    get_valid_moves: callable) -> bool:
        """
        Проверяет мат.
        
        Args:
            color: Цвет игрока для проверки
            board: Доска 8x8
            get_valid_moves: Функция для получения допустимых ходов
            
        Returns:
            True если мат
        """
        # Если не под шахом, то не мат
        if not ChessRules.is_in_check(color, board):
            return False
        
        # Проверяем, есть ли хотя бы один допустимый ход
        for x in range(8):
            for y in range(8):
                piece = board[x][y]
                if piece and piece.color == color:
                    valid = get_valid_moves((x, y))
                    if valid.get("moves") or valid.get("attacks"):
                        return False
        
        return True
    
    @staticmethod
    def is_stalemate(color: str, board: List[List[Optional[ChessPiece]]], 
                    get_valid_moves: callable) -> bool:
        """
        Проверяет пат.
        
        Args:
            color: Цвет игрока для проверки
            board: Доска 8x8
            get_valid_moves: Функция для получения допустимых ходов
            
        Returns:
            True если пат
        """
        # Если под шахом, то не пат
        if ChessRules.is_in_check(color, board):
            return False
        
        # Проверяем, есть ли хотя бы один допустимый ход
        for x in range(8):
            for y in range(8):
                piece = board[x][y]
                if piece and piece.color == color:
                    valid = get_valid_moves((x, y))
                    if valid.get("moves") or valid.get("attacks"):
                        return False
        
        return True
