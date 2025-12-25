# tournament.py - Система турниров
from typing import Dict, List, Optional
import uuid
import time
from enum import Enum


class TournamentType(Enum):
    SWISS = "swiss"  # Швейцарская система
    ROUND_ROBIN = "round_robin"  # Круговая система


class TournamentStatus(Enum):
    REGISTRATION = "registration"  # Регистрация
    IN_PROGRESS = "in_progress"  # Идёт
    FINISHED = "finished"  # Завершён


class Tournament:
    """Класс для управления турниром"""
    
    def __init__(self, 
                 name: str,
                 tournament_type: TournamentType,
                 max_players: int = 16,
                 time_control: int = 600):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.type = tournament_type
        self.status = TournamentStatus.REGISTRATION
        self.max_players = max_players
        self.time_control = time_control
        self.players: List[str] = []  # player_id
        self.rounds: List[Dict] = []
        self.current_round = 0
        self.standings: Dict[str, Dict] = {}  # player_id -> {wins, draws, losses, points}
        self.created_at = time.time()
    
    def register_player(self, player_id: str) -> bool:
        """Зарегистрировать игрока"""
        if self.status != TournamentStatus.REGISTRATION:
            return False
        if len(self.players) >= self.max_players:
            return False
        if player_id in self.players:
            return False
        
        self.players.append(player_id)
        self.standings[player_id] = {
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "points": 0
        }
        return True
    
    def unregister_player(self, player_id: str) -> bool:
        """Отменить регистрацию игрока"""
        if player_id in self.players:
            self.players.remove(player_id)
            if player_id in self.standings:
                del self.standings[player_id]
            return True
        return False
    
    def start_tournament(self) -> bool:
        """Начать турнир"""
        if len(self.players) < 2:
            return False
        if self.status != TournamentStatus.REGISTRATION:
            return False
        
        self.status = TournamentStatus.IN_PROGRESS
        self.current_round = 0
        
        if self.type == TournamentType.SWISS:
            self._create_swiss_round()
        elif self.type == TournamentType.ROUND_ROBIN:
            self._create_round_robin_rounds()
        
        return True
    
    def _create_swiss_round(self):
        """Создать раунд по швейцарской системе"""
        # Упрощённая реализация - парим игроков по рейтингу
        sorted_players = sorted(self.players, key=lambda p: self.standings[p]["points"], reverse=True)
        
        pairs = []
        used = set()
        
        for i, player1 in enumerate(sorted_players):
            if player1 in used:
                continue
            
            # Ищем соперника
            for j, player2 in enumerate(sorted_players[i+1:], i+1):
                if player2 not in used:
                    pairs.append((player1, player2))
                    used.add(player1)
                    used.add(player2)
                    break
        
        round_data = {
            "round_number": self.current_round + 1,
            "pairs": pairs,
            "results": {}
        }
        
        self.rounds.append(round_data)
    
    def _create_round_robin_rounds(self):
        """Создать все раунды для круговой системы"""
        # Каждый играет с каждым
        for round_num in range(len(self.players) - 1):
            pairs = []
            # Упрощённая реализация ротации
            for i in range(0, len(self.players) - 1, 2):
                pairs.append((self.players[i], self.players[i + 1]))
            
            round_data = {
                "round_number": round_num + 1,
                "pairs": pairs,
                "results": {}
            }
            self.rounds.append(round_data)
    
    def record_result(self, player1: str, player2: str, result: str):
        """
        Записать результат игры
        
        Args:
            player1: ID первого игрока
            player2: ID второго игрока
            result: "1-0", "0-1", "1/2-1/2"
        """
        if self.current_round >= len(self.rounds):
            return
        
        round_data = self.rounds[self.current_round]
        pair_key = f"{player1}-{player2}"
        
        if pair_key not in round_data["results"]:
            round_data["results"][pair_key] = result
            
            # Обновляем таблицу
            if result == "1-0":
                self.standings[player1]["wins"] += 1
                self.standings[player1]["points"] += 1
                self.standings[player2]["losses"] += 1
            elif result == "0-1":
                self.standings[player2]["wins"] += 1
                self.standings[player2]["points"] += 1
                self.standings[player1]["losses"] += 1
            elif result == "1/2-1/2":
                self.standings[player1]["draws"] += 1
                self.standings[player1]["points"] += 0.5
                self.standings[player2]["draws"] += 1
                self.standings[player2]["points"] += 0.5
    
    def next_round(self) -> bool:
        """Перейти к следующему раунду"""
        if self.type == TournamentType.SWISS:
            if self.current_round < len(self.rounds) - 1:
                self.current_round += 1
                return True
            else:
                # Создаём новый раунд
                self._create_swiss_round()
                return True
        elif self.type == TournamentType.ROUND_ROBIN:
            if self.current_round < len(self.rounds) - 1:
                self.current_round += 1
                return True
        
        # Турнир завершён
        self.status = TournamentStatus.FINISHED
        return False
    
    def get_standings(self) -> List[Dict]:
        """Получить таблицу турнира"""
        standings_list = []
        for player_id, stats in self.standings.items():
            standings_list.append({
                "player_id": player_id,
                **stats
            })
        
        standings_list.sort(key=lambda x: x["points"], reverse=True)
        return standings_list
    
    def to_dict(self) -> Dict:
        """Конвертировать турнир в словарь"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "max_players": self.max_players,
            "time_control": self.time_control,
            "players": self.players,
            "current_round": self.current_round,
            "total_rounds": len(self.rounds),
            "standings": self.get_standings()
        }


# Хранилище турниров
tournaments: Dict[str, Tournament] = {}


