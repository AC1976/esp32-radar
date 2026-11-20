# esp32-radar

A sweeping, radar-style display of nearby aircraft on an ESP32-C6 running MicroPython.
Live ADS-B positions come from the public [airplanes.live](https://airplanes.live) API and are
drawn as fading "phosphor" blips under a rotating beam.

## Hardware

- ESP32-C6 board
- 240x240 SPI TFT: GC9A01 (round, recommended) or ST7789 (square)
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
| Strip 5V / GND | 5V / GND | 5V / GND |
| Strip DIN (via 330 ohm) | D0 · GPIO 0 | GPIO 22 |

Diagrams: [`esp32-radar-wiring-xiao.svg`](esp32-radar-wiring-xiao.svg) and
[`esp32-radar-wiring.svg`](esp32-radar-wiring.svg) (DevKitC).

XIAO notes: it ships without headers (solder them first); its 5V pin only carries USB power;
`main.py` drives GPIO3/GPIO14 low to enable the RF switch and select the on-board antenna.

## LED proximity bar

Once per sweep (as the beam passes north) the strip shows the closest aircraft that is within
`LED_RANGE_NM` (default 20 nm) **and** closing on your position at `MIN_CLOSING_KT` or more.
Each LED is 2 nm: one LED lights at 18-20 nm, all ten inside 2 nm; the bar animates up or
down to its new height and goes dark when nothing qualifies.

Wiring: strip 5V to the board's 5V/VBUS pin (not 3V3), GND to GND, DIN to `LED_PIN` (GPIO 22).
A 330 ohm resistor in the data line and a common ground are recommended.

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
4. Edit the config block at the top of `main.py`: your latitude/longitude, range, and the SPI
   pins for your wiring.
5. Copy both files to the board (`mpremote cp main.py secrets.py :`) and reset.

## How it works

Every frame is drawn into a single 115 KB RGB565 framebuffer with MicroPython's built-in
`framebuf` module and pushed to the display in one SPI transfer. The afterglow is a fan of
filled triangles in decreasing brightness; each aircraft's brightness depends on how many
degrees ago the beam passed its bearing. A background thread polls the API every few seconds,
and positions are dead-reckoned from ground speed and track between updates.

## Notes

- Respect the API rate limit (max ~1 request/second).
