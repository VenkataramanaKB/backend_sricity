from flask import Blueprint, request, jsonify, send_file
from .models import create_room, add_voice_note, store_transcript_pdf, mongo, check_user_status, users_collection, rooms_collection
from .services import transcribe_audio, generate_documents, save_as_pdf
from flask_jwt_extended import jwt_required, get_jwt_identity
from .models import create_user, find_user_by_email, verify_password
from flask_jwt_extended import create_access_token
import qrcode
import base64
from io import BytesIO
import uuid
import os
from werkzeug.utils import secure_filename

routes = Blueprint("routes", __name__)
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a"}

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@routes.route("/register", methods=["POST"])
def register():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    role = data.get("role")

    if find_user_by_email(email):
        return jsonify({"error": "User already exists"}), 400

    create_user(email, password, role)
    return jsonify({"message": "User registered successfully"}), 201

@routes.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not verify_password(email, password):
        return jsonify({"error": "Invalid credentials"}), 401

    access_token = create_access_token(identity=email)
    return jsonify({"token": access_token})

@routes.route("/session", methods=["GET", "POST"])
def session():
    if request.method == "POST":
        data = request.get_json()
        if data and 'user' in data:
            email = data['user']['emailAddresses'][0]['emailAddress']
            user_exists, is_admin, is_approved = check_user_status(email)
            return jsonify({
                'message': 'Login successful' if is_approved else 'User on waitlist',
                'Login': is_approved,
                'isAdmin': bool(is_admin)
            })
    return jsonify({'message': 'Login failed ', 'Login': False, 'isAdmin': False})

@routes.route("/users", methods=["GET"])
def get_users():
    users = list(users_collection.find())
    for user in users:
        user['_id'] = str(user['_id'])
    return jsonify(users)

@routes.route("/create-room", methods=["POST"])
def create_room_route():
    rooms_collection = mongo.db.rooms  # Fetch dynamically to avoid 'NoneType' error
    if rooms_collection is None:
        return jsonify({'error': 'Database not initialized'}), 500
    
    data = request.get_json()
    email = data.get('session')
    room_name = data.get('roomName')

    if not email or not room_name:
        return jsonify({'error': 'Missing required fields'}), 400

    room_id = str(uuid.uuid4())
    qr = qrcode.make(room_id)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    room_data = {
        "roomID": room_id,
        "roomName": room_name,
        "email": email,
        "qrCode": qr_base64
    }
    
    rooms_collection.insert_one(room_data)  # Ensure rooms_collection is not None
    return jsonify({'message': 'Room created successfully', 'roomID': room_id, 'qrCode': qr_base64})

@routes.route("/users/<email>", methods=["PUT"])
def update_user(email):
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    update_data = {}
    if 'isApproved' in data:
        update_data['isApproved'] = data['isApproved']
    if 'isAdmin' in data:
        update_data['isAdmin'] = data['isAdmin']
        
    if not update_data:
        return jsonify({'error': 'No valid fields to update'}), 400
    
    result = users_collection.update_one(
        {"email": email},
        {"$set": update_data}
    )
    
    if result.modified_count:
        return jsonify({'message': 'User updated successfully'})
    return jsonify({'error': 'User not found'}), 404

@routes.route("/upload_audio", methods=["POST"])
@jwt_required()
def upload_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400

    file = request.files["audio"]
    room_id = request.form.get("room_id")

    if not room_id:
        return jsonify({"error": "Missing room_id"}), 400

    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file format"}), 400

    # Save the file securely
    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    try:
        file.save(file_path)
    except Exception as e:
        return jsonify({"error": f"Error saving file: {e}"}), 500

    # Check if the room exists
    room = mongo.db.rooms.find_one({"roomID": room_id})  # Ensure this matches the field name in MongoDB
    if not room:
        return jsonify({"error": "Room not found"}), 404

    # Store in MongoDB
    add_voice_note(room_id, file_path, get_jwt_identity())

    # Send for transcription
    transcript = transcribe_audio(room_id)

    return jsonify({"message": "Audio file uploaded successfully", "file_path": file_path, "transcript": transcript})
@routes.route("/get_transcript_pdf/<room_id>", methods=["GET"])
@jwt_required()
def get_transcript_pdf(room_id):
    room = mongo.db.rooms.find_one({"room_id": room_id})
    if room and room.get("transcript_pdf"):
        return send_file(room["transcript_pdf"], as_attachment=True)
    return jsonify({"error": "Transcript not found"}), 404