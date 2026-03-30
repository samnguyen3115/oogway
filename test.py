import lgpio
import spidev
from PIL import Image, ImageDraw, ImageFont
import time
import psutil
import subprocess

# ── Pin definitions (BCM) ─────────────────────────────────────────────────────
DC_PIN  = 25
RST_PIN = 27
BL_PIN  = 18

# ── GPIO & SPI setup ──────────────────────────────────────────────────────────
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, DC_PIN)
lgpio.gpio_claim_output(h, RST_PIN)
lgpio.gpio_claim_output(h, BL_PIN)
lgpio.gpio_write(h, BL_PIN, 1)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 40000000
spi.mode = 0

# ── ST7789 driver ─────────────────────────────────────────────────────────────
def send_command(cmd):
    lgpio.gpio_write(h, DC_PIN, 0)
    spi.writebytes([cmd])

def send_data(data):
    lgpio.gpio_write(h, DC_PIN, 1)
    spi.writebytes(data if isinstance(data, list) else [data])

def reset():
    for v in [1, 0, 1]:
        lgpio.gpio_write(h, RST_PIN, v)
        time.sleep(0.1)

def init_display():
    reset()
    send_command(0x01); time.sleep(0.15)   # SW reset
    send_command(0x11); time.sleep(0.5)    # Sleep out
    send_command(0x3A); send_data(0x55)    # 16-bit colour
    send_command(0x36); send_data(0x00)    # Memory access
    send_command(0x29); time.sleep(0.1)    # Display on

def display_image(img):
    img = img.convert('RGB')
    pixels = list(img.getdata())
    data = []
    for r, g, b in pixels:
        c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        data += [(c >> 8) & 0xFF, c & 0xFF]
    send_command(0x2A); send_data([0, 0, 0, 239])
    send_command(0x2B); send_data([0, 0, 1, 63])
    send_command(0x2C)
    lgpio.gpio_write(h, DC_PIN, 1)
    for i in range(0, len(data), 4096):
        spi.writebytes(data[i:i+4096])

# ── Stats helpers ─────────────────────────────────────────────────────────────
def get_cpu_temp():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return int(f.read()) / 1000.0
    except:
        return 0.0

def get_ip():
    try:
        result = subprocess.check_output(['hostname', '-I'], text=True)
        return result.strip().split()[0]
    except:
        return 'N/A'

def bar(draw, x, y, w, h_bar, pct, fg, bg=(30, 30, 30)):
    draw.rectangle([x, y, x+w, y+h_bar], fill=bg)
    draw.rectangle([x, y, x+int(w*pct/100), y+h_bar], fill=fg)

def temp_color(t):
    if t < 50: return (0, 220, 100)
    if t < 70: return (255, 200, 0)
    return (255, 60, 60)

def cpu_color(p):
    if p < 50: return (0, 200, 255)
    if p < 80: return (255, 200, 0)
    return (255, 60, 60)

# ── Font (fallback to default if not found) ───────────────────────────────────
def load_font(size):
    for path in [
        '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf',
        '/usr/share/fonts/truetype/freefont/FreeMono.ttf',
    ]:
        try:
            return ImageFont.truetype(path, size)
        except:
            pass
    return ImageFont.load_default()

# ── Draw one frame ────────────────────────────────────────────────────────────
def draw_frame(font_lg, font_md, font_sm):
    W, H = 240, 320
    img  = Image.new('RGB', (W, H), (10, 10, 15))
    d    = ImageDraw.Draw(img)

    cpu_pct  = psutil.cpu_percent(interval=None)
    ram      = psutil.virtual_memory()
    ram_pct  = ram.percent
    ram_used = ram.used  / (1024**3)
    ram_tot  = ram.total / (1024**3)
    temp     = get_cpu_temp()
    disk     = psutil.disk_usage('/')
    disk_pct = disk.percent
    net      = psutil.net_io_counters()
    ip       = get_ip()
    uptime_s = int(time.time() - psutil.boot_time())
    h_up, r  = divmod(uptime_s, 3600)
    m_up, s_up = divmod(r, 60)

    # ── Header ────────────────────────────────────────────────────────────────
    d.rectangle([0, 0, W, 38], fill=(0, 0, 0))
    d.text((8, 6), "PI MONITOR", font=font_lg, fill=(0, 220, 100))
    d.text((W-70, 10), time.strftime('%H:%M:%S'), font=font_sm, fill=(120, 120, 120))
    d.line([0, 38, W, 38], fill=(0, 80, 40), width=1)

    # ── CPU ───────────────────────────────────────────────────────────────────
    y = 46
    d.text((8, y), "CPU", font=font_sm, fill=(120, 120, 120))
    cc = cpu_color(cpu_pct)
    d.text((52, y), f"{cpu_pct:5.1f}%", font=font_md, fill=cc)
    bar(d, 8, y+22, W-16, 10, cpu_pct, cc)

    # ── RAM ───────────────────────────────────────────────────────────────────
    y = 98
    d.text((8, y), "RAM", font=font_sm, fill=(120, 120, 120))
    d.text((52, y), f"{ram_used:.1f}/{ram_tot:.1f}G", font=font_md, fill=(100, 180, 255))
    d.text((W-52, y), f"{ram_pct:.0f}%", font=font_sm, fill=(100, 180, 255))
    bar(d, 8, y+22, W-16, 10, ram_pct, (100, 180, 255))

    # ── Temperature ───────────────────────────────────────────────────────────
    y = 148
    tc = temp_color(temp)
    d.text((8, y), "TEMP", font=font_sm, fill=(120, 120, 120))
    d.text((60, y), f"{temp:.1f} °C", font=font_md, fill=tc)
    bar(d, 8, y+22, W-16, 10, min(temp/100*100, 100), tc)

    # ── Disk ──────────────────────────────────────────────────────────────────
    y = 198
    d.text((8, y), "DISK", font=font_sm, fill=(120, 120, 120))
    d.text((60, y), f"{disk.used/(1024**3):.1f}/{disk.total/(1024**3):.1f}G", font=font_md, fill=(220, 150, 255))
    d.text((W-52, y), f"{disk_pct:.0f}%", font=font_sm, fill=(220, 150, 255))
    bar(d, 8, y+22, W-16, 10, disk_pct, (220, 150, 255))

    # ── Network ───────────────────────────────────────────────────────────────
    y = 248
    d.line([0, y-6, W, y-6], fill=(30, 30, 30), width=1)
    d.text((8, y), f"IP  {ip}", font=font_sm, fill=(100, 200, 180))
    y += 18
    sent_mb = net.bytes_sent / (1024**2)
    recv_mb = net.bytes_recv / (1024**2)
    d.text((8, y), f"↑{sent_mb:.1f}MB  ↓{recv_mb:.1f}MB", font=font_sm, fill=(80, 160, 140))

    # ── Uptime ────────────────────────────────────────────────────────────────
    y += 18
    d.text((8, y), f"UP  {h_up:02d}:{m_up:02d}:{s_up:02d}", font=font_sm, fill=(80, 80, 100))

    return img

# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    init_display()
    font_lg = load_font(20)
    font_md = load_font(16)
    font_sm = load_font(13)

    print("Stats monitor running — Ctrl+C to quit")
    psutil.cpu_percent(interval=None)  # prime the cpu reading

    try:
        while True:
            img = draw_frame(font_lg, font_md, font_sm)
            display_image(img)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        spi.close()
        lgpio.gpiochip_close(h)
        print("Cleanup done.")

if __name__ == '__main__':
    main()
