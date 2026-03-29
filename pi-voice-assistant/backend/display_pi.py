import os
import time
import json
import math
import threading
import websocket
from PIL import Image, ImageDraw

# Try to import hardware libraries, but handle failure for Windows development
try:
    import ST7789
    HAS_HARDWARE_DISPLAY = True
except (ImportError, RuntimeError):
    HAS_HARDWARE_DISPLAY = False
    print("WARNING: ST7789 Hardware not found. Entering 'Mock Mode' for Desktop.")

# Display Configuration (2-inch ST7789 240x240)
DISP_DC = 25
DISP_RST = 27
DISP_BL = 18

disp = None
if HAS_HARDWARE_DISPLAY:
    disp = ST7789.ST7789(
        height=240,
        width=240,
        rotation=90,
        port=0,
        cs=ST7789.BG_SPI_CS_BACK,
        dc=DISP_DC,
        backlight=DISP_BL,
        spi_speed_hz=80 * 1000 * 1000,
        offset_left=0,
        offset_top=0
    )
    disp.begin()

# Global State for animation
current_state = "IDLE" 
last_state_change = time.time()

def on_message(ws, message):
    global current_state, last_state_change
    try:
        data = json.loads(message)
        new_state = data.get("state", "IDLE")
        if new_state != current_state:
            current_state = new_state
            last_state_change = time.time()
            print(f"Display State Change: {current_state}")
    except Exception as e:
        pass

def run_ws():
    try:
        ws = websocket.WebSocketApp("ws://localhost:8000/ws",
                                  on_message=on_message)
        ws.run_forever()
    except Exception:
        print("WebSocket Connection Failed. Is the server running?")

threading.Thread(target=run_ws, daemon=True).start()

def draw_frame(frame_count):
    img = Image.new('RGB', (240, 240), color=(13, 17, 23))
    draw = ImageDraw.Draw(img)
    cx, cy = 120, 120
    
    if current_state == "AWAKE":
        radius = 60 + 10 * math.sin(frame_count * 0.2)
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), outline=(88, 166, 255), width=4)
        radius2 = radius - 15
        draw.ellipse((cx-radius2, cy-radius2, cx+radius2, cy+radius2), outline=(163, 113, 247), width=2)
    elif current_state == "THINKING":
        for i in range(8):
            angle = (frame_count * 0.1) + (i * math.pi / 4)
            x = cx + 40 * math.cos(angle)
            y = cy + 40 * math.sin(angle)
            draw.ellipse((x-8, y-8, x+8, y+8), fill=(163, 113, 247))
    elif current_state == "SPEAKING" or (current_state == "ASLEEP" and (time.time() - last_state_change < 0.5)):
        for x in range(20, 220, 10):
            amp = 30 * math.sin((x * 0.05) + (frame_count * 0.4))
            draw.line((x, cy - amp, x, cy + amp), fill=(88, 166, 255), width=6)
    else:
        radius = 10 + 2 * math.sin(frame_count * 0.05)
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=(88, 166, 255))
        
    return img

print("Animation script starting...")
frame = 0
try:
    while True:
        img = draw_frame(frame)
        if HAS_HARDWARE_DISPLAY:
            disp.display(img)
        else:
            # On Windows, we just print the status so you know it's working
            if frame % 50 == 0:
                print(f"Animation active (State: {current_state})")
        
        frame += 1
        time.sleep(0.04)
except KeyboardInterrupt:
    print("Stopping Display...")
