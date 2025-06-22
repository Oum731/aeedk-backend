from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, send_from_directory, url_for, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_mail import Message
from app import db, mail
from models.user import User
import os
import uuid
import re
from werkzeug.utils import secure_filename
from sqlalchemy import or_

user_bp = Blueprint('user', __name__, url_prefix='/api/user')

EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "media", "avatars")
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
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
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

    try:
        mail.send(msg)
        return jsonify({"message": "Inscription réussie. Vérifiez votre email pour confirmer votre compte."}), 201
    except Exception as e:
        return jsonify({"error": "Erreur lors de l'envoi de l'email", "details": str(e)}), 500

# Connexion
@user_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    identifier = data.get('identifier')
    password = data.get('password')
    if not identifier or not password:
        return jsonify({"error": "Identifiant et mot de passe requis"}), 400

    user = User.query.filter(
        (User.email == identifier) | (User.username == identifier)
    ).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Identifiants invalides"}), 401
    if not user.confirmed:
        return jsonify({"error": "Veuillez confirmer votre email avant de vous connecter."}), 403

    from flask_jwt_extended import create_access_token
    token = create_access_token(identity=user.id)
    return jsonify({"token": token, "user": user.to_dict()}), 200

@user_bp.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    user = User.query.filter_by(confirmation_token=token).first()
    if not user:
        return jsonify({"error": "Token invalide ou expiré"}), 404
    user.confirmed = True
    user.confirmation_token = None
    db.session.commit()
    return jsonify({"message": "Email confirmé avec succès. Vous pouvez vous connecter."})

@user_bp.route('/forgot-password', methods=['POST'])
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
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": f"Utilisateur avec ID {user_id} non trouvé"}), 404
    return jsonify(user.to_dict()), 200

@user_bp.route('/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return make_response(jsonify({"error": "Utilisateur non trouvé"}), 404)
    try:
        if request.content_type and 'multipart/form-data' in request.content_type:
            data = request.form.to_dict()
            if 'avatar' in request.files:
                avatar = request.files['avatar']
                if avatar and allowed_file(avatar.filename):
                    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                    filename = secure_filename(avatar.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    avatar.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                    user.avatar = f"avatars/{unique_filename}"
        else:
            data = request.get_json() or {}

        if 'username' in data and data['username'] != user.username:
            if User.query.filter(User.username == data['username'], User.id != user.id).first():
                return make_response(jsonify({"error": "Nom d'utilisateur déjà pris"}), 409)
        if 'email' in data and data['email'] != user.email:
            if User.query.filter(User.email == data['email'], User.id != user.id).first():
                return make_response(jsonify({"error": "Email déjà utilisé"}), 409)

        fields = ['first_name', 'last_name', 'sub_prefecture', 'village', 'phone', 'email', 'username', 'role']
        for field in fields:
            if field in data:
                setattr(user, field, data[field])

        if 'confirmed' in data:
            val = data['confirmed']
            if isinstance(val, bool):
                user.confirmed = val
            elif isinstance(val, str):
                user.confirmed = val.lower() in ['true', '1', 'yes']

        if 'birth_date' in data:
            raw = data['birth_date']
            if isinstance(raw, str) and raw.strip():
                try:
                    user.birth_date = datetime.strptime(raw.strip(), "%Y-%m-%d").date()
                except ValueError:
                    return make_response(jsonify({"error": "Format de date invalide (YYYY-MM-DD)"}), 422)
            elif raw in [None, ""]:
                user.birth_date = None

        db.session.commit()
        return jsonify({
            "message": "Profil mis à jour",
            "user": user.to_dict(),
            "avatar_url": url_for('user.get_avatar', filename=os.path.basename(user.avatar), _external=True)
        }), 200

    except Exception as e:
        return make_response(jsonify({"error": "Erreur interne", "details": str(e)}), 500)


def safe_int(val, default=1):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

@user_bp.route('/admin/users', methods=['GET'])
@jwt_required()
def admin_get_all_users():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user or user.role != 'admin':
        return jsonify({"error": "Accès refusé"}), 403

    page = safe_int(request.args.get('page', 1), 1)
    per_page = safe_int(request.args.get('per_page', 100), 100)
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
def admin_update_user(user_id):
    current_user_id = get_jwt_identity()
    user_admin = User.query.get(current_user_id)
    if not user_admin or user_admin.role != 'admin':
        return jsonify({"error": "Accès refusé"}), 403

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
def admin_delete_user(user_id):
    current_user_id = get_jwt_identity()
    user_admin = User.query.get(current_user_id)
    if not user_admin or user_admin.role != 'admin':
        return jsonify({"error": "Accès refusé"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Utilisateur supprimé"}), 200
