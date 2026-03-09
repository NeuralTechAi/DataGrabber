"""
Environment detection utilities for Cloud Run deployment
"""
import os

def is_cloud_environment():
    """
    Detect if the application is running in a cloud environment (Cloud Run, GAE, etc.)
    """
    # Strong cloud environment indicators
    cloud_indicators = [
        os.getenv('K_SERVICE') is not None,  # Cloud Run specific
        os.getenv('GAE_ENV', '').startswith('standard'),  # App Engine
        os.getenv('GOOGLE_CLOUD_PROJECT') is not None,  # Any Google Cloud service
        os.getenv('CLOUD_RUN_SERVICE') is not None,  # Cloud Run alternate
        '/layers/' in os.getcwd() if hasattr(os, 'getcwd') else False,  # Cloud buildpacks
    ]

    # If any strong indicator is present, it's definitely cloud
    if any(cloud_indicators):
        return True

    # Secondary indicators (less reliable)
    secondary_indicators = [
        os.getenv('FLASK_ENV') == 'production',
        os.getenv('PORT') is not None,
        not os.path.exists('/home'),  # Many cloud environments don't have /home
        os.getcwd().startswith('/app') if hasattr(os, 'getcwd') else False,  # Common cloud pattern
    ]

    # If multiple secondary indicators, likely cloud
    return sum(secondary_indicators) >= 2

def get_default_storage_path():
    """
    Get the default storage path based on environment
    """
    if is_cloud_environment():
        return '/tmp'
    else:
        # Even in local environment, use fallback for better compatibility
        try:
            user_home = os.path.expanduser('~')
            if os.path.exists(user_home) and os.access(user_home, os.W_OK):
                return user_home
        except (OSError, PermissionError):
            pass
        # Fallback to /tmp if user home has issues
        return '/tmp'

def get_allowed_browse_paths():
    """
    Get allowed paths for directory browsing based on environment
    """
    if is_cloud_environment():
        return ['/tmp', '/tmp/uploads', '/tmp/DataGrabber']
    else:
        # Even in local environment, restrict to safe directories to avoid permission errors
        safe_paths = ['/tmp', '/tmp/uploads']

        # Try to add user directories if they exist and are accessible
        try:
            user_home = os.path.expanduser('~')
            if os.path.exists(user_home) and os.access(user_home, os.R_OK):
                safe_paths.extend([
                    user_home,
                    os.path.join(user_home, 'DataGrabber'),
                    os.path.join(user_home, 'Documents'),
                    os.path.join(user_home, 'Desktop'),
                    os.path.join(user_home, 'Downloads')
                ])
        except (OSError, PermissionError):
            # Skip user directories if there are permission issues
            pass

        # Only add /home if it's accessible (avoid permission errors)
        try:
            if os.path.exists('/home') and os.access('/home', os.R_OK):
                safe_paths.append('/home')
        except (OSError, PermissionError):
            pass

        return safe_paths