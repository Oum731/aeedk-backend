from datetime import datetime
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
    avatar = db.Column(db.String(255), default="")
    role = db.Column(db.String(20), default='membre')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed = db.Column(db.Boolean, default=False)
    confirmation_token = db.Column(db.String(128), nullable=True)
    reset_token = db.Column(db.String(128), nullable=True)
    reset_token_expiration = db.Column(db.DateTime, nullable=True)
    last_active = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    comments = db.relationship('Comment', back_populates='user', cascade="all, delete-orphan")
    likes = db.relationship('Like', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        default_avatar_url = "https://collection.cloudinary.com/dk6mvlzji/510146622a6b9787c7454c15adb84e7c"
        avatar_value = self.avatar if self.avatar and isinstance(self.avatar, str) else ""
        avatar_url = avatar_value if avatar_value.startswith("http") else default_avatar_url

        try:
            if not self.birth_date:
                birth_date_str = ""
            elif isinstance(self.birth_date, str):
                birth_date_str = self.birth_date
            elif hasattr(self.birth_date, 'strftime'):
                birth_date_str = self.birth_date.strftime("%Y-%m-%d")
            else:
                birth_date_str = str(self.birth_date)
        except Exception:
            birth_date_str = ""

        from datetime import datetime, timedelta
        is_online = False
        if self.last_active:
            is_online = (datetime.utcnow() - self.last_active) < timedelta(minutes=5)

        return {
            "id": self.id,
            "username": self.username or "",
            "email": self.email or "",
            "first_name": self.first_name or "",
            "last_name": self.last_name or "",
            "birth_date": birth_date_str,
            "sub_prefecture": self.sub_prefecture or "",
            "village": self.village or "",
            "avatar": avatar_value,
            "avatar_url": avatar_url,
            "role": self.role or "membre",
            "confirmed": bool(self.confirmed),
            "phone": self.phone or "",
            "is_online": is_online
        }
