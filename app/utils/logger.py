"""
Logging configuration for HealthmateUI
"""
import logging
import sys
from typing import Optional
from .config import get_config

config = get_config()


def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Setup logger with appropriate configuration
    
    Args:
        name: Logger name (defaults to __name__)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name or __name__)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Set log level based on environment
    log_level = logging.DEBUG if config.DEBUG else logging.INFO
    logger.setLevel(log_level)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


# Create default logger
logger = setup_logger('healthmate_ui')