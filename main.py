# main.py - ADS-B "sweeping radar" for ESP32-C6 + MicroPython (v1.24 or newer)
#
# Display : 240x240 SPI TFT (GC9A01 round is ideal, ST7789 square also works)
# Driver  : any pure-Python driver with blit_buffer(buf, x, y, w, h), e.g.
#           russhughes/gc9a01py or russhughes/st7789py_mpy (copy the .py to the board)
# Data    : adsb.lol public API (no key; keep to <= 1 request/second)
#
# How it works: everything is drawn into ONE RGB565 framebuffer in RAM using the
# built-in (C-speed) framebuf module, then the whole frame is pushed to the
# display in a single SPI transfer. A background thread polls the API.

import gc, math, time, _thread
import network, framebuf, requests
from array import array
from machine import Pin, SPI

# ------------------------------------------------------------------ config
from secrets import WIFI_SSID, WIFI_PASS   # secrets.py lives on the board, not in git

# Which board? Pin maps match the wiring diagrams in this repo.
BOARD = "XIAO_C6"              # "XIAO_C6" (Seeed XIAO ESP32C6) or "DEVKITC" (ESP32-C6-DevKitC-1)
PINS = {
    #             SPI clock/data    display control          LED strip
    "XIAO_C6": dict(sck=18, mosi=20, res=22, dc=21, cs=2,  blk=1,  led=0,  cs2=19),   # D10 D9 D4 D3 D2 D1 D0, D8
    "DEVKITC": dict(sck=6,  mosi=7,  res=18, dc=19, cs=20, blk=21, led=22, cs2=23),
}[BOARD]

HOME_LAT    = 52.3086          # your position (decimal degrees); default = Schiphol airport area
HOME_LON    = 4.7639
try:                           # keep your real home position private: put it in secrets.py
    from secrets import HOME_LAT, HOME_LON
except ImportError:
    pass
RANGE_KM    = 20               # outer ring radius in kilometres
RANGE_NM    = RANGE_KM / 1.852 # the same, in nautical miles (used internally)
MIN_ALT_FT  = 200             # hard cut-off: ignore aircraft below this altitude
FETCH_S     = 18               # seconds between API calls (positions are dead-reckoned in between)

# Two displays share the SPI bus, DC, RES and BLK lines and have their own CS pin:
# display A (PINS["cs"]) shows aircraft below SPLIT_FT, display B (PINS["cs2"]) the ones above.
SPLIT_FT    = 5000
LABELS      = ("LOW <5K", "HIGH >5K")
SWEEP_S     = 8.0              # seconds per full beam rotation
TRAIL_DEG   = 60               # length of the fading afterglow behind the beam
TRAIL_STEPS = 15               # number of wedges the afterglow is built from
LABEL_DEG   = 360              # flight details stay visible this many degrees after the beam passes
                               # (180 = half a sweep, 360 = a full sweep; they dim with the blip)
# airplanes.live now returns 403 unless you email them; adsb.lol serves the same JSON format.
API_URL     = "https://api.adsb.lol/v2/point/{:.4f}/{:.4f}/{}"

# LED proximity bar (WS2812 / NeoPixel strip)
LED_PIN        = PINS["led"]   # data-in of the strip
LED_N          = 10            # number of LEDs
LED_RANGE_NM   = RANGE_NM      # bar spans the whole radar range (RANGE_KM / LED_N = 1.5 km per LED)
LED_SECTOR     = (0, 90)       # only aircraft whose bearing from home is in this sector count:
                               # (from_deg, to_deg) clockwise, 0 = north, 90 = east -> north-east quarter
MIN_CLOSING_KT = 30            # must be closing at least this fast to count as "approaching"
LED_BRIGHT     = 40            # 0-255 brightness when ALL LEDs are lit (closest aircraft)
LED_BRIGHT_MIN = 6             # 0-255 brightness when only the first LED is lit; in between it
                               # scales up with the number of lit LEDs
LED_SPEED      = 25            # bar animation speed, LEDs per second

MISO_PIN = 23                  # unused dummy pin for the SPI bus (D5 on the XIAO)
W, H   = 240, 240
CX, CY = W // 2, H // 2
R      = min(W, H) // 2 - 2

# ------------------------------------------------------------------ framebuffer
# A full 240x240 RGB565 frame is 115 KB, too much next to Wi-Fi/TLS/threads on the C6
# (the MicroPython heap shares RAM with the Wi-Fi stack). So each frame is drawn and pushed
# in horizontal strips of STRIP_H rows that share one small buffer (28.8 KB for 60 rows).
STRIP_H = 30                   # must divide H evenly (two buffers, one per display)
buf  = bytearray(W * STRIP_H * 2)
_fb  = framebuf.FrameBuffer(buf, W, STRIP_H, framebuf.RGB565)

buf2 = bytearray(W * STRIP_H * 2)     # second strip buffer, for display B
_fb2 = framebuf.FrameBuffer(buf2, W, STRIP_H, framebuf.RGB565)

class View:
    """Drawing calls take full-screen coordinates; y0 selects the strip being drawn,
    f the strip buffer (_fb for display A, _fb2 for display B)."""
    y0 = 0
    f = _fb
    def fill(self, c): self.f.fill(c)
    def line(self, x1, y1, x2, y2, c): self.f.line(x1, y1 - self.y0, x2, y2 - self.y0, c)
    def ellipse(self, x, y, rx, ry, c): self.f.ellipse(x, y - self.y0, rx, ry, c)
    def hline(self, x, y, w, c): self.f.hline(x, y - self.y0, w, c)
    def vline(self, x, y, h, c): self.f.vline(x, y - self.y0, h, c)
    def text(self, s, x, y, c): self.f.text(s, x, y - self.y0, c)
    def fill_rect(self, x, y, w, h, c): self.f.fill_rect(x, y - self.y0, w, h, c)
    def poly(self, x, y, coords, c, f=True): self.f.poly(x, y - self.y0, coords, c, f)

fb = View()

# ------------------------------------------------------------------ display
# Pins come from PINS above (see the wiring SVGs). The C6 can route SPI to any GPIO;
# on the DevKitC, GPIO 6/7 are the native SPI pins and run best at high clocks. On the
# XIAO those pins aren't on the headers, so if 60-80 MHz gives garbage, drop back to 40.
# GC9A01 uses SPI mode 0; many CS-less ST7789 modules need polarity=1, phase=1.
spi = SPI(1, baudrate=40_000_000, polarity=0, phase=0,
          sck=Pin(PINS["sck"]), mosi=Pin(PINS["mosi"]),
          miso=Pin(MISO_PIN))   # unused, but must NOT default to GPIO2 (the XIAO's CS pin)

import gc9a01py as drv         # use the driver file's actual module name
cs2 = Pin(PINS["cs2"], Pin.OUT, value=1)       # deselect B while A is initialised (shared RES pulses both)
tft = drv.GC9A01(spi, dc=Pin(PINS["dc"], Pin.OUT), cs=Pin(PINS["cs"], Pin.OUT),
                 reset=Pin(PINS["res"], Pin.OUT), backlight=Pin(PINS["blk"], Pin.OUT),
                 rotation=0)
# display B: same bus/DC/RES/BLK wires, own CS; reset and backlight are already handled by A
tft2 = drv.GC9A01(spi, dc=Pin(PINS["dc"], Pin.OUT), cs=cs2, reset=None, backlight=None,
                  rotation=0)
# ST7789 alternative (check your driver's README for the exact constructor):
# import st7789py as drv
# tft = drv.ST7789(spi, 240, 240, reset=Pin(PINS["res"], Pin.OUT), dc=Pin(PINS["dc"], Pin.OUT),
#                  cs=Pin(PINS["cs"], Pin.OUT), backlight=Pin(PINS["blk"], Pin.OUT), rotation=0)

if BOARD == "XIAO_C6":
    # XIAO RF switch: GPIO3 low enables it, GPIO14 selects the antenna
    # (0 = on-board ceramic antenna, 1 = external U.FL antenna).
    Pin(3, Pin.OUT, value=0)
    Pin(14, Pin.OUT, value=0)

# ------------------------------------------------------------------ LED strip
import neopixel
np = neopixel.NeoPixel(Pin(LED_PIN, Pin.OUT), LED_N)
# Colour of each LED at full scale: green (far) -> yellow -> orange -> red (overhead)
_STOPS = ((0, 255, 0), (255, 190, 0), (255, 70, 0), (255, 0, 0))
LED_COL = []
for i in range(LED_N):
    pos = i / (LED_N - 1) * (len(_STOPS) - 1)      # 0 .. 3 across the strip
    k = min(int(pos), len(_STOPS) - 2)
    f = pos - k
    a, b = _STOPS[k], _STOPS[k + 1]
    LED_COL.append(tuple(int(a[c] + (b[c] - a[c]) * f) for c in range(3)))

# ------------------------------------------------------------------ colours
def rgb(r, g, b):
    """RGB888 -> RGB565, byte-swapped: framebuf stores little-endian,
    SPI panels expect big-endian. If red/blue look swapped, your panel is BGR."""
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)

BLACK = 0
GRID  = rgb(0, 70, 0)
SECTOR = rgb(0, 90, 110)      # dim cyan edges of the LED sector
TEXT  = rgb(0, 150, 0)
BEAM  = rgb(170, 255, 170)

# Afterglow: brightest right behind the beam, quadratic fall-off
TRAIL = [rgb(0, int(190 * (1 - i / TRAIL_STEPS) ** 2) + 12, 0) for i in range(TRAIL_STEPS)]

# Blip brightness levels ("phosphor decay"); small floor so contacts never vanish
LEVELS = 16
BLIP = []
for i in range(LEVELS):
    f = 0.15 + 0.85 * (i / (LEVELS - 1)) ** 1.5
    BLIP.append(rgb(int(110 * f), int(255 * f), int(110 * f)))

# ------------------------------------------------------------------ geometry tables
# Compass convention: 0 deg = north (up), clockwise. Precomputed rim offsets per degree.
D2R = math.pi / 180
EX = array('h', [int(R * math.sin(a * D2R)) for a in range(360)])
EY = array('h', [int(-R * math.cos(a * D2R)) for a in range(360)])

STEP = TRAIL_DEG // TRAIL_STEPS
_tri = array('h', [0, 0, 0, 0, 0, 0])      # reused triangle: centre + two rim points

def wedge(a0, a1, c):
    a0 %= 360
    a1 %= 360
    _tri[2] = EX[a0]; _tri[3] = EY[a0]
    _tri[4] = EX[a1]; _tri[5] = EY[a1]
    fb.poly(CX, CY, _tri, c, True)          # filled triangle, coords relative to centre

def draw_trail(a):
    for i in range(TRAIL_STEPS):
        hi = a - i * STEP
        wedge(hi - STEP, hi, TRAIL[i])

def draw_grid():
    for k in range(1, RANGE_KM // 5 + 1):     # one ring every 5 km
        r = R * k * 5 // RANGE_KM
        fb.ellipse(CX, CY, r, r, GRID)
    fb.hline(CX - R, CY, 2 * R, GRID)
    fb.vline(CX, CY - R, 2 * R, GRID)
    for ang in LED_SECTOR:                  # edges of the sector the LED bar listens to
        a = int(ang) % 360
        fb.line(CX, CY, CX + EX[a], CY + EY[a], SECTOR)
    fb.text("N", CX - 3, CY - R + 4, TEXT)
    fb.text("%dKM" % RANGE_KM, CX + 4, CY + R - 14, TEXT)

# ------------------------------------------------------------------ aircraft data
# Each entry: (east_nm, north_nm, v_east, v_north [nm per ms], t_ms, label, info, alt_ft)
# label = "ICAO TYPE" (e.g. "KLM A21N"), info = "KT FLnnn" (ground speed and flight level)
planes = []

def fetch_once():
    r = requests.get(API_URL.format(HOME_LAT, HOME_LON, int(RANGE_NM) + 1),
                     headers={"User-Agent": "esp32c6-radar"})
    try:
        if r.status_code != 200:
            raise OSError("HTTP %d" % r.status_code)
        data = r.json()
    finally:
        r.close()
    now = time.ticks_ms()
    k = math.cos(HOME_LAT * D2R)            # shrink longitude degrees with latitude
    out = []
    for ac in data.get("ac", ()):
        lat = ac.get("lat"); lon = ac.get("lon")
        if lat is None or lon is None:
            continue
        # alt_baro is feet, or the string "ground"; fall back to GPS altitude
        alt = ac.get("alt_baro")
        if alt == "ground":
            continue
        if not isinstance(alt, (int, float)):
            alt = ac.get("alt_geom")
        if not isinstance(alt, (int, float)) or alt < MIN_ALT_FT:
            continue
        e = (lon - HOME_LON) * 60 * k       # 1 deg latitude = 60 nm
        n = (lat - HOME_LAT) * 60
        v = (ac.get("gs") or 0) / 3_600_000 # knots -> nm per ms
        trk = (ac.get("track") or 0) * D2R
        call = (ac.get("flight") or ac.get("hex") or "").strip()
        # airline callsigns are 3 letters + digits: keep just the ICAO airline code;
        # anything else (private flights, registrations) is shown as-is, shortened
        if len(call) > 3 and call[:3].isalpha() and call[3].isdigit():
            call = call[:3]
        label = "%s %s" % (call[:6], ac.get("t") or "?")
        gs = ac.get("gs")
        fl = "FL%03d" % (int(alt) // 100)
        info = "%d %s" % (gs, fl) if gs is not None else fl
        out.append((e, n, v * math.sin(trk), v * math.cos(trk), now, label, info, int(alt)))
    return out

def fetch_loop():
    global planes
    while True:
        try:
            planes = fetch_once()           # rebinding a name is atomic: no lock needed
        except Exception as e:
            print("fetch failed:", e)
        gc.collect()
        time.sleep(FETCH_S)

SCALE = R / RANGE_NM
RMAX2 = RANGE_NM * RANGE_NM

def project_planes(angle, now):
    """Screen position, colour and label of every plane (computed once per frame).
    Returns (low, high): planes below / above SPLIT_FT, for display A / B."""
    low = []
    high = []
    for e0, n0, ve, vn, t0, label, info, alt in planes:
        dt = time.ticks_diff(now, t0)
        e = e0 + ve * dt                    # dead-reckon between API updates
        n = n0 + vn * dt
        if e * e + n * n > RMAX2:
            continue
        brg = math.atan2(e, n) / D2R        # bearing from home, 0 = north
        lag = (angle - brg) % 360           # degrees since the beam last swept it
        c = BLIP[int((1 - lag / 360) * (LEVELS - 1))]
        x = CX + int(e * SCALE)
        y = CY - int(n * SCALE)
        (low if alt < SPLIT_FT else high).append(
            (x, y, c, label if lag < LABEL_DEG else None, info))   # text only for LABEL_DEG after the beam
    return low, high

def draw_band(i):
    txt = LABELS[i]
    fb.text(txt, CX - 4 * len(txt), CY - R + 16, TEXT)

def draw_planes(pl):
    lo = fb.y0
    hi = lo + STRIP_H
    for x, y, c, label, info in pl:
        if y + 14 < lo or y - 4 >= hi:      # not in this strip
            continue
        fb.fill_rect(x - 1, y - 1, 3, 3, c)
        if label:                           # two lines: callsign, then "TYPE KT"
            w = 8 * max(len(label), len(info))
            tx = x + 4 if x + 4 + w <= W - 12 else x - 4 - w   # flip left near the edge
            fb.text(label, tx, y - 3, c)
            fb.text(info, tx, y + 6, c)

# ------------------------------------------------------------------ LED proximity bar
KT_PER_NM_MS = 3_600_000          # (nm per ms) -> knots

def nearest_inbound(now):
    """Distance (nm) of the closest aircraft (any flight level) inside LED_RANGE_NM and
    LED_SECTOR that is closing on home, or None if there isn't one."""
    best = None
    for e0, n0, ve, vn, t0, label, info, alt in planes:
        dt = time.ticks_diff(now, t0)
        e = e0 + ve * dt
        n = n0 + vn * dt
        d = math.sqrt(e * e + n * n)
        if d > LED_RANGE_NM or d < 0.01:
            continue
        # bearing of the aircraft from home, must lie inside the LED sector
        if (math.atan2(e, n) / D2R - LED_SECTOR[0]) % 360 > (LED_SECTOR[1] - LED_SECTOR[0]) % 360:
            continue
        # closing speed = -(radial velocity); positive means getting closer
        closing_kt = -(e * ve + n * vn) / d * KT_PER_NM_MS
        if closing_kt < MIN_CLOSING_KT:
            continue
        if best is None or d < best:
            best = d
    return best

def led_target(d):
    """Number of LEDs to light: 1 at the edge of LED_RANGE_NM, all of them overhead."""
    if d is None:
        return 0
    return min(LED_N, int((LED_RANGE_NM - d) / LED_RANGE_NM * LED_N) + 1)

led_level = 0.0                   # animated (fractional) bar height
led_goal  = 0                     # where the bar is heading
led_shown = -1                    # what is currently on the strip

def led_update(dt_ms):
    """Move the bar one animation step toward led_goal; write only on change."""
    global led_level, led_shown
    step = LED_SPEED * dt_ms / 1000
    if led_level < led_goal:
        led_level = min(led_goal, led_level + step)
    elif led_level > led_goal:
        led_level = max(led_goal, led_level - step)
    lit = int(led_level + 0.5)
    if lit != led_shown:
        # dim when few LEDs are lit (far away), brightest when all are (overhead)
        br = LED_BRIGHT_MIN + (LED_BRIGHT - LED_BRIGHT_MIN) * (lit - 1) // (LED_N - 1) if lit else 0
        for i in range(LED_N):
            if i < lit:
                r, g, b = LED_COL[i]
                np[i] = (r * br // 255, g * br // 255, b * br // 255)
            else:
                np[i] = (0, 0, 0)
        np.write()
        led_shown = lit

# ------------------------------------------------------------------ main
def wifi():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if not sta.isconnected():
        sta.connect(WIFI_SSID, WIFI_PASS)
        for _ in range(150):
            if sta.isconnected():
                break
            time.sleep_ms(100)
    print("wifi:", sta.isconnected(), sta.ifconfig())

def main():
    global led_goal
    np.fill((0, 0, 0))
    np.write()
    for y0 in range(0, H, STRIP_H):
        fb.y0 = y0
        fb.fill(BLACK)
        fb.text("connecting...", CX - 52, CY - 4, TEXT)
        tft.blit_buffer(buf, 0, y0, W, STRIP_H)
        tft2.blit_buffer(buf, 0, y0, W, STRIP_H)
    wifi()

    _thread.stack_size(16 * 1024)           # TLS + JSON need a bigger stack
    _thread.start_new_thread(fetch_loop, ())

    deg_per_ms = 360 / (SWEEP_S * 1000)
    angle = 0.0
    last = time.ticks_ms()
    while True:
        now = time.ticks_ms()
        dt = time.ticks_diff(now, last)
        last = now
        # advance by elapsed time, so sweep speed is constant whatever the fps
        prev = angle
        angle = (angle + dt * deg_per_ms) % 360
        a = int(angle)

        if angle < prev:                    # beam just passed north: once per sweep
            led_goal = led_target(nearest_inbound(now))   # LED bar looks at every flight level
        led_update(dt)

        low, high = project_planes(angle, now)   # once per frame, shared by all strips
        for y0 in range(0, H, STRIP_H):
            fb.y0 = y0
            fb.f = _fb
            fb.fill(BLACK)
            draw_trail(a)                   # 1. afterglow wedges
            draw_grid()                     # 2. rings on top of the glow
            fb.line(CX, CY, CX + EX[a], CY + EY[a], BEAM)   # 3. the beam itself
            fb.fill_rect(CX - 1, CY - 1, 3, 3, BEAM)        # home marker
            _fb2.blit(_fb, 0, 0)            # same base layer for display B
            draw_band(0)                    # 4. each display: band label + its blips
            draw_planes(low)
            tft.blit_buffer(buf, 0, y0, W, STRIP_H)         # one SPI burst per strip and display
            fb.f = _fb2
            draw_band(1)
            draw_planes(high)
            tft2.blit_buffer(buf2, 0, y0, W, STRIP_H)
        time.sleep_ms(1)                    # let the fetch thread get the GIL

main()
