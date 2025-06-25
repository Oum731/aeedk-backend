from datetime import datetime
import cloudinary
from flask import Blueprint, jsonify, request
from flask_cors import cross_origin 
from app import db
from models.like import Like
from models.post import Post
from models.user import User
import os
import uuid

post_bp = Blueprint('post_bp', __name__, url_prefix='/api/posts')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_admin(user_id):
    user = User.query.get(user_id)
    return user and user.role == 'admin'

@post_bp.route('', methods=['POST'])
@cross_origin()
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
            ext = file.filename.rsplit('.', 1)[1].lower()
            # Upload sur Cloudinary
            result = cloudinary.uploader.upload(
                file,
                folder="posts_aeedk",
                public_id=f"{uuid.uuid4()}_post",
                resource_type="video" if ext in {'mp4', 'webm'} else "image"
            )
            media_url = result["secure_url"]
            media_type = 'video' if ext in {'mp4', 'webm'} else 'image'
            medias.append({
                "url": media_url,
                "filename": result.get("original_filename") + '.' + ext,
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
@cross_origin()
def get_posts():
    try:
        posts = Post.query.order_by(Post.created_at.desc()).all()
        return jsonify([post.to_dict() for post in posts]), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Erreur serveur", "details": str(e)}), 500

@post_bp.route('/<int:post_id>', methods=['GET'])
@cross_origin()
def get_post(post_id):
    post = Post.query.get(post_id)
    if not post:
        return jsonify({"error": "Post non trouvé"}), 404
    return jsonify(post.to_dict(include_comments=True)), 200

@post_bp.route('/<int:post_id>', methods=['PUT'])
@cross_origin()
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
                ext = file.filename.rsplit('.', 1)[1].lower()
                result = cloudinary.uploader.upload(
                    file,
                    folder="posts_aeedk",
                    public_id=f"{uuid.uuid4()}_post",
                    resource_type="video" if ext in {'mp4', 'webm'} else "image"
                )
                media_url = result["secure_url"]
                media_type = 'video' if ext in {'mp4', 'webm'} else 'image'
                medias.append({
                    "url": media_url,
                    "filename": result.get("original_filename") + '.' + ext,
                    "type": media_type,
                })
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
@cross_origin()
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
@cross_origin()
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
@cross_origin()
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
