import time
import random
import uvicorn
import google.api_core.exceptions
import os
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

# Fetch API keys from environment variables
GEMINI_API_KEYS = os.getenv("GEMINI_API_KEYS", "").split(",")

# Ensure at least one API key is available
if not GEMINI_API_KEYS or GEMINI_API_KEYS == [""]:
    raise ValueError("No Gemini API keys found. Set GEMINI_API_KEYS in environment variables.")

api_semaphore = Semaphore(len(GEMINI_API_KEYS))

class VideoRequest(BaseModel):
    url: str

def get_video_id(url: str):
    print(f"Received URL: {url}")  # Debugging line
    if "youtube.com" in url and "v=" in url:
        video_id = url.split("v=")[-1].split("&")[0]
    elif "youtu.be" in url:
        video_id = url.split("/")[-1].split("?")[0]
    else:
        video_id = None
    print(f"Extracted Video ID: {video_id}")  # Debugging line
    return video_id

def get_transcript(video_id: str, retries=3):
    print(f"Fetching transcript for Video ID: {video_id}")  
    for attempt in range(retries):
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            try:
                transcript = transcript_list.find_transcript(["en"]).fetch()
            except:
                transcript = transcript_list.find_generated_transcript(["en"]).fetch()
            return [t['text'] for t in transcript]
        except (TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript) as e:
            print(f"Transcript error: {e}")  
            return None
        except Exception as e:
            print(f"Error fetching transcript: {e}")
            wait_time = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff
            print(f"Retrying in {wait_time:.2f} seconds...")
            time.sleep(wait_time)
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
    """Retrieve an API key from the list dynamically."""
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
    print("Received URL:", video.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    transcript_list = get_transcript(video_id)
    if not transcript_list:
        raise HTTPException(status_code=404, detail="No captions available")
    summary = await summarize_large_transcript(transcript_list)
    return {"summary": summary}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
