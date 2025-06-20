from app import db
from datetime import datetime

class Contact(db.Model):
    __tablename__="contacts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)       
    email = db.Column(db.String(120), nullable=False)      
    subject = db.Column(db.String(200), nullable=False)   
    message = db.Column(db.Text, nullable=False)           
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "subject": self.subject,
            "message": self.message,
            "created_at": self.created_at.isoformat()
        }
