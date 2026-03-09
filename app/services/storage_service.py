import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class StorageService:
    """Service for storage and file path operations"""
    
    @staticmethod
    def format_path_for_display(storage_path: str) -> str:
        """Format a storage path for nice display in the UI"""
        if not storage_path:
            return ""

        # Shorten path if it's too long
        if len(storage_path) > 50:
            from app.utils.environment import is_cloud_environment

            if not is_cloud_environment():
                # Only do home directory replacement in local environment
                home_expanded = os.path.expanduser('~')
                if storage_path.startswith(home_expanded):
                    storage_path_display = f"~{storage_path[len(home_expanded):]}"
                else:
                    storage_path_display = storage_path
            else:
                # In cloud environment, show full path
                storage_path_display = storage_path

            # If still too long, truncate the middle
            if len(storage_path_display) > 50:
                parts = storage_path_display.split(os.sep)
                if len(parts) > 4:
                    storage_path_display = os.path.join(parts[0], parts[1], "...", *parts[-2:])

            return storage_path_display

        return storage_path
    
    @staticmethod
    def ensure_directory_exists(path: str) -> bool:
        """Ensure a directory exists, create if it doesn't"""
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            return False
    
    @staticmethod
    def get_safe_filename(filename: str) -> str:
        """Get a safe filename for storage"""
        from werkzeug.utils import secure_filename
        return secure_filename(filename)