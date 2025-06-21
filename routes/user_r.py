from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, send_from_directory, url_for
from flask_jwt_extended import jwt_required
from flask_mail import Message
from flask_cors import cross_origin 
from app import db, mail
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
@cross_origin()
def get_avatar(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@user_bp.route('/register', methods=['POST'])
@cross_origin()
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
        role='membre',
        confirmation_token=str(uuid.uuid4())
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()

    verify_url = url_for('user.verify_email', token=user.confirmation_token, _external=True)
    msg = Message(
        subject="Confirmation de votre inscription",
        sender=os.getenv('MAIL_USERNAME'),
        recipients=[user.email]
    )
    msg.body = f"Cliquez sur le lien suivant pour confirmer votre compte : {verify_url}"
    msg.html = f'<p>Merci pour votre inscription.</p><p><a href="{verify_url}">Confirmez votre adresse email</a></p>'
    mail.send(msg)

    return jsonify({"message": "Inscription réussie. Vérifiez votre email pour confirmer votre compte."}), 201


@user_bp.route('/verify/<token>', methods=['GET'])
@cross_origin()
def verify_email(token):
    user = User.query.filter_by(confirmation_token=token).first()
    if not user:
        return jsonify({"error": "Token invalide ou expiré"}), 404
    user.confirmed = True
    user.confirmation_token = None
    db.session.commit()
    return jsonify({"message": "Email confirmé avec succès. Vous pouvez vous connecter."})


@user_bp.route('/forgot-password', methods=['POST'])
@cross_origin()
def forgot_password():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({"error": "Email requis"}), 400
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "Aucun utilisateur trouvé avec cet email"}), 404
    token = str(uuid.uuid4())
    user.reset_token = token
    user.reset_token_expiration = datetime.utcnow() + timedelta(hours=1)
    db.session.commit()

    reset_url = url_for('user.reset_password', token=token, _external=True)
    msg = Message(
        subject="Réinitialisation du mot de passe",
        sender=os.getenv('MAIL_USERNAME'),
        recipients=[email]
    )
    msg.body = f"Cliquez ici pour réinitialiser votre mot de passe : {reset_url}"
    msg.html = f'<p><a href="{reset_url}">Réinitialisez votre mot de passe</a></p>'
    mail.send(msg)

    return jsonify({"message": "Email de réinitialisation envoyé"})


@user_bp.route('/reset-password/<token>', methods=['POST'])
@cross_origin()
def reset_password(token):
    data = request.get_json()
    password = data.get('password')
    if not password:
        return jsonify({"error": "Mot de passe requis"}), 400
    user = User.query.filter_by(reset_token=token).first()
    if not user or user.reset_token_expiration < datetime.utcnow():
        return jsonify({"error": "Token invalide ou expiré"}), 400
    user.set_password(password)
    user.reset_token = None
    user.reset_token_expiration = None
    db.session.commit()
    return jsonify({"message": "Mot de passe réinitialisé avec succès"})


@user_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
@cross_origin()
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": f"Utilisateur avec ID {user_id} non trouvé"}), 404
    return jsonify(user.to_dict()), 200


@user_bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required()
@cross_origin()
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
@jwt_required()
@cross_origin()
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
@jwt_required()
@cross_origin()
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
@jwt_required()
@cross_origin()
def admin_delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Utilisateur supprimé"}), 200
