from datetime import timedelta
from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
from extensions import db, bcrypt, jwt, mail
from routes import comment_r, contact_r, like_r, post_r, user_r

load_dotenv()

def create_app():
    app = Flask(__name__)

    CORS(
        app,
        origins=[
            "http://localhost:5173",
            "https://aeedk.netlify.app",
            "https://aeedk-frontend.onrender.com"
        ],
        supports_credentials=True,
        expose_headers=["Authorization"],
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )

    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY'),
        JWT_SECRET_KEY=os.getenv('JWT_SECRET_KEY'),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=12),
        SQLALCHEMY_DATABASE_URI=os.getenv('SQLALCHEMY_DATABASE_URI'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAIL_SERVER=os.getenv('MAIL_SERVER'),
        MAIL_PORT=int(os.getenv('MAIL_PORT')),
        MAIL_USE_TLS=os.getenv('MAIL_USE_TLS') == 'True',
        MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
        MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.getenv('MAIL_DEFAULT_SENDER'),
        MAIL_DEBUG=True
    )

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)

    app.register_blueprint(user_r.user_bp)
    app.register_blueprint(post_r.post_bp)
    app.register_blueprint(like_r.like_bp)
    app.register_blueprint(comment_r.comment_bp)
    app.register_blueprint(contact_r.contact_bp)

    @app.route('/media/<path:filename>')
    def media(filename):
        return send_from_directory('media', filename)

    @app.route('/')
    def index():
        return "<h1>Bienvenue dans l'API Flask</h1>"

    return app

if __name__ == "__main__":
    app = create_app()

    with app.app_context():
        from models.user import User
        from models.post import Post
        from models.comment import Comment
        from models.contact import Contact
        from models.like import Like
        db.create_all()

    app.run(
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'True') == 'True'
    )
