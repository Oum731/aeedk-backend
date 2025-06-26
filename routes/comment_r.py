from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from app import db
from models.comment import Comment
from models.notification import Notification
from models.user import User
from models.post import Post

comment_bp = Blueprint('comment_bp', __name__, url_prefix='/api/comments')


@comment_bp.route('/', methods=['GET'])
@cross_origin()
def get_all_comments():
    comments = Comment.query.order_by(Comment.created_at.desc()).all()
    return jsonify({"comments": [c.to_dict() for c in comments]}), 200


@comment_bp.route('/', methods=['POST'])
@cross_origin()
def create_comment():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "JSON invalide"}), 400

    if not data:
        return jsonify({"error": "Aucune donnée reçue"}), 400

    content = data.get('content')
    post_id = data.get('post_id')
    parent_comment_id = data.get('parent_comment_id')
    user_id = data.get('user_id')

    if not content or not post_id or not user_id:
        return jsonify({"error": "Le contenu, l'id du post et l'id utilisateur sont requis"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404

    post = Post.query.get(post_id)
    if not post:
        return jsonify({"error": "Post non trouvé"}), 404

    if parent_comment_id:
        parent_comment = Comment.query.get(parent_comment_id)
        if not parent_comment or parent_comment.post_id != post_id:
            return jsonify({"error": "Commentaire parent invalide"}), 400

    comment = Comment(
        content=content,
        user_id=user_id,
        post_id=post_id,
        parent_comment_id=parent_comment_id
    )
    db.session.add(comment)
    db.session.commit()

    if post.author_id != user_id:
        notif = Notification(
            recipient_id=post.author_id,
            message=f"Nouveau commentaire sur votre post : {post.title}"
        )
        db.session.add(notif)
        db.session.commit()

    return jsonify({
        "message": "Commentaire créé avec succès",
        "comment": comment.to_dict()
    }), 201



@comment_bp.route('/<int:comment_id>', methods=['GET'])
@cross_origin()
def get_comment(comment_id):
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"error": "Commentaire non trouvé"}), 404
    return jsonify(comment.to_dict()), 200


@comment_bp.route('/<int:comment_id>', methods=['PUT'])
@cross_origin()
def update_comment(comment_id):
    data = request.get_json()
    user_id = data.get('user_id')
    content = data.get('content')

    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"error": "Commentaire non trouvé"}), 404

    if comment.user_id != user_id:
        return jsonify({"error": "Accès refusé"}), 403

    if not content:
        return jsonify({"error": "Le contenu est requis"}), 400

    comment.content = content
    db.session.commit()
    return jsonify({"message": "Commentaire mis à jour", "comment": comment.to_dict()}), 200


@comment_bp.route('/<int:comment_id>', methods=['DELETE'])
@cross_origin()
def delete_comment(comment_id):
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "Utilisateur requis"}), 400

    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"error": "Commentaire non trouvé"}), 404

    user = User.query.get(user_id)
    if comment.user_id != user_id and (not user or user.role != 'admin'):
        return jsonify({"error": "Accès refusé"}), 403

    db.session.delete(comment)
    db.session.commit()
    return jsonify({"message": "Commentaire supprimé"}), 200


@comment_bp.route('/post/<int:post_id>', methods=['GET'])
@cross_origin()
def list_comments(post_id):
    post = Post.query.get(post_id)
    if not post:
        return jsonify({"error": "Post non trouvé"}), 404

    parent_comments = Comment.query.filter_by(post_id=post_id, parent_comment_id=None)\
        .order_by(Comment.created_at.desc()).all()

    def recursive_count(comments):
        total = 0
        for c in comments:
            total += 1
            total += recursive_count(c.children)
        return total

    total_comments = recursive_count(parent_comments)
    comments_dict = [comment.to_dict() for comment in parent_comments]
    return jsonify({
        "comments": comments_dict,
        "total": total_comments,
    }), 200
