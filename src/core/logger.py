import logging
import sys

def setup_logger(name: str = "VB-Login") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        # Ensure Windows console handles UTF-8 cleanly
        stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace', buffering=1) if hasattr(sys.stdout, 'fileno') else sys.stdout
        stream_handler = logging.StreamHandler(stream)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger

logger = setup_logger()
