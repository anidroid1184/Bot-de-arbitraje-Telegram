"""
Logging utilities for the arbitrage bot.
Provides structured logging with different levels and output formats.
"""
import logging
import sys
from pathlib import Path
from typing import Optional, Any

# Try to import structlog, fallback to std logging if unavailable
try:
    import structlog  # type: ignore
except ModuleNotFoundError:  # graceful fallback
    structlog = None  # type: ignore

def setup_logger(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    service_name: str = "arbitrage_bot"
) -> Any:
    """
    Set up structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        service_name: Name of the service for log context
    
    Returns:
        Configured logger (structlog if available, else standard logging.Logger)
    """
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )

    # If structlog is available, configure it; otherwise return std logger
    if structlog is not None:
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    # Create file handler if log_file is specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        
        # Add file handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
    
    # Create and return logger instance
    if structlog is not None:
        logger = structlog.get_logger(service_name)
        return logger
    else:
        # Return a standard logger with the given service name
        return logging.getLogger(service_name)

def get_module_logger(module_name: str) -> Any:
    """Get a logger instance for a specific module"""
    if structlog is not None:
        return structlog.get_logger(module_name)
    else:
        return logging.getLogger(module_name)
