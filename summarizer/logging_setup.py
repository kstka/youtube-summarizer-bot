from pathlib import Path

from loguru import logger

from .config import Logging


def setup_logging() -> None:
    log_dir = Path(Logging.DIR)
    logger.add(
        log_dir / 'bot.log',
        rotation=Logging.ROTATION,
        retention=Logging.RETENTION,
        compression='zip',
        level='INFO',
    )
