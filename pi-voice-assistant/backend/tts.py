import os
import tempfile
import subprocess
import urllib.request

MODEL_DIR = os.path.join(os.path.dirname(__file__), "piper_models")
MODEL_NAME = "en_US-lessac-medium"
MODEL_FILE = f"{MODEL_NAME}.onnx"
CONFIG_FILE = f"{MODEL_NAME}.onnx.json"

MODEL_PATH = os.path.join(MODEL_DIR, MODEL_FILE)
CONFIG_PATH = os.path.join(MODEL_DIR, CONFIG_FILE)

# official HuggingFace repository for the Lessac voice
BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"

def download_file(url, path):
    print(f"Downloading {url} to {path}...")
    urllib.request.urlretrieve(url, path)

def ensure_model_exists():
    """Ensure that the required Piper ONNX model files are locally downloaded."""
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
    
    if not os.path.exists(MODEL_PATH):
        download_file(f"{BASE_URL}/{MODEL_FILE}", MODEL_PATH)
        
    if not os.path.exists(CONFIG_PATH):
        download_file(f"{BASE_URL}/{CONFIG_FILE}", CONFIG_PATH)

def synthesize_audio(text: str) -> str:
    """
    Synthesize audio from text using piper-tts.
    Returns the path to a temporary generated .wav file.
    """
    print("Synthesizing highly natural audio with Piper Neural TTS...")
    ensure_model_exists()
    
    # Create a temporary file to save the audio
    fd, temp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    
    # Modern piper-tts usually installs a standalone 'piper' binary in your venv/bin
    # We will try 'piper' first, and then 'python -m piper' as a fallback.
    try:
        process = subprocess.Popen(
            ['piper', '-m', MODEL_PATH, '-f', temp_path, '--config', CONFIG_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except FileNotFoundError:
        # Fallback for environments where the binary isn't in PATH
        process = subprocess.Popen(
            [sys.executable, '-m', 'piper', '-m', MODEL_PATH, '-f', temp_path, '--config', CONFIG_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    
    # Send the text to Piper's standard input
    stdout, stderr = process.communicate(input=text.encode('utf-8'))
    
    if process.returncode != 0:
        print("Piper TTS error:", stderr.decode('utf-8'))
    else:
        print(f"Audio synthesized perfectly to: {temp_path}")
    
    return temp_path
