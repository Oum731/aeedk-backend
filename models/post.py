from datetime import datetime
from app import db
from models.like import Like

class Post(db.Model):
    __tablename__ = 'posts'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User', backref=db.backref('posts', lazy=True))
    comments = db.relationship('Comment', back_populates='post', cascade="all, delete-orphan")
    media = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(50), default='published')
    views = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)

    def count_all_comments(self):
        def count_recursive(comments):
            total = 0
            for c in comments:
                total += 1
                total += count_recursive(c.children)
            return total
        parents = [c for c in self.comments if c.parent_comment_id is None]
        return count_recursive(parents)

    def to_dict(self, include_comments=False):
        data = {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "author_id": self.author_id,
            "author_username": self.author.username if self.author else None,
            "user": self.author.to_dict() if self.author else None,
            "media": self.media,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status,
            "likes": Like.query.filter_by(content_type='post', content_id=self.id, is_like=True).count(),
            "dislikes": Like.query.filter_by(content_type='post', content_id=self.id, is_like=False).count(),
            "views": self.views,
            "is_featured": self.is_featured,
            "comments_count": self.count_all_comments(),
        }
        if include_comments:
            data["comments"] = [
                comment.to_dict() for comment in self.comments if comment.parent_comment_id is None
            ]
        return data
