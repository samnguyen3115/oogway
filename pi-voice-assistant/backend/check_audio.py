import pyaudio

p = pyaudio.PyAudio()
print("Scanning for audio devices...")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info.get('maxInputChannels') > 0:
        print(f"[{i}] {info.get('name')}")
p.terminate()
