import time
import random
import uvicorn
import google.api_core.exceptions
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript
from asyncio import Semaphore
import asyncio

# Set up FastAPI
app = FastAPI()

# Allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Multiple Gemini API keys for load balancing
GEMINI_API_KEYS = [
    "AIzaSyBgnJBmdeVI1TaITQwQygLOkeLh6setsaQ",
    "AIzaSyAqCDmafS3m1R6goYEypOb8lktdrM0ouu0",
    "AIzaSyAhCuyUiRZqnIYskynMkZuuTd-1WFbTo-A"
]
api_semaphore = Semaphore(len(GEMINI_API_KEYS))

class VideoRequest(BaseModel):
    url: str

def get_video_id(url: str):
    if "youtube.com" in url and "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    elif "youtu.be" in url:
        return url.split("/")[-1].split("?")[0]
    return None

def get_transcript(video_id: str):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript(["en"]).fetch()
        except:
            transcript = transcript_list.find_generated_transcript(["en"]).fetch()
        return [t['text'] for t in transcript]
    except (TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript):
        return None

def chunk_text(text_list, chunk_size=2000):
    chunks, current_chunk = [], ""
    for text in text_list:
        if len(current_chunk) + len(text) < chunk_size:
            current_chunk += text + " "
        else:
            chunks.append(current_chunk.strip())
            current_chunk = text + " "
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def get_api_key():
    """Retrieve an API key from the list and configure it dynamically."""
    return random.choice(GEMINI_API_KEYS)

async def summarize_chunk(text, retries=3):
    """Summarizes a text chunk using Gemini AI with concurrency support."""
    for attempt in range(retries):
        async with api_semaphore:
            try:
                api_key = get_api_key()
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-pro")
                response = model.generate_content(f"Summarize this content in English: {text}")
                return response.text.strip()
            except google.api_core.exceptions.ResourceExhausted:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"Quota exceeded. Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            except Exception as e:
                return f"Error: {str(e)}"
    return "Quota exceeded. Please try again later."

async def summarize_large_transcript(text_list):
    """Handles summarization for large transcripts asynchronously."""
    text_chunks = chunk_text(text_list)
    summaries = await asyncio.gather(*[summarize_chunk(chunk) for chunk in text_chunks])
    final_summary = await summarize_chunk(" ".join(summaries))
    return final_summary

@app.post("/summarize")
async def summarize_video(video: VideoRequest):
    video_id = get_video_id(video.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    transcript_list = get_transcript(video_id)
    if not transcript_list:
        raise HTTPException(status_code=404, detail="No captions available")
    summary = await summarize_large_transcript(transcript_list)
    return {"summary": summary}

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)


# import re
# from flask import Flask, request, jsonify
# from flask_cors import CORS
# from youtube_transcript_api import YouTubeTranscriptApi
# import google.generativeai as genai

# app = Flask(__name__)
# CORS(app)  # Enable CORS for frontend requests

# def extract_video_id(video_url):
#     match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", video_url)
#     return match.group(1) if match else None

# def get_transcript(video_url):
#     video_id = extract_video_id(video_url)
#     if not video_id:
#         return "Error: Invalid YouTube URL!"
    
#     try:
#         transcript = YouTubeTranscriptApi.get_transcript(video_id)
#         transcript_text = "\n".join([f"[{entry['start']:.2f}s] {entry['text']}" for entry in transcript])
#         return transcript_text[:8000]  # Limit to 8000 chars to prevent API overflow
#     except Exception as e:
#         return f"Error fetching transcript: {e}"

# def summarize_text(text):
#     genai.configure(api_key="AIzaSyBgnJBmdeVI1TaITQwQygLOkeLh6setsaQ")  # Replace with your API key
#     model = genai.GenerativeModel("gemini-pro")
#     response = model.generate_content(f"Summarize this transcript with captions, keeping the summary under 400 lines:\n{text}")
#     return response.text

# @app.route("/summarize", methods=["POST"])
# def summarize():
#     data = request.json
#     video_url = data.get("video_url", "").strip()
#     transcript = get_transcript(video_url)
    
#     if "Error" not in transcript:
#         summary = summarize_text(transcript)
#         return jsonify({"summary": summary})
#     else:
#         return jsonify({"error": transcript}), 400

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=10000)
