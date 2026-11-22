# esp32-radar PCB (draft 1)

Carrier board for the dual-display radar: two GC9A01 round modules plug into 1x8 sockets, a XIAO ESP32-C6
plugs into two 1x7 sockets (USB-C to the right), and a 74AHCT125 (DIP-14, in a socket) level-shifts the
WS2812 data line to 5 V. The display modules lie flat on the board, pin row at the top edge, so the whole top half of the board is
covered by the two modules; everything else sits in the strip below them. Everything is through-hole.
Board is about 85 x 79 mm, 2 layers, GND pour both sides.

Regenerate with KiCad's Python (also writes the routing):

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 build_pcb.py

## Nets and pin map
| Net | XIAO pin | Where |
|---|---|---|
| SCL | D10 (GPIO18) | both displays |
| SDA | D9 (GPIO20) | both displays |
| DC | D3 (GPIO21) | both displays |
| RES | D4 (GPIO22) | both displays (shared) |
| BLK | D1 (GPIO1) | both displays |
| CS1 | D2 (GPIO2) | display A (low, below 5000 ft) |
| CS2 | D8 (GPIO19) | display B (high) |
| LED_IN | D0 (GPIO0) | 74AHCT125 pin 2 (10k pull-down) |
| +3V3 / GND / +5V | 3V3 / GND / 5V | power |

Socket order on each display header, left to right, same as the module silkscreen with the pin row at the top:
GND VCC SCL SDA RES DC CS BLK.

## Parts
- 2x 1x8 female header 2.54 mm (displays), 2x 1x7 female header 2.54 mm (XIAO)
- 74AHCT125 in a DIP-14 socket (gate 1 used, unused gates grounded)
- R1 330 ohm (data line), R2 10 kohm (pull-down), both 1/4 W axial
- C1, C2, C3 100 nF ceramic (2.5 mm pitch), C4 10 uF ceramic (5 mm pitch)
- C5 1000 uF electrolytic 10 mm, mounted on the BACK (optional)
- J5 3-way screw terminal 5.08 mm: 5V, GND, DIN (LED strip)
- 4x M2.5 mounting holes (corners; two are optional, see notes)

## Mechanical notes
- Display modules (36 x 44 mm, glass 32.4 mm, pin row 21.5 mm above the glass centre) are drawn on the
  Dwgs.User layer. They sit directly above the board; nothing tall is placed under them (only copper).
- Display centres are 40.64 mm apart.
- The XIAO antenna end (left, opposite USB-C) has a copper keep-out. Keep metal away from it.
- Check before ordering: pin order and pitch against a real module, hole positions against the case, and the
  height of the sockets versus the case depth.
