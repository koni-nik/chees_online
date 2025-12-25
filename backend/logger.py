"""
Система логирования для онлайн версии шахмат.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(name: str = "chess_online", log_dir: str = "logs") -> logging.Logger:
    """
    Настраивает и возвращает logger.
    
    Args:
        name: Имя логгера
        log_dir: Директория для логов
        
    Returns:
        Настроенный logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Не добавляем обработчики повторно
    if logger.handlers:
        return logger
    
    # Создаём директорию для логов
    Path(log_dir).mkdir(exist_ok=True)
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Файловый обработчик с ротацией
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'chess_online.log'),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger



