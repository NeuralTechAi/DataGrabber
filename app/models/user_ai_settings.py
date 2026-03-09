"""Per-user AI provider and API key settings."""
from app.extensions import db


class UserAISettings(db.Model):
    """One row per user: selected provider, model, and API keys per provider."""
    __tablename__ = 'user_ai_settings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, unique=True)

    # Selected provider and model for extraction
    ai_provider = db.Column(db.String(32), nullable=True)   # openai, gemini, openrouter, ollama
    ai_model = db.Column(db.String(128), nullable=True)

    # API keys (store per provider; only the selected provider's key is required)
    openai_api_key = db.Column(db.String(512), nullable=True)
    gemini_api_key = db.Column(db.String(512), nullable=True)
    openrouter_api_key = db.Column(db.String(512), nullable=True)

    # Ollama (no API key)
    ollama_base_url = db.Column(db.String(256), nullable=True)   # e.g. http://localhost:11434/v1
    ollama_model = db.Column(db.String(128), nullable=True)

    # Relationship
    user = db.relationship('User', backref=db.backref('ai_settings', uselist=False, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<UserAISettings user_id={self.user_id} provider={self.ai_provider}>'
