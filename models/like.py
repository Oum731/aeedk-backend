from datetime import datetime
from app import db

class Like(db.Model):
    __tablename__ = 'likes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content_type = db.Column(db.String(20), nullable=False)
    content_id = db.Column(db.Integer, nullable=False)
    is_like = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='likes')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'content_type', 'content_id', name='unique_user_like'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content_type": self.content_type,
            "content_id": self.content_id,
            "is_like": self.is_like,
            "created_at": self.created_at.isoformat(),
        }
