# Writes BOM.csv from the finished board (refs and counts come from the board file, notes from NOTES below).
# Run with KiCad's python:  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 make_bom.py
import pcbnew, os, csv, collections
here = os.path.dirname(os.path.abspath(__file__))
b = pcbnew.LoadBoard(os.path.join(here, "esp32-radar.kicad_pcb"))
NOTES = {
 "DISPLAY A (LOW) 1x08 socket": ("1x8 female header, 2.54 mm", "Display A socket. Pins must be long enough to take the module's pins."),
 "DISPLAY B (HIGH) 1x08 socket": ("1x8 female header, 2.54 mm", "Display B socket."),
 "XIAO top row (D6..D0)": ("1x7 female header, 2.54 mm", "XIAO socket. The XIAO ships without headers: it needs 2x 1x7 MALE pins soldered on."),
 "XIAO bottom row (D7..5V)": ("1x7 female header, 2.54 mm", "XIAO socket (second row)."),
 "74AHCT125 (DIP-14)": ("DIP-14 IC socket, 7.62 mm row spacing", "For the SN74AHCT125N you already have."),
 "330R (data line)": ("Resistor 330 ohm 1/4 W, axial", "In series with the LED data line."),
 "10k (pull-down)": ("Resistor 10 kohm 1/4 W, axial", "Holds the LED data input low while the XIAO boots."),
 "LED strip: 5V GND DIN": ("Screw terminal 3-way, 5.08 mm pitch, wire entry on the side", "e.g. Phoenix MKDS 1,5/3-5,08 or a generic KF128-5.08 clone. Wire entry faces the board edge."),
 "100nF (display A)": ("Capacitor 100 nF (0.1 uF) ceramic X7R, radial, 2.54 mm lead pitch, 50 V", "No polarity."),
 "100nF (display B)": ("Capacitor 100 nF (0.1 uF) ceramic X7R, radial, 2.54 mm lead pitch, 50 V", "No polarity."),
 "100nF (74AHCT125)": ("Capacitor 100 nF (0.1 uF) ceramic X7R, radial, 2.54 mm lead pitch, 50 V", "No polarity."),
 "10uF ceramic (3V3)": ("Capacitor 10 uF ceramic X7R, radial, 5.08 mm lead pitch, 16 V", "No polarity. A 10 uF electrolytic also works: then + goes to pad 1 (the +3V3 pad)."),
 "1000uF (optional, back)": ("Capacitor 1000 uF electrolytic, radial, 10 mm diameter, 5 mm lead pitch, 10 V or 16 V", "Optional. POLARISED: + to pad 1 (the square pad, +3V3). Mounted on the back of the board."),
 "MountingHole_2.7mm_M2.5": ("M2.5 screw + standoff (optional)", "Four corner holes; only if the case uses them."),
}
rows = collections.OrderedDict()
for fp in sorted(b.GetFootprints(), key=lambda f: (f.GetReference()[0], int(''.join(c for c in f.GetReference() if c.isdigit()) or 0))):
    val = fp.GetValue()
    rows.setdefault(val, []).append(fp.GetReference())
with open(os.path.join(here, "BOM.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Qty", "References", "What to buy", "Notes"])
    for val, refs in rows.items():
        what, note = NOTES.get(val, (val, ""))
        w.writerow([len(refs), " ".join(refs), what, note])
    w.writerow([1, "(U1 chip)", "SN74AHCT125N, DIP-14", "You have it. Goes in the DIP-14 socket."])
    w.writerow([1, "(XIAO)", "Seeed XIAO ESP32-C6", "You have it."])
    w.writerow([2, "(displays)", "GC9A01 1.28 in round display module, 8-pin", "You have them."])
print(open(os.path.join(here, "BOM.csv")).read())
