import os
import re
import json
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allow frontend requests

# Google Drive API Setup
SERVICE_ACCOUNT_FILE = "service_account1.json"  # Update this with your service account file
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Replace with your Google Drive folder ID
GOOGLE_DRIVE_FOLDER_ID = "1P1qtHdoyXjyKX3siBOIDCgs8Njn7KYMn"

def authenticate_drive():
    """Authenticate with Google Drive API."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

def upload_to_drive(file_path, file_name):
    """Uploads a file to Google Drive and returns the file link."""
    try:
        drive_service = authenticate_drive()

        file_metadata = {
            "name": file_name,
            "parents": [GOOGLE_DRIVE_FOLDER_ID],  # Upload to specific folder
        }
        media = MediaFileUpload(file_path, mimetype="text/plain")

        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()

        file_id = uploaded_file.get("id")
        file_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

        # Make file publicly accessible
        drive_service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
        ).execute()

        print(f"✅ File uploaded: {file_link}")
        return file_link

    except Exception as e:
        print(f"❌ Error uploading to Google Drive: {str(e)}")
        return None

def extract_video_id(url):
    """Extracts video ID from YouTube URL."""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

def get_transcript(video_id):
    """Fetches the transcript for a YouTube video."""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript(['en'])
        except NoTranscriptFound:
            transcript = transcript_list.find_generated_transcript([lang.language_code for lang in transcript_list])
            transcript = transcript.translate('en')

        return "\n".join([entry['text'] for entry in transcript.fetch()])
    except TranscriptsDisabled:
        return None
    except Exception as e:
        return None

def save_transcript(video_id, transcript_text):
    """Saves the transcript to a file."""
    file_name = f"{video_id}_transcript.txt"
    with open(file_name, "w", encoding="utf-8") as file:
        file.write(transcript_text)
    print(f"✅ File saved: {file_name}")
    return file_name

@app.route('/process_video', methods=['POST'])
def process_video():
    """Processes the video URL and returns the Google Drive link."""
    try:
        data = request.form
        video_url = data.get("video_url")
        print(f"📌 Received Video URL: {video_url}")

        if not video_url:
            return jsonify({"error": "❌ No YouTube URL provided."}), 400

        video_id = extract_video_id(video_url)
        if not video_id:
            return jsonify({"error": "❌ Invalid YouTube URL!"}), 400

        transcript_text = get_transcript(video_id)
        if not transcript_text:
            return jsonify({"error": "❌ No transcript found."}), 500

        file_name = save_transcript(video_id, transcript_text)

        # Upload to Google Drive
        file_link = upload_to_drive(file_name, file_name)

        if file_link:
            print(f"✅ Uploaded File Link: {file_link}")
            return jsonify({"file_link": file_link}), 200
        else:
            print("❌ Upload failed.")
            return jsonify({"error": "Upload failed."}), 500

    except Exception as e:
        print(f"❌ Error processing request: {str(e)}")
        return jsonify({"error": f"Error processing request: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))


# import os
# import re
# import requests
# from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
# from flask import Flask, request, jsonify
# from flask_cors import CORS  # Enable CORS

# app = Flask(__name__)
# CORS(app)  # Allow frontend to call this API

# def extract_video_id(url):
#     """Extracts video ID from YouTube URL."""
#     match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
#     return match.group(1) if match else None

# def get_transcript(video_id):
#     """Fetches the transcript for a YouTube video."""
#     try:
#         transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
#         try:
#             transcript = transcript_list.find_transcript(['en'])
#         except NoTranscriptFound:
#             transcript = transcript_list.find_generated_transcript([lang.language_code for lang in transcript_list])
#             transcript = transcript.translate('en')
        
#         transcript_text = "\n".join([entry['text'] for entry in transcript.fetch()])
#         return transcript_text
    
#     except TranscriptsDisabled:
#         return None, "❌ Error: Transcripts are disabled for this video."
#     except Exception as e:
#         return None, f"❌ Error: {str(e)}"

# def upload_to_drive(file_path):
#     """Uploads file to external endpoint and returns the file link."""
#     with open(file_path, 'rb') as f:
#         files = {'file': f}
#         response = requests.post("https://upload-to-drive.onrender.com/file", files=files)
#         if response.status_code == 200:
#             return response.json().get("file_link", "Error: No link returned")
#         else:
#             return f"Error: {response.text}"

# @app.route('/process_video', methods=['POST'])
# def process_video():
#     """Processes the video URL and returns the file link."""
#     try:
#         data = request.form  # Get form data from request
#         video_url = data.get("video_url")
#         print(f"📌 Received Video URL: {video_url}")  # Debugging log

#         if not video_url:
#             return jsonify({"error": "❌ No YouTube URL provided."}), 400

#         video_id = extract_video_id(video_url)
#         if not video_id:
#             return jsonify({"error": "❌ Invalid YouTube URL!"}), 400

#         transcript_text = get_transcript(video_id)
#         if not transcript_text:
#             return jsonify({"error": "❌ No transcript found."}), 500

#         # Save transcript to file
#         file_path = f"{video_id}.txt"
#         with open(file_path, "w", encoding="utf-8") as f:
#             f.write(transcript_text)
        
#         # Upload file and get link
#         file_link = upload_to_drive(file_path)
#         os.remove(file_path)  # Remove file after upload

#         return jsonify({
#             "video_id": video_id,
#             "file_link": file_link
#         }), 200

#     except Exception as e:
#         return jsonify({"error": f"Error processing request: {str(e)}"}), 500

# if __name__ == '__main__':
#     app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))


# # import os
# # import re
# # import google.generativeai as genai
# # from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
# # from flask import Flask, request, jsonify, render_template
# # from flask_cors import CORS  # 🔹 Enable CORS

# # app = Flask(__name__)
# # CORS(app)  # 🔹 Allow frontend to call this API

# # # 🔹 Configure Gemini API
# # genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# # def extract_video_id(url):
# #     """Extracts video ID from YouTube URL."""
# #     match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
# #     return match.group(1) if match else None

# # def get_transcript(video_id):
# #     """Fetches the transcript for a YouTube video."""
# #     try:
# #         transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

# #         try:
# #             transcript = transcript_list.find_transcript(['en'])
# #         except NoTranscriptFound:
# #             transcript = transcript_list.find_generated_transcript([lang.language_code for lang in transcript_list])
# #             transcript = transcript.translate('en')

# #         transcript_text = "\n".join([entry['text'] for entry in transcript.fetch()])
# #         return transcript_text

# #     except TranscriptsDisabled:
# #         return None, "❌ Error: Transcripts are disabled for this video."
# #     except Exception as e:
# #         return None, f"❌ Error: {str(e)}"

# # def get_gemini_summary(transcript_text):
# #     """Generates a summary using Gemini API."""
# #     try:
# #         prompt = f"The below is the transcripts of You Tube video, now summarize the content in 200 to 400 lines : \n\n{transcript_text}"
# #         model = genai.GenerativeModel("gemini-1.5-flash")
# #         response = model.generate_content(prompt)
# #         return response.text if response.text else "❌ Gemini API returned no response."
# #     except Exception as e:
# #         return f"❌ Gemini API Error: {str(e)}"

# # @app.route('/process_video', methods=['POST'])
# # def process_video():
# #     """Processes the video URL and returns the summary."""
# #     try:
# #         data = request.form  # Get form data from request
# #         video_url = data.get("video_url")
# #         print(f"📌 Received Video URL: {video_url}")  # Debugging log

# #         if not video_url:
# #             return jsonify({"error": "❌ No YouTube URL provided."}), 400

# #         video_id = extract_video_id(video_url)
# #         if not video_id:
# #             return jsonify({"error": "❌ Invalid YouTube URL!"}), 400

# #         transcript_text = get_transcript(video_id)
# #         if not transcript_text:
# #             return jsonify({"error": "❌ No transcript found."}), 500

# #         summary_text = get_gemini_summary(transcript_text)

# #         return jsonify({
# #             "video_id": video_id,
# #             "summary": summary_text
# #         }), 200  # Ensure response status is 200

# #     except Exception as e:
# #         return jsonify({"error": f"Error processing request: {str(e)}"}), 500

# # if __name__ == '__main__':
# #     app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
