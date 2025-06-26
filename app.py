from datetime import timedelta
from flask import Flask, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
from extensions import db, bcrypt, jwt, mail
from routes import comment_r, contact_r, like_r, post_r, user_r, notification_r
import cloudinary
import cloudinary.uploader

load_dotenv()

FRONTEND_URL = os.getenv('FRONTEND_URL', "https://aeedk-frontend.onrender.com")

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

def create_app():
    app = Flask(__name__, static_folder='frontend/build', static_url_path='/')

    frontend_origins = [FRONTEND_URL]

    CORS(
        app,
        resources={r"/api/*": {"origins": frontend_origins}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["Authorization"],
        max_age=600,
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )

    @app.before_request
    def handle_options_requests():
        if request.method == 'OPTIONS':
            return '', 200

    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', 'devkey'),
        JWT_SECRET_KEY=os.getenv('JWT_SECRET_KEY', 'devjwtkey'),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(days=30),
        SQLALCHEMY_DATABASE_URI=f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAIL_SERVER=os.getenv('MAIL_SERVER'),
        MAIL_PORT=int(os.getenv('MAIL_PORT', 587)),
        MAIL_USE_TLS=os.getenv('MAIL_USE_TLS', 'True') == 'True',
        MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
        MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.getenv('MAIL_DEFAULT_SENDER'),
        MAIL_DEBUG=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_recycle": 280,
            "pool_pre_ping": True
        },
        SQLALCHEMY_POOL_SIZE=5,
        SQLALCHEMY_MAX_OVERFLOW=10,
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
    app.register_blueprint(notification_r.notification_bp)

    @app.route('/media/<path:filename>')
    def media(filename):
        return send_from_directory('media', filename)

    @app.route('/<path:path>', methods=['GET'])
    def serve_react_app(path):
        if path.startswith('api') or path.startswith('media'):
            return "Not found", 404
        if os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

    @app.route('/', methods=['GET'])
    def serve_index():
        return send_from_directory(app.static_folder, 'index.html')

    return app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        from models.user import User
        from models.post import Post
        from models.comment import Comment
        from models.contact import Contact
        from models.like import Like

    app.run(
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'False') == 'True'
    )
