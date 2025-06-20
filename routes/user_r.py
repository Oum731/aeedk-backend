from datetime import datetime
from flask import Blueprint, jsonify, request, send_from_directory
from app import db
from models.user import User
import re
import os
import uuid
from werkzeug.utils import secure_filename
from sqlalchemy import or_

user_bp = Blueprint('user', __name__, url_prefix='/api/user')

EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'
UPLOAD_FOLDER = os.path.join(os.getcwd(), "media", "avatars")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@user_bp.route('/avatar/<path:filename>')
def get_avatar(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@user_bp.route('/register', methods=['POST'])
def register():
    data = request.form.to_dict() if request.form else (request.json or {})
    required_fields = [
        'username', 'email', 'password', 'first_name', 'last_name', 'birth_date',
        'sub_prefecture', 'village', 'phone'
    ]
    if not all(field in data and data[field] for field in required_fields):
        return jsonify({"error": "Champs manquants"}), 400
    if not re.match(EMAIL_REGEX, data['email']):
        return jsonify({"error": "Email invalide"}), 400
    if User.query.filter(or_(User.email == data['email'], User.username == data['username'])).first():
        return jsonify({"error": "Utilisateur déjà existant"}), 409
    try:
        birth_date = datetime.strptime(data['birth_date'], "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Format de birth_date invalide, attendu YYYY-MM-DD"}), 400
    avatar_path = "avatars/avatar.jpeg"
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
            avatar_path = f"avatars/{unique_filename}"
    user = User(
        username=data['username'],
        email=data['email'],
        first_name=data['first_name'],
        last_name=data['last_name'],
        birth_date=birth_date,
        sub_prefecture=data['sub_prefecture'],
        village=data['village'],
        phone=data['phone'],
        avatar=avatar_path,
        role='membre'
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "Utilisateur créé avec succès. Vous pouvez vous connecter."}), 201

@user_bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": f"Utilisateur avec ID {user_id} non trouvé"}), 404
    return jsonify(user.to_dict()), 200

@user_bp.route('/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404
    if request.content_type and 'multipart/form-data' in request.content_type:
        data = request.form.to_dict()
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                user.avatar = f"avatars/{unique_filename}"
    else:
        data = request.json or {}
    fields = ['first_name', 'last_name', 'sub_prefecture', 'village', 'phone', 'email', 'username', 'role', 'confirmed']
    for field in fields:
        if field in data:
            setattr(user, field, data[field])
    if 'birth_date' in data:
        try:
            user.birth_date = datetime.strptime(data['birth_date'], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Format de date invalide (YYYY-MM-DD)"}), 400
    db.session.commit()
    return jsonify({"message": "Profil mis à jour", "user": user.to_dict()}), 200

@user_bp.route('/admin/users', methods=['GET'])
def admin_get_all_users():
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=100, type=int)
    role = request.args.get('role', default=None, type=str)
    query = User.query
    if role:
        query = query.filter_by(role=role)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    users = pagination.items
    return jsonify({
        "users": [user.to_dict() for user in users],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages
    }), 200

@user_bp.route('/admin/users/<int:user_id>', methods=['PUT'])
def admin_update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404
    data = request.json or {}
    for field in ['username', 'email', 'first_name', 'last_name', 'role', 'confirmed', 'sub_prefecture', 'village', 'avatar']:
        if field in data:
            setattr(user, field, data[field])
    db.session.commit()
    return jsonify({"message": "Utilisateur mis à jour", "user": user.to_dict()}), 200

@user_bp.route('/admin/users/<int:user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Utilisateur supprimé"}), 200
