from flask import Flask, request, jsonify
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
import google.generativeai as genai
import re

app = Flask(__name__)
CORS(app)  # Allow CORS for frontend requests

# Configure Google Generative AI (Replace with your API Key)
API_KEY = "AIzaSyBgnJBmdeVI1TaITQwQygLOkeLh6setsaQ"
genai.configure(api_key=API_KEY)

def extract_video_id(url):
    """Extracts video ID from YouTube URLs."""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

@app.route('/')
def home():
    return jsonify({"message": "YouTube Video Summarizer API is running!"})

@app.route('/summarize', methods=['POST'])
def summarize():
    try:
        data = request.get_json()
        if not data or 'video_url' not in data:
            return jsonify({"error": "Missing video_url in request"}), 400

        # Extract Video ID from URL
        video_url = data["video_url"]
        video_id = extract_video_id(video_url)

        if not video_id:
            return jsonify({"error": "Invalid YouTube video URL"}), 400

        # Get Transcript (Captions)
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            transcript_text = " ".join([entry['text'] for entry in transcript])
        except TranscriptsDisabled:
            return jsonify({"error": "Transcripts are disabled for this video."}), 400
        except Exception:
            return jsonify({"error": "Could not fetch transcript. It may not be available."}), 400

        # Summarize using Google AI
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(f"Summarize the following video transcript in under 400 words:\n{transcript_text}")
        
        summary = response.text if response and response.text else "No summary available."

        return jsonify({"summary": summary, "video_url": video_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
