from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from flask import url_for

class User(db.Model):
    __tablename__ = "user"
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    phone = db.Column(db.String(30))
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    birth_date = db.Column(db.Date)
    sub_prefecture = db.Column(db.String(100))
    village = db.Column(db.String(100))
    avatar = db.Column(db.String(255), default="default_avatar.png")
    role = db.Column(db.String(20), default='member', nullable=False)
    confirmed = db.Column(db.Boolean, default=False, nullable=False)
    confirmation_token = db.Column(db.String(128))
    reset_token = db.Column(db.String(128))
    reset_token_expiration = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    comments = db.relationship('Comment', back_populates='author', cascade="all, delete-orphan")
    likes = db.relationship('Like', back_populates='user', cascade='all, delete-orphan')
    posts = db.relationship('Post', back_populates='author', cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if not self.avatar:
            self.avatar = "default_avatar.png"
        if not self.role:
            self.role = 'member'

    def set_password(self, password):
        """Hash and set the user's password"""
        self.password_hash = generate_password_hash(
            password, 
            method='pbkdf2:sha256', 
            salt_length=16
        )

    def check_password(self, password):
        """Verify the provided password against the stored hash"""
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self):
        """Generate a unique confirmation token"""
        self.confirmation_token = generate_password_hash(
            f"{self.email}{datetime.utcnow().timestamp()}",
            method='pbkdf2:sha256',
            salt_length=8
        )[:128]

    def generate_reset_token(self):
        """Generate a password reset token"""
        self.reset_token = generate_password_hash(
            f"{self.id}{datetime.utcnow().timestamp()}",
            method='pbkdf2:sha256',
            salt_length=8
        )[:128]
        self.reset_token_expiration = datetime.utcnow() + timedelta(hours=1)

    def get_avatar_url(self):
        """Generate full URL for the user's avatar"""
        if self.avatar.startswith(('http://', 'https://')):
            return self.avatar
        return url_for('user.get_avatar', filename=self.avatar, _external=True)

    def to_dict(self, include_sensitive=False):
        """Convert user object to dictionary"""
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "sub_prefecture": self.sub_prefecture,
            "village": self.village,
            "avatar": self.get_avatar_url(),
            "role": self.role,
            "confirmed": self.confirmed,
            "phone": self.phone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data.update({
                "confirmation_token": self.confirmation_token,
                "reset_token": self.reset_token,
                "reset_token_expiration": self.reset_token_expiration.isoformat() 
                    if self.reset_token_expiration else None
            })
        
        return {k: v for k, v in data.items() if v is not None}

    def __repr__(self):
        return f"<User {self.username} ({self.email})>"