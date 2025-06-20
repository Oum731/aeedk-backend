from flask import Blueprint, request, jsonify
from flask_mail import Message
from app import mail
import re
import os

contact_bp = Blueprint('contact_bp', __name__, url_prefix='/api/contact')

EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'

@contact_bp.route('/send/', methods=['POST'])
def send_contact_email():
    data = request.json

    required_fields = ['name', 'email', 'subject', 'message']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Champs manquants"}), 400

    if not re.match(EMAIL_REGEX, data['email']):
        return jsonify({"error": "Email invalide"}), 400

    try:
        msg = Message(
            subject=f"Message de contact : {data['subject']}",
            sender=data['email'],
            recipients=[os.getenv('CONTACT_RECEIVER_EMAIL')],
            body=(
                f"Nom : {data['name']}\n"
                f"Email : {data['email']}\n\n"
                f"Message :\n{data['message']}"
            )
        )
        mail.send(msg)
        return jsonify({"message": "Email envoyé avec succès"}), 200
    except Exception as e:
        return jsonify({"error": f"Erreur lors de l'envoi de l'email : {str(e)}"}), 500
