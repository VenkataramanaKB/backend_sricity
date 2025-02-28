from app import create_app
from app.services import transcribe_audio

app = create_app()

with app.app_context():  # Ensure MongoDB is initialized
    room_id = "8f174c8d-b9b3-4d3f-b481-5cf83b1652f6"
    result = transcribe_audio(room_id)
    print(result)
