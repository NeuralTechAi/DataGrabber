import os
import logging

logger = logging.getLogger(__name__)

def setup_directories(base_dir, upload_folder):
    """Create necessary directories for the application"""
    try:
        os.makedirs(base_dir, exist_ok=True)
        logger.info(f"Created base directory: {base_dir}")
    except PermissionError as e:
        logger.error(f"Permission denied creating base directory {base_dir}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error creating base directory {base_dir}: {e}")
        raise

    try:
        os.makedirs(upload_folder, exist_ok=True)
        logger.info(f"Created upload directory: {upload_folder}")
    except PermissionError as e:
        logger.error(f"Permission denied creating upload directory {upload_folder}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error creating upload directory {upload_folder}: {e}")
        raise

# Server-side folder browsing functions removed
# These have been replaced with client-side folder selection
# using HTML5 directory input capabilities