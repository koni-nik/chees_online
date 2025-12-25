# analysis.py - Анализ шахматных позиций
from typing import List, Dict, Tuple, Optional
from game_logic import ChessGame, Piece, PieceType


class PositionAnalyzer:
    """Анализатор шахматных позиций"""
    
    # Материальные ценности фигур (в пешках)
    PIECE_VALUES = {
        PieceType.PAWN: 1,
        PieceType.KNIGHT: 3,
        PieceType.BISHOP: 3,
        PieceType.ROOK: 5,
        PieceType.QUEEN: 9,
        PieceType.KING: 0  # Король не имеет материальной ценности
    }
    
    @staticmethod
    def evaluate_position(board: List[List[Optional[Piece]]], color: str = "white") -> float:
        """
        Оценить позицию
        
        Args:
            board: Состояние доски
            color: Цвет для оценки (white или black)
        
        Returns:
            Оценка позиции в пешках (положительная - лучше для белых)
        """
        material = 0
        position = 0
        
        for x in range(8):
            for y in range(8):
                piece = board[x][y]
                if piece:
                    value = PositionAnalyzer.PIECE_VALUES.get(piece.type, 0)
                    
                    # Материальный баланс
                    if piece.color == "white":
                        material += value
                    else:
                        material -= value
                    
                    # Позиционная оценка (упрощённая)
                    position += PositionAnalyzer._evaluate_piece_position(piece, x, y)
        
        # Если оцениваем для чёрных, инвертируем
        if color == "black":
            return -(material + position * 0.1)
        
        return material + position * 0.1
    
    @staticmethod
    def _evaluate_piece_position(piece: Piece, x: int, y: int) -> float:
        """Оценить позицию фигуры на доске"""
        score = 0
        
        # Центральные клетки более ценны
        center_distance = abs(x - 3.5) + abs(y - 3.5)
        score -= center_distance * 0.1
        
        # Для пешек - продвижение
        if piece.type == PieceType.PAWN:
            if piece.color == "white":
                score += (7 - y) * 0.1  # Чем ближе к 8-й горизонтали, тем лучше
            else:
                score += y * 0.1  # Чем ближе к 1-й горизонтали, тем лучше
        
        # Для короля - безопасность (упрощённо)
        if piece.type == PieceType.KING:
            # В эндшпиле король должен быть активным
            score -= center_distance * 0.2
        
        return score if piece.color == "white" else -score
    
    @staticmethod
    def find_best_moves(game: ChessGame, color: str, depth: int = 1) -> List[Dict]:
        """
        Найти лучшие ходы для указанного цвета
        
        Args:
            game: Объект игры
            color: Цвет игрока
            depth: Глубина анализа (1 = только текущий ход)
        
        Returns:
            Список лучших ходов с оценками
        """
        best_moves = []
        
        # Находим все возможные ходы
        for x in range(8):
            for y in range(8):
                piece = game.board[x][y]
                if piece and piece.color == color:
                    moves = game.get_valid_moves((x, y))
                    all_moves = moves["moves"] + moves["attacks"]
                    
                    for move in all_moves:
                        # Пробуем ход
                        result = game.make_move((x, y), tuple(move), {})
                        
                        if result["success"]:
                            # Оцениваем позицию после хода
                            evaluation = PositionAnalyzer.evaluate_position(game.board, color)
                            
                            # Откатываем ход
                            # (упрощённо - в реальности нужна более сложная логика)
                            
                            best_moves.append({
                                "from": [x, y],
                                "to": list(move),
                                "evaluation": evaluation,
                                "piece": piece.type.value
                            })
        
        # Сортируем по оценке
        best_moves.sort(key=lambda m: m["evaluation"], reverse=(color == "white"))
        
        return best_moves[:5]  # Возвращаем топ-5 ходов
    
    @staticmethod
    def analyze_threats(board: List[List[Optional[Piece]]], color: str) -> Dict:
        """
        Анализ угроз и возможностей
        
        Args:
            board: Состояние доски
            color: Цвет для анализа
        
        Returns:
            Словарь с информацией об угрозах
        """
        threats = {
            "in_check": False,
            "pieces_under_attack": [],
            "pieces_attacking": [],
            "material_balance": 0
        }
        
        # Находим короля
        king_pos = None
        for x in range(8):
            for y in range(8):
                piece = board[x][y]
                if piece and piece.type == PieceType.KING and piece.color == color:
                    king_pos = (x, y)
                    break
            if king_pos:
                break
        
        # Проверяем шах
        if king_pos:
            opponent_color = "black" if color == "white" else "white"
            # Упрощённая проверка (в реальности нужна полная проверка)
            threats["in_check"] = False  # TODO: реализовать проверку шаха
        
        # Материальный баланс
        material = 0
        for x in range(8):
            for y in range(8):
                piece = board[x][y]
                if piece:
                    value = PositionAnalyzer.PIECE_VALUES.get(piece.type, 0)
                    if piece.color == "white":
                        material += value
                    else:
                        material -= value
        
        threats["material_balance"] = material if color == "white" else -material
        
        return threats


