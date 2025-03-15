import os
import re
import requests
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 🔹 Enable CORS for frontend calls

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")

def extract_video_id(url):
    """Extracts video ID from YouTube URL."""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

def get_transcript(video_id):
    """Fetch transcript via a proxy"""
    proxy_url = f"https://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url=https://www.youtube.com/watch?v={video_id}"

    try:
        response = requests.get(proxy_url)
        if response.status_code != 200:
            return None, f"❌ Proxy Error: {response.status_code}"

        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        try:
            transcript = transcript_list.find_transcript(['en'])
        except NoTranscriptFound:
            transcript = transcript_list.find_generated_transcript([lang.language_code for lang in transcript_list])
            transcript = transcript.translate('en')

        transcript_text = "\n".join([entry['text'] for entry in transcript.fetch()])
        return transcript_text, None

    except TranscriptsDisabled:
        return None, "❌ Error: Transcripts are disabled for this video."
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

def get_gemini_summary(transcript_text):
    """Generates a summary using Gemini API."""
    try:
        prompt = f"The below is the transcript of a YouTube video. Summarize the content in 200 to 400 words:\n\n{transcript_text}"
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text if response.text else "❌ Gemini API returned no response."
    except Exception as e:
        return f"❌ Gemini API Error: {str(e)}"

@app.route('/process_video', methods=['POST'])
def process_video():
    """Processes the video URL and returns the summary."""
    try:
        data = request.form  # Get form data from request
        video_url = data.get("video_url")
        print(f"📌 Received Video URL: {video_url}")  # Debugging log

        if not video_url:
            return jsonify({"error": "❌ No YouTube URL provided."}), 400

        video_id = extract_video_id(video_url)
        if not video_id:
            return jsonify({"error": "❌ Invalid YouTube URL!"}), 400

        transcript_text, error = get_transcript(video_id)
        if error:
            return jsonify({"error": error}), 500

        summary_text = get_gemini_summary(transcript_text)

        return jsonify({
            "video_id": video_id,
            "summary": summary_text
        }), 200  # Ensure response status is 200

    except Exception as e:
        return jsonify({"error": f"Error processing request: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))


# import os
# import re
# import google.generativeai as genai
# from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
# from flask import Flask, request, jsonify, render_template
# from flask_cors import CORS  # 🔹 Enable CORS

# app = Flask(__name__)
# CORS(app)  # 🔹 Allow frontend to call this API

# # 🔹 Configure Gemini API
# genai.configure(api_key="AIzaSyCM96LDOorxeHp0mopClAdm7wkOOovhWCA")

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

# def get_gemini_summary(transcript_text):
#     """Generates a summary using Gemini API."""
#     try:
#         prompt = f"The below is the transcripts of You Tube video, now summarize the content in 200 to 400 lines : \n\n{transcript_text}"
#         model = genai.GenerativeModel("gemini-1.5-flash")
#         response = model.generate_content(prompt)
#         return response.text if response.text else "❌ Gemini API returned no response."
#     except Exception as e:
#         return f"❌ Gemini API Error: {str(e)}"

# @app.route('/process_video', methods=['POST'])
# def process_video():
#     """Processes the video URL and returns the summary."""
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

#         summary_text = get_gemini_summary(transcript_text)

#         return jsonify({
#             "video_id": video_id,
#             "summary": summary_text
#         }), 200  # Ensure response status is 200

#     except Exception as e:
#         return jsonify({"error": f"Error processing request: {str(e)}"}), 500

# if __name__ == '__main__':
#     app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
