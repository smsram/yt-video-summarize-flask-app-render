import re
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

def extract_video_id(video_url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", video_url)
    return match.group(1) if match else None

def get_transcript(video_url):
    video_id = extract_video_id(video_url)
    if not video_id:
        return "Error: Invalid YouTube URL!"
    
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = "\n".join([f"[{entry['start']:.2f}s] {entry['text']}" for entry in transcript])
        return transcript_text[:8000]  # Limit to 8000 chars to prevent API overflow
    except Exception as e:
        return f"Error fetching transcript: {e}"

def summarize_text(text):
    genai.configure(api_key="AIzaSyBgnJBmdeVI1TaITQwQygLOkeLh6setsaQ")
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(f"Summarize this transcript with captions, keeping the summary under 400 lines:\n{text}")
    return response.text

@app.route("/summarize", methods=["POST"])
def summarize():
    data = request.json
    video_url = data.get("video_url", "").strip()
    transcript = get_transcript(video_url)
    
    if "Error" not in transcript:
        summary = summarize_text(transcript)
        return jsonify({"summary": summary})
    else:
        return jsonify({"error": transcript}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Use Render's assigned port
    app.run(host="0.0.0.0", port=port, debug=True)
