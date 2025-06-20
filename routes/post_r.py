from datetime import datetime
from flask import Blueprint, jsonify, request, send_from_directory
from app import db
from models.like import Like
from models.post import Post
from models.user import User
import os
import uuid
from werkzeug.utils import secure_filename

post_bp = Blueprint('post_bp', __name__, url_prefix='/api/posts')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm'}
UPLOAD_FOLDER = './media/posts'
BASE_URL = 'http://localhost:5000'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_admin(user_id):
    user = User.query.get(user_id)
    return user and user.role == 'admin'

@post_bp.route('/media/<path:filename>')
def media_posts(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@post_bp.route('', methods=['POST'])
def create_post():
    user_id = request.form.get('author_id')
    if not user_id or not is_admin(user_id):
        return jsonify({"error": "Accès non autorisé"}), 403

    title = request.form.get('title')
    content = request.form.get('content')
    if not title or not content:
        return jsonify({"error": "Titre et contenu sont obligatoires"}), 400

    medias = []
    for file in request.files.getlist('media'):
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4()}_{filename}"
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            file_path = os.path.join(UPLOAD_FOLDER, unique_name)
            file.save(file_path)
            ext = filename.rsplit('.', 1)[1].lower()
            media_type = 'video' if ext in {'mp4', 'webm'} else 'image'
            media_url = f"{BASE_URL}/api/posts/media/{unique_name}"
            medias.append({
                "url": media_url,
                "filename": filename,
                "type": media_type,
            })

    post = Post(
        title=title,
        content=content,
        author_id=user_id,
        is_featured=request.form.get('is_featured', 'false').lower() == 'true',
        status=request.form.get('status', 'published'),
        media=medias if medias else None,
        created_at=datetime.utcnow()
    )
    db.session.add(post)
    db.session.commit()

    return jsonify({
        "message": "Post créé avec succès",
        "post": post.to_dict(),
    }), 201

@post_bp.route('', methods=['GET'])
def get_posts():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return jsonify([post.to_dict() for post in posts]), 200

@post_bp.route('/<int:post_id>', methods=['GET'])
def get_post(post_id):
    post = Post.query.get(post_id)
    if not post:
        return jsonify({"error": "Post non trouvé"}), 404
    return jsonify(post.to_dict(include_comments=True)), 200

@post_bp.route('/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    user_id = request.form.get('author_id') or (request.json and request.json.get('author_id'))
    if not user_id:
        return jsonify({"error": "Identifiant utilisateur manquant"}), 400
    if not is_admin(user_id):
        return jsonify({"error": "Accès refusé, vous devez être admin"}), 403

    post = Post.query.get(post_id)
    if not post:
        return jsonify({"error": "Post non trouvé"}), 404

    if request.content_type and 'multipart/form-data' in request.content_type:
        form = request.form
        post.title = form.get('title', post.title)
        post.content = form.get('content', post.content)
        post.is_featured = form.get('is_featured', str(post.is_featured)).lower() == 'true'
        post.status = form.get('status', post.status)
        medias = []
        for file in request.files.getlist('media'):
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_name = f"{uuid.uuid4()}_{filename}"
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file_path = os.path.join(UPLOAD_FOLDER, unique_name)
                file.save(file_path)
                ext = filename.rsplit('.', 1)[1].lower()
                media_type = 'video' if ext in {'mp4', 'webm'} else 'image'
                url = f"{BASE_URL}/api/posts/media/{unique_name}"
                medias.append({"url": url, "filename": filename, "type": media_type})
        if medias:
            post.media = medias
    else:
        data = request.json
        for field in ['title', 'content', 'is_featured', 'status']:
            if data and field in data:
                setattr(post, field, data[field])

    post.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Post mis à jour", "post": post.to_dict()}), 200

@post_bp.route('/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    user_id = request.args.get('author_id') or (request.json and request.json.get('author_id'))
    if not user_id:
        return jsonify({"error": "Identifiant utilisateur manquant"}), 400
    if not is_admin(user_id):
        return jsonify({"error": "Accès refusé, vous devez être admin"}), 403

    post = Post.query.get(post_id)
    if not post:
        return jsonify({"error": "Post non trouvé"}), 404

    db.session.delete(post)
    db.session.commit()
    return jsonify({"message": "Post supprimé"}), 200

@post_bp.route('/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id manquant"}), 400
    post = Post.query.get_or_404(post_id)
    existing_like = Like.query.filter_by(user_id=user_id, content_type='post', content_id=post_id).first()
    if existing_like:
        return jsonify({"message": "Post déjà liké"}), 400

    like = Like(user_id=user_id, content_type='post', content_id=post_id)
    db.session.add(like)
    db.session.commit()
    return jsonify({"message": "Post liké"}), 201

@post_bp.route('/<int:post_id>/like', methods=['DELETE'])
def unlike_post(post_id):
    user_id = request.args.get('user_id') or (request.json and request.json.get('user_id'))
    if not user_id:
        return jsonify({"error": "user_id manquant"}), 400
    like = Like.query.filter_by(user_id=user_id, content_type='post', content_id=post_id).first()
    if not like:
        return jsonify({"message": "Like non trouvé"}), 404
    db.session.delete(like)
    db.session.commit()
    return jsonify({"message": "Like supprimé"}), 200
