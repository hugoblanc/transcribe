"""Configuration and logging setup."""

import logging
import sys
from pathlib import Path
from datetime import datetime

# Detect platform
IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# Audio settings
SAMPLE_RATE = 16000  # Optimal for Whisper
CHANNELS = 1  # Mono
BLOCK_SIZE = 1024

# Directories
BASE_DIR = Path(__file__).parent.parent
RECORDINGS_DIR = BASE_DIR / "recordings"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
LOGS_DIR = BASE_DIR / "logs"


def setup_logging(debug: bool = False, log_to_file: bool = True) -> logging.Logger:
    """Setup logging configuration.

    Args:
        debug: Enable debug level logging
        log_to_file: Also write logs to file

    Returns:
        Configured logger
    """
    logger = logging.getLogger("transcribe")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)

    # Format
    if debug:
        fmt = "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s"
    else:
        fmt = "%(message)s"

    console_handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    logger.addHandler(console_handler)

    # File handler (always debug level)
    if log_to_file:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOGS_DIR / f"transcribe_{datetime.now():%Y%m%d_%H%M%S}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d - %(message)s"
        ))
        logger.addHandler(file_handler)
        logger.debug(f"Logging to file: {log_file}")

    return logger


def get_logger() -> logging.Logger:
    """Get the transcribe logger."""
    return logging.getLogger("transcribe")


def get_platform_info() -> dict:
    """Get platform information for debugging."""
    import platform

    info = {
        "os": platform.system(),
        "os_version": platform.version(),
        "python_version": platform.python_version(),
        "machine": platform.machine(),
    }

    # Add GPU info
    try:
        import torch
        info["torch_version"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        info["mps_available"] = torch.backends.mps.is_available()
        if torch.cuda.is_available():
            info["cuda_device"] = torch.cuda.get_device_name(0)
    except ImportError:
        info["torch_version"] = "not installed"

    return info
