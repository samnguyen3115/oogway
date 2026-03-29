import os
import wave
import json
import zipfile
import urllib.request
import tempfile
import pyaudio
from vosk import Model, KaldiRecognizer

# Model Configuration
MODEL_DIR = os.path.join(os.path.dirname(__file__), "vosk_models")
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_PATH = os.path.join(MODEL_DIR, "vosk-model-small-en-us-0.15")

def ensure_vosk_model():
    """Download and extract the small Vosk English model if not present."""
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        
    if not os.path.exists(MODEL_PATH):
        print(f"Downloading Vosk model from {MODEL_URL}...")
        zip_path = os.path.join(MODEL_DIR, "model.zip")
        urllib.request.urlretrieve(MODEL_URL, zip_path)
        
        print("Extracting model...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(MODEL_DIR)
        os.remove(zip_path)
        print("Vosk model successfully installed.")

def start_background_listener(callback=None):
    """
    Listens to the microphone using Vosk to identify sentence endpoints.
    Sends BOTH the transcription and the raw audio file path to the callback.
    """
    ensure_vosk_model()
    
    model = Model(MODEL_PATH)
    rec = KaldiRecognizer(model, 16000)
    
    p = pyaudio.PyAudio()
    
    input_device_index = None
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info.get('maxInputChannels') > 0:
            input_device_index = i
            print(f"Using audio input: {info.get('name')} (index {i})")
            break
            
    if input_device_index is None:
        print("Error: No microphone found!")
        return

    # Open stream
    stream = p.open(format=pyaudio.paInt16, 
                    channels=1, 
                    rate=16000, 
                    input=True, 
                    frames_per_buffer=4000,
                    input_device_index=input_device_index)
    stream.start_stream()

    print("Hybrid Listener is active. Ready for 'Bob'...")

    audio_buffer = []

    while True:
        try:
            data = stream.read(4000, exception_on_overflow=False)
            if len(data) == 0:
                break
                
            audio_buffer.append(data)

            if rec.AcceptWaveform(data):
                # We have a full sentence!
                result = json.loads(rec.Result())
                text = result.get("text", "").strip()
                
                if text:
                    print(f"DEBUG: Vosk Final -> '{text}'")
                    # Save the current buffer to a temp wav file for Whisper
                    fd, temp_wav = tempfile.mkstemp(suffix=".wav")
                    os.close(fd)
                    
                    wf = wave.open(temp_wav, 'wb')
                    wf.setnchannels(1)
                    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                    wf.setframerate(16000)
                    wf.writeframes(b''.join(audio_buffer))
                    wf.close()
                    
                    if callback:
                        callback(text, temp_wav)
                
                # Clear buffer for the next sentence
                audio_buffer = []
            else:
                # Partial transcription (real-time feedback)
                partial_data = json.loads(rec.PartialResult())
                partial_text = partial_data.get("partial", "").strip()
                if partial_text:
                    print(f"DEBUG: Hearing -> '{partial_text}'...")
                pass


        except Exception as e:
            print("Error in Listener loop:", e)
            continue

    stream.stop_stream()
    stream.close()
    p.terminate()
