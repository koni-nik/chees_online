# pgn.py - Экспорт и импорт партий в формате PGN
from typing import List, Dict, Optional
from datetime import datetime


class PGNExporter:
    """Экспортёр партий в формат PGN"""
    
    @staticmethod
    def export_game(move_history: List[Dict], 
                    white_player: str = "White",
                    black_player: str = "Black",
                    result: str = "*",
                    event: str = "Online Game",
                    site: str = "Chess Online",
                    date: Optional[str] = None) -> str:
        """
        Экспортировать партию в формат PGN
        
        Args:
            move_history: История ходов
            white_player: Имя игрока белыми
            black_player: Имя игрока чёрными
            result: Результат партии (*, 1-0, 0-1, 1/2-1/2)
            event: Название события
            site: Место проведения
            date: Дата (формат YYYY.MM.DD)
        
        Returns:
            Строка в формате PGN
        """
        if date is None:
            date = datetime.now().strftime("%Y.%m.%d")
        
        # Заголовок PGN
        pgn_lines = [
            f'[Event "{event}"]',
            f'[Site "{site}"]',
            f'[Date "{date}"]',
            f'[Round "1"]',
            f'[White "{white_player}"]',
            f'[Black "{black_player}"]',
            f'[Result "{result}"]',
            ''
        ]
        
        # Ходы
        moves = []
        move_number = 1
        
        for i, move in enumerate(move_history):
            from_pos = move["from"]
            to_pos = move["to"]
            
            # Конвертируем координаты в шахматную нотацию
            from_square = PGNExporter._coords_to_square(from_pos)
            to_square = PGNExporter._coords_to_square(to_pos)
            
            piece_type = move.get("piece", {}).get("type", "pawn")
            piece_symbol = PGNExporter._piece_to_symbol(piece_type)
            
            # Формируем нотацию хода
            if move.get("captured"):
                notation = f"{piece_symbol}{from_square}x{to_square}"
            else:
                notation = f"{piece_symbol}{from_square}-{to_square}"
            
            # Превращение пешки
            if move.get("promotion"):
                notation += f"={PGNExporter._piece_to_symbol(move['promotion']).upper()}"
            
            # Рокировка
            if move.get("castling") == "kingside":
                notation = "O-O"
            elif move.get("castling") == "queenside":
                notation = "O-O-O"
            
            # Взятие на проходе
            if move.get("en_passant"):
                notation = f"{from_square[0]}x{to_square}"
            
            # Добавляем номер хода для белых
            if i % 2 == 0:
                moves.append(f"{move_number}. {notation}")
            else:
                moves[-1] += f" {notation}"
                move_number += 1
        
        pgn_lines.append(" ".join(moves))
        pgn_lines.append(result)
        
        return "\n".join(pgn_lines)
    
    @staticmethod
    def _coords_to_square(coords: List[int]) -> str:
        """Конвертировать координаты [x, y] в шахматную нотацию (например, e4)"""
        files = "abcdefgh"
        ranks = "12345678"
        return files[coords[0]] + ranks[7 - coords[1]]
    
    @staticmethod
    def _piece_to_symbol(piece_type: str) -> str:
        """Конвертировать тип фигуры в символ для PGN"""
        symbols = {
            "pawn": "",
            "rook": "R",
            "knight": "N",
            "bishop": "B",
            "queen": "Q",
            "king": "K"
        }
        return symbols.get(piece_type, "")


class PGNImporter:
    """Импортёр партий из формата PGN"""
    
    @staticmethod
    def import_game(pgn_text: str) -> Dict:
        """
        Импортировать партию из формата PGN
        
        Args:
            pgn_text: Текст в формате PGN
        
        Returns:
            Словарь с данными партии
        """
        lines = pgn_text.strip().split("\n")
        
        metadata = {}
        moves_text = ""
        
        # Парсим заголовки
        for line in lines:
            line = line.strip()
            if line.startswith("["):
                # Заголовок PGN
                key, value = PGNImporter._parse_header(line)
                if key:
                    metadata[key.lower()] = value
            elif line and not line.startswith("["):
                # Ходы
                moves_text += line + " "
        
        # Парсим ходы
        moves = PGNImporter._parse_moves(moves_text)
        
        return {
            "metadata": metadata,
            "moves": moves
        }
    
    @staticmethod
    def _parse_header(header_line: str) -> tuple:
        """Парсить строку заголовка PGN"""
        try:
            header_line = header_line.strip("[]")
            key, value = header_line.split(' "', 1)
            value = value.rstrip('"')
            return key, value
        except:
            return None, None
    
    @staticmethod
    def _parse_moves(moves_text: str) -> List[str]:
        """Парсить ходы из текста"""
        # Упрощённый парсер (в реальности нужен более сложный)
        moves = []
        parts = moves_text.split()
        
        for part in parts:
            # Пропускаем номера ходов и результат
            if part and not part[0].isdigit() and part not in ["1-0", "0-1", "1/2-1/2", "*"]:
                moves.append(part)
        
        return moves


