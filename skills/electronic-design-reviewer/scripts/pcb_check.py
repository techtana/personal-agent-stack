#!/usr/bin/env python3
"""pcb_check.py - layout checks on a .kicad_pcb, mapped to design-guide rule IDs (beta).

Geometry is approximate. Every hit is a LEAD: confirm it in the PCB editor
(highlight the net, inspect the pad) before you report it.

Usage:
  pcb_check.py board.kicad_pcb                       # markdown report
  pcb_check.py board.kicad_pcb --json out.json       # also write JSON
  pcb_check.py board.kicad_pcb --decap-mm 3 --min-ring 0.175 --min-track 0.15
  pcb_check.py board.kicad_pcb --ir VBUS J1.1 U3.1 --current 2   # IR drop along tracks

Checks: stack-up and plane assignment (LAY-01/04/05/06), traces on the Inner1
ground plane (LAY-06), one via per ground pad (LAY-14), decoupling distance
(PLC-02), fiducials (LAY-17), mounting holes (MECH-02), version text (LAY-18),
layer markers (LAY-19), via ring and size (LAY-08/22), track width (LAY-08),
unshielded inductor proximity (PLC-04), floating copper (LAY-07), paste
openings (LAY-24), copper balance (LAY-25), IR drop (LAY-27).
"""
import argparse
import heapq
import json
import math
import os
import re
import sys

VERSION = '1.0.0'
RHO = 1.724e-8

# ---------------------------------------------------------------- S-expressions
_TOK = re.compile(r'\(|\)|"((?:[^"\\]|\\.)*)"|([^\s()"]+)')
_ESC = {'n': '\n', 't': '\t', 'r': '\r'}


def parse_sexpr(text):
    stack = [[]]
    for m in _TOK.finditer(text):
        tok = m.group(0)
        if tok == '(':
            stack.append([])
        elif tok == ')':
            node = stack.pop()
            stack[-1].append(node)
        elif m.group(1) is not None:
            stack[-1].append(re.sub(r'\\(.)', lambda e: _ESC.get(e.group(1), e.group(1)), m.group(1)))
        else:
            stack[-1].append(m.group(2))
    return stack[0][0]


def kids(n, key):
    return [c for c in n[1:] if isinstance(c, list) and c and c[0] == key]


def kid(n, key):
    for c in n[1:]:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def val(n, key, default=None):
    c = kid(n, key)
    if c is not None and len(c) > 1 and not isinstance(c[1], list):
        return c[1]
    return default


def fnum(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def xy(n, key):
    c = kid(n, key)
    if not c or len(c) < 3:
        return None
    return (fnum(c[1]), fnum(c[2]), fnum(c[3]) if len(c) > 3 and not isinstance(c[3], list) else 0.0)


# ---------------------------------------------------------------- naming helpers
_GND_RE = re.compile(r'^(?:[A-Z]{0,4}_?)?(?:GND|GROUND|VSS)(?:_?[A-Z0-9]{0,8})?$')


def base(name):
    return name.rsplit('/', 1)[-1] if name.startswith('/') else name


def is_ground(name):
    b = base(name or '').upper()
    return bool(_GND_RE.match(b)) or b in ('0V', 'EARTH', 'PE', 'CHASSIS')


_RAIL_RE = re.compile(r'^\+?\d+V\d*|^[+-]\d|^V(BUS|IN|BAT|CC|DD|SYS|MOT)|^\+?[AD]?V(CC|DD)|^PWR|_\d+V\d*$|^P\d+V')


def is_rail(name):
    return bool(_RAIL_RE.search(base(name or '').upper()))


def prefix(ref):
    m = re.match(r'^([A-Za-z_#]+)', ref or '')
    return m.group(1).upper() if m else ''


# ---------------------------------------------------------------- geometry
def rot(px, py, deg):
    """KiCad convention: y down, positive angle = counter-clockwise on screen."""
    a = math.radians(deg)
    return px * math.cos(a) + py * math.sin(a), -px * math.sin(a) + py * math.cos(a)


def dist_point_seg(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay), 0.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy)), t


def poly_area(pts):
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def point_in_poly(p, pts):
    x, y = p
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def clip_rect(pts, x0, y0, x1, y1):
    """Sutherland-Hodgman clip of polygon to an axis-aligned rectangle."""
    def clip(poly, inside, inter):
        out = []
        for i in range(len(poly)):
            cur, prev = poly[i], poly[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(inter(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(inter(prev, cur))
        return out

    def ix(xc):
        return lambda p, q: (xc, p[1] + (q[1] - p[1]) * (xc - p[0]) / ((q[0] - p[0]) or 1e-12))

    def iy(yc):
        return lambda p, q: (p[0] + (q[0] - p[0]) * (yc - p[1]) / ((q[1] - p[1]) or 1e-12), yc)

    poly = pts
    for inside, inter in ((lambda p: p[0] >= x0, ix(x0)), (lambda p: p[0] <= x1, ix(x1)),
                          (lambda p: p[1] >= y0, iy(y0)), (lambda p: p[1] <= y1, iy(y1))):
        if not poly:
            break
        poly = clip(poly, inside, inter)
    return poly


def pts_of(node):
    p = kid(node, 'pts')
    if not p:
        return []
    out = []
    for c in p[1:]:
        if isinstance(c, list) and c and c[0] == 'xy':
            out.append((fnum(c[1]), fnum(c[2])))
        elif isinstance(c, list) and c and c[0] == 'arc':
            for k in ('start', 'mid', 'end'):
                q = xy(c, k)
                if q:
                    out.append(q[:2])
    return out


class Grid:
    def __init__(self, cell=1.0):
        self.cell, self.cells = cell, {}

    def add_box(self, item, x0, y0, x1, y1):
        c = self.cell
        for gx in range(int(math.floor(x0 / c)), int(math.floor(x1 / c)) + 1):
            for gy in range(int(math.floor(y0 / c)), int(math.floor(y1 / c)) + 1):
                self.cells.setdefault((gx, gy), []).append(item)

    def near(self, x, y, r=0.0):
        c = self.cell
        seen, out = set(), []
        for gx in range(int(math.floor((x - r) / c)), int(math.floor((x + r) / c)) + 1):
            for gy in range(int(math.floor((y - r) / c)), int(math.floor((y + r) / c)) + 1):
                for it in self.cells.get((gx, gy), ()):
                    if id(it) not in seen:
                        seen.add(id(it))
                        out.append(it)
        return out


class UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


# ---------------------------------------------------------------- board model
class Board:
    def __init__(self, path):
        with open(path, encoding='utf-8') as fh:
            self.root = parse_sexpr(fh.read())
        r = self.root
        self.path = path
        self.nets = {str(n[1]): n[2] for n in kids(r, 'net') if len(n) >= 3}
        self.copper = []
        lay = kid(r, 'layers')
        if lay:
            for L in lay[1:]:
                if isinstance(L, list) and len(L) >= 2 and str(L[1]).endswith('.Cu'):
                    self.copper.append(L[1])
        order = {'F.Cu': -1, 'B.Cu': 999}
        self.copper.sort(key=lambda n: order.get(n, int(re.sub(r'\D', '', n) or 0)))
        self.stack = []
        st = kid(kid(r, 'setup') or ['setup'], 'stackup')
        if st:
            for L in kids(st, 'layer'):
                self.stack.append({'name': L[1], 'type': val(L, 'type', ''), 'thickness': fnum(val(L, 'thickness'), 0.0),
                                   'er': fnum(val(L, 'epsilon_r'), 0.0)})
        self.thickness = fnum(val(kid(r, 'general') or ['general'], 'thickness'), 1.6)
        self.fps, self.pads = [], []
        for fp in kids(r, 'footprint') + kids(r, 'module'):
            self._footprint(fp)
        self.segs, self.vias, self.zones, self.texts = [], [], [], []
        for s in kids(r, 'segment'):
            a, b = xy(s, 'start'), xy(s, 'end')
            if a and b:
                self.segs.append({'a': a[:2], 'b': b[:2], 'w': fnum(val(s, 'width'), 0.25),
                                  'layer': val(s, 'layer', ''), 'net': self._net(kid(s, 'net'))})
        for s in kids(r, 'arc'):
            a, m, b = xy(s, 'start'), xy(s, 'mid'), xy(s, 'end')
            if a and m and b:
                for p, q in ((a, m), (m, b)):
                    self.segs.append({'a': p[:2], 'b': q[:2], 'w': fnum(val(s, 'width'), 0.25),
                                      'layer': val(s, 'layer', ''), 'net': self._net(kid(s, 'net'))})
        for v in kids(r, 'via'):
            at = xy(v, 'at')
            if not at:
                continue
            lays = kid(v, 'layers')
            self.vias.append({'at': at[:2], 'size': fnum(val(v, 'size'), 0.6), 'drill': fnum(val(v, 'drill'), 0.3),
                              'layers': [x for x in (lays[1:] if lays else []) if isinstance(x, str)],
                              'net': self._net(kid(v, 'net'))})
        for z in kids(r, 'zone'):
            layers = [val(z, 'layer')] if val(z, 'layer') else [x for x in (kid(z, 'layers') or [None])[1:] if isinstance(x, str)]
            filled = {}
            for fpoly in kids(z, 'filled_polygon'):
                filled.setdefault(val(fpoly, 'layer', layers[0] if layers else ''), []).append(pts_of(fpoly))
            outline = pts_of(kid(z, 'polygon') or ['polygon'])
            name = val(z, 'net_name')
            if name is None:
                name = self._net(kid(z, 'net'))
            self.zones.append({'net': name or '', 'layers': layers, 'outline': outline, 'filled': filled,
                               'keepout': kid(z, 'keepout') is not None})
        for t in kids(r, 'gr_text'):
            at = xy(t, 'at')
            self.texts.append({'text': t[1] if len(t) > 1 and isinstance(t[1], str) else '',
                               'layer': val(t, 'layer', ''), 'at': at[:2] if at else (0, 0)})
        self.outline = self._outline()

    def _net(self, node):
        if node is None or len(node) < 2:
            return ''
        if len(node) >= 3:
            return node[2]
        v = str(node[1])
        return self.nets.get(v, v) if re.fullmatch(r'\d+', v) else v

    def _footprint(self, fp):
        at = xy(fp, 'at') or (0, 0, 0)
        props = {p[1]: p[2] for p in kids(fp, 'property') if len(p) >= 3 and isinstance(p[2], str)}
        ref, value = props.get('Reference', ''), props.get('Value', '')
        for t in kids(fp, 'fp_text'):
            if len(t) > 2 and t[1] == 'reference' and not ref:
                ref = t[2]
            if len(t) > 2 and t[1] == 'value' and not value:
                value = t[2]
        attr = kid(fp, 'attr')
        f = {'ref': ref, 'value': value, 'lib': fp[1] if isinstance(fp[1], str) else '', 'at': at[:2], 'rot': at[2],
             'layer': val(fp, 'layer', 'F.Cu'), 'attr': [x for x in (attr[1:] if attr else []) if isinstance(x, str)],
             'pads': [], 'props': props}
        for p in kids(fp, 'pad'):
            pat = xy(p, 'at') or (0, 0, 0)
            dx, dy = rot(pat[0], pat[1], at[2])
            size = kid(p, 'size')
            w, h = (fnum(size[1]), fnum(size[2])) if size and len(size) >= 3 else (0.5, 0.5)
            lays = kid(p, 'layers')
            pad = {'fp': f, 'num': str(p[1]) if len(p) > 1 else '', 'type': p[2] if len(p) > 2 else '',
                   'at': (at[0] + dx, at[1] + dy), 'rot': pat[2], 'w': w, 'h': h,
                   'layers': [x for x in (lays[1:] if lays else []) if isinstance(x, str)],
                   'net': self._net(kid(p, 'net')), 'func': val(p, 'pinfunction', '') or '',
                   'ptype': val(p, 'pintype', '') or ''}
            f['pads'].append(pad)
            self.pads.append(pad)
        self.fps.append(f)

    def _outline(self):
        xs, ys = [], []
        for kind in ('gr_line', 'gr_rect', 'gr_arc', 'gr_poly', 'gr_circle'):
            for g in kids(self.root, kind):
                if val(g, 'layer') != 'Edge.Cuts':
                    continue
                for k in ('start', 'end', 'mid', 'center'):
                    q = xy(g, k)
                    if q:
                        xs.append(q[0])
                        ys.append(q[1])
                for q in pts_of(g):
                    xs.append(q[0])
                    ys.append(q[1])
        if not xs:
            for p in self.pads:
                xs.append(p['at'][0])
                ys.append(p['at'][1])
        if not xs:
            return (0, 0, 1, 1)
        return (min(xs), min(ys), max(xs), max(ys))

    def board_area(self):
        x0, y0, x1, y1 = self.outline
        return max((x1 - x0) * (y1 - y0), 1e-9)


def pad_on_layer(pad, layer):
    ls = pad['layers']
    if '*.Cu' in ls:
        return True
    if layer in ls:
        return True
    if 'F&B.Cu' in ls and layer in ('F.Cu', 'B.Cu'):
        return True
    return False


def point_in_pad(p, pad, tol=0.02):
    dx, dy = p[0] - pad['at'][0], p[1] - pad['at'][1]
    for ang in (pad['rot'], pad['rot'] + 90):
        a = math.radians(ang)
        lx = dx * math.cos(a) - dy * math.sin(a)
        ly = dx * math.sin(a) + dy * math.cos(a)
        if abs(lx) <= pad['w'] / 2 + tol and abs(ly) <= pad['h'] / 2 + tol:
            return True
    return False


class Leads:
    def __init__(self):
        self.items, self.info = [], {}

    def add(self, check, rule, sev, title, detail='', where=None):
        self.items.append({'check': check, 'rule': rule, 'severity': sev, 'title': title, 'detail': detail,
                           'where': where or []})


# ---------------------------------------------------------------- checks
def zone_cover(b, layer, pred):
    area = 0.0
    for z in b.zones:
        if z['keepout'] or layer not in z['layers'] or not pred(z['net']):
            continue
        if z['outline']:
            x0, y0, x1, y1 = b.outline
            area += poly_area(clip_rect(z['outline'], x0, y0, x1, y1))
    return min(area / b.board_area(), 1.0)


def check_stackup(b, L):
    n = len(b.copper)
    L.info['copper_layers'] = b.copper
    seg_len = {}
    for s in b.segs:
        seg_len[s['layer']] = seg_len.get(s['layer'], 0.0) + math.dist(s['a'], s['b'])
    total = sum(seg_len.values()) or 1.0
    cover = {lay: zone_cover(b, lay, is_ground) for lay in b.copper}
    L.info['gnd_zone_coverage'] = {k: round(v, 2) for k, v in cover.items()}
    L.info['track_length_mm'] = {k: round(v, 1) for k, v in seg_len.items()}
    if b.stack:
        diel = []
        seen_first = False
        for s in b.stack:
            if s['name'] == 'F.Cu':
                seen_first = True
                continue
            if seen_first and s['type'] in ('core', 'prepreg'):
                diel.append(s['thickness'])
            if seen_first and s['name'].endswith('.Cu'):
                break
        if diel:
            L.info['top_to_L2_dielectric_mm'] = round(sum(diel), 4)
    if n == 2:
        if cover.get('B.Cu', 0) < 0.7:
            L.add('no_bottom_plane', 'LAY-05', 'S2',
                  f"Bottom layer GND coverage {cover.get('B.Cu', 0) * 100:.0f}% (2-layer board)",
                  'Guide 2-layer assignment: bottom = ground plane with as few traces as possible.')
        share = seg_len.get('B.Cu', 0) / total
        if share > 0.3:
            L.add('bottom_traces', 'LAY-05', 'S3', f"{share * 100:.0f}% of track length is on the bottom (ground) layer",
                  'Every trace on the ground layer cuts the plane and lengthens return paths.')
    elif n >= 4:
        l2 = b.copper[1]
        if cover.get(l2, 0) < 0.8:
            L.add('no_l2_plane', 'LAY-04', 'S2', f"{l2} GND coverage only {cover.get(l2, 0) * 100:.0f}%",
                  'Guide: put a solid ground plane on the layer right below the main signal layer (Inner1).')
        if seg_len.get(l2, 0) > 0:
            cnt = sum(1 for s in b.segs if s['layer'] == l2)
            L.add('traces_on_l2', 'LAY-06', 'S2', f"{cnt} track segment(s), {seg_len[l2]:.1f} mm, routed on {l2}",
                  'Guide: Inner1 is a ground plane with only via holes as obstruction - NO TRACES.',
                  where=sorted({s['net'] for s in b.segs if s['layer'] == l2}))
        nets_on_l2 = {z['net'] for z in b.zones if l2 in z['layers'] and not z['keepout'] and z['net']}
        if len(nets_on_l2) > 1:
            L.add('split_plane', 'LAY-06', 'S2', f"{l2} carries zones of several nets: {', '.join(sorted(nets_on_l2))}",
                  'A split reference plane forces return currents around the gap.')


def check_ground_vias(b, L, pour_via_mm=1.0):
    uf = UF()
    gnd_segs = [s for s in b.segs if is_ground(s['net'])]
    grid = Grid(1.0)
    for i, s in enumerate(gnd_segs):
        s['id'] = ('s', i)
        hw = s['w'] / 2
        grid.add_box(s, min(s['a'][0], s['b'][0]) - hw, min(s['a'][1], s['b'][1]) - hw,
                     max(s['a'][0], s['b'][0]) + hw, max(s['a'][1], s['b'][1]) + hw)
    for s in gnd_segs:
        for p in (s['a'], s['b']):
            for o in grid.near(p[0], p[1], s['w']):
                if o is s or o['layer'] != s['layer'] or o['net'] != s['net']:
                    continue
                d, _ = dist_point_seg(p, o['a'], o['b'])
                if d <= o['w'] / 2 + 0.01:
                    uf.union(s['id'], o['id'])
    gnd_vias = [v for v in b.vias if is_ground(v['net'])]
    for j, v in enumerate(gnd_vias):
        v['id'] = ('v', j)
        uf.find(v['id'])
        for s in grid.near(v['at'][0], v['at'][1], v['size']):
            if s['net'] != v['net']:
                continue
            d, _ = dist_point_seg(v['at'], s['a'], s['b'])
            if d < v['size'] / 2 + s['w'] / 2 - 0.01:
                uf.union(v['id'], s['id'])
    pads = [p for p in b.pads if is_ground(p['net']) and p['type'] == 'smd']
    for k, p in enumerate(pads):
        p['id'] = ('p', k)
        uf.find(p['id'])
        lay = 'F.Cu' if pad_on_layer(p, 'F.Cu') else 'B.Cu'
        p['lay'] = lay
        r = max(p['w'], p['h'])
        for s in grid.near(p['at'][0], p['at'][1], r):
            if s['layer'] == lay and s['net'] == p['net'] and (point_in_pad(s['a'], p) or point_in_pad(s['b'], p)):
                uf.union(p['id'], s['id'])
        for v in gnd_vias:
            if v['net'] == p['net'] and point_in_pad(v['at'], p, tol=v['size'] / 2):
                uf.union(p['id'], v['id'])
                p['via_in_pad'] = True
    groups = {}
    for p in pads:
        groups.setdefault(uf.find(p['id']), {'pads': [], 'vias': []})['pads'].append(p)
    for v in gnd_vias:
        g = groups.get(uf.find(v['id']))
        if g is not None:
            g['vias'].append(v)
    pours = {}
    for z in b.zones:
        if is_ground(z['net']) and not z['keepout'] and z['outline']:
            for lay in z['layers']:
                pours.setdefault(lay, []).append(z['outline'])   # outline, not fill: thermal reliefs cut the fill
    result = {'own': 0, 'shared': [], 'pour_far': [], 'none': [], 'pour_ok': 0}
    for g in groups.values():
        assign = {id(p): 0 for p in g['pads']}
        for v in g['vias']:
            near = min(g['pads'], key=lambda p: math.dist(p['at'], v['at']))
            assign[id(near)] += 1
        for p in g['pads']:
            tag = f"{p['fp']['ref']}.{p['num']} @({p['at'][0]:.2f},{p['at'][1]:.2f})"
            if p.get('via_in_pad') or (g['vias'] and assign[id(p)] > 0):
                result['own'] += 1
                continue
            if g['vias']:
                result['shared'].append(tag)
                continue
            in_pour = any(point_in_poly(p['at'], poly) for poly in pours.get(p['lay'], []))
            if in_pour:
                dmin = min((math.dist(p['at'], v['at']) for v in gnd_vias), default=99.0)
                reach = max(p['w'], p['h']) / 2 + pour_via_mm
                if dmin <= reach:
                    result['pour_ok'] += 1
                else:
                    result['pour_far'].append(f"{tag} nearest GND via {dmin:.1f} mm")
            else:
                result['none'].append(tag)
    L.info['ground_pads'] = {'smd_ground_pads': len(pads), 'own_via': result['own'], 'pour_with_near_via': result['pour_ok'],
                             'shared': len(result['shared']), 'pour_far': len(result['pour_far']),
                             'no_via': len(result['none'])}
    if result['shared']:
        L.add('shared_ground_via', 'LAY-14', 'S2', f"{len(result['shared'])} ground pad(s) share a via with other pads",
              'Guide (critical): give each ground connection its own via. Shared vias/traces create common '
              'ground impedance and crosstalk.', where=result['shared'][:40])
    if result['none']:
        L.add('ground_pad_no_via', 'LAY-14', 'S2', f"{len(result['none'])} ground pad(s) reach no via",
              'No via path found from these pads to the ground plane (unrouted, or only via other pads).',
              where=result['none'][:40])
    if result['pour_far']:
        L.add('pour_no_near_via', 'LAY-14', 'S2',
              f"{len(result['pour_far'])} ground pad(s) rely on a same-layer pour with no via within {pour_via_mm} mm",
              'On 2-layer boards the guide wants the via to be the ONLY ground path; on 4-layer boards each '
              'ground pad still needs its own short via to the plane.', where=result['pour_far'][:40])
    if len(b.copper) == 2 and pours.get('F.Cu'):
        L.add('top_ground_pour_2layer', 'LAY-14', 'S3', 'Top-layer ground pour on a 2-layer board',
              'Guide: on 2-layer boards avoid a second ground path on top copper; pads joined by top pour plus '
              'vias form loops that couple noise.')


def check_decaps(b, L, limit_mm):
    decaps = {}
    for f in b.fps:
        if prefix(f['ref']) != 'C':
            continue
        pads = {p['num']: p for p in f['pads'] if p['net']}
        if len(pads) != 2:
            continue
        ps = list(pads.values())
        g = [p for p in ps if is_ground(p['net'])]
        r = [p for p in ps if not is_ground(p['net'])]
        if len(g) == 1 and len(r) == 1:
            decaps.setdefault(r[0]['net'], []).append(r[0])
    far = []
    checked = 0
    for f in b.fps:
        if prefix(f['ref']) not in ('U', 'IC'):
            continue
        for p in f['pads']:
            if not p['net'] or is_ground(p['net']) or p['net'] not in decaps:
                continue
            if p['ptype'] and p['ptype'].split('+')[0] != 'power_in':
                continue
            if not p['ptype'] and not re.match(r'(?i)^(A|D)?V(DD|CC)|^VBAT|^VIN', p['func'] or ''):
                continue
            checked += 1
            best = min(decaps[p['net']], key=lambda c: math.dist(c['at'], p['at']))
            d = math.dist(best['at'], p['at'])
            side = '' if best['fp']['layer'] == f['layer'] else ' (other side)'
            if d > limit_mm:
                far.append(f"{f['ref']}.{p['num']} ({p['func'] or p['net']}): nearest {best['fp']['ref']} at {d:.1f} mm{side}")
    L.info['decap_pins_checked'] = checked
    if far:
        L.add('decap_far', 'PLC-02', 'S2', f"{len(far)} IC power pin(s) with the nearest decoupling cap > {limit_mm:g} mm away",
              'Distance adds loop inductance, which defeats the capacitor at high frequency.', where=far[:40])


def check_fiducials(b, L):
    fids = [f for f in b.fps if 'fiducial' in f['lib'].lower() or prefix(f['ref']) in ('FID', 'FD')]
    x0, y0, x1, y1 = b.outline
    L.info['fiducials'] = [f['ref'] for f in fids]
    if len(fids) < 3:
        L.add('few_fiducials', 'LAY-17', 'S3', f"{len(fids)} fiducial(s) found; guide wants 3 near three corners",
              'Pick-and-place machines use them to align the board (skip only for hand assembly).')
    else:
        best = 0.0
        for i in range(len(fids)):
            for j in range(i + 1, len(fids)):
                for k in range(j + 1, len(fids)):
                    best = max(best, poly_area([fids[i]['at'], fids[j]['at'], fids[k]['at']]))
        if best < 0.25 * b.board_area():
            L.add('fiducials_bunched', 'LAY-17', 'S3', 'Fiducials are not spread to the board corners',
                  'Spread them as far apart as possible for accurate alignment.')
    fine = []
    for f in b.fps:
        smd = [p for p in f['pads'] if p['type'] == 'smd' and p['num'] and any(l.endswith('.Cu') for l in p['layers'])]
        if len(smd) < 8:
            continue
        pitch = min((math.dist(p['at'], q['at']) for i, p in enumerate(smd) for q in smd[i + 1:]
                     if p['num'] != q['num'] and math.dist(p['at'], q['at']) > 0.05), default=9)
        if pitch <= 0.55:
            near = [g for g in fids if math.dist(g['at'], f['at']) < 15]
            if len(near) < 2:
                fine.append(f"{f['ref']} (pitch {pitch:.2f} mm, {len(near)} fiducial(s) within 15 mm)")
    if fine:
        L.add('no_local_fiducials', 'LAY-17', 'S3', 'Fine-pitch parts without local fiducials',
              'Guide: add three local fiducials around fine-pitch areas.', where=fine)


def check_mech_text(b, L):
    holes = [f for f in b.fps if 'mountinghole' in f['lib'].lower().replace('_', '')
             or (f['pads'] and all(p['type'] == 'np_thru_hole' for p in f['pads']) and prefix(f['ref']) in ('H', 'MH'))]
    L.info['mounting_holes'] = len(holes)
    if not holes:
        L.add('no_mounting_holes', 'MECH-02', 'S3', 'No mounting holes found',
              'Fine if the board mounts another way (edge guides, connector). Otherwise add them before layout.')
    silk = [t for t in b.texts if 'SilkS' in t['layer'] or t['layer'].endswith('.Cu')]
    ver = re.compile(r'(?i)\b(v|rev|ver|version|r)\s*[.:]?\s*\d|\$\{REVISION\}|\$\{ISSUE_DATE\}|\b20\d\d[-/.]\d{1,2}'
                     r'|(?<![\w.])\d+\.\d+\.\d+(?![\w.])')
    if not any(ver.search(t['text']) for t in silk):
        L.add('no_version_text', 'LAY-18', 'S3', 'No version/revision text found on silkscreen or copper',
              "Boards without a version get mixed up after the first respin. Add e.g. 'v1.0' or ${REVISION}.")
    marks = {}
    for t in b.texts:
        if t['layer'].endswith('.Cu') and re.fullmatch(r'\s*L?\d{1,2}\s*', t['text'] or ''):
            marks.setdefault(t['layer'], []).append(t['at'])
    missing = [lay for lay in b.copper if lay not in marks]
    L.info['layer_markers'] = sorted(marks)
    if missing and len(b.copper) >= 4:
        L.add('layer_markers', 'LAY-19', 'S3', f"Layer number markers missing on: {', '.join(missing)}",
              'Put 1..N in copper on each layer, stacked at one spot, so the fab can verify layer order.')
    elif missing:
        L.add('layer_markers', 'LAY-19', 'S4', f"Layer number markers missing on: {', '.join(missing)}",
              'Cheap insurance even on 2-layer boards.')


def check_vias_tracks(b, L, min_ring, min_track):
    if b.vias:
        drills = [v['drill'] for v in b.vias]
        rings = [(v['size'] - v['drill']) / 2 for v in b.vias]
        dmin = min(drills)
        at_min = sum(1 for d in drills if abs(d - dmin) < 1e-6) / len(drills)
        L.info['vias'] = {'count': len(b.vias), 'min_drill_mm': dmin, 'min_ring_mm': round(min(rings), 4),
                          'share_at_min_drill': round(at_min, 2)}
        thin = sorted({f"{v['size']:g}/{v['drill']:g}" for v in b.vias if (v['size'] - v['drill']) / 2 < min_ring - 1e-6})
        if thin:
            L.add('via_ring', 'LAY-08', 'S2', f"Via annular ring below {min_ring:g} mm (size/drill: {', '.join(thin)})",
                  'Check against your fab minimum; thin rings risk breakout and opens.')
        if dmin <= 0.25 and at_min > 0.8 and len(b.vias) > 10:
            L.add('smallest_vias_everywhere', 'LAY-22', 'S3', f"{at_min * 100:.0f}% of vias use the minimum drill {dmin:g} mm",
                  'Guide: use the smallest vias only where pitch forces it; larger vias are more reliable and lower impedance.')
    if b.segs:
        wmin = min(s['w'] for s in b.segs)
        L.info['min_track_mm'] = wmin
        if wmin < min_track - 1e-6:
            L.add('thin_track', 'LAY-08', 'S2', f"Tracks as narrow as {wmin:g} mm (< {min_track:g} mm)",
                  'Confirm your fab supports this width at your copper weight.')
        power = {}
        for s in b.segs:
            if is_rail(s['net']):
                power[s['net']] = min(power.get(s['net'], 9e9), s['w'])
        L.info['min_width_on_power_nets_mm'] = power


def check_inductors(b, L, pairs_mm=None):
    inds = [f for f in b.fps if prefix(f['ref']) == 'L' and not re.search(r'(?i)ferrite|bead|FB', f['lib'] + f['value'])]
    near = []
    for i, a in enumerate(inds):
        for c in inds[i + 1:]:
            ext = lambda f: max([math.dist(p['at'], f['at']) + max(p['w'], p['h']) / 2 for p in f['pads']] or [1.0])
            lim = pairs_mm or 2 * (ext(a) + ext(c))
            d = math.dist(a['at'], c['at'])
            if d < lim:
                near.append(f"{a['ref']}-{c['ref']} {d:.1f} mm")
    if near:
        L.add('inductor_proximity', 'PLC-04', 'S2', 'Inductors placed close together',
              'Guide: never place unshielded inductors in line; they couple magnetically. Confirm shielded parts '
              'or rotate/separate them.', where=near)


def check_floating_and_paste(b, L):
    floating = [z for z in b.zones if not z['keepout'] and not z['net'] and any(l.endswith('.Cu') for l in z['layers'])]
    if floating:
        L.add('floating_copper', 'LAY-07', 'S3', f"{len(floating)} copper zone(s) with no net",
              'Floating copper can resonate (RF) and couples noise. Tie it to GND or delete it.',
              where=[','.join(z['layers']) for z in floating])
    nopaste = []
    for p in b.pads:
        f = p['fp']
        if p['type'] != 'smd' or re.search(r'(?i)fiducial|testpoint|nettie|logo|mountinghole', f['lib']):
            continue
        cu = 'F' if 'F.Cu' in p['layers'] else 'B' if 'B.Cu' in p['layers'] else None
        if cu and f"{cu}.Paste" not in p['layers'] and f"{cu}.Mask" in p['layers'] and p['net']:
            apertures = [q for q in f['pads'] if f"{cu}.Paste" in q['layers'] and f"{cu}.Cu" not in q['layers']]
            if any(point_in_pad(q['at'], p, tol=0.05) for q in apertures):
                continue                      # custom paste aperture pad covers this pad
            nopaste.append(f"{f['ref']}.{p['num']}")
    if nopaste:
        L.add('pads_without_paste', 'LAY-24', 'S3', f"{len(nopaste)} SMD pad(s) without a paste opening",
              'No paste = no solder on that pad. Intentional only for test pads and some thermal pads.',
              where=nopaste[:40])


def check_balance(b, L):
    x0, y0, x1, y1 = b.outline
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    quads = {'TL': (x0, y0, mx, my), 'TR': (mx, y0, x1, my), 'BL': (x0, my, mx, y1), 'BR': (mx, my, x1, y1)}
    qa = (mx - x0) * (my - y0) or 1e-9
    has_fill = any(z['filled'] for z in b.zones)
    per_layer = {}
    for lay in b.copper:
        q = {k: 0.0 for k in quads}
        for z in b.zones:
            if z['keepout'] or lay not in z['layers']:
                continue
            for poly in z['filled'].get(lay, []):
                for k, r in quads.items():
                    c = clip_rect(poly, *r)
                    if len(c) >= 3:
                        q[k] += poly_area(c)
        for s in b.segs:
            if s['layer'] != lay:
                continue
            m = ((s['a'][0] + s['b'][0]) / 2, (s['a'][1] + s['b'][1]) / 2)
            k = ('T' if m[1] < my else 'B') + ('L' if m[0] < mx else 'R')
            q[k] += math.dist(s['a'], s['b']) * s['w']
        for p in b.pads:
            if pad_on_layer(p, lay):
                k = ('T' if p['at'][1] < my else 'B') + ('L' if p['at'][0] < mx else 'R')
                q[k] += p['w'] * p['h']
        per_layer[lay] = {k: min(v / qa, 1.0) for k, v in q.items()}
    L.info['copper_fraction_by_quadrant'] = {k: {q: round(v, 2) for q, v in d.items()} for k, d in per_layer.items()}
    if not has_fill and any(not z['keepout'] for z in b.zones):
        L.info['balance_note'] = 'Zones are not filled in the saved file: refill (B) and save for a real balance check.'
        return
    avg = {k: sum(per_layer[l][k] for l in per_layer) / max(len(per_layer), 1) for k in quads}
    spread = max(avg.values()) - min(avg.values())
    if spread > 0.4:
        L.add('copper_imbalance', 'LAY-25', 'S3', f"Copper density differs by {spread * 100:.0f} points between board quadrants",
              'Uneven copper can bow the board or bond poorly in lamination. Fill empty areas with stitched ground.')
    n = len(b.copper)
    for i in range(n // 2):
        a, c = b.copper[i], b.copper[n - 1 - i]
        fa = sum(per_layer[a].values()) / 4
        fc = sum(per_layer[c].values()) / 4
        if abs(fa - fc) > 0.4:
            L.add('layer_imbalance', 'LAY-25', 'S3', f"{a} ({fa * 100:.0f}%) vs {c} ({fc * 100:.0f}%) copper differs a lot",
                  'Mirror-pair layers should carry similar copper to keep the board flat.')


def ir_path(b, net, src, dst, current):
    thick = {}
    for s in b.stack:
        if s['name'].endswith('.Cu') and s['thickness']:
            thick[s['name']] = s['thickness']
    segs = [s for s in b.segs if s['net'] == net]
    pads = {f"{p['fp']['ref']}.{p['num']}": p for p in b.pads if p['net'] == net}
    vias = [v for v in b.vias if v['net'] == net]
    if src not in pads or dst not in pads:
        return {'error': f"pads not found on net {net}: have {sorted(pads)[:20]}"}
    G = {}

    def edge(a, c, r, info=None):
        G.setdefault(a, []).append((c, r, info))
        G.setdefault(c, []).append((a, r, info))

    def key(p, lay):
        return (round(p[0], 3), round(p[1], 3), lay)

    for i, s in enumerate(segs):
        t = thick.get(s['layer'], 0.035)
        R = RHO * (math.dist(s['a'], s['b']) * 1e-3) / ((s['w'] * 1e-3) * (t * 1e-3))
        edge(key(s['a'], s['layer']), key(s['b'], s['layer']), R, s)
    for i, s in enumerate(segs):
        for p in (s['a'], s['b']):
            for o in segs:
                if o is s or o['layer'] != s['layer']:
                    continue
                d, f = dist_point_seg(p, o['a'], o['b'])
                if d <= o['w'] / 2 + 0.01 and 0.0 < f < 1.0:
                    t = thick.get(o['layer'], 0.035)
                    Ro = RHO * (math.dist(o['a'], o['b']) * 1e-3) / ((o['w'] * 1e-3) * (t * 1e-3))
                    edge(key(p, s['layer']), key(o['a'], o['layer']), Ro * f, o)
                    edge(key(p, s['layer']), key(o['b'], o['layer']), Ro * (1 - f), o)
    for name, p in pads.items():
        for s in segs:
            for q in (s['a'], s['b']):
                if pad_on_layer(p, s['layer']) and point_in_pad(q, p):
                    edge(('pad', name), key(q, s['layer']), 0.0)
    for j, v in enumerate(vias):
        for s in segs:
            for q in (s['a'], s['b']):
                if math.dist(q, v['at']) <= v['size'] / 2 + 0.01:
                    edge(('via', j), key(q, s['layer']), 0.0)
        for name, p in pads.items():
            if point_in_pad(v['at'], p, tol=v['size'] / 2):
                edge(('via', j), ('pad', name), 0.0)
    start, goal = ('pad', src), ('pad', dst)
    dist = {start: 0.0}
    prev = {}
    pq = [(0.0, 0, start)]
    cnt = 1
    while pq:
        d, _, u = heapq.heappop(pq)
        if u == goal:
            break
        if d > dist.get(u, 9e99):
            continue
        for w, r, info in G.get(u, []):
            nd = d + r
            if nd < dist.get(w, 9e99):
                dist[w] = nd
                prev[w] = (u, info)
                heapq.heappush(pq, (nd, cnt, w))
                cnt += 1
    if goal not in dist:
        return {'error': f"no track path from {src} to {dst} on {net} (zones are ignored)"}
    narrow, n = None, goal
    while n in prev:
        n, info = prev[n]
        if info and (narrow is None or info['w'] < narrow['w']):
            narrow = info
    R = dist[goal]
    out = {'net': net, 'from': src, 'to': dst, 'r_ohm': R, 'narrowest_mm': narrow['w'] if narrow else None}
    if current:
        out.update({'current_a': current, 'drop_v': R * current, 'loss_w': R * current * current})
    return out


SEV_ORDER = {'S1': 0, 'S2': 1, 'S3': 2, 'S4': 3}


def to_markdown(b, L):
    out = ['# pcb_check report (beta)', '',
           f"Board: `{os.path.basename(b.path)}` · {len(b.copper)} copper layers · {len(b.fps)} footprints · "
           f"{len(b.segs)} track segments · {len(b.vias)} vias · tool v{VERSION}", '',
           '> Geometry is approximate. Every item is a **lead**: confirm it in the PCB editor before reporting.', '']
    items = sorted(L.items, key=lambda i: (SEV_ORDER[i['severity']], i['rule']))
    if items:
        out += ['| Sev | Rule | Lead | Why it matters |', '|---|---|---|---|']
        for i in items:
            out.append(f"| {i['severity']} | {i['rule']} | {i['title']} | {i['detail']} |")
        out.append('')
        for i in items:
            if i['where']:
                out.append(f"**{i['rule']} {i['check']}:** " + '; '.join(i['where']))
                out.append('')
    else:
        out += ['No leads.', '']
    out.append('## Board facts')
    for k, v in L.info.items():
        out.append(f"- **{k}:** {json.dumps(v, default=str)}")
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pcb')
    ap.add_argument('--json', help="write JSON here ('-' = stdout instead of markdown)")
    ap.add_argument('--decap-mm', type=float, default=3.0)
    ap.add_argument('--pour-via-mm', type=float, default=1.0)
    ap.add_argument('--min-ring', type=float, default=0.175)
    ap.add_argument('--min-track', type=float, default=0.15)
    ap.add_argument('--ir', nargs=3, metavar=('NET', 'FROM_PAD', 'TO_PAD'), help='e.g. VBUS J1.1 U3.1')
    ap.add_argument('--current', type=float, help='amps for --ir')
    a = ap.parse_args(argv)
    b = Board(a.pcb)
    L = Leads()
    for chk, args in ((check_stackup, ()), (check_ground_vias, (a.pour_via_mm,)), (check_decaps, (a.decap_mm,)),
                      (check_fiducials, ()), (check_mech_text, ()), (check_vias_tracks, (a.min_ring, a.min_track)),
                      (check_inductors, ()), (check_floating_and_paste, ()), (check_balance, ())):
        try:
            chk(b, L, *args)
        except Exception as e:
            L.info.setdefault('check_errors', []).append(f"{chk.__name__}: {type(e).__name__}: {e}")
    if a.ir:
        L.info['ir_path'] = ir_path(b, a.ir[0], a.ir[1], a.ir[2], a.current)
    data = {'tool': 'pcb_check', 'version': VERSION, 'board': a.pcb, 'leads': L.items, 'info': L.info}
    if a.json == '-':
        print(json.dumps(data, indent=2, default=str))
        return
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(data, fh, indent=2, default=str)
    print(to_markdown(b, L))


if __name__ == '__main__':
    main()
