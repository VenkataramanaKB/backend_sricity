from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash

mongo = PyMongo()

# Collections will be initialized after the app is initialized
users_collection = None
rooms_collection = None

def init_db(app):
    print("Initializing database...")
    global users_collection, rooms_collection
    mongo.init_app(app)

    # Ensure collections are correctly assigned
    users_collection = mongo.db.users
    rooms_collection = mongo.db.rooms

    # Fix the boolean check
    if users_collection is None or rooms_collection is None:
        raise RuntimeError("Database collections are not initialized correctly.")

    print("Database initialized.")
    print(f"Users collection: {users_collection}")
    print(f"Rooms collection: {rooms_collection}")

# User Schema
def create_user(email, password, role):
    hashed_password = generate_password_hash(password)
    users_collection.insert_one({
        "email": email,
        "password": hashed_password,
        "role": role  # "admin" or "doctor"
    })

def find_user_by_email(email):
    return users_collection.find_one({"email": email})

def verify_password(email, password):
    user = find_user_by_email(email)
    return user and check_password_hash(user["password"], password)

def check_user_status(email):
    user = users_collection.find_one({
        "$or": [
            {"email": email},
            {f'"{email}"': "admin"}
        ]
    })
    
    if not user:
        new_user = {
            "email": email,
            "isAdmin": False,
            "isApproved": False
        }
        users_collection.insert_one(new_user)
        return False, False, False
    
    is_admin = (
        user.get('isAdmin', False) or
        user.get('"isAdmin"', '').lower() == 'true'
    )
    
    is_approved = user.get('isApproved', False)
    return True, is_admin, is_approved

# Room Schema
def create_room(room_id, created_by):
    rooms_collection.insert_one({
        "room_id": room_id,
        "created_by": created_by,
        "voice_notes": [],
        "transcript_pdf": None  # Path to saved PDF
    })

def add_voice_note(room_id, file_path, doctor_id):
    rooms_collection.update_one(
        {"room_id": room_id},
        {"$push": {"voice_notes": {"doctor_id": doctor_id, "audio_path": file_path, "processed": False}}}
    )

# Store PDF path
def store_transcript_pdf(room_id, pdf_path):
    rooms_collection.update_one(
        {"room_id": room_id},
        {"$set": {"transcript_pdf": pdf_path}}
    )