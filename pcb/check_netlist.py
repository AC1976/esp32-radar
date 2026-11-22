# Reads the finished board and prints the connections as the copper has them, then checks them
# against the pin map in ../main.py. Run with KiCad's python:
#   /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 check_netlist.py
import pcbnew, os, re, collections
here = os.path.dirname(os.path.abspath(__file__))
b = pcbnew.LoadBoard(os.path.join(here, "esp32-radar.kicad_pcb"))
GPIO = {"D0": 0, "D1": 1, "D2": 2, "D3": 21, "D4": 22, "D5": 23, "D6": 16, "D7": 17, "D8": 19, "D9": 20, "D10": 18}
XIAO = {("J3", i + 1): n for i, n in enumerate(["D6", "D5", "D4", "D3", "D2", "D1", "D0"])}
XIAO.update({("J4", i + 1): n for i, n in enumerate(["D7", "D8", "D9", "D10", "3V3", "GND", "5V"])})
DISP = ["GND", "VCC", "SCL", "SDA", "RES", "DC", "CS", "BLK"]
nets = collections.defaultdict(list)
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname(): nets[p.GetNetname()].append((fp.GetReference(), int(p.GetNumber())))
def where(ref, n):
    if ref in ("J1", "J2"): return "display %s pin %d (%s)" % ("A" if ref == "J1" else "B", n, DISP[n - 1])
    return "%s pin %d" % (ref, n)
print("%-5s %-6s %-7s %s" % ("XIAO", "GPIO", "net", "goes to"))
for (ref, n), d in sorted(XIAO.items(), key=lambda kv: (kv[0][0], kv[0][1])):
    net = next((nm for nm, pads in nets.items() if (ref, n) in pads), "-")
    others = [where(r, k) for r, k in nets.get(net, []) if (r, k) != (ref, n) and net not in ("GND",)]
    print("%-5s %-6s %-7s %s" % (d := d if (d := XIAO[(ref, n)]) else "", GPIO.get(d, ""), net, "; ".join(others) or "(nothing)"))
# check against main.py
src = open(os.path.join(here, "..", "main.py")).read()
m = re.search(r'"XIAO_C6":\s*dict\(([^)]*)\)', src)
cfg = dict((k.strip(), int(v)) for k, v in (x.split("=") for x in m.group(1).split("#")[0].split(",")))
want = {"SCL": cfg["sck"], "SDA": cfg["mosi"], "RES": cfg["res"], "DC": cfg["dc"], "CS1": cfg["cs"],
        "BLK": cfg["blk"], "LED_IN": cfg["led"], "CS2": cfg["cs2"]}
bad = 0
for net, gp in want.items():
    xp = [XIAO[(r, k)] for r, k in nets[net] if (r, k) in XIAO]
    ok = len(xp) == 1 and GPIO[xp[0]] == gp
    bad += not ok
    print("%-7s main.py GPIO%-2d  board %s  %s" % (net, gp, xp, "OK" if ok else "MISMATCH"))
print("ALL MATCH main.py" if not bad else "%d MISMATCHES" % bad)
