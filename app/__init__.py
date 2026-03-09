import os
import logging
from flask import Flask
from config import config
from app.extensions import db, migrate, bcrypt

def create_app(config_name=None):
    """Application factory pattern"""
    if config_name is None:
        # Enhanced environment detection for Cloud Run
        if (os.getenv('FLASK_ENV') == 'production' or
            os.getenv('GAE_ENV', '').startswith('standard') or
            os.getenv('K_SERVICE') or  # Cloud Run specific
            os.getenv('PORT')):  # Cloud Run port
            config_name = 'production'
        else:
            config_name = 'default'
    
    # Get the absolute path to the project root (where templates/ is located)
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
    
    app = Flask(__name__, 
                template_folder=template_dir,
                static_folder=static_dir)
    
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    
    # Configure SQLite for better concurrent access
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        import sqlite3
        
        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            if isinstance(dbapi_connection, sqlite3.Connection):
                cursor = dbapi_connection.cursor()
                # Enable WAL mode for better concurrent access
                cursor.execute("PRAGMA journal_mode=WAL")
                # Set timeout for database locks
                cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds
                # Other optimizations
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA temp_store=memory")
                cursor.close()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Register blueprints
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    from app.projects import bp as projects_bp
    app.register_blueprint(projects_bp, url_prefix='/projects')
    
    from app.user import bp as user_bp
    app.register_blueprint(user_bp, url_prefix='/user')
    
    # Setup directories
    from app.utils.file_utils import setup_directories
    setup_directories(app.config['BASE_DIR'], app.config['UPLOAD_FOLDER'])
    
    return app