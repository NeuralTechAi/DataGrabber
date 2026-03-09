from datetime import datetime
from app.extensions import db

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_superadmin = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<Admin {self.username}>'
    
class AdminActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    action = db.Column(db.String(255), nullable=False)  # e.g., "Suspend User"
    target_user_email = db.Column(db.String(120), nullable=True)  # just a string, no FK
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    admin = db.relationship('Admin', backref='activities')

    def __repr__(self):
        return f'<AdminActivity {self.action} on {self.target_user_email}>'
