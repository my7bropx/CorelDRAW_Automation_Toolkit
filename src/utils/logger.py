"""
Logging utilities for the application.
"""

import logging
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


# User action logger - tracks all user interactions for debugging
_user_action_logger: Optional[logging.Logger] = None


def setup_file_logger(name: str, log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a file logger with rotation.

    Args:
        name: Logger name.
        log_dir: Directory for log files.
        level: Logging level.

    Returns:
        Configured logger.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Create log directory if needed
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create file handler with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{name}_{timestamp}.log"

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(formatter)

    # Add handler
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger by name.

    Args:
        name: Logger name.

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)


class LogCapture:
    """Context manager to capture log messages."""

    def __init__(self, logger_name: str = None):
        """Initialize log capture."""
        self.logger_name = logger_name
        self.messages = []
        self.handler = None

    def __enter__(self):
        """Start capturing."""
        class CaptureHandler(logging.Handler):
            def __init__(self, capture):
                super().__init__()
                self.capture = capture

            def emit(self, record):
                self.capture.messages.append(self.format(record))

        if self.logger_name:
            logger = logging.getLogger(self.logger_name)
        else:
            logger = logging.getLogger()

        self.handler = CaptureHandler(self)
        self.handler.setLevel(logging.DEBUG)
        logger.addHandler(self.handler)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop capturing."""
        if self.handler and self.logger_name:
            logger = logging.getLogger(self.logger_name)
            logger.removeHandler(self.handler)
        elif self.handler:
            logging.getLogger().removeHandler(self.handler)


def get_user_action_logger(log_dir: Path = None) -> logging.Logger:
    """
    Get or create the user action logger.
    
    Args:
        log_dir: Directory for log files. If None, uses a default.
        
    Returns:
        Logger for user actions.
    """
    global _user_action_logger
    
    if _user_action_logger is not None:
        return _user_action_logger
    
    _user_action_logger = logging.getLogger("user_actions")
    _user_action_logger.setLevel(logging.INFO)
    
    if log_dir is None:
        log_dir = Path.home() / ".coreldraw_automation" / "logs"
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Action log file
    action_log = log_dir / "actions.log"
    handler = logging.FileHandler(action_log, encoding='utf-8')
    handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    _user_action_logger.addHandler(handler)
    
    return _user_action_logger


def log_user_action(action: str, details: Dict[str, Any] = None, tool: str = None):
    """
    Log a user action for debugging and analytics.
    
    Args:
        action: The action performed (e.g., "connect_coreldraw", "apply_preset")
        details: Additional details about the action
        tool: The tool/feature where action occurred
    """
    logger = get_user_action_logger()
    
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "tool": tool,
        "details": details or {}
    }
    
    logger.info(json.dumps(log_data))


def log_corel_operation(operation: str, success: bool, error: str = None):
    """
    Log a CorelDRAW operation.
    
    Args:
        operation: The operation performed
        success: Whether it succeeded
        error: Error message if failed
    """
    logger = get_user_action_logger()
    
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "type": "corel_operation",
        "operation": operation,
        "success": success,
        "error": error
    }
    
    if success:
        logger.info(json.dumps(log_data))
    else:
        logger.warning(json.dumps(log_data))
