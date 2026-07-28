import logging
import sys
from app.config import settings

def setup_logger():
    # Get logger
    logger = logging.getLogger("costmate")
    
    # Configure level
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Check if handler already exists
    if not logger.handlers:
        # Create formatter
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Stream Handler (Stdout)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        
    return logger

logger = setup_logger()
