# esp32-radar

A sweeping, radar-style display of nearby aircraft on an ESP32-C6 running MicroPython.
Live ADS-B positions come from the public [adsb.lol](https://api.adsb.lol) API (no key needed) and are
drawn as fading "phosphor" blips under a rotating beam.

## Hardware

- ESP32-C6 board
- 240x240 SPI TFT: GC9A01 (round, recommended) or ST7789 (square)
- Optional second display (same type): low aircraft on one screen, high on the other
- Optional: 10-LED WS2812 (NeoPixel) strip as an inbound-traffic proximity bar

## Wiring

Set `BOARD` at the top of `main.py` to match your board; the pin map follows automatically.

| Signal | Seeed XIAO ESP32C6 (`XIAO_C6`) | ESP32-C6-DevKitC-1 (`DEVKITC`) |
|---|---|---|
| Display VCC (3.3 V only!) | 3V3 | 3V3 |
| Display GND | GND | GND |
| Display SCL (SPI clock) | D10 · GPIO 18 | GPIO 6 |
| Display SDA (SPI MOSI) | D9 · GPIO 20 | GPIO 7 |
| Display RES | D4 · GPIO 22 | GPIO 18 |
| Display DC | D3 · GPIO 21 | GPIO 19 |
| Display CS | D2 · GPIO 2 | GPIO 20 |
| Display BLK | D1 · GPIO 1 | GPIO 21 |
| Display 2 CS (all other pins shared with display 1) | D8 · GPIO 19 | GPIO 23 |
| Strip 5V / GND | 5V / GND | 5V / GND |
| Strip DIN (via 330 ohm) | D0 · GPIO 0 | GPIO 22 |

Display 2 shares SCL, SDA, DC, RES, BLK, VCC and GND with display 1 and only needs its own CS wire.
Without a second display, remove the `tft2` lines in `main.py`.

Diagrams: [`esp32-radar-wiring-xiao.svg`](esp32-radar-wiring-xiao.svg) and
[`esp32-radar-wiring.svg`](esp32-radar-wiring.svg) (DevKitC).

XIAO notes: it ships without headers (solder them first); its 5V pin only carries USB power;
`main.py` drives GPIO3/GPIO14 low to enable the RF switch and select the on-board antenna.

## LED proximity bar

Once per sweep (as the beam passes north) the strip shows the closest aircraft, at any flight
level, that is inside the radar range (`RANGE_KM`), inside `LED_SECTOR` (default: bearing 0-90 deg,
the north-east quarter, drawn as two dim cyan lines on the radar) **and** closing on your position at
`MIN_CLOSING_KT` or more. The bar spans the radar range (10 LEDs = 1.5 km each at 15 km): one LED at
the outer edge, all ten overhead. It animates up or down and goes dark when nothing qualifies.
Colours run green (far), yellow, orange, red (overhead); brightness scales from `LED_BRIGHT_MIN`
with one LED to `LED_BRIGHT` with all ten lit.

Wiring: strip 5V to the board's 5V/VBUS pin (not 3V3), GND to GND, DIN to `LED_PIN` (GPIO 0 on the
XIAO). A 330 ohm resistor in the data line and a common ground are recommended.

## Software

- MicroPython v1.24 or newer for ESP32-C6
- A pure-Python display driver with `blit_buffer()`, e.g.
  [russhughes/gc9a01py](https://github.com/russhughes/gc9a01py) or
  [russhughes/st7789py_mpy](https://github.com/russhughes/st7789py_mpy)

## Setup

1. Flash MicroPython to the ESP32-C6.
2. Copy the display driver `.py` file to the board.
3. Copy `secrets.example.py` to `secrets.py` and fill in your Wi-Fi credentials
   (`secrets.py` is git-ignored).
4. Add your position to `secrets.py` (`HOME_LAT = ...`, `HOME_LON = ...`, decimal degrees) so it
   is not committed, and edit the config block at the top of `main.py` (range, sweep speed, altitude
   bands, LED sector, pins).
5. Copy both files to the board (`mpremote cp main.py secrets.py :`) and reset.

## How it works

Every frame is drawn with MicroPython's built-in `framebuf` module into a small RGB565 buffer,
one horizontal strip at a time (`STRIP_H` rows), and each strip is pushed to the display in one
SPI transfer. The afterglow is a fan of
filled triangles in decreasing brightness; each aircraft's brightness depends on how many
degrees ago the beam passed its bearing. A background thread polls the API every few seconds,
and positions are dead-reckoned from ground speed and track between updates.

## Notes

- Respect the API rate limit (max ~1 request/second).
- **Data source.** `api.airplanes.live` now returns HTTP 403 unless you contact them by email first,
  so `API_URL` points at adsb.lol, which serves the same JSON format. Change `API_URL` to switch.
- **Memory.** A full 240x240 RGB565 frame (115 KB) leaves too little RAM for Wi-Fi, TLS and the
  fetch thread on the C6, so `main.py` draws and sends the frame in strips that share one small
  buffer (28.8 KB). `STRIP_H` must divide 240 evenly.
- **SPI MISO pin.** The display never sends data back, but if no `miso` is given MicroPython uses the
  C6 default (GPIO 2), which is the display CS pin on the XIAO map, and the screen stays dark.
  `main.py` therefore passes a dummy `MISO_PIN` (GPIO 23).
- **Two displays.** Display A (CS D2) shows aircraft from `MIN_ALT_FT` (100 ft) to `SPLIT_FT` (5000 ft),
  display B (CS D8) everything above. The base layer (afterglow, grid, beam) is drawn once per strip and
  copied to the second buffer. Only display A gets the `reset` pin: the RES line is shared, and B's CS is
  held high while A initialises. With two 30-row strip buffers (`STRIP_H = 30`) memory matches the
  single-display build; two 60-row buffers ran out of memory (`ENOMEM` in the fetch thread).
  Positions are dead-reckoned between API calls (`FETCH_S` = 18 s).
- **Labels.** Each blip shows the airline ICAO code from the callsign and the aircraft type, with ground
  speed and flight level beneath (e.g. `KLM A21N` / `250 FL065`). They stay visible for `LABEL_DEG`
  degrees after the beam passes. `KLC` is KLM Cityhopper.
