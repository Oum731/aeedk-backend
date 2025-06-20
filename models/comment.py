from datetime import datetime
from app import db
from models.like import Like

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_moderated = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', back_populates='comments')
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    post = db.relationship('Post', back_populates='comments')
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True)
    children = db.relationship(
        'Comment',
        backref=db.backref('parent', remote_side=[id]),
        cascade="all, delete-orphan",
        order_by="Comment.created_at"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_moderated": self.is_moderated,
            "user_id": self.user_id,
            "user": {
                "id": self.user.id,
                "username": self.user.username,
                "avatar": self.user.avatar,
            } if self.user else None,
            "post_id": self.post_id,
            "parent_comment_id": self.parent_comment_id,
            "children": [child.to_dict() for child in self.children],
            "likes": Like.query.filter_by(content_type='comment', content_id=self.id, is_like=True).count(),
            "dislikes": Like.query.filter_by(content_type='comment', content_id=self.id, is_like=False).count(),
        }
