# Generates esp32-radar.kicad_pcb: 2x GC9A01 round displays + XIAO ESP32-C6 + WS2812 level shifter.
# Run with KiCad's python:  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3 build_pcb.py
# Coordinates: mm, KiCad convention (x right, y DOWN). Header row of the displays is at y = 0.
import pcbnew, heapq, sys, os
try:
    import wx
    _app = wx.App()
except Exception as e:
    print('wx unavailable', e)
FP = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "esp32-radar.kicad_pcb")
mm = pcbnew.FromMM
def V(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))

board = pcbnew.BOARD()
nets = {}
def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n
    return nets[name]

# ------------------------------------------------------------ board outline
X0, Y0, X1, Y1 = -43.18, -9.2, 41.5, 69.5
def line(layer, pts, w=0.1, closed=True):
    for i in range(len(pts) - (0 if closed else 1)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(*a)); s.SetEnd(V(*b)); s.SetLayer(layer); s.SetWidth(mm(w)); board.Add(s)
line(pcbnew.Edge_Cuts, [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)])

# ------------------------------------------------------------ parts
PARTS = {}
def place(lib, name, ref, x, y, rot=0, back=False, value=None):
    fp = pcbnew.FootprintLoad(FP + lib + ".pretty", name)
    fp.SetReference(ref); fp.SetValue(value or name)
    fp.SetPosition(V(x, y))
    if rot: fp.SetOrientationDegrees(rot)
    board.Add(fp); PARTS[ref] = fp
    if back: fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    return fp
def connect(ref, mapping):
    fp = PARTS[ref]
    pads = {p.GetNumber(): p for p in fp.Pads()}
    for num, nm in mapping.items():
        if nm: pads[str(num)].SetNet(net(nm))

SOCK8 = ("Connector_PinSocket_2.54mm", "PinSocket_1x08_P2.54mm_Vertical")
SOCK7 = ("Connector_PinSocket_2.54mm", "PinSocket_1x07_P2.54mm_Vertical")
# display headers, left to right as in the module photo: modules lie flat on the board, pin row at the TOP
DISP = ["GND", "+3V3", "SCL", "SDA", "RES", "DC", "CS1", "BLK"]
DX = 20.32                                   # display centres at x = -DX / +DX
place(*SOCK8, "J1", -DX - 8.89, 0, 90, value="DISPLAY A (LOW) 1x08 socket")
connect("J1", {i + 1: n for i, n in enumerate(DISP)})
place(*SOCK8, "J2", DX - 8.89, 0, 90, value="DISPLAY B (HIGH) 1x08 socket")
connect("J2", {i + 1: ("CS2" if n == "CS1" else n) for i, n in enumerate(DISP)})
# XIAO ESP32-C6, USB-C to the right.  Top row (toward the displays) left to right:
# D6 D5 D4 D3 D2 D1 D0 ; bottom row: D7 D8 D9 D10 3V3 GND 5V
XCX = 31.75
place(*SOCK7, "J3", XCX - 7.62, 47.5, 90, value="XIAO top row (D6..D0)")
connect("J3", {3: "RES", 4: "DC", 5: "CS1", 6: "BLK", 7: "LED_IN"})
place(*SOCK7, "J4", XCX - 7.62, 62.74, 90, value="XIAO bottom row (D7..5V)")
connect("J4", {2: "CS2", 3: "SDA", 4: "SCL", 5: "+3V3", 6: "GND", 7: "+5V"})
# level shifter 74AHCT125 (DIP-14 socket): gate 1 = D0 -> WS2812 data; unused gates grounded
place("Package_DIP", "DIP-14_W7.62mm_Socket", "U1", 2.54, 49.5, value="74AHCT125 (DIP-14)")
connect("U1", {1: "GND", 2: "LED_IN", 3: "LED_5V", 4: "GND", 5: "GND", 7: "GND", 9: "GND",
               10: "GND", 12: "GND", 13: "GND", 14: "+5V"})
RES_FP = ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal")
place(*RES_FP, "R1", -14.0, 58.0, value="330R (data line)")
connect("R1", {1: "LED_5V", 2: "DIN"})
place(*RES_FP, "R2", -14.0, 52.0, value="10k (pull-down)")
connect("R2", {1: "LED_IN", 2: "GND"})
place("TerminalBlock_Phoenix", "TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal", "J5",
      -32.0, 62.0, value="LED strip: 5V GND DIN")
connect("J5", {1: "+5V", 2: "GND", 3: "DIN"})
CAP_S = ("Capacitor_THT", "C_Disc_D3.0mm_W2.0mm_P2.50mm")
CAP_M = ("Capacitor_THT", "C_Disc_D5.0mm_W2.5mm_P5.00mm")
place(*CAP_S, "C1", -27.94, -3.2, value="100nF (display A)"); connect("C1", {1: "GND", 2: "+3V3"})
place(*CAP_S, "C2", 12.7, -3.2, value="100nF (display B)"); connect("C2", {1: "GND", 2: "+3V3"})
place(*CAP_S, "C3", 15.5, 56.0, 90, value="100nF (74AHCT125)"); connect("C3", {1: "+5V", 2: "GND"})
place(*CAP_M, "C4", 15.5, 66.0, 90, value="10uF ceramic (3V3)"); connect("C4", {1: "+3V3", 2: "GND"})
place("Capacitor_THT", "CP_Radial_D10.0mm_P5.00mm", "C5", -26.0, 52.0, back=True,
      value="1000uF (optional, back)"); connect("C5", {1: "+3V3", 2: "GND"})
for i, (hx, hy) in enumerate([(-39.9, -6.0), (38.2, -6.0), (-39.9, 66.5), (39.0, 67.6)]):
    place("MountingHole", "MountingHole_2.7mm_M2.5", "H%d" % (i + 1), hx, hy)

# ------------------------------------------------------------ keep-out under the XIAO antenna end
KO = (19.0, 46.1, 25.4, 64.2)
ko = pcbnew.ZONE(board)
ko.SetIsRuleArea(True); ko.SetDoNotAllowZoneFills(True); ko.SetDoNotAllowTracks(True)
ko.SetDoNotAllowVias(True); ko.SetDoNotAllowPads(False); ko.SetDoNotAllowFootprints(False)
ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu); ko.SetLayerSet(ls)
for p in [(KO[0], KO[1]), (KO[2], KO[1]), (KO[2], KO[3]), (KO[0], KO[3])]:
    ko.AppendCorner(V(*p), -1)
ko.SetZoneName("XIAO antenna keep-out")
board.Add(ko)

# ------------------------------------------------------------ router (2 layers, grid A*)
G = 0.254; C = 0.2; VIA_D, VIA_H = 0.8, 0.4
NX = int((X1 - X0) / G) + 1; NY = int((Y1 - Y0) / G) + 1
def cell(x, y): return round((x - X0) / G), round((y - Y0) / G)
def xy(ix, iy): return X0 + ix * G, Y0 + iy * G
objs = []          # (kind, x1, y1, x2, y2, r, net, layer)  kind 'd' disk (both layers) / 's' segment
padlist = []       # (ref, num, netname, x, y)
for ref, fp in PARTS.items():
    for p in fp.Pads():
        pos = p.GetPosition(); x, y = pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)
        sz = p.GetSize(pcbnew.F_Cu); r = max(pcbnew.ToMM(sz.x), pcbnew.ToMM(sz.y)) / 2
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            dr = p.GetDrillSize(); r = max(pcbnew.ToMM(dr.x), pcbnew.ToMM(dr.y)) / 2 + 0.4
        nm = p.GetNetname()
        objs.append(('d', x, y, x, y, r, nm, -1))
        if nm: padlist.append((ref, p.GetNumber(), nm, x, y))

def build_blocks(netname, w):
    tb = [bytearray(NX * NY), bytearray(NX * NY)]
    vb = [bytearray(NX * NY), bytearray(NX * NY)]
    def rect(arr, xa, ya, xb, yb):
        i0, j0 = cell(xa, ya); i1, j1 = cell(xb, yb)
        for j in range(max(j0, 0), min(j1, NY - 1) + 1):
            row = j * NX
            for i in range(max(i0, 0), min(i1, NX - 1) + 1): arr[row + i] = 1
    def disk(arr, x, y, R):
        i0, j0 = cell(x - R, y - R); i1, j1 = cell(x + R, y + R)
        R2 = R * R
        for j in range(max(j0, 0), min(j1, NY - 1) + 1):
            cy = Y0 + j * G
            for i in range(max(i0, 0), min(i1, NX - 1) + 1):
                cx = X0 + i * G
                if (cx - x) ** 2 + (cy - y) ** 2 <= R2: arr[j * NX + i] = 1
    for o in objs:
        kind, x1, y1, x2, y2, r, nm, layer = o
        if nm == netname and nm: continue
        for l in (0, 1):
            if layer not in (-1, l): continue
            Rt = r + C + w / 2; Rv = r + C + VIA_D / 2
            if kind == 'd':
                disk(tb[l], x1, y1, Rt); disk(vb[l], x1, y1, Rv)
            else:
                rect(tb[l], min(x1, x2) - Rt, min(y1, y2) - Rt, max(x1, x2) + Rt, max(y1, y2) + Rt)
                rect(vb[l], min(x1, x2) - Rv, min(y1, y2) - Rv, max(x1, x2) + Rv, max(y1, y2) + Rv)
    for l in (0, 1):                                    # keep-out and board edge
        for arr, m in ((tb[l], 0.3 + w / 2), (vb[l], 0.3 + VIA_D / 2)):
            rect(arr, KO[0] - m, KO[1] - m, KO[2] + m, KO[3] + m)
            rect(arr, X0 - 1, Y0 - 1, X1 + 1, Y0 + 0.5 + m)
            rect(arr, X0 - 1, Y1 - 0.5 - m, X1 + 1, Y1 + 1)
            rect(arr, X0 - 1, Y0 - 1, X0 + 0.5 + m, Y1 + 1)
            rect(arr, X1 - 0.5 - m, Y0 - 1, X1 + 1, Y1 + 1)
    return tb, vb

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
BEND, VIAC = 4, 20
def astar(srcs, target, tb, vb):
    tx, ty = target
    heap = []; best = {}; parent = {}
    for (l, x, y) in srcs:
        st = (l, x, y, 4); best[st] = 0
        heapq.heappush(heap, (abs(x - tx) + abs(y - ty), 0, st))
    while heap:
        f, g, st = heapq.heappop(heap)
        if best.get(st, 1e18) < g: continue
        l, x, y, d = st
        if x == tx and y == ty:
            path = []
            while st is not None:
                path.append(st[:3]); st = parent.get(st)
            return path[::-1]
        for nd, (dx, dy) in enumerate(DIRS):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < NX and 0 <= ny < NY): continue
            if tb[l][ny * NX + nx] and not (nx == tx and ny == ty): continue
            ng = g + 1 + (BEND if d != 4 and nd != d else 0)
            ns = (l, nx, ny, nd)
            if ng < best.get(ns, 1e18):
                best[ns] = ng; parent[ns] = st
                heapq.heappush(heap, (ng + abs(nx - tx) + abs(ny - ty), ng, ns))
        i = y * NX + x
        if not vb[0][i] and not vb[1][i]:
            ns = (1 - l, x, y, 4); ng = g + VIAC
            if ng < best.get(ns, 1e18):
                best[ns] = ng; parent[ns] = st
                heapq.heappush(heap, (ng + abs(x - tx) + abs(y - ty), ng, ns))
    return None

T_OUT = []; V_OUT = []
def add_track(netname, l, a, b, w):
    T_OUT.append((netname, l, a, b, w))
    objs.append(('s', a[0], a[1], b[0], b[1], w / 2, netname, l))
def add_via(netname, p):
    V_OUT.append((netname, p))
    objs.append(('d', p[0], p[1], p[0], p[1], VIA_D / 2, netname, -1))

def route_all(order):
    failed = []
    for nm, w in order:
        pads = [(x, y) for (_, _, n, x, y) in padlist if n == nm]
        tb, vb = build_blocks(nm, w)
        tree = set()
        c0 = cell(*pads[0]); tree |= {(0,) + c0, (1,) + c0}
        todo = pads[1:]
        while todo:
            def dist(p):
                c = cell(*p); return min(abs(c[0] - t[1]) + abs(c[1] - t[2]) for t in tree)
            todo.sort(key=dist); p = todo.pop(0); c = cell(*p)
            path = astar(list(tree), c, tb, vb)
            if path is None:
                failed.append(nm); print("ROUTE FAILED", nm, p); continue
            pts = [path[0]]; prev = path[0]
            for cur in path[1:]:
                if cur[0] != prev[0]: add_via(nm, xy(cur[1], cur[2]))
                pts.append(cur); prev = cur
            i = 0
            while i < len(pts) - 1:
                a = pts[i]
                if pts[i + 1][0] != a[0]: i += 1; continue
                j = i + 1
                dx, dy = pts[j][1] - a[1], pts[j][2] - a[2]
                while j + 1 < len(pts) and pts[j + 1][0] == a[0] and \
                        (pts[j + 1][1] - pts[j][1], pts[j + 1][2] - pts[j][2]) == (dx, dy): j += 1
                add_track(nm, a[0], xy(a[1], a[2]), xy(pts[j][1], pts[j][2]), w)
                i = j
            for t in path: tree.add(t)
            tree |= {(0,) + c, (1,) + c}
        for (px, py) in pads:                        # stubs from pad centres to grid cells
            cx, cy = xy(*cell(px, py))
            if abs(cx - px) > 1e-3 or abs(cy - py) > 1e-3:
                for l in (0, 1): add_track(nm, l, (px, py), (cx, cy), w)
    return failed

BASE = list(objs)
ORDER = [("GND", 0.4), ("+5V", 0.5), ("+3V3", 0.5), ("CS1", 0.3), ("CS2", 0.3), ("SDA", 0.3), ("SCL", 0.3),
         ("DC", 0.3), ("RES", 0.3), ("BLK", 0.3), ("LED_IN", 0.3), ("LED_5V", 0.3), ("DIN", 0.3)]
GND_ROUTE = [("GND", 0.4)]
for attempt in range(10):
    objs[:] = BASE; T_OUT.clear(); V_OUT.clear()
    failed = route_all(ORDER)
    if not failed: break
    print("attempt", attempt, "failed", failed)
    ORDER = [o for o in ORDER if o[0] in failed] + [o for o in ORDER if o[0] not in failed]
for (nm, l, a, b, w) in T_OUT:
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(V(*a)); t.SetEnd(V(*b)); t.SetWidth(mm(w))
    t.SetLayer(pcbnew.F_Cu if l == 0 else pcbnew.B_Cu); t.SetNet(net(nm)); board.Add(t)
for (nm, p) in V_OUT:
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(*p)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_H)); v.SetNet(net(nm)); board.Add(v)

# ------------------------------------------------------------ GND pour on both layers (+ stitching vias)
gnd = net("GND")
for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(board); z.SetLayer(lay); z.SetNet(gnd)
    for p in [(X0 + 0.3, Y0 + 0.3), (X1 - 0.3, Y0 + 0.3), (X1 - 0.3, Y1 - 0.3), (X0 + 0.3, Y1 - 0.3)]:
        z.AppendCorner(V(*p), -1)
    z.SetMinThickness(mm(0.25)); z.SetLocalClearance(mm(0.3))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(mm(0.3)); z.SetThermalReliefSpokeWidth(mm(0.4))
    board.Add(z)
tb, vb = build_blocks("__stitch__", 0.3)
n_st = 0
STITCH = []
for j in range(NY):
    for i in range(NX):
        x, y = xy(i, j)
        if (round(x / 0.254) % 16 == 0) and (round(y / 0.254) % 16 == 0):   # ~6.1 mm grid
            if not vb[0][j * NX + i] and not vb[1][j * NX + i]:
                v = pcbnew.PCB_VIA(board); v.SetPosition(V(x, y)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_H)); v.SetNet(net("GND")); board.Add(v); n_st += 1; STITCH.append(v)
print("stitching vias:", n_st)

# ------------------------------------------------------------ silkscreen and mechanical drawings
def text(s, x, y, size=1.0, rot=0, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(board); t.SetText(s); t.SetPosition(V(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(0.15))
    if rot: t.SetTextAngle(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
    board.Add(t)
for k, nm in enumerate(DISP):
    text(nm, -DX - 8.89 + 2.54 * k, -6.9, 0.9, 90)
    text(nm if nm != "CS1" else "CS", DX - 8.89 + 2.54 * k, -6.9, 0.9, 90)
text("A LOW <5K", -DX - 5, 3.2, 1.0); text("B HIGH >5K", DX - 5, 3.2, 1.0)
text("USB-C >", 32.0, 55.2, 0.8)
for k, nm in enumerate(["D6", "D5", "D4", "D3", "D2", "D1", "D0"]):          # XIAO pin names, top row
    text(nm, XCX - 7.62 + 2.54 * k, 44.2, 0.8, 90)
for k, nm in enumerate(["D7", "D8", "D9", "D10", "3V3", "GND", "5V"]):        # bottom row
    text(nm, XCX - 7.62 + 2.54 * k, 65.4, 0.8, 90)
text("LED: 5V GND DIN", -32.0, 54.0, 0.8)
text("NO COPPER", 22.2, 55.0, 0.8, 90)
# display module outlines (36 x 44 mm, header centre 21.5 mm below the screen centre) and 32.4 mm glass
for cx in (-DX, DX):
    line(pcbnew.Dwgs_User, [(cx - 18, -0.5), (cx + 18, -0.5), (cx + 18, 43.5), (cx - 18, 43.5)], 0.1)
    c = pcbnew.PCB_SHAPE(board); c.SetShape(pcbnew.SHAPE_T_CIRCLE)
    c.SetCenter(V(cx, 21.5)); c.SetEnd(V(cx + 16.2, 21.5)); c.SetLayer(pcbnew.Dwgs_User); c.SetWidth(mm(0.1))
    board.Add(c)
t = pcbnew.PCB_TEXT(board); t.SetText("display module outline (36x44) + 32.4 glass"); t.SetPosition(V(0, 46.0))
t.SetLayer(pcbnew.Dwgs_User); t.SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2))); board.Add(t)

for ref in ("H1", "H2", "H3", "H4", "C1", "C2", "C4"): PARTS[ref].Reference().SetVisible(False)
zf = pcbnew.ZONE_FILLER(board); zf.Fill(board.Zones())
zones = [z for z in board.Zones() if not z.GetIsRuleArea()]
removed = 0
for v in STITCH:
    ok = all(any(z.GetLayer() == lay and z.HitTestFilledArea(lay, v.GetPosition(), 0) for z in zones)
             for lay in (pcbnew.F_Cu, pcbnew.B_Cu))
    if not ok: board.Remove(v); removed += 1
print("removed unconnected stitching vias:", removed)
zf.Fill(board.Zones())
board.Save(OUT)
print("saved", OUT, "failed:", failed)
