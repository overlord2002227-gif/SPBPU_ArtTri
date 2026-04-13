import logging
from pathlib import Path
import sys


def setup_logger(name: str, log_file: str = "logs/bot.log") -> logging.Logger:
    """Настройка логирования с ротацией"""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Формат
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Файл
    file_handler = logging.FileHandler(
        logs_dir / "bot.log",
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger("ai_assistant")