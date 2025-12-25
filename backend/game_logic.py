# game_logic.py - Серверная логика шахмат (без pygame)
from typing import List, Tuple, Dict, Optional
import copy
import sys
from pathlib import Path

# Добавляем путь к shared модулю
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from chess_engine import ChessPiece, ChessBoard, ChessRules, PieceType


class Piece(ChessPiece):
    """
    Класс шахматной фигуры для онлайн версии.
    Наследуется от ChessPiece из общего движка.
    
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
        super().__init__(color, piece_type, position)
    
    def to_dict(self) -> dict:
        """
        Преобразует фигуру в словарь для сериализации.
        
        Returns:
            Словарь с данными фигуры
        """
        return {
            "color": self.color,
            "type": self.type.value,
            "position": list(self.position),
            "moved": self.moved
        }
    
    def get_valid_moves(self, board: List[List[Optional['Piece']]], en_passant_target: Optional[Tuple[int, int]] = None, check_castling_safety: callable = None) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
        """Возвращает (moves, attacks)"""
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
            # Проверяем текущую позицию и клетки, через которые проходит король
            squares_to_check = [(x, y), (x + step, y), (x + 2 * step, y)]
            for sq in squares_to_check:
                if check_castling_safety(sq, self.color):
                    return False
        
        return True


class ChessGame:
    """
    Класс для управления шахматной игрой.
    
    Attributes:
        board: Доска 8x8 с фигурами
        current_player: Текущий игрок ("white" или "black")
        game_over: Флаг окончания игры
        winner: Победитель ("white", "black", "draw" или None)
        en_passant_target: Целевая клетка для взятия на проходе
        move_history: История ходов
    """
    
    def __init__(self):
        """Инициализирует новую шахматную игру."""
        self.board: List[List[Optional[Piece]]] = [[None for _ in range(8)] for _ in range(8)]
        self.current_player = "white"
        self.game_over = False
        self.winner = None
        self.en_passant_target: Optional[Tuple[int, int]] = None  # Клетка для взятия на проходе
        self.move_history: List[dict] = []  # История ходов
        self._init_board()
    
    def _init_board(self):
        """Расставляет фигуры на начальные позиции."""
        # Используем общий метод инициализации доски
        initial_board = ChessBoard.init_board()
        
        # Преобразуем ChessPiece в Piece для совместимости
        for x in range(8):
            for y in range(8):
                chess_piece = initial_board[x][y]
                if chess_piece:
                    self.board[x][y] = Piece(
                        chess_piece.color,
                        chess_piece.type,
                        chess_piece.position
                    )
                    self.board[x][y].moved = chess_piece.moved
    
    def get_board_state(self) -> List[List[Optional[dict]]]:
        """
        Возвращает состояние доски для отправки клиенту.
        
        Returns:
            Двумерный массив с данными фигур или None
        """
        result = []
        for x in range(8):
            row = []
            for y in range(8):
                piece = self.board[x][y]
                row.append(piece.to_dict() if piece else None)
            result.append(row)
        return result
    
    def _is_square_attacked(self, square: Tuple[int, int], by_color: str) -> bool:
        """
        Проверяет, атакована ли клетка фигурами указанного цвета.
        Использует оптимизированный метод из общего движка.
        
        Args:
            square: Позиция для проверки (x, y)
            by_color: Цвет атакующих фигур
            
        Returns:
            True если клетка атакована
        """
        # Преобразуем доску в формат для общего движка
        chess_board = [[None for _ in range(8)] for _ in range(8)]
        for x in range(8):
            for y in range(8):
                piece = self.board[x][y]
                if piece:
                    chess_board[x][y] = ChessPiece(piece.color, piece.type, piece.position)
                    chess_board[x][y].moved = piece.moved
        
        return ChessRules.is_square_attacked(square, by_color, chess_board)
    
    def _check_castling_safety(self, square: Tuple[int, int], king_color: str) -> bool:
        """Проверяет, атакована ли клетка противником (для рокировки)"""
        opponent = "black" if king_color == "white" else "white"
        return self._is_square_attacked(square, opponent)
    
    def get_valid_moves(self, position: Tuple[int, int]) -> dict:
        """
        Возвращает допустимые ходы для фигуры на указанной позиции.
        
        Args:
            position: Позиция фигуры (x, y)
            
        Returns:
            Словарь с ключами "moves" (список ходов) и "attacks" (список атак)
        """
        x, y = position
        piece = self.board[x][y]
        if not piece:
            return {"moves": [], "attacks": []}
        
        moves, attacks = piece.get_valid_moves(
            self.board, 
            self.en_passant_target,
            self._check_castling_safety
        )
        
        # Фильтруем ходы, которые оставляют короля под шахом
        valid_moves = []
        valid_attacks = []
        
        for move in moves:
            if not self._move_leaves_in_check(piece, move):
                valid_moves.append(list(move))
        
        for attack in attacks:
            if not self._move_leaves_in_check(piece, attack):
                valid_attacks.append(list(attack))
        
        return {"moves": valid_moves, "attacks": valid_attacks, "en_passant": self.en_passant_target}
    
    def _move_leaves_in_check(self, piece: Piece, to_pos: Tuple[int, int]) -> bool:
        """Проверяет, оставит ли ход короля под шахом"""
        from_pos = piece.position
        target = self.board[to_pos[0]][to_pos[1]]
        
        # Временно делаем ход
        self.board[from_pos[0]][from_pos[1]] = None
        self.board[to_pos[0]][to_pos[1]] = piece
        old_pos = piece.position
        piece.position = to_pos
        
        in_check = self._is_in_check(piece.color)
        
        # Откатываем
        self.board[from_pos[0]][from_pos[1]] = piece
        self.board[to_pos[0]][to_pos[1]] = target
        piece.position = old_pos
        
        return in_check
    
    def _is_in_check(self, color: str) -> bool:
        """
        Проверяет, под шахом ли король указанного цвета.
        Использует оптимизированный метод из общего движка.
        
        Args:
            color: Цвет короля для проверки
            
        Returns:
            True если король под шахом
        """
        # Преобразуем доску в формат для общего движка
        chess_board = [[None for _ in range(8)] for _ in range(8)]
        for x in range(8):
            for y in range(8):
                piece = self.board[x][y]
                if piece:
                    chess_board[x][y] = ChessPiece(piece.color, piece.type, piece.position)
                    chess_board[x][y].moved = piece.moved
        
        return ChessRules.is_in_check(color, chess_board)
    
    def _is_checkmate(self, color: str) -> bool:
        """
        Проверяет мат.
        Использует метод из общего движка.
        
        Args:
            color: Цвет игрока для проверки
            
        Returns:
            True если мат
        """
        # Преобразуем доску в формат для общего движка
        chess_board = [[None for _ in range(8)] for _ in range(8)]
        for x in range(8):
            for y in range(8):
                piece = self.board[x][y]
                if piece:
                    chess_board[x][y] = ChessPiece(piece.color, piece.type, piece.position)
                    chess_board[x][y].moved = piece.moved
        
        return ChessRules.is_checkmate(color, chess_board, self.get_valid_moves)
    
    def _is_stalemate(self, color: str) -> bool:
        """
        Проверяет пат.
        Использует метод из общего движка.
        
        Args:
            color: Цвет игрока для проверки
            
        Returns:
            True если пат
        """
        # Преобразуем доску в формат для общего движка
        chess_board = [[None for _ in range(8)] for _ in range(8)]
        for x in range(8):
            for y in range(8):
                piece = self.board[x][y]
                if piece:
                    chess_board[x][y] = ChessPiece(piece.color, piece.type, piece.position)
                    chess_board[x][y].moved = piece.moved
        
        return ChessRules.is_stalemate(color, chess_board, self.get_valid_moves)
    
    def make_move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], custom_moves: dict = None, promotion_piece: str = None) -> dict:
        """
        Выполняет ход на доске.
        
        Args:
            from_pos: Начальная позиция (x, y)
            to_pos: Конечная позиция (x, y)
            custom_moves: Словарь кастомных ходов (опционально)
            promotion_piece: Тип фигуры для превращения пешки (опционально)
            
        Returns:
            Словарь с результатом хода:
            - success: True если ход выполнен успешно
            - message: Сообщение об ошибке (если success=False)
            - captured: Информация о захваченной фигуре
            - check: True если шах
            - checkmate: True если мат
            - stalemate: True если пат
            - castling: Тип рокировки (если была)
            - en_passant: True если взятие на проходе
            - promotion: Тип фигуры превращения (если было)
        """
        x, y = from_pos
        piece = self.board[x][y]
        
        if not piece:
            return {"success": False, "message": "Нет фигуры на этой позиции"}
        
        if piece.color != self.current_player:
            return {"success": False, "message": "Не ваш ход"}
        
        valid = self.get_valid_moves(from_pos)
        all_valid = [tuple(m) for m in valid["moves"] + valid["attacks"]]
        
        # Добавляем кастомные ходы
        if custom_moves:
            piece_type = piece.type.value
            custom = custom_moves.get(piece.color, {}).get(piece_type, {})
            for move in custom.get("moves", []):
                dx, dy = move[0], move[1]
                nx, ny = x + dx, y + dy
                if 0 <= nx < 8 and 0 <= ny < 8:
                    target = self.board[nx][ny]
                    if not target:
                        all_valid.append((nx, ny))
            for attack in custom.get("attacks", []):
                dx, dy = attack[0], attack[1]
                nx, ny = x + dx, y + dy
                if 0 <= nx < 8 and 0 <= ny < 8:
                    target = self.board[nx][ny]
                    if target and target.color != piece.color:
                        all_valid.append((nx, ny))
        
        if to_pos not in all_valid:
            return {"success": False, "message": "Недопустимый ход"}
        
        # Сохраняем ход в историю
        move_record = {
            "from": from_pos,
            "to": to_pos,
            "piece": piece.to_dict(),
            "captured": None,
            "en_passant": False,
            "castling": None,
            "promotion": None
        }
        
        # Захват фигуры
        captured = None
        target = self.board[to_pos[0]][to_pos[1]]
        if target:
            captured = target.to_dict()
            move_record["captured"] = captured
        
        # Взятие на проходе
        en_passant_capture = False
        if piece.type == PieceType.PAWN and self.en_passant_target and to_pos == self.en_passant_target:
            # Убираем пешку, которую берём на проходе
            captured_pawn_y = to_pos[1] + (1 if piece.color == "white" else -1)
            captured_pawn = self.board[to_pos[0]][captured_pawn_y]
            if captured_pawn:
                captured = captured_pawn.to_dict()
                move_record["captured"] = captured
                move_record["en_passant"] = True
                self.board[to_pos[0]][captured_pawn_y] = None
                en_passant_capture = True
        
        # Сбрасываем en passant target
        old_en_passant = self.en_passant_target
        self.en_passant_target = None
        
        # Устанавливаем новый en passant target если пешка двигается на 2 клетки
        if piece.type == PieceType.PAWN and abs(to_pos[1] - from_pos[1]) == 2:
            en_passant_y = (from_pos[1] + to_pos[1]) // 2
            self.en_passant_target = (to_pos[0], en_passant_y)
        
        # Рокировка
        castling_type = None
        if piece.type == PieceType.KING and abs(to_pos[0] - from_pos[0]) == 2:
            # Перемещаем ладью
            if to_pos[0] > from_pos[0]:  # Kingside
                rook = self.board[7][from_pos[1]]
                self.board[7][from_pos[1]] = None
                self.board[5][from_pos[1]] = rook
                rook.position = (5, from_pos[1])
                rook.moved = True
                castling_type = "kingside"
            else:  # Queenside
                rook = self.board[0][from_pos[1]]
                self.board[0][from_pos[1]] = None
                self.board[3][from_pos[1]] = rook
                rook.position = (3, from_pos[1])
                rook.moved = True
                castling_type = "queenside"
            move_record["castling"] = castling_type
        
        # Выполняем ход
        self.board[from_pos[0]][from_pos[1]] = None
        self.board[to_pos[0]][to_pos[1]] = piece
        piece.position = to_pos
        piece.moved = True
        
        # Превращение пешки
        promotion = None
        if piece.type == PieceType.PAWN:
            if (piece.color == "white" and to_pos[1] == 0) or (piece.color == "black" and to_pos[1] == 7):
                # Выбор фигуры для превращения
                promotion_type = PieceType.QUEEN  # По умолчанию
                if promotion_piece:
                    promotion_map = {
                        "queen": PieceType.QUEEN,
                        "rook": PieceType.ROOK,
                        "bishop": PieceType.BISHOP,
                        "knight": PieceType.KNIGHT
                    }
                    promotion_type = promotion_map.get(promotion_piece, PieceType.QUEEN)
                
                self.board[to_pos[0]][to_pos[1]] = Piece(piece.color, promotion_type, to_pos)
                self.board[to_pos[0]][to_pos[1]].moved = True
                promotion = promotion_type.value
                move_record["promotion"] = promotion
        
        # Сохраняем ход в историю
        self.move_history.append(move_record)
        
        # Переключаем игрока
        self.current_player = "black" if self.current_player == "white" else "white"
        
        # Проверяем окончание игры
        check = self._is_in_check(self.current_player)
        checkmate = self._is_checkmate(self.current_player)
        stalemate = self._is_stalemate(self.current_player)
        
        if checkmate:
            self.game_over = True
            self.winner = "white" if self.current_player == "black" else "black"
        elif stalemate:
            self.game_over = True
            self.winner = "draw"
        
        return {
            "success": True,
            "captured": captured,
            "check": check,
            "checkmate": checkmate,
            "stalemate": stalemate,
            "castling": castling_type,
            "en_passant": en_passant_capture,
            "promotion": promotion,
            "en_passant_target": self.en_passant_target
        }

