from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models.notification import Notification
from models.user import User

notification_bp = Blueprint('notification', __name__, url_prefix='/api/notifications')

@notification_bp.route('/', methods=['GET'])
@jwt_required()
def get_notifications():
    current_user_id = get_jwt_identity()
    notifications = Notification.query.filter_by(recipient_id=current_user_id).order_by(Notification.created_at.desc()).all()
    return jsonify([n.to_dict() for n in notifications]), 200

@notification_bp.route('/<int:notif_id>/read', methods=['POST'])
@jwt_required()
def mark_notification_read(notif_id):
    current_user_id = get_jwt_identity()
    notification = Notification.query.get(notif_id)
    if not notification or notification.recipient_id != current_user_id:
        return jsonify({"error": "Notification non trouvée ou accès refusé"}), 404
    notification.is_read = True
    db.session.commit()
    return jsonify({"message": "Notification marquée comme lue"}), 200

@notification_bp.route('/', methods=['POST'])
@jwt_required()
def create_notification():
    # Cette route peut être appelée par un admin ou un système pour créer une notif
    data = request.get_json() or {}
    recipient_id = data.get('recipient_id')
    message = data.get('message')

    if not recipient_id or not message:
        return jsonify({"error": "recipient_id et message requis"}), 400

    user = User.query.get(recipient_id)
    if not user:
        return jsonify({"error": "Utilisateur destinataire non trouvé"}), 404

    notif = Notification(recipient_id=recipient_id, message=message)
    db.session.add(notif)
    db.session.commit()

    return jsonify(notif.to_dict()), 201

@notification_bp.route('/unread_count', methods=['GET'])
@jwt_required()
def get_unread_notifications_count():
    current_user_id = get_jwt_identity()
    count = Notification.query.filter_by(recipient_id=current_user_id, is_read=False).count()
    return jsonify({"unread_count": count}), 200

