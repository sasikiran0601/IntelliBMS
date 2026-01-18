"""
Database models and configuration for IntelliBMS
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship with batteries
    batteries = db.relationship('Battery', backref='owner', lazy=True)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Battery(db.Model):
    """Battery model for storing battery configurations"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    battery_type = db.Column(db.String(50), nullable=False)
    num_cells = db.Column(db.Integer, nullable=False)
    base_voltage = db.Column(db.Float, nullable=False)
    base_soh = db.Column(db.Float, nullable=False)
    base_temp = db.Column(db.Float, nullable=False)
    degradation_rate = db.Column(db.Float, nullable=False)
    fault_probability = db.Column(db.Float, nullable=False)
    capacity_ah = db.Column(db.Float, nullable=True)
    max_charge_rate = db.Column(db.Float, nullable=True)
    max_discharge_rate = db.Column(db.Float, nullable=True)
    operating_temp_min = db.Column(db.Float, nullable=True)
    operating_temp_max = db.Column(db.Float, nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign key to user
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def to_dict(self):
        """Convert battery to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'battery_type': self.battery_type,
            'num_cells': self.num_cells,
            'base_voltage': self.base_voltage,
            'base_soh': self.base_soh,
            'base_temp': self.base_temp,
            'degradation_rate': self.degradation_rate,
            'fault_probability': self.fault_probability,
            'capacity_ah': self.capacity_ah,
            'max_charge_rate': self.max_charge_rate,
            'max_discharge_rate': self.max_discharge_rate,
            'operating_temp_min': self.operating_temp_min,
            'operating_temp_max': self.operating_temp_max,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Battery {self.name}>'

def init_db(app):
    """Initialize database with app"""
    db.init_app(app)
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Create default admin user if not exists
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@intellibms.com'
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin user created: admin/admin123")
