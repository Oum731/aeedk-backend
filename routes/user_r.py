from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, send_from_directory, url_for, make_response, redirect
from flask_cors import cross_origin
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

FRONTEND_URL = "https://aeedk-frontend.onrender.com"
user_bp = Blueprint('user', __name__, url_prefix='/api/user')

EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "media", "avatars")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_AVATAR_SIZE = 2 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@user_bp.route('/avatar/<filename>')
def get_avatar(filename):
    safe_name = secure_filename(filename)
    full_path = os.path.join(UPLOAD_FOLDER, safe_name)
    if not os.path.exists(full_path):
        return send_from_directory(UPLOAD_FOLDER, "avatar.jpeg")
    response = make_response(send_from_directory(UPLOAD_FOLDER, safe_name))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response

@user_bp.route('/register', methods=['POST'])
@cross_origin(origin=FRONTEND_URL, supports_credentials=True)
def register():
    data = request.form.to_dict() if request.form else (request.get_json() or {})
    required_fields = [
        'username', 'email', 'password', 'first_name', 'last_name',
        'birth_date', 'sub_prefecture', 'village', 'phone'
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
    avatar_path = "avatar.jpeg"
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and allowed_file(file.filename):
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            if file_size > MAX_AVATAR_SIZE:
                return jsonify({"error": "Avatar trop volumineux (max 2 Mo)"}), 413
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            temp_filename = secure_filename(file.filename)
            temp_path = os.path.join(UPLOAD_FOLDER, f"tmp_{uuid.uuid4()}_{temp_filename}")
            file.save(temp_path)
            try:
                img = Image.open(temp_path).convert("RGBA")
                unique_filename = f"{uuid.uuid4()}_avatar.png"
                save_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                img.save(save_path, "PNG")
                avatar_path = unique_filename
            except Exception:
                return jsonify({"error": "Impossible de traiter l'avatar"}), 400
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        else:
            return jsonify({"error": "Format d'avatar non autorisé"}), 400
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
    sender = str(os.getenv('MAIL_USERNAME'))
    if not sender or not isinstance(sender, str):
        return jsonify({"error": "Configuration email invalide (MAIL_USERNAME manquant)"}), 500
    recipient = str(user.email)
    msg = Message(
        subject="Confirmation de votre inscription",
        sender=sender,
        recipients=[recipient]
    )
    msg.body = f"Cliquez sur le lien suivant pour confirmer votre compte : {verify_url}"
    msg.html = f'<p>Merci pour votre inscription.</p><p><a href="{verify_url}">Confirmez votre adresse email</a></p>'
    try:
        mail.send(msg)
        return jsonify({"message": "Inscription réussie. Vérifiez votre email."}), 201
    except Exception as e:
        return jsonify({"error": "Erreur lors de l'envoi de l'email", "details": str(e)}), 500

@user_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    identifier = data.get('identifier')
    password = data.get('password')
    if not identifier or not password:
        return jsonify({"error": "Identifiant et mot de passe requis"}), 400
    user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Identifiants invalides"}), 401
    if not user.confirmed:
        return jsonify({"error": "Veuillez confirmer votre email."}), 403
    token = create_access_token(identity=user.id)
    return jsonify({"token": token, "user": user.to_dict()}), 200

@user_bp.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    user = User.query.filter_by(confirmation_token=token).first()
    if not user:
        return redirect(f"{FRONTEND_URL}/login?verified=fail", code=302)
    user.confirmed = True
    user.confirmation_token = None
    db.session.commit()
    return redirect(f"{FRONTEND_URL}/login?verified=success", code=302)

@user_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json() or {}
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
    reset_url = url_for('user.reset_password_get', token=token, _external=True)
    sender = str(os.getenv('MAIL_USERNAME'))
    if not sender or not isinstance(sender, str):
        return jsonify({"error": "Configuration email invalide (MAIL_USERNAME manquant)"}), 500
    recipient = str(email)
    msg = Message(
        subject="Réinitialisation du mot de passe",
        sender=sender,
        recipients=[recipient]
    )
    msg.body = f"Cliquez ici pour réinitialiser votre mot de passe : {reset_url}"
    msg.html = f'<p><a href="{reset_url}">Réinitialisez votre mot de passe</a></p>'
    try:
        mail.send(msg)
        return jsonify({"message": "Email de réinitialisation envoyé"})
    except Exception as e:
        return jsonify({"error": "Erreur lors de l'envoi de l'email", "details": str(e)}), 500

@user_bp.route('/reset-password/<token>', methods=['GET'])
def reset_password_get(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or user.reset_token_expiration < datetime.utcnow():
        return redirect(f"{FRONTEND_URL}/login?reset=fail", code=302)
    return redirect(f"{FRONTEND_URL}/reset-password?token={token}", code=302)

@user_bp.route('/reset-password/<token>', methods=['POST'])
def reset_password(token):
    data = request.get_json() or {}
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
    return redirect(f"{FRONTEND_URL}/login?reset=success", code=302)

@user_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": f"Utilisateur avec ID {user_id} non trouvé"}), 404
    try:
        d = user.to_dict()
        return jsonify({"user": d}), 200
    except Exception as e:
        return jsonify({"error": "Erreur interne", "details": str(e)}), 500

@user_bp.route('/<int:user_id>', methods=['PUT', 'POST'])
@jwt_required()
def update_user(user_id):
    current_user_id = get_jwt_identity()
    if int(user_id) != int(current_user_id):
        return jsonify({"error": "Accès interdit"}), 403
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404

    try:
        data = {}

        if request.content_type and 'multipart/form-data' in request.content_type:
            data = {k: v for k, v in request.form.items()}
            if 'avatar' in request.files:
                avatar = request.files['avatar']
                if avatar and avatar.filename and allowed_file(avatar.filename):
                    avatar.seek(0, os.SEEK_END)
                    file_size = avatar.tell()
                    avatar.seek(0)
                    if file_size > MAX_AVATAR_SIZE:
                        return jsonify({"error": "Avatar trop volumineux (max 2 Mo)"}), 413
                    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                    temp_filename = secure_filename(avatar.filename)
                    temp_path = os.path.join(UPLOAD_FOLDER, f"tmp_{uuid.uuid4()}_{temp_filename}")
                    avatar.save(temp_path)
                    try:
                        img = Image.open(temp_path).convert("RGBA")
                        unique_filename = f"{uuid.uuid4()}_avatar.png"
                        save_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                        img.save(save_path, "PNG")
                        user.avatar = unique_filename
                    except Exception:
                        return jsonify({"error": "Impossible de traiter l'avatar"}), 400
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                elif avatar and avatar.filename:
                    return jsonify({"error": "Format d'avatar non autorisé"}), 400
        else:
            data = request.get_json(silent=True) or {}

        fields = [
            'username', 'first_name', 'last_name',
            'sub_prefecture', 'village', 'phone'
        ]
        for field in fields:
            if field in data:
                value = data[field]
                if value is not None and str(value).strip() != "":
                    if field == 'username' and value != user.username:
                        if User.query.filter(User.username == value, User.id != user.id).first():
                            return jsonify({"error": "Nom d'utilisateur déjà pris"}), 409
                        user.username = value
                    else:
                        setattr(user, field, value)

        if 'birth_date' in data:
            raw = data['birth_date']
            if isinstance(raw, str) and raw.strip():
                try:
                    user.birth_date = datetime.strptime(raw.strip(), "%Y-%m-%d").date()
                except ValueError:
                    return jsonify({"error": "Format de date invalide (YYYY-MM-DD)"}), 422

        db.session.commit()
        return jsonify({"message": "Profil mis à jour", "user": user.to_dict()}), 200

    except Exception as e:
        return jsonify({"error": "Erreur interne", "details": str(e)}), 500


@user_bp.route('/admin/users', methods=['GET'])
@jwt_required()
def admin_get_all_users():
    current_user_id = get_jwt_identity()
    user_admin = User.query.get(current_user_id)
    if not user_admin or user_admin.role != 'admin':
        return jsonify({"error": "Accès refusé"}), 403
    users = User.query.all()
    out = []
    for u in users:
        try:
            out.append(u.to_dict())
        except Exception as e:
            return jsonify({"error": f"Erreur de serialization sur user {u.id}", "details": str(e)}), 500
    return jsonify({
        "users": out,
        "total": len(out)
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
    data = request.get_json(silent=True) or {}
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
