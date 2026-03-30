import os
import time
import json
import math
import threading
import websocket
from PIL import Image, ImageDraw

# Try to import hardware libraries, but handle failure for Windows development
try:
    import lgpio
    import spidev
    HAS_HARDWARE_DISPLAY = True
except (ImportError, RuntimeError):
    HAS_HARDWARE_DISPLAY = False
    print("WARNING: Hardware libraries (lgpio/spidev) not found. Entering 'Mock Mode' for Desktop.")

# ── Pin definitions (BCM) ─────────────────────────────────────────────────────
DC_PIN  = 25
RST_PIN = 27
BL_PIN  = 18

h = None
spi = None

# Hardware Initialization
if HAS_HARDWARE_DISPLAY:
    try:
        h = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(h, DC_PIN)
        lgpio.gpio_claim_output(h, RST_PIN)
        lgpio.gpio_claim_output(h, BL_PIN)
        lgpio.gpio_write(h, BL_PIN, 1)

        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 40000000
        spi.mode = 0
    except Exception as e:
        print(f"Hardware initialization failed: {e}")
        HAS_HARDWARE_DISPLAY = False

def send_command(cmd):
    if not HAS_HARDWARE_DISPLAY: return
    lgpio.gpio_write(h, DC_PIN, 0)
    spi.writebytes([cmd])

def send_data(data):
    if not HAS_HARDWARE_DISPLAY: return
    lgpio.gpio_write(h, DC_PIN, 1)
    spi.writebytes(data if isinstance(data, list) else [data])

def reset_display():
    if not HAS_HARDWARE_DISPLAY: return
    for v in [1, 0, 1]:
        lgpio.gpio_write(h, RST_PIN, v)
        time.sleep(0.1)

def init_display():
    if not HAS_HARDWARE_DISPLAY: return
    reset_display()
    send_command(0x01); time.sleep(0.15)  # Software Reset
    send_command(0x11); time.sleep(0.5)   # Sleep Out
    send_command(0x3A); send_data(0x55)   # Interface Pixel Format (16-bit)
    # 0xB0 is 180-degree flipped Landscape (compared to 0x70)
    send_command(0x36); send_data(0xB0) 
    send_command(0x21)                    # DISPLAY INVERSION ON (Fixes Black appearing as White)
    send_command(0x29); time.sleep(0.1)   # Display On

def display_image(img):
    if not HAS_HARDWARE_DISPLAY: return
    img = img.convert('RGB')
    pixels = list(img.getdata())
    data = []
    for r, g, b in pixels:
        c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        data += [(c >> 8) & 0xFF, c & 0xFF]
    # Window for 320 (Width) x 240 (Height)
    send_command(0x2A); send_data([0, 0, 1, 63])  # 319
    send_command(0x2B); send_data([0, 0, 0, 239]) # 239
    send_command(0x2C)
    lgpio.gpio_write(h, DC_PIN, 1)
    for i in range(0, len(data), 4096):
        spi.writebytes(data[i:i+4096])

# ── Animation & State Logic ──────────────────────────────────────────────────
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
    except Exception:
        pass

def run_ws():
    try:
        ws = websocket.WebSocketApp("ws://localhost:8000/ws", on_message=on_message)
        ws.run_forever()
    except Exception:
        print("WebSocket Connection Failed.")

threading.Thread(target=run_ws, daemon=True).start()

def draw_frame(frame_count):
    # --- PALETTES FROM IMAGE ---
    BG_COLOR = (180, 230, 200)      # Pale Mint
    EYE_COLOR = (0, 0, 0)           # Deep Black
    MOUTH_OUTLINE = (0, 0, 0)       # Black Border
    MOUTH_THROAT = (11, 89, 45)     # Dark Forest Green
    MOUTH_TEETH = (255, 255, 255)   # Pure White
    MOUTH_TONGUE = (84, 184, 115)   # Bright Kawaii Green
    
    img = Image.new('RGB', (320, 240), color=BG_COLOR)
    draw = ImageDraw.Draw(img)
    cx, cy = 160, 120 
    
    # --- BLINKING LOGIC ---
    is_blinking = (frame_count % 160) < 6 

    if current_state == "AWAKE":
        # Attentive Eyes
        for x_off in [-60, 60]:
            draw.ellipse((cx+x_off-12, cy-45, cx+x_off+12, cy-10), fill=EYE_COLOR)
        # Pulsing simple mouth
        m_r = 10 + 4 * math.sin(frame_count * 0.4)
        draw.ellipse((cx-m_r, cy+40-m_r, cx+m_r, cy+40+m_r), outline=EYE_COLOR, width=3)

    elif current_state == "THINKING":
        # Spinner dots (hidden face)
        spinner_r = 40
        start_angle = (frame_count * 10) % 360
        draw.arc((cx-spinner_r, cy-spinner_r-20, cx+spinner_r, cy+spinner_r-20), 
                 start=start_angle, end=start_angle+280, fill=EYE_COLOR, width=6)
        try:
            font = None
            for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/freefont/FreeSans.ttf']:
                if os.path.exists(p):
                    from PIL import ImageFont
                    font = ImageFont.truetype(p, 24); break
            if font:
                w = draw.textlength("Thinking...", font=font)
                draw.text((cx-w/2, cy+50), "Thinking...", font=font, fill=EYE_COLOR)
        except Exception: pass

    elif current_state == "SPEAKING" or (current_state == "ASLEEP" and (time.time() - last_state_change < 0.5)):
        # --- DETAILED SPEAKING FACE ---
        y_b = 3 * math.sin(frame_count * 0.6)
        for x_off in [-60, 60]:
            draw.ellipse((cx+x_off-10, cy-45+y_b, cx+x_off+10, cy-15+y_b), fill=EYE_COLOR)
        
        # Mouth: m_top is the flat lip line, mouth grows downward
        m_w = 55
        m_h = 15 + 30 * abs(math.sin(frame_count * 0.5))  # depth grows dynamically
        m_top = cy + 15  # flat lip line (stays fixed)
        
        # Chord bounding box centered at m_top so flat edge = m_top
        draw.chord((cx-m_w-2, m_top-m_h-2, cx+m_w+2, m_top+m_h+2), start=0, end=180, fill=MOUTH_OUTLINE)
        draw.chord((cx-m_w, m_top-m_h, cx+m_w, m_top+m_h), start=0, end=180, fill=MOUTH_THROAT)
        # Teeth pinned exactly to m_top (the flat lip line)
        draw.rectangle([cx-m_w+5, m_top-2, cx+m_w-5, m_top+12], fill=MOUTH_TEETH)
        # Tongue near bottom of mouth
        draw.ellipse((cx-28, m_top+m_h-18, cx+28, m_top+m_h+5), fill=MOUTH_TONGUE)

    else:
        # --- DETAILED IDLE FACE ---
        if is_blinking:
            for x_off in [-60, 60]:
                draw.line((cx+x_off-15, cy-30, cx+x_off+15, cy-30), fill=EYE_COLOR, width=4)
        else:
            for x_off in [-60, 60]:
                draw.ellipse((cx+x_off-10, cy-45, cx+x_off+10, cy-15), fill=EYE_COLOR)
        
        # Static Layered Mouth — m_top is the flat lip line
        m_w = 55
        m_h = 38   # mouth depth
        m_top = cy + 15
        draw.chord((cx-m_w-2, m_top-m_h-2, cx+m_w+2, m_top+m_h+2), start=0, end=180, fill=MOUTH_OUTLINE)
        draw.chord((cx-m_w, m_top-m_h, cx+m_w, m_top+m_h), start=0, end=180, fill=MOUTH_THROAT)
        # Teeth pinned to m_top
        draw.rectangle([cx-m_w+5, m_top-2, cx+m_w-5, m_top+10], fill=MOUTH_TEETH)
        # Tongue
        draw.ellipse((cx-28, m_top+m_h-18, cx+28, m_top+m_h+5), fill=MOUTH_TONGUE)
        
    return img

if HAS_HARDWARE_DISPLAY:
    init_display()

print("BMO/Sam Horizontal Animation starting...")
frame = 0
try:
    while True:
        img = draw_frame(frame)
        if HAS_HARDWARE_DISPLAY:
            display_image(img)
        else:
            if frame % 50 == 0:
                print(f"Mock Mode: Horizontal (State: {current_state})")
        
        frame += 1
        time.sleep(0.04)
except KeyboardInterrupt:
    print("Stopping Display...")
finally:
    if HAS_HARDWARE_DISPLAY:
        spi.close()
        lgpio.gpiochip_close(h)
