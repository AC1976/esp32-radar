# esp32-radar

A sweeping, radar-style display of nearby aircraft on an ESP32-C6 running MicroPython.
Live ADS-B positions come from the public [airplanes.live](https://airplanes.live) API and are
drawn as fading "phosphor" blips under a rotating beam.

## Hardware

- ESP32-C6 board
- 240x240 SPI TFT: GC9A01 (round, recommended) or ST7789 (square)

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
