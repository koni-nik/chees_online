"""
Unit-тесты для шахматного движка.
"""
import pytest
import sys
from pathlib import Path

# Добавляем путь к shared модулю
sys.path.insert(0, str(Path(__file__).parent.parent))

from chess_engine import ChessPiece, ChessBoard, ChessRules, PieceType


class TestChessPiece:
    """Тесты для класса ChessPiece."""
    
    def test_pawn_moves_white(self):
        """Тест ходов белой пешки."""
        board = [[None for _ in range(8)] for _ in range(8)]
        pawn = ChessPiece("white", PieceType.PAWN, (4, 6))
        moves, attacks = pawn.get_valid_moves(board)
        
        assert (4, 5) in moves  # Ход вперёд
        assert (4, 4) in moves  # Двойной ход
        assert len(attacks) == 0  # Нет фигур для атаки
    
    def test_pawn_attacks(self):
        """Тест атак пешки."""
        board = [[None for _ in range(8)] for _ in range(8)]
        board[3][5] = ChessPiece("black", PieceType.PAWN, (3, 5))
        pawn = ChessPiece("white", PieceType.PAWN, (4, 6))
        moves, attacks = pawn.get_valid_moves(board)
        
        assert (3, 5) in attacks  # Атака по диагонали
    
    def test_rook_moves(self):
        """Тест ходов ладьи."""
        board = [[None for _ in range(8)] for _ in range(8)]
        rook = ChessPiece("white", PieceType.ROOK, (0, 0))
        moves, attacks = rook.get_valid_moves(board)
        
        # Должны быть ходы по горизонтали и вертикали
        assert (0, 1) in moves
        assert (1, 0) in moves
        assert (0, 7) in moves
        assert (7, 0) in moves
    
    def test_knight_moves(self):
        """Тест ходов коня."""
        board = [[None for _ in range(8)] for _ in range(8)]
        knight = ChessPiece("white", PieceType.KNIGHT, (1, 0))
        moves, attacks = knight.get_valid_moves(board)
        
        # Конь может ходить на 8 позиций из начальной позиции
        assert len(moves) + len(attacks) == 2  # Только 2 доступны с края доски
    
    def test_king_moves(self):
        """Тест ходов короля."""
        board = [[None for _ in range(8)] for _ in range(8)]
        king = ChessPiece("white", PieceType.KING, (4, 0))
        moves, attacks = king.get_valid_moves(board)
        
        # Король может ходить на соседние клетки
        assert (3, 0) in moves or (3, 0) in attacks
        assert (5, 0) in moves or (5, 0) in attacks
        assert (4, 1) in moves or (4, 1) in attacks


class TestChessRules:
    """Тесты для класса ChessRules."""
    
    def test_is_square_attacked(self):
        """Тест проверки атакованной клетки."""
        board = ChessBoard.init_board()
        
        # Клетка e4 должна быть атакована пешкой e2
        assert ChessRules.is_square_attacked((4, 3), "white", board) == False  # e4 не атакована белыми
        assert ChessRules.is_square_attacked((4, 4), "black", board) == False  # e5 не атакована чёрными
    
    def test_is_in_check(self):
        """Тест проверки шаха."""
        board = [[None for _ in range(8)] for _ in range(8)]
        # Создаём позицию с шахом
        board[4][0] = ChessPiece("black", PieceType.KING, (4, 0))
        board[4][7] = ChessPiece("white", PieceType.KING, (4, 7))
        board[4][6] = ChessPiece("white", PieceType.QUEEN, (4, 6))
        
        # Чёрный король под шахом
        assert ChessRules.is_in_check("black", board) == True
        assert ChessRules.is_in_check("white", board) == False
    
    def test_is_checkmate(self):
        """Тест проверки мата."""
        board = [[None for _ in range(8)] for _ in range(8)]
        board[4][0] = ChessPiece("black", PieceType.KING, (4, 0))
        board[4][7] = ChessPiece("white", PieceType.KING, (4, 7))
        board[4][6] = ChessPiece("white", PieceType.QUEEN, (4, 6))
        board[3][6] = ChessPiece("white", PieceType.ROOK, (3, 6))
        
        def get_valid_moves(pos):
            x, y = pos
            piece = board[x][y]
            if not piece:
                return {"moves": [], "attacks": []}
            moves, attacks = piece.get_valid_moves(board)
            return {"moves": [list(m) for m in moves], "attacks": [list(a) for a in attacks]}
        
        # Это не мат, так как король может уйти
        assert ChessRules.is_checkmate("black", board, get_valid_moves) == False
    
    def test_is_stalemate(self):
        """Тест проверки пата."""
        board = [[None for _ in range(8)] for _ in range(8)]
        board[0][0] = ChessPiece("black", PieceType.KING, (0, 0))
        board[7][7] = ChessPiece("white", PieceType.KING, (7, 7))
        board[1][2] = ChessPiece("white", PieceType.QUEEN, (1, 2))
        
        def get_valid_moves(pos):
            x, y = pos
            piece = board[x][y]
            if not piece:
                return {"moves": [], "attacks": []}
            moves, attacks = piece.get_valid_moves(board)
            return {"moves": [list(m) for m in moves], "attacks": [list(a) for a in attacks]}
        
        # Это пат для чёрных
        assert ChessRules.is_stalemate("black", board, get_valid_moves) == True


class TestChessBoard:
    """Тесты для класса ChessBoard."""
    
    def test_init_board(self):
        """Тест инициализации доски."""
        board = ChessBoard.init_board()
        
        # Проверяем наличие фигур
        assert board[0][0] is not None  # Ладья
        assert board[4][0] is not None  # Король чёрных
        assert board[4][7] is not None  # Король белых
        assert board[0][1] is not None  # Пешка
    
    def test_validate_position(self):
        """Тест валидации позиции."""
        assert ChessBoard.validate_position((0, 0)) == True
        assert ChessBoard.validate_position((7, 7)) == True
        assert ChessBoard.validate_position((8, 0)) == False
        assert ChessBoard.validate_position((0, 8)) == False
        assert ChessBoard.validate_position((-1, 0)) == False
    
    def test_get_piece_at(self):
        """Тест получения фигуры на позиции."""
        board = ChessBoard.init_board()
        piece = ChessBoard.get_piece_at(board, (0, 0))
        assert piece is not None
        assert piece.type == PieceType.ROOK
        assert piece.color == "black"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



