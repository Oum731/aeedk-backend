from flask import Blueprint, request, jsonify
from app import db
from models.like import Like
from models.post import Post
from models.comment import Comment

like_bp = Blueprint('like_bp', __name__, url_prefix='/api/likes')

def check_existence(content_type, content_id):
    if content_type == 'post':
        return Post.query.get(content_id)
    elif content_type == 'comment':
        return Comment.query.get(content_id)
    return None

@like_bp.route('/<string:content_type>/<int:content_id>', methods=['POST'])
def like_or_dislike(content_type, content_id):
    data = request.json or {}
    user_id = data.get('user_id')
    is_like = data.get('is_like')

    if not user_id:
        return jsonify({"error": "user_id requis"}), 400

    if content_type not in ['post', 'comment']:
        return jsonify({"error": "Type de contenu invalide"}), 400

    if is_like is None or not isinstance(is_like, bool):
        return jsonify({"error": "Le champ 'is_like' (bool) est requis"}), 400

    if not check_existence(content_type, content_id):
        return jsonify({"error": f"{content_type.capitalize()} non trouvé"}), 404

    existing = Like.query.filter_by(user_id=user_id, content_type=content_type, content_id=content_id).first()

    if existing:
        if existing.is_like == is_like:
            db.session.delete(existing)
            db.session.commit()
            return jsonify({"message": f"{content_type.capitalize()} { 'like' if is_like else 'dislike' } supprimé"}), 200
        else:
            existing.is_like = is_like
            db.session.commit()
            return jsonify({"message": f"{content_type.capitalize()} changé en { 'like' if is_like else 'dislike' }"}), 200
    else:
        new_like = Like(user_id=user_id, content_type=content_type, content_id=content_id, is_like=is_like)
        db.session.add(new_like)
        db.session.commit()
        return jsonify({"message": f"{content_type.capitalize()} { 'liké' if is_like else 'disliké' }"}), 201

@like_bp.route('/<string:content_type>/<int:content_id>', methods=['DELETE'])
def delete_like(content_type, content_id):
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id requis"}), 400

    like = Like.query.filter_by(user_id=user_id, content_type=content_type, content_id=content_id).first()
    if not like:
        return jsonify({"error": "Interaction non trouvée"}), 404

    db.session.delete(like)
    db.session.commit()
    return jsonify({"message": "Interaction supprimée"}), 200

@like_bp.route('/<string:content_type>/<int:content_id>', methods=['GET'])
def get_likes_info(content_type, content_id):
    
    user_id = request.args.get("user_id", type=int)
    if content_type not in ['post', 'comment']:
        return jsonify({"error": "Type de contenu invalide"}), 400

    likes_count = Like.query.filter_by(content_type=content_type, content_id=content_id, is_like=True).count()
    dislikes_count = Like.query.filter_by(content_type=content_type, content_id=content_id, is_like=False).count()

    user_vote = None
    if user_id:
        like = Like.query.filter_by(user_id=user_id, content_type=content_type, content_id=content_id).first()
        if like:
            user_vote = 1 if like.is_like else -1

    return jsonify({
        "likes": likes_count,
        "dislikes": dislikes_count,
        "user_vote": user_vote
    }), 200
