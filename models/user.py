from datetime import datetime, timedelta
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    phone = db.Column(db.String(30))
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    birth_date = db.Column(db.Date)
    sub_prefecture = db.Column(db.String(100))
    village = db.Column(db.String(100))
    avatar = db.Column(db.String(255), default="avatars/avatar.jpeg")
    role = db.Column(db.String(20), default='membre')
    confirmed = db.Column(db.Boolean, default=False)
    confirmation_token = db.Column(db.String(128), nullable=True)
    reset_token = db.Column(db.String(128), nullable=True)
    reset_token_expiration = db.Column(db.DateTime, nullable=True)
    comments = db.relationship('Comment', back_populates='user', cascade="all, delete-orphan")
    likes = db.relationship('Like', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password, method='pbkdf2:sha256', salt_length=16
        )

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        if self.avatar:
            if self.avatar.startswith("http"):
                avatar_url = self.avatar
            elif self.avatar.startswith("/media"):
                avatar_url = self.avatar
            else:
                path = self.avatar.replace("\\", "/").lstrip("./")
                if path.startswith("media/"):
                    path = path[6:]
                avatar_url = f"/media/{path}"
        else:
            avatar_url = "/media/avatars/avatar.jpeg"
        return {
            "id": self.id,
            "username": str(self.username) if self.username else "",
            "email": str(self.email) if self.email else "",
            "first_name": str(self.first_name) if self.first_name else "",
            "last_name": str(self.last_name) if self.last_name else "",
            "birth_date": self.birth_date.strftime("%Y-%m-%d") if self.birth_date else None,
            "sub_prefecture": str(self.sub_prefecture) if self.sub_prefecture else "",
            "village": str(self.village) if self.village else "",
            "avatar": str(self.avatar) if self.avatar else "/media/avatars/avatar.jpeg",
            "role": str(self.role) if self.role else "membre",
            "confirmed": bool(self.confirmed),
            "phone": str(self.phone) if self.phone else "",
            "confirmation_token": str(self.confirmation_token) if self.confirmation_token else None,
            "reset_token": str(self.reset_token) if self.reset_token else None,
            "reset_token_expiration": self.reset_token_expiration.isoformat() if self.reset_token_expiration else None
        }
