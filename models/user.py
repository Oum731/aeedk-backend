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
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "birth_date": self.birth_date.strftime("%Y-%m-%d") if self.birth_date else None,
            "sub_prefecture": self.sub_prefecture,
            "village": self.village,
            "avatar": avatar_url,
            "role": self.role,
            "confirmed": self.confirmed,
            "phone": self.phone
        }
