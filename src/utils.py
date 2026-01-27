
import logging

MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

logger = logging.getLogger(__name__)

def check_file_size(file_size: int) -> bool:
    """Checks if file size is within limits."""
    if file_size > MAX_FILE_SIZE_BYTES:
        logger.warning(f"File too large: {file_size / 1024 / 1024:.2f} MB")
        return False
    return True
