from datetime import datetime
from app.extensions import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    credits = db.Column(db.Integer, default=0)
    balance = db.Column(db.Float, default=0.0)  # Available money balance in USD
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    is_suspended = db.Column(db.Boolean, default=False)

    # ✅ Add cascade deletes
    projects = db.relationship(
        'Project',
        backref='user',
        lazy=True,
        cascade="all, delete-orphan"
    )
    # Legacy relationships for payments/credits have been removed – app is now free to use

    def __repr__(self):
        return f'<User {self.username}>'
        
    def sync_balance_with_credits(self):
        """Synchronize the money balance with credits value (1 credit = $0.10)"""
        credit_value = self.credits * 0.10
        if self.balance != credit_value:
            self.balance = credit_value
            return True  # Balance was updated
        return False  # No change needed
