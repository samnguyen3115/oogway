from faster_whisper import WhisperModel

# Use the 'tiny.en' model which is extremely fast and light. Perfect for Pi 5 fully offline.
model_size = "tiny.en"

# Load the model directly into CPU (since Pi 5 does not have NVIDIA GPU)
# compute_type='int8' minimizes memory usage.
print(f"Loading Faster-Whisper model ({model_size})...")
model = WhisperModel(model_size, device="cpu", compute_type="int8")
print("Faster-Whisper loaded.")

def transcribe_audio_file(file_path: str) -> str:
    """
    Transcribes an audio file into English text using faster-whisper.
    Returns the concatenated text.
    """
    segments, info = model.transcribe(file_path, beam_size=5)
    text = ""
    for segment in segments:
        text += segment.text + " "
    return text.strip()
