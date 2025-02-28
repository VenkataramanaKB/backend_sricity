import time
import requests
import os
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

ASSEMBLYAI_UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
ASSEMBLYAI_TRANSCRIBE_URL = "https://api.assemblyai.com/v2/transcript"

headers = {"authorization": ASSEMBLYAI_API_KEY}

def transcribe_audio(file_path):
    """Transcribe an audio file using AssemblyAI and return the text."""

    # 1. Upload the audio file
    with open(file_path, "rb") as f:
        upload_response = requests.post(ASSEMBLYAI_UPLOAD_URL, headers=headers, files={"file": f})
    
    if upload_response.status_code != 200:
        return {"error": f"Upload failed: {upload_response.json()}"}

    upload_url = upload_response.json().get("upload_url")
    
    # 2. Request transcription
    transcript_request = requests.post(
        ASSEMBLYAI_TRANSCRIBE_URL,
        json={"audio_url": upload_url},
        headers=headers
    )
    
    if transcript_request.status_code != 200:
        return {"error": f"Transcription request failed: {transcript_request.json()}"}

    transcript_id = transcript_request.json().get("id")
    
    # 3. Poll for the result
    while True:
        result_response = requests.get(f"{ASSEMBLYAI_TRANSCRIBE_URL}/{transcript_id}", headers=headers)
        result = result_response.json()
        
        if result_response.status_code != 200:
            return {"error": f"Error fetching transcription: {result}"}

        if result.get("status") == "completed":
            return {"text": result.get("text", "")}
        
        elif result.get("status") == "failed":
            return {"error": "Transcription failed"}
        
        time.sleep(5)  # Wait before polling again

# Example usage
if __name__ == "__main__":
    file_path = "/home/venkat/workstation/medscript/uploads/output.mp3"
    result = transcribe_audio(file_path)
    print(result)
