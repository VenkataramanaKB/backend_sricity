from fpdf import FPDF
import time
import requests
import os
from flask import current_app as app
from .models import mongo

ASSEMBLYAI_UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
ASSEMBLYAI_TRANSCRIBE_URL = "https://api.assemblyai.com/v2/transcript"

def transcribe_audio(room_id):
    """
    Process all unprocessed voice notes for the given room_id.
    Upload each to AssemblyAI, transcribe it, store the result in MongoDB,
    and return a dictionary of transcripts keyed by doctor_id.
    """
    # Fetch room details using consistent "roomID"
    room = mongo.db.rooms.find_one({"roomID": room_id})

    if not room:
        print(f"[ERROR] Room with roomID {room_id} not found in MongoDB.")
        return {"error": f"Room {room_id} not found"}

    # Initialize voice_notes if missing
    if "voice_notes" not in room:
        print(f"[INFO] No voice_notes found for room {room_id}, initializing empty list.")
        mongo.db.rooms.update_one({"roomID": room_id}, {"$set": {"voice_notes": []}})
        room["voice_notes"] = []

    print(f"[DEBUG] Found room for transcription: roomID={room_id}, notes_count={len(room['voice_notes'])}")

    transcripts = {}
    headers = {"authorization": app.config["ASSEMBLYAI_API_KEY"]}

    for note in room["voice_notes"]:
        if note.get("processed", False):
            continue  # Skip already processed notes

        file_path = note.get("audio_path")
        doctor_id = note.get("doctor_id")

        if not file_path or not doctor_id:
            print(f"[WARNING] Skipping voice note with missing file_path or doctor_id: {note}")
            continue

        print(f"[INFO] Uploading file for transcription: {file_path}")

        try:
            with open(file_path, "rb") as f:
                upload_response = requests.post(ASSEMBLYAI_UPLOAD_URL, headers=headers, files={"file": f})
        except Exception as e:
            print(f"[ERROR] Failed to read file {file_path}: {e}")
            continue

        if upload_response.status_code != 200:
            print(f"[ERROR] AssemblyAI upload failed: {upload_response.json()}")
            return {"error": f"Upload failed for {file_path}: {upload_response.json()}"}

        upload_url = upload_response.json().get("upload_url")
        if not upload_url:
            print("[ERROR] Missing upload_url in AssemblyAI response.")
            return {"error": "Upload URL missing from AssemblyAI response"}

        transcript_request = requests.post(
            ASSEMBLYAI_TRANSCRIBE_URL,
            json={"audio_url": upload_url},
            headers=headers
        )

        if transcript_request.status_code != 200:
            print(f"[ERROR] AssemblyAI transcription request failed: {transcript_request.json()}")
            return {"error": f"Transcription request failed for {file_path}: {transcript_request.json()}"}

        transcript_id = transcript_request.json().get("id")

        # Poll for transcription result
        while True:
            result_response = requests.get(f"{ASSEMBLYAI_TRANSCRIBE_URL}/{transcript_id}", headers=headers)
            result = result_response.json()

            print(f"[DEBUG] Polling AssemblyAI transcript result for {file_path}: {result}")

            if result_response.status_code != 200:
                print(f"[ERROR] Failed to fetch transcript result: {result}")
                return {"error": f"Failed to fetch transcript for {file_path}: {result}"}

            if result.get("status") == "completed":
                transcript_text = result.get("text", "")
                transcripts[doctor_id] = transcript_text

                # Mark note as processed and attach transcription
                note["processed"] = True
                note["transcription"] = transcript_text

                print(f"[INFO] Transcription completed for doctor {doctor_id} in room {room_id}")
                break

            elif result.get("status") == "failed":
                print(f"[ERROR] Transcription failed for {file_path}")
                return {"error": f"Transcription failed for {file_path}"}

            time.sleep(5)  # Poll every 5 seconds

    # Update the room document with processed voice notes
    mongo.db.rooms.update_one({"roomID": room_id}, {"$set": {"voice_notes": room["voice_notes"]}})

    print(f"[INFO] Transcription process completed for room {room_id}")
    return transcripts

# Generate Documents using Gemini API
def generate_documents(transcripts):
    api_url = "https://api.gemini.com/v1/generate"
    headers = {"Authorization": f"Bearer {app.config['GEMINI_API_KEY']}"}
    
    payload = {
        "input": f"Generate minutes of meeting and medical notes for: {transcripts}",
        "model": "gemini-pro"
    }
    
    response = requests.post(api_url, json=payload, headers=headers)
    return response.json()

# Save Transcripts as PDF
def save_as_pdf(room_id, documents):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, "Minutes of Surgery Meeting", ln=True, align="C")
    pdf.ln(10)
    pdf.multi_cell(0, 10, documents.get("minutes", ""))
    pdf.ln(10)

    pdf.cell(200, 10, "Medical Notes for Students", ln=True, align="C")
    pdf.ln(10)
    pdf.multi_cell(0, 10, documents.get("notes", ""))

    os.makedirs(app.config["TRANSCRIPT_FOLDER"], exist_ok=True)
    pdf_path = os.path.join(app.config["TRANSCRIPT_FOLDER"], f"{room_id}.pdf")
    pdf.output(pdf_path)

    return pdf_path