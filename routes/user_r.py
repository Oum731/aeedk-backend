from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, send_from_directory, url_for, make_response, redirect
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from flask_mail import Message
from app import db, mail
from models.user import User
import os
import uuid
import re
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from PIL import Image
import traceback

FRONTEND_URL = "https://aeedk-frontend.onrender.com"
EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_AVATAR_SIZE = 2 * 1024 * 1024

user_bp = Blueprint('user', __name__, url_prefix='/api/user')
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "media", "avatars")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_avatar(file):
    if not file or not allowed_file(file.filename):
        return None
    
    file.seek(0, os.SEEK_END)
    if file.tell() > MAX_AVATAR_SIZE:
        return None
    file.seek(0)

    temp_filename = f"tmp_{uuid.uuid4()}_{secure_filename(file.filename)}"
    temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)
    file.save(temp_path)

    try:
        img = Image.open(temp_path).convert("RGBA")
        unique_filename = f"{uuid.uuid4()}_avatar.png"
        save_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        img.save(save_path, "PNG")
        return f"avatars/{unique_filename}"
    except Exception:
        return None
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@user_bp.route('/avatar/<path:filename>')
def get_avatar(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@user_bp.route('/register', methods=['POST'])
def register():
    data = request.form.to_dict() if request.form else (request.json or {})
    
    required_fields = ['username', 'email', 'password', 'first_name', 'last_name', 
                     'birth_date', 'sub_prefecture', 'village', 'phone']
    if not all(field in data and data[field] for field in required_fields):
        return jsonify({"error": "Champs manquants"}), 400

    if not re.match(EMAIL_REGEX, data['email']):
        return jsonify({"error": "Email invalide"}), 400

    if User.query.filter(or_(User.email == data['email'], User.username == data['username'])).first():
        return jsonify({"error": "Utilisateur déjà existant"}), 409

    try:
        birth_date = datetime.strptime(data['birth_date'], "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Format de date invalide (YYYY-MM-DD)"}), 400

    avatar_path = process_avatar(request.files.get('avatar')) if 'avatar' in request.files else "avatars/avatar.jpeg"
    if avatar_path is None:
        return jsonify({"error": "Erreur de traitement de l'avatar"}), 400

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
        confirmation_token=str(uuid.uuid4()))
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()

    verify_url = f"{FRONTEND_URL}/verify-email?token={user.confirmation_token}"
    msg = Message(
        subject="Confirmation de votre inscription",
        sender=os.getenv('MAIL_USERNAME'),
        recipients=[user.email],
        body=f"Confirmez votre email: {verify_url}",
        html=f'<p><a href="{verify_url}">Confirmez votre email</a></p>')
    
    try:
        mail.send(msg)
        return jsonify({"message": "Inscription réussie. Vérifiez votre email."}), 201
    except Exception as e:
        return jsonify({"error": "Erreur d'envoi d'email", "details": str(e)}), 500

@user_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'identifier' not in data or 'password' not in data:
        return jsonify({"error": "Identifiant et mot de passe requis"}), 400

    user = User.query.filter(
        (User.email == data['identifier']) | (User.username == data['identifier'])
    ).first()

    if not user or not user.check_password(data['password']):
        return jsonify({"error": "Identifiants invalides"}), 401

    if not user.confirmed:
        return jsonify({"error": "Email non confirmé"}), 403

    token = create_access_token(identity=user.id)
    return jsonify({"token": token, "user": user.to_dict()}), 200

@user_bp.route('/verify/<token>')
def verify_email(token):
    user = User.query.filter_by(confirmation_token=token).first()
    if not user:
        return redirect(f"{FRONTEND_URL}/login?verified=fail")
    
    user.confirmed = True
    user.confirmation_token = None
    db.session.commit()
    return redirect(f"{FRONTEND_URL}/login?verified=success")

@user_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.json.get('email')
    if not email:
        return jsonify({"error": "Email requis"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "Email non trouvé"}), 404

    user.reset_token = str(uuid.uuid4())
    user.reset_token_expiration = datetime.utcnow() + timedelta(hours=1)
    db.session.commit()

    reset_url = f"{FRONTEND_URL}/reset-password?token={user.reset_token}"
    msg = Message(
        subject="Réinitialisation du mot de passe",
        sender=os.getenv('MAIL_USERNAME'),
        recipients=[user.email],
        html=f'<p><a href="{reset_url}">Réinitialiser votre mot de passe</a></p>')
    
    mail.send(msg)
    return jsonify({"message": "Email envoyé"}), 200

@user_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or user.reset_token_expiration < datetime.utcnow():
        return redirect(f"{FRONTEND_URL}/login?reset=fail")

    if request.method == 'GET':
        return redirect(f"{FRONTEND_URL}/reset-password?token={token}")

    password = request.json.get('password')
    if not password:
        return jsonify({"error": "Mot de passe requis"}), 400

    user.set_password(password)
    user.reset_token = None
    user.reset_token_expiration = None
    db.session.commit()
    
    return jsonify({"message": "Mot de passe mis à jour"}), 200

@user_bp.route('/<int:user_id>', methods=['GET', 'POST', 'PUT'])
@jwt_required()
def user_profile(user_id):
    current_user_id = get_jwt_identity()
    if user_id != current_user_id and not User.query.get(current_user_id).role == 'admin':
        return jsonify({"error": "Accès non autorisé"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404

    if request.method == 'GET':
        return jsonify(user.to_dict())

    try:
        data = request.form if request.content_type == 'multipart/form-data' else request.json
        data = data.to_dict() if hasattr(data, 'to_dict') else data or {}

        if 'avatar' in request.files:
            avatar_path = process_avatar(request.files['avatar'])
            if avatar_path:
                user.avatar = avatar_path

        if 'username' in data and data['username'] != user.username:
            if User.query.filter(User.username == data['username']).first():
                return jsonify({"error": "Nom d'utilisateur déjà pris"}), 409
            user.username = data['username']

        if 'email' in data and data['email'] != user.email:
            if User.query.filter(User.email == data['email']).first():
                return jsonify({"error": "Email déjà utilisé"}), 409
            user.email = data['email']

        for field in ['first_name', 'last_name', 'sub_prefecture', 'village', 'phone']:
            if field in data:
                setattr(user, field, data[field])

        if 'birth_date' in data:
            try:
                user.birth_date = datetime.strptime(data['birth_date'], "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "Format de date invalide"}), 400

        db.session.commit()
        return jsonify({"message": "Profil mis à jour", "user": user.to_dict()})

    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"error": "Erreur serveur", "details": str(e)}), 500

@user_bp.route('/admin/users', methods=['GET'])
@jwt_required()
def admin_users():
    if not User.query.get(get_jwt_identity()).role == 'admin':
        return jsonify({"error": "Accès refusé"}), 403

    users = [u.to_dict() for u in User.query.all()]
    return jsonify({"users": users, "total": len(users)})

@user_bp.route('/admin/users/<int:user_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def admin_user_actions(user_id):
    admin = User.query.get(get_jwt_identity())
    if not admin or admin.role != 'admin':
        return jsonify({"error": "Accès refusé"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404

    if request.method == 'PUT':
        data = request.json
        for field in ['username', 'email', 'first_name', 'last_name', 'role', 'confirmed']:
            if field in data:
                setattr(user, field, data[field])
        db.session.commit()
        return jsonify({"message": "Utilisateur mis à jour"})

    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Utilisateur supprimé"})