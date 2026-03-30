import os
import sys
import tempfile
import subprocess
import urllib.request

MODEL_DIR = os.path.join(os.path.dirname(__file__), "piper_models", "voices")
MODEL_FILE = "bmo.onnx"
CONFIG_FILE = "bmo.onnx.json"

MODEL_PATH = os.path.join(MODEL_DIR, MODEL_FILE)
CONFIG_PATH = os.path.join(MODEL_DIR, CONFIG_FILE)

def synthesize_audio(text: str) -> str:
    """
    Synthesize audio from text using piper-tts.
    Returns the path to a temporary generated .wav file.
    """
    print("Synthesizing audio with Custom BMO Voice (Piper TTS)...")
    
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: BMO voice model not found at {MODEL_PATH}")
        return temp_path
    
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
