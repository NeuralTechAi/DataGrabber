import os
import secrets
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
    
    # File storage (local by default, under your home directory)
    USER_HOME = os.path.expanduser("~")
    BASE_DIR = os.path.join(USER_HOME, "DataGrabber")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

    # Database – default to a simple local SQLite file for non‑technical users
    _db_url = (os.getenv('DATABASE_URL') or '').strip()
    SQLALCHEMY_DATABASE_URI = _db_url if _db_url else f"sqlite:///{os.path.join(BASE_DIR, 'datagrabber.db')}"
    # Per-request upload limit. Folder uploads now send CHUNK_SIZE=10 files per request
    # so 200 MB per chunk handles even very large individual files comfortably.
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 200 * 1024 * 1024))  # 200 MB per chunk
    
    # Session
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    
    # API Keys
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    
    # Local / self-hosted model endpoints (Ollama)
    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434/v1')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2')
    
    # URLs
    BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
    
    # AI Provider Settings - Gemini as default
    # Valid providers: gemini, openai, anthropic, openrouter, ollama
    AI_PROVIDER = os.getenv('AI_PROVIDER', 'gemini')
    AI_MODEL = os.getenv('AI_MODEL', 'gemini-1.5-flash')
    ENABLE_OPENAI = os.getenv('ENABLE_OPENAI', 'true').lower() == 'true'
    ENABLE_ANTHROPIC = os.getenv('ENABLE_ANTHROPIC', '').lower() == 'true'
    ENABLE_GEMINI = True  # Always enable Gemini as default
    
    # Email Configuration for Password Recovery
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    FROM_EMAIL = os.getenv('FROM_EMAIL')  # Optional, defaults to SMTP_USERNAME

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

    # GAE specific settings
    BASE_DIR = "/tmp"  # GAE has limited filesystem access
    UPLOAD_FOLDER = "/tmp/uploads"

    # Force HTTPS
    PREFERRED_URL_SCHEME = 'https'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}