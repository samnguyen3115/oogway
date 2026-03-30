import os
import uuid
import tempfile
import base64
import threading
import wave
import pyaudio
import asyncio
from typing import List
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import ollama

from stt import transcribe_audio_file
from tts import synthesize_audio
from listener import start_background_listener

app = FastAPI()

# Allow frontend to communicate locally
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = os.path.join(os.path.dirname(__file__), "../frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# WebSocket Connections
connected_clients: List[WebSocket] = []

async def broadcast_to_frontend(data: dict):
    """Send voice/text updates to everyone viewing the UI."""
    for client in connected_clients:
        try:
            await client.send_json(data)
        except Exception:
            pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

# Global configuration / State
MODEL_NAME = "phi"
IS_AWAKE = False

def play_audio_file(file_path: str):
    """
    Play a .wav file. 
    On Linux/Pi, we use 'aplay' because it handles hardware sample-rate 
    resampling (e.g., 22050Hz to 44100Hz) automatically.
    """
    if not os.path.exists(file_path):
        return
    
    # Check if we are on Linux (Raspberry Pi)
    if os.name != 'nt':
        try:
            # 'plug:default' is a special ALSA device that FORCES software resampling.
            # This is the most compatible way to play audio on Pi hardware.
            import subprocess
            subprocess.run(['aplay', '-D', 'plughw:0', file_path], check=True, capture_output=True)
            return
        except Exception:
            try:
                # Fallback to the standard 'default' if plughw:0 isn't the right index
                subprocess.run(['aplay', '-D', 'default', file_path], check=True, capture_output=True)
                return
            except Exception as e:
                print(f"aplay failed, falling back to pyaudio: {e}")

    # Fallback to PyAudio (for Windows or if aplay is missing)
    try:
        CHUNK = 1024
        wf = wave.open(file_path, 'rb')
        p = pyaudio.PyAudio()
        
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True)
        
        data = wf.readframes(CHUNK)
        while data:
            stream.write(data)
            data = wf.readframes(CHUNK)
            
        stream.stop_stream()
        stream.close()
        p.terminate()
        wf.close()
    except Exception as e:
        print(f"Audio playback error: {e}")

def handle_voice_input(transcription: str, audio_path: str):
    """
    Called by the listener thread when a full audio chunk is ready.
    Uses Vosk transcription for wake words, and Whisper for the actual query.
    """
    global IS_AWAKE
    
    # Run the logic in an async loop since we need to broadcast
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        lower_transcription = transcription.lower().strip()
        
        # 1. State Machine: Asleep vs Awake
        if not IS_AWAKE:
            # Look for wake words (any phrase with "bob" - using Vosk for speed)
            if "bob" in lower_transcription:
                print(f"Wake word 'bob' detected with Vosk! Waking up...")
                IS_AWAKE = True
                ai_text = "Yes? I'm listening. What can I do for you?"
                
                # Push status to UI
                # --- FIX: Start in SPEAKING state for the greeting ---
                loop.run_until_complete(broadcast_to_frontend({
                    "transcription": transcription,
                    "ai_text": ai_text,
                    "state": "SPEAKING"
                }))
                
                # Speak it
                ai_audio_path = synthesize_audio(ai_text)
                play_audio_file(ai_audio_path)
                if os.path.exists(ai_audio_path):
                    os.remove(ai_audio_path)
                    
                # After greeting, stay AWAKE and ready for the query
                loop.run_until_complete(broadcast_to_frontend({
                    "transcription": transcription,
                    "ai_text": ai_text,
                    "state": "AWAKE"
                }))
            
            # Transcription isn't needed if we are asleep and didn't hear a wake word
            
        else:
            # We are AWAKE, use Faster-Whisper for high accuracy query
            print("Assistant is awake. Transcribing query with Faster-Whisper...")
            
            # Send 'Thinking' status while Whisper works
            loop.run_until_complete(broadcast_to_frontend({
                "transcription": "(Processing...)",
                "ai_text": "Thinking...",
                "state": "THINKING"
            }))

            high_acc_transcription = transcribe_audio_file(audio_path)
            print(f"User (Whisper): {high_acc_transcription}")

            if not high_acc_transcription.strip():
                print("Whisper could not find any speech. Ignoring.")
                IS_AWAKE = False
                return

            # Query Ollama
            print(f"Querying Ollama with '{MODEL_NAME}'...")
            response = ollama.chat(model=MODEL_NAME, messages=[
                {'role': 'user', 'content': high_acc_transcription},
            ])
            
            ai_text = response['message']['content']
            
            # Add the signature sign-off
            if not ai_text.strip().endswith("bye bye"):
                ai_text = ai_text.strip() + " bye bye"
                
            print(f"AI: {ai_text}")
            IS_AWAKE = False # Go back to sleep
            
            # Synthesize answer
            ai_audio_path = synthesize_audio(ai_text)

            # --- FIX: Broadcast SPEAKING state before playing audio ---
            loop.run_until_complete(broadcast_to_frontend({
                "transcription": high_acc_transcription,
                "ai_text": ai_text,
                "state": "SPEAKING"
            }))
            
            play_audio_file(ai_audio_path)
            if os.path.exists(ai_audio_path):
                os.remove(ai_audio_path)
            
            # Broadcast final response to UI
            loop.run_until_complete(broadcast_to_frontend({
                "transcription": high_acc_transcription,
                "ai_text": ai_text,
                "state": "ASLEEP"
            }))
            
    except Exception as e:
        print("Error in voice handler:", e)
    finally:
        # Cleanup the temporary audio chunk
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        loop.close()

@app.on_event("startup")
async def startup_event():
    """Start the background audio listener thread when the server starts."""
    print("Starting background microphone listener...")
    # Passing the callback function to the listener
    threading.Thread(target=start_background_listener, args=(handle_voice_input,), daemon=True).start()

@app.get("/")
def read_root():
    return FileResponse(os.path.join(frontend_dir, "index.html"))
