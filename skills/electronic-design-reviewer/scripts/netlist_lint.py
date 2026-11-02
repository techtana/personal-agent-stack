#!/usr/bin/env python3
"""netlist_lint.py - schematic-level checks mapped to design-guide rule IDs.

Reads a KiCad netlist (.net S-expression or .xml), a CSV pin list, or a
.kicad_pcb (pads carry nets). Every hit is a LEAD: confirm it before you report
it as a finding. Rule IDs refer to references/guide-rosenberg-v5.md.

Usage:
  netlist_lint.py design.net                      # markdown report to stdout
  netlist_lint.py design.net --json out.json      # also write JSON
  netlist_lint.py design.xml --nets               # add a named-net index
  netlist_lint.py board.kicad_pcb                 # netlist recovered from the PCB
  netlist_lint.py pins.csv --bom bom.csv          # CSV: net,ref,pin[,pintype][,pinfunction]
  netlist_lint.py design.net --sch root.kicad_sch # add schematic readability stats

Export a netlist with KiCad 8+:  kicad-cli sch export netlist -o design.net root.kicad_sch
"""
import argparse
import csv
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

VERSION = '1.0.0'

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
            if len(stack) == 1:
                raise ValueError('unbalanced ")"')
            node = stack.pop()
            stack[-1].append(node)
        elif m.group(1) is not None:
            stack[-1].append(re.sub(r'\\(.)', lambda e: _ESC.get(e.group(1), e.group(1)), m.group(1)))
        else:
            stack[-1].append(m.group(2))
    if len(stack) != 1 or not stack[0]:
        raise ValueError('unbalanced "(" or empty file')
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


# ---------------------------------------------------------------- value parsing
_MULT = {'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'μ': 1e-6, 'm': 1e-3,
         'k': 1e3, 'K': 1e3, 'M': 1e6, 'MEG': 1e6, 'meg': 1e6, 'G': 1e9, 'R': 1.0, 'r': 1.0}
_VAL_RE = re.compile(r'^\s*(\d*\.?\d+)\s*(meg|MEG|[fpnuµμmkKMGRr])?(\d*)\s*'
                     r'(?:ohms?|Ω|F|H|f|h)?(?![A-Za-z0-9])')


def parse_value(text, kind='R'):
    """Return (value, explicit_multiplier) or (None, False). kind: R, C or L."""
    if text is None:
        return None, False
    s = str(text).strip().replace(',', '.')
    m = re.match(r'^[Rr](\d+)\b', s)
    if m and kind == 'R':
        return float('0.' + m.group(1)), True
    m = _VAL_RE.match(s)
    if not m:
        return None, False
    num, mult, frac = m.groups()
    if frac:
        if '.' in num or not mult:
            return None, False
        num = num + '.' + frac
    if kind == 'C' and mult == 'M':
        mult = 'm'                  # 1M as capacitance is meaningless; treat as milli
    v = float(num) * (_MULT[mult] if mult else 1.0)
    return v, bool(mult)


def voltage_rating(comp):
    """Voltage rating from fields or value text ('100u/25V', '10u 6V3', field Voltage=16V)."""
    for k, v in comp['fields'].items():
        nk = re.sub(r'[^a-z]', '', k.lower())
        if nk in ('voltage', 'ratedvoltage', 'voltagerating', 'v', 'vrated', 'vmax', 'ratingvoltage'):
            m = re.search(r'(\d+(?:\.\d+)?)\s*V?(\d*)', v)
            if m:
                return float(m.group(1) + ('.' + m.group(2) if m.group(2) else ''))
    text = ' '.join([comp['value'] or '', comp['description'] or ''] +
                    [v for k, v in comp['fields'].items() if k.lower() not in ('footprint', 'datasheet')])
    m = re.search(r'(?<![\d.])(\d+)V(\d+)(?![\d])', text)            # RKM: 6V3
    if m:
        return float(m.group(1) + '.' + m.group(2))
    m = re.search(r'(?<![\w.])(\d+(?:\.\d+)?)\s*V(?:DC|dc)?(?![A-Za-z0-9])', text)
    if m:
        return float(m.group(1))
    return None


def dielectric(comp):
    text = ' '.join([comp['value'] or '', comp['description'] or ''] + list(comp['fields'].values()))
    m = re.search(r'\b(C0G|NP0|NPO|X5R|X7R|X6S|X7S|X8R|X7T|Y5V|Z5U|U2J)\b', text.upper())
    if not m:
        return None
    return {'NPO': 'NP0'}.get(m.group(1), m.group(1))


# ---------------------------------------------------------------- net naming
def base_name(name):
    if name.startswith('/') and not name.startswith('/Net-(') and '/unconnected-(' not in name:
        return name.rsplit('/', 1)[-1] or name
    return name.lstrip('/')


def is_auto(name):
    return 'Net-(' in name or 'unconnected-(' in name or name.startswith('N$') or name == ''


def is_unconnected_auto(name):
    return 'unconnected-(' in name


_GND_RE = re.compile(r'^(?:[A-Z]{0,4}_?)?(?:GND|GROUND|VSS)(?:_?[A-Z0-9]{0,8})?$')
_CHASSIS_RE = re.compile(r'EARTH|CHASSIS|SHIELD|SHLD|^PE$|^FG$|FRAME')


def is_ground(name):
    b = base_name(name).upper().replace(' ', '')
    return bool(_GND_RE.match(b)) or b in ('0V', '0', 'EARTH', 'PE', 'CHASSIS', 'SHIELD') or \
        bool(_CHASSIS_RE.search(b) and ('GND' in b or b in ('EARTH', 'PE', 'CHASSIS', 'SHIELD', 'FG')))


def is_chassis(name):
    return bool(_CHASSIS_RE.search(base_name(name).upper()))


_POWER_WORDS = re.compile(r'^\+?(?:[AD]?VDD[A-Z0-9]*|[AD]?VCC[A-Z0-9]*|VIN|VBAT\w*|VBATT|VCELL|VSYS|VBUS|VUSB|'
                          r'VMOT|VM|VPP|VREF\w*|VLED|PWR\w*|BATT?\+?|\+BATT?|V\+|VS|VSUPPLY|SUPPLY|VDDIO|VCCIO)$')


def rail_voltage(name):
    """Voltage implied by a net name: +3V3 -> 3.3, VDD_1V8 -> 1.8, -12V -> -12, VBUS -> 5."""
    b = base_name(name).upper().replace(' ', '')
    if b in ('VBUS', 'VUSB', 'USB_VBUS', 'VBUS_USB', 'USB5V', '+VBUS'):
        return 5.0
    pats = [
        (r'^([+-]?)(\d+)V(\d+)(?:$|_)', None),
        (r'^([+-]?)(\d+(?:\.\d+)?)V(?:$|_)', None),
        (r'^([PN])(\d+)V(\d*)(?:$|_)', 'PN'),
        (r'^V(\d+)P(\d+)(?:$|_)', 'VP'),
        (r'^(?:[A-Z]*V[A-Z]*|PWR[A-Z]*)_([+-]?)(\d+(?:\.\d+)?)V(\d*)(?:$|_)', None),
    ]
    for pat, kind in pats:
        m = re.match(pat, b)
        if not m:
            continue
        g = m.groups()
        if kind == 'VP':
            return float(f"{g[0]}.{g[1]}")
        if kind == 'PN':
            v = float(g[1] + ('.' + g[2] if g[2] else ''))
            return -v if g[0] == 'N' else v
        sign = -1.0 if g[0] == '-' else 1.0
        num = g[1]
        frac = g[2] if len(g) > 2 else ''
        v = float(num + ('.' + frac if frac and '.' not in num else ''))
        return sign * v
    return None


def is_power_name(name):
    return bool(_POWER_WORDS.match(base_name(name).upper().replace(' ', '')))


# ---------------------------------------------------------------- loaders
def new_comp(ref):
    return {'ref': ref, 'value': '', 'footprint': '', 'lib': '', 'part': '', 'description': '',
            'fields': {}, 'props': {}, 'dnp': False, 'exclude_bom': False}


def finish_comp(c):
    for k, v in c['fields'].items():
        nk = re.sub(r'[^a-z]', '', k.lower())
        vv = (v or '').strip().lower()
        if nk in ('dnp', 'donotpopulate', 'donotplace', 'nopop', 'dnf', 'notfitted'):
            if vv in ('1', 'yes', 'y', 'true', 'dnp', 'x', 'dnf', 'nf'):
                c['dnp'] = True
        if nk in ('populate', 'fitted', 'mounted', 'place') and vv in ('0', 'no', 'n', 'false'):
            c['dnp'] = True
    for k in c['props']:
        if k.lower() == 'dnp':
            c['dnp'] = True
        if k.lower() == 'exclude_from_bom':
            c['exclude_bom'] = True
    return c


def load_kicad_sexpr(text):
    root = parse_sexpr(text)
    comps, nets = {}, {}
    for comp in kids(kid(root, 'components') or ['components'], 'comp'):
        c = new_comp(val(comp, 'ref', '?'))
        c['value'] = val(comp, 'value', '') or ''
        c['footprint'] = val(comp, 'footprint', '') or ''
        c['description'] = val(comp, 'description', '') or ''
        ls = kid(comp, 'libsource')
        if ls:
            c['lib'] = val(ls, 'lib', '') or ''
            c['part'] = val(ls, 'part', '') or ''
            c['description'] = c['description'] or (val(ls, 'description', '') or '')
        fl = kid(comp, 'fields')
        if fl:
            for f in kids(fl, 'field'):
                nm = val(f, 'name', '')
                txt = f[2] if len(f) > 2 and isinstance(f[2], str) else ''
                c['fields'][nm] = txt
        for p in kids(comp, 'property'):
            c['props'][val(p, 'name', '')] = val(p, 'value', '') or ''
        comps[c['ref']] = finish_comp(c)
    for net in kids(kid(root, 'nets') or ['nets'], 'net'):
        name = val(net, 'name', '') or f"code{val(net, 'code', '?')}"
        nodes = []
        for nd in kids(net, 'node'):
            nodes.append({'ref': val(nd, 'ref', '?'), 'pin': str(val(nd, 'pin', '?')),
                          'func': val(nd, 'pinfunction', '') or '', 'type': val(nd, 'pintype', '') or ''})
        nets[name] = nodes
    return comps, nets


def load_kicad_xml(path):
    root = ET.parse(path).getroot()
    comps, nets = {}, {}
    for comp in root.iter('comp'):
        c = new_comp(comp.get('ref', '?'))
        c['value'] = comp.findtext('value') or ''
        c['footprint'] = comp.findtext('footprint') or ''
        c['description'] = comp.findtext('description') or ''
        ls = comp.find('libsource')
        if ls is not None:
            c['lib'], c['part'] = ls.get('lib', ''), ls.get('part', '')
            c['description'] = c['description'] or ls.get('description', '')
        for f in comp.findall('fields/field'):
            c['fields'][f.get('name', '')] = f.text or ''
        for p in comp.findall('property'):
            c['props'][p.get('name', '')] = p.get('value', '')
        comps[c['ref']] = finish_comp(c)
    for net in root.iter('net'):
        name = net.get('name') or f"code{net.get('code')}"
        nets[name] = [{'ref': n.get('ref', '?'), 'pin': n.get('pin', '?'),
                       'func': n.get('pinfunction', ''), 'type': n.get('pintype', '')}
                      for n in net.findall('node')]
    return comps, nets


def load_pcb(text):
    root = parse_sexpr(text)
    table = {}
    for n in kids(root, 'net'):
        if len(n) >= 3:
            table[str(n[1])] = n[2]
    comps, nets = {}, {}
    for fp in kids(root, 'footprint') + kids(root, 'module'):
        props = {p[1]: p[2] for p in kids(fp, 'property') if len(p) >= 3 and isinstance(p[2], str)}
        ref, value = props.get('Reference'), props.get('Value')
        for t in kids(fp, 'fp_text'):
            if len(t) > 2 and t[1] == 'reference':
                ref = ref or t[2]
            if len(t) > 2 and t[1] == 'value':
                value = value or t[2]
        if not ref:
            continue
        c = new_comp(ref)
        c['value'] = value or ''
        c['footprint'] = fp[1] if len(fp) > 1 and isinstance(fp[1], str) else ''
        c['description'] = props.get('Description', '')
        c['fields'] = {k: v for k, v in props.items() if k not in ('Reference', 'Value')}
        attr = kid(fp, 'attr')
        flags = [x for x in attr[1:] if isinstance(x, str)] if attr else []
        if 'dnp' in flags:
            c['props']['dnp'] = ''
        if 'exclude_from_bom' in flags:
            c['props']['exclude_from_bom'] = ''
        comps[ref] = finish_comp(c)
        seen = set()
        for pad in kids(fp, 'pad'):
            num = str(pad[1]) if len(pad) > 1 else ''
            if (ref, num) in seen or num == '':
                continue
            seen.add((ref, num))
            nc = kid(pad, 'net')
            name = None
            if nc is not None:
                if len(nc) >= 3:
                    name = nc[2]
                elif len(nc) == 2:
                    name = table.get(str(nc[1]), str(nc[1]))
            ptype = val(pad, 'pintype', '') or ''
            if not name:
                if not ptype:
                    continue
                name = f"unconnected-({ref}-Pad{num})"
            nets.setdefault(name, []).append({'ref': ref, 'pin': num, 'func': val(pad, 'pinfunction', '') or '',
                                              'type': ptype})
    return comps, nets


def _col(row, *names):
    low = {re.sub(r'[^a-z]', '', k.lower()): v for k, v in row.items() if k}
    for n in names:
        if n in low and low[n] is not None:
            return low[n].strip()
    return ''


def load_csv(path):
    comps, nets = {}, {}
    with open(path, newline='', encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            net = _col(row, 'net', 'netname', 'signal')
            ref = _col(row, 'ref', 'refdes', 'designator', 'reference', 'component')
            pin = _col(row, 'pin', 'pinnumber', 'pad', 'padnumber')
            if not (net and ref):
                continue
            nets.setdefault(net, []).append({'ref': ref, 'pin': pin, 'func': _col(row, 'pinfunction', 'pinname', 'function'),
                                             'type': _col(row, 'pintype', 'type', 'electricaltype')})
            comps.setdefault(ref, new_comp(ref))
    return comps, nets


def merge_bom(comps, path):
    with open(path, newline='', encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            refs = _col(row, 'references', 'reference', 'designator', 'designators', 'refdes', 'ref', 'refs')
            for r in re.split(r'[\s,;]+', refs):
                if not r:
                    continue
                c = comps.setdefault(r, new_comp(r))
                c['value'] = c['value'] or _col(row, 'value', 'comment', 'val')
                c['footprint'] = c['footprint'] or _col(row, 'footprint', 'package')
                for k, v in row.items():
                    if k and v and k not in ('Reference', 'References', 'Designator'):
                        c['fields'].setdefault(k, v)
                finish_comp(c)


# ---------------------------------------------------------------- model
class Netlist:
    def __init__(self, comps, nets, source, fmt):
        self.comps, self.nets, self.source, self.fmt = comps, nets, source, fmt
        self.pin_net = {}
        self.comp_nets = {}
        self.comp_pins = {}
        for name, nodes in nets.items():
            for n in nodes:
                self.pin_net[(n['ref'], n['pin'])] = name
                self.comp_nets.setdefault(n['ref'], set()).add(name)
                self.comp_pins.setdefault(n['ref'], []).append((n, name))
                self.comps.setdefault(n['ref'], new_comp(n['ref']))
        self.ground = {n for n in nets if is_ground(n)}

    def v(self, net):
        if net in self.ground:
            return 0.0
        return rail_voltage(net)

    def two_pin(self, ref):
        pins = self.comp_pins.get(ref, [])
        uniq = {}
        for n, net in pins:
            uniq.setdefault(n['pin'], (n, net))
        return list(uniq.values()) if len(uniq) == 2 else None


def prefix(ref):
    m = re.match(r'^([A-Za-z_#]+)', ref)
    return m.group(1).upper() if m else ''


def text_of(c):
    return ' '.join([c['value'], c['footprint'], c['lib'], c['part'], c['description']]).lower()


def is_polarized(c):
    part = c['part'].lower()
    t = text_of(c)
    if part in ('c', 'c_small', 'c_us', 'c_small_us', 'c_feedthrough'):
        return False
    return (part in ('cp', 'cp_small', 'cp1', 'cp1_small', 'c_polarized', 'c_polarized_small',
                     'c_polarized_us', 'c_polarized_small_us', 'cp_elec') or
            any(k in t for k in ('cp_elec', 'cp_radial', 'cp_axial', 'cp_tantalum', 'tantalum',
                                 'electrolytic')) or
            bool(re.search(r'(?<!un)(?<!non)(?<!non-)(?<!non )polari[sz]ed', t)))


def is_cap(ref, c):
    return prefix(ref) in ('C', 'CP', 'CE') or c['part'].lower().startswith('c_') or c['part'] == 'C'


class Findings:
    def __init__(self):
        self.items, self.info = [], {}

    def add(self, check, rule, sev, title, detail='', refs=(), nets=(), confidence='lead'):
        self.items.append({'check': check, 'rule': rule, 'severity': sev, 'title': title,
                           'detail': detail, 'refs': sorted(set(refs)), 'nets': sorted(set(nets)),
                           'confidence': confidence})


def pin_desc(n):
    f = n.get('func') or ''
    return f"{n['ref']}.{n['pin']}" + (f" ({f})" if f and f != '~' else '')


# ---------------------------------------------------------------- checks
def check_single_pin(nl, F):
    other = []
    for name, nodes in nl.nets.items():
        uniq = {(n['ref'], n['pin']): n for n in nodes}
        if len(uniq) != 1:
            continue
        n = next(iter(uniq.values()))
        ptype = (n['type'] or '').lower()
        base_t, nc = ptype.split('+')[0], '+no_connect' in ptype
        if base_t in ('no_connect', 'not_connected', 'nc'):
            continue
        if is_unconnected_auto(name):
            if base_t == 'power_in':
                F.add('unconnected_power_pin', 'SCH-01', 'S1',
                      f"Power input pin unconnected: {pin_desc(n)}" + (' (marked no-connect)' if nc else ''),
                      'A power pin with no connection usually means the IC will not work or will be '
                      'back-powered through other pins. Confirm the datasheet says it may float.',
                      refs=[n['ref']], nets=[name], confidence='likely')
            elif base_t == 'input':
                F.add('floating_input', 'SCH-15', 'S2',
                      f"Input pin left floating: {pin_desc(n)}" + (' (marked no-connect, still an input)' if nc else ''),
                      'Floating CMOS inputs pick up noise, toggle randomly and can draw extra current. '
                      'Tie to GND or a rail (or use a documented internal pull).',
                      refs=[n['ref']], nets=[name], confidence='likely')
            elif not nc:
                other.append(pin_desc(n))
        else:
            sev = 'S1' if (nl.v(name) is not None or is_power_name(name)) and name not in nl.ground else 'S2'
            F.add('single_pin_net', 'SCH-01', sev,
                  f"Net '{name}' reaches only one pin ({pin_desc(n)})",
                  'A labelled or wired net with one pin is usually a label typo or a missing wire.',
                  refs=[n['ref']], nets=[name], confidence='likely')
    if other:
        F.info['unconnected_pins_without_nc_flag'] = other


def bridging_parts(nl, net_a, net_b):
    out = []
    for ref, nets in nl.comp_nets.items():
        if net_a in nets and net_b in nets:
            out.append(ref)
    return out


def check_grounds(nl, F):
    gnds = sorted(nl.ground)
    signal = [g for g in gnds if not is_chassis(g)]
    F.info['ground_nets'] = gnds
    if len(signal) > 1:
        bridges, iso = set(), set()
        for i, a in enumerate(signal):
            for b in signal[i + 1:]:
                for ref in bridging_parts(nl, a, b):
                    c = nl.comps.get(ref, new_comp(ref))
                    t = text_of(c)
                    if any(k in t for k in ('iso', 'adum', 'opto', 'pc817', 'transformer', 'b0505', 'isolat')):
                        iso.add(ref)
                    else:
                        bridges.add(ref)
        if iso and not bridges:
            F.add('ground_split', 'SCH-05', 'S4',
                  f"Separate grounds {', '.join(signal)} with isolating parts ({', '.join(sorted(iso))})",
                  'Galvanic isolation is the one case where separate grounds are correct (guide SCH-05). '
                  'Check creepage/clearance across the barrier.', refs=iso, nets=signal)
        else:
            how = (f"joined through {', '.join(sorted(bridges))}" if bridges else 'NOT connected anywhere')
            F.add('ground_split', 'SCH-05', 'S2',
                  f"{len(signal)} ground nets ({', '.join(signal)}) - {how}",
                  'Guide: use one ground (one plane) unless galvanically isolated; ignore datasheet advice '
                  'to split grounds. Unconnected grounds are a broken circuit; joined split grounds '
                  'force return currents to detour.', refs=bridges, nets=signal)


def norm_name(name):
    return re.sub(r'[^A-Z0-9+\-]', '', base_name(name).upper())


def check_names(nl, F):
    groups = {}
    for name in nl.nets:
        if is_auto(name):
            continue
        groups.setdefault(norm_name(name), []).append(name)
    for key, names in groups.items():
        if len(names) < 2:
            continue
        bases = {base_name(n) for n in names}
        if len(bases) == 1:
            F.add('same_label_different_sheets', 'SCH-02', 'S2',
                  f"'{bases.pop()}' exists as separate nets: {', '.join(names)}",
                  'Local labels only connect within one sheet. If these should be one signal, use a '
                  'global or hierarchical label (guide SCH-02/SCH-10).', nets=names)
        else:
            F.add('name_variants', 'SCH-04', 'S2',
                  f"Net names differ only by case/punctuation: {', '.join(names)}",
                  'EDA tools treat these as different nets, so they are NOT connected (guide "double names").',
                  nets=names)
    by_v = {}
    for name in nl.nets:
        if name in nl.ground or is_auto(name):
            continue
        v = rail_voltage(name)
        if v is not None:
            by_v.setdefault(v, []).append(name)
    rails_info = []
    for v, names in sorted(by_v.items()):
        if len(names) < 2:
            continue
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if norm_name(a) == norm_name(b):
                    continue
                br = bridging_parts(nl, a, b)
                if br:
                    rails_info.append(f"{a} <-> {b} via {', '.join(br)} (sub-rail)")
                else:
                    F.add('double_rail_names', 'SCH-04', 'S2',
                          f"Two {v:g} V nets not directly connected: '{a}' and '{b}'",
                          'Either a double name (one rail drawn with two names, leaving parts unpowered) '
                          'or two intended rails (e.g. separate regulators). Confirm which.', nets=[a, b])
    generic = [n for n in nl.nets if is_power_name(n) and rail_voltage(n) is None and n not in nl.ground]
    if generic and by_v:
        F.add('generic_rail_names', 'SCH-04', 'S3',
              f"Generic rail names ({', '.join(sorted(generic))}) coexist with explicit ones "
              f"({', '.join(sorted(n for ns in by_v.values() for n in ns))})",
              'Make sure a generic name (VCC, VDD...) is not the same rail as an explicit one (+5V...).',
              nets=generic)
    if rails_info:
        F.info['sub_rails'] = rails_info


def check_pin_names(nl, F):
    pwr = re.compile(r'^(?:[AD]?VDD[A-Z0-9_]*|[AD]?VCC[A-Z0-9_]*|VDDIO|VDDA|AVDD|DVDD|VBAT)$')
    gnd = re.compile(r'^(?:[AD]?GND[A-Z0-9_]*|[AD]?VSS[A-Z0-9_]*|VSSA|AVSS|DVSS|PGND)$')
    for name, nodes in nl.nets.items():
        for n in nodes:
            f = (n.get('func') or '').upper().replace(' ', '')
            if not f:
                continue
            if pwr.match(f) and name in nl.ground:
                F.add('power_pin_on_ground', 'SCH-06', 'S1', f"Power pin {pin_desc(n)} is on ground net '{name}'",
                      'Check the symbol pin mapping and the wiring.', refs=[n['ref']], nets=[name])
            if gnd.match(f) and name not in nl.ground and not is_unconnected_auto(name):
                F.add('ground_pin_off_ground', 'SCH-06', 'S1', f"Ground pin {pin_desc(n)} is on non-ground net '{name}'",
                      'OK only if deliberate (e.g. a low-side current-sense resistor). Otherwise the IC has '
                      'no ground return.', refs=[n['ref']], nets=[name])


def check_ic_ground(nl, F):
    for ref, nets in nl.comp_nets.items():
        if prefix(ref) not in ('U', 'IC'):
            continue
        if len(nets) >= 3 and not (nets & nl.ground):
            F.add('ic_without_ground', 'SCH-06', 'S1', f"{ref} has no pin on any ground net",
                  'Every IC needs a ground return. Check hidden pins, the exposed pad and the symbol.',
                  refs=[ref])


def check_outputs(nl, F):
    for name, nodes in nl.nets.items():
        drivers = [n for n in nodes if (n['type'] or '').split('+')[0] in ('output', 'power_out')]
        if len({(n['ref'], n['pin']) for n in drivers}) > 1:
            F.add('output_conflict', 'SCH-18', 'S1',
                  f"Net '{name}' is driven by {len(drivers)} outputs: {', '.join(pin_desc(n) for n in drivers)}",
                  'Two push-pull or regulator outputs fighting each other overheat or latch up.',
                  refs=[n['ref'] for n in drivers], nets=[name])
        types = {(n['type'] or '').split('+')[0] for n in nodes}
        if len({(n['ref'], n['pin']) for n in nodes}) >= 2 and types == {'input'}:
            F.add('undriven_net', 'SCH-15', 'S2',
                  f"Net '{name}' connects only inputs ({', '.join(pin_desc(n) for n in nodes)})",
                  'Nothing drives this net, so all those inputs float.', refs=[n['ref'] for n in nodes], nets=[name])


def check_caps(nl, F):
    unknown = []
    for ref, c in sorted(nl.comps.items()):
        if not is_cap(ref, c):
            continue
        tp = nl.two_pin(ref)
        if not tp:
            continue
        (n1, net1), (n2, net2) = tp
        rating = voltage_rating(c)
        diel = dielectric(c)
        if is_polarized(c):
            plus, minus = (n1, net1), (n2, net2)
            for n, net in tp:
                if n.get('func') in ('+', 'A', 'anode'):
                    plus = (n, net)
                    minus = [x for x in tp if x[0] is not n][0]
            if plus[0].get('func') not in ('+', 'A', 'anode') and plus[0]['pin'] != '1':
                plus, minus = minus, plus
            vp, vm = nl.v(plus[1]), nl.v(minus[1])
            if vp is None or vm is None:
                F.add('polarized_cap_unverified', 'SCH-03', 'S3',
                      f"{ref} ({c['value']}): verify polarity: + on '{plus[1]}', - on '{minus[1]}'",
                      'Net names do not reveal both voltages; check by hand.', refs=[ref], nets=[plus[1], minus[1]])
                continue
            if vp < vm:
                F.add('polarized_cap_reversed', 'SCH-03', 'S1',
                      f"{ref} ({c['value']}) looks REVERSED: + on '{plus[1]}' ({vp:g} V), - on '{minus[1]}' ({vm:g} V)",
                      'A reversed electrolytic/tantalum heats, vents or explodes.', refs=[ref],
                      nets=[plus[1], minus[1]], confidence='likely')
            applied = abs(vp - vm)
            if rating:
                tant = 'tantal' in text_of(c)
                if applied > rating:
                    F.add('cap_overvoltage', 'CMP-04', 'S1', f"{ref}: {applied:g} V applied, rated {rating:g} V",
                          'Exceeding the rating shortens life or destroys the part.', refs=[ref], confidence='likely')
                elif tant and applied > 0.5 * rating:
                    F.add('cap_margin', 'CMP-04', 'S2', f"{ref}: tantalum at {applied / rating * 100:.0f}% of rating",
                          'MnO2 tantalums are commonly derated to ~50% (check the maker; polymer types differ).',
                          refs=[ref])
                elif applied > 0.8 * rating:
                    F.add('cap_margin', 'CMP-04', 'S2', f"{ref}: {applied:g} V on a {rating:g} V part "
                          f"({applied / rating * 100:.0f}% of rating)",
                          'Thin margin: supply tolerance and spikes can exceed the rating; life drops (CMP-09).',
                          refs=[ref])
            else:
                unknown.append(ref)
            continue
        v1, v2 = nl.v(net1), nl.v(net2)
        applied = abs(v1 - v2) if (v1 is not None and v2 is not None) else None
        if diel in ('Y5V', 'Z5U'):
            F.add('bad_dielectric', 'CMP-05', 'S3', f"{ref} uses {diel}",
                  'Y5V/Z5U lose most of their capacitance with temperature and bias. Use X7R/X5R or C0G.',
                  refs=[ref])
        if applied is not None and rating:
            if applied > rating:
                F.add('cap_overvoltage', 'CMP-04', 'S1', f"{ref} ({c['value']}): {applied:g} V across a {rating:g} V part",
                      'Overvoltage cracks or shorts MLCCs.', refs=[ref], confidence='likely')
            elif diel and diel not in ('C0G', 'NP0', 'U2J') and applied >= 0.5 * rating:
                F.add('dc_bias', 'CMP-03', 'S2',
                      f"{ref} ({c['value']}{'' if diel in c['value'].upper() else ' ' + diel}) biased at "
                      f"{applied / rating * 100:.0f}% of its {rating:g} V rating",
                      'Class-2 ceramics lose a large share of capacitance under DC bias (X5R up to ~84% at '
                      'rated voltage). Check the maker curve; run ee_calc.py mlcc.', refs=[ref])
        if applied is not None and applied > 0 and (rating is None or diel is None):
            unknown.append(ref)
    if unknown:
        F.info['caps_missing_rating_or_dielectric'] = unknown


def check_decoupling(nl, F):
    decaps = {}
    for ref, c in nl.comps.items():
        if not is_cap(ref, c):
            continue
        tp = nl.two_pin(ref)
        if not tp:
            continue
        nets = [tp[0][1], tp[1][1]]
        g = [n for n in nets if n in nl.ground]
        r = [n for n in nets if n not in nl.ground]
        if len(g) == 1 and len(r) == 1:
            decaps.setdefault(r[0], []).append(ref)
    rails = {}
    for name, nodes in nl.nets.items():
        if name in nl.ground:
            continue
        pins = [n for n in nodes if (n['type'] or '').split('+')[0] == 'power_in']
        if pins:
            rails[name] = pins
    table = []
    for net, pins in sorted(rails.items()):
        caps = decaps.get(net, [])
        vals = []
        for r in caps:
            v, explicit = parse_value(nl.comps[r]['value'], 'C')
            vals.append(v if explicit else None)      # a bare '100' is ambiguous: leave it out
        total = sum(v for v in vals if v)
        biggest = max([v for v in vals if v] or [0])
        ics = sorted({p['ref'] for p in pins})
        table.append({'rail': net, 'power_pins': len(pins), 'ics': ics, 'caps': len(caps), 'total_c': total})
        if not caps:
            F.add('no_decoupling', 'SCH-07', 'S2',
                  f"Rail '{net}' feeds {len(pins)} power pin(s) on {', '.join(ics)} with NO capacitor to ground",
                  'Every supply pin needs local decoupling per its datasheet (typ. 100 nF per pin + bulk).',
                  refs=ics, nets=[net], confidence='likely')
            continue
        if len(caps) * 2 < len(pins):
            F.add('thin_decoupling', 'SCH-07', 'S3',
                  f"Rail '{net}': {len(caps)} cap(s) for {len(pins)} power pins ({', '.join(ics)})",
                  'Check each IC datasheet for the per-pin requirement.', refs=ics, nets=[net])
        if biggest and biggest < 1e-6:
            F.add('no_bulk', 'SCH-07', 'S3', f"Rail '{net}' has no capacitor >= 1 µF (largest {biggest * 1e9:g} nF)",
                  'Bulk capacitance supplies lower-frequency load steps; check regulator output-cap needs.',
                  refs=ics, nets=[net])
    F.info['rails'] = table


_DRIVER_RE = re.compile(r'ULN2\d0\d|ULQ2\d0\d|ULN2803|TPL7407|MAX4896|DRV8803|DRV8804|TBD62\d+|MIC2981')


def check_inductive(nl, F):
    diodes = {}
    for ref, c in nl.comps.items():
        if prefix(ref) in ('D',):
            tp = nl.two_pin(ref)
            if tp:
                diodes[ref] = tp
    for ref, c in sorted(nl.comps.items()):
        t = text_of(c)
        if not (prefix(ref) == 'K' or 'relay' in t or 'solenoid' in t):
            continue
        pins = nl.comp_pins.get(ref, [])
        coil = {net for n, net in pins if re.search(r'coil|^a1$|^a2$', (n.get('func') or '').lower())}
        nets = coil or {net for _, net in pins}
        across = [d for d, tp in diodes.items() if tp[0][1] in nets and tp[1][1] in nets and tp[0][1] != tp[1][1]]
        drivers = [r for r, cc in nl.comps.items() if _DRIVER_RE.search((cc['value'] + cc['part']).upper())
                   and nl.comp_nets.get(r, set()) & nets]
        if across:
            for d in across:
                tp = diodes[d]
                k = next((x for x in tp if (x[0].get('func') or '').upper() in ('K', 'CATHODE')), None)
                if k is None:
                    k = next((x for x in tp if x[0]['pin'] == '1'), None)
                a = next(x for x in tp if x is not k) if k else None
                if k and a:
                    vk, va = nl.v(k[1]), nl.v(a[1])
                    if va is not None and va > 0 and (vk is None or vk < va):
                        F.add('flyback_reversed', 'SCH-08', 'S1',
                              f"{d} across {ref} looks reversed: anode on '{a[1]}' ({va:g} V)",
                              'A clamp diode must have its cathode on the supply side; reversed, it shorts the '
                              'supply when the driver turns on.', refs=[d, ref], nets=[a[1], k[1]], confidence='likely')
            F.info.setdefault('flyback_ok', []).append(f"{ref}: clamp {', '.join(across)}")
        elif drivers:
            for drv in drivers:
                com = [net for n, net in nl.comp_pins.get(drv, []) if (n.get('func') or '').upper() in ('COM', 'COMMON')]
                if com and not (set(com) & nets) and not any(nl.v(x) for x in com):
                    F.add('driver_com', 'SCH-08', 'S1',
                          f"{drv} drives {ref} but its COM pin is on '{com[0]}', not the coil supply",
                          'The internal clamp diodes only work when COM connects to the coil supply.',
                          refs=[drv, ref], nets=com)
                else:
                    F.info.setdefault('flyback_ok', []).append(f"{ref}: driver {drv} with internal clamps"
                                                               + ('' if com else ' (COM pin not identified: verify)'))
        else:
            F.add('no_flyback', 'SCH-08', 'S1', f"No clamp (flyback) diode found across {ref}'s coil",
                  'Switching off a coil without a clamp produces a voltage spike that can destroy the '
                  'driver transistor (simulate: recipe R1; calc: ee_calc.py flyback).', refs=[ref], nets=sorted(nets))
    _check_loads(nl, F, diodes)


_HBRIDGE_RE = re.compile(r'DRV8\d|L293|L298|TB6612|TB67|A49\d\d|MP6\d{3}|BD62|ULN2|DRV10|MX1508|VNH\d')


def _check_loads(nl, F, diodes):
    """Motors, pumps, solenoids, fans: suppression for the inductive kick when switched off."""
    for ref, c in sorted(nl.comps.items()):
        t = text_of(c)
        t = ' '.join([c['value'], c['part'], c['description']]).lower()
        if prefix(ref) in ('K', 'J', 'P', 'CN', 'X', 'TP', 'U', 'IC') or 'relay' in t or c['part'].lower().startswith('conn'):
            continue
        if not (prefix(ref) == 'M' or re.search(r'motor|pump|solenoid|valve|\bfan\b|actuator', t)):
            continue
        tp = nl.two_pin(ref)
        if not tp:
            F.info.setdefault('inductive_loads_unchecked', []).append(ref)
            continue
        a, b = tp[0][1], tp[1][1]
        switched = {n for n in (a, b) if n not in nl.ground and nl.v(n) is None and not is_power_name(n)}
        if any({x[1] for x in dtp} == {a, b} for dtp in diodes.values()):
            F.info.setdefault('flyback_ok', []).append(f"{ref}: diode across load")
            continue
        drivers = [r for r, cc in nl.comps.items() if _HBRIDGE_RE.search((cc['value'] + cc['part']).upper())
                   and nl.comp_nets.get(r, set()) & switched]
        if drivers:
            F.info.setdefault('flyback_ok', []).append(f"{ref}: driver IC {', '.join(drivers)} (check its clamp/body diodes)")
            continue
        relays = [r for r in nl.comps if (prefix(r) == 'K' or 'relay' in text_of(nl.comps[r]))
                  and nl.comp_nets.get(r, set()) & switched]
        switches = [r for r in nl.comps if prefix(r) in ('Q',) and nl.comp_nets.get(r, set()) & switched]
        if switches:
            F.add('load_no_flyback', 'SCH-08', 'S1',
                  f"{ref} ({c['value']}) is switched by {', '.join(switches)} with no clamp across the load",
                  'Same physics as a relay coil (guide SCH-08): the load inductance kicks the switch when it '
                  'turns off. Add a diode across a DC motor/solenoid (sim R1; ee_calc.py flyback).',
                  refs=[ref] + switches, nets=[a, b])
        elif relays:
            F.add('contact_load_no_suppression', 'EXP-DRV-05', 'S2',
                  f"{ref} ({c['value']}) is switched by relay contacts ({', '.join(relays)}) with no suppression",
                  'Opening contacts on an inductive load draws an arc and a voltage spike: contact wear and '
                  'EMI that can reset nearby logic. Add a diode across a DC load, or an RC snubber/TVS across '
                  'the contacts; keep the load current out of the logic ground path.',
                  refs=[ref] + relays, nets=[a, b])
        else:
            F.info.setdefault('inductive_loads_unchecked', []).append(f"{ref} ({c['value']})")


def check_values(nl, F):
    vals = {}
    for ref, c in nl.comps.items():
        p = prefix(ref)
        kind = {'R': 'R', 'C': 'C', 'L': 'L'}.get(p)
        if not kind or c['dnp']:
            continue
        raw = (c['value'] or '').strip()
        if raw in ('', '~', '?', kind, kind + '_Small', 'R_Small', 'C_Small', 'L_Small') or raw.upper().startswith('DNP'):
            if not raw.upper().startswith('DNP'):
                F.add('value_not_set', 'SCH-16', 'S2', f"{ref} has no real value ('{raw}')",
                      'Default or empty values end up in the BOM and get assembled wrong.', refs=[ref])
            continue
        v, explicit = parse_value(raw, kind)
        if v is None:
            F.add('value_unparsed', 'SCH-16', 'S3', f"{ref}: cannot read value '{raw}'",
                  'Use standard notation (10k, 4k7, 100n, 4.7u) so humans and tools agree.', refs=[ref])
            continue
        vals.setdefault(kind, []).append((ref, raw, v, explicit))
    rs = vals.get('R', [])
    kvals = {re.sub(r'[^0-9.]', '', raw.split('k')[0].split('K')[0]) for _, raw, v, e in rs if v >= 1e3}
    series_ok = []
    for ref, raw, v, explicit in rs:
        if not explicit and v < 1000 and raw.strip().replace('.', '').isdigit() and raw.strip() in kvals:
            nets = nl.comp_nets.get(ref, set())
            on_rail = any(n in nl.ground or nl.v(n) is not None or is_power_name(n) for n in nets)
            if on_rail:
                F.add('missing_multiplier', 'SCH-16', 'S2',
                      f"{ref} = '{raw}' ({v:g} Ω) sits on a rail while '{raw}k' is used elsewhere - missing 'k'?",
                      "The guide's classic: 10 instead of 10k. On a rail, a missing 'k' means 1000x the current.",
                      refs=[ref])
            else:
                series_ok.append(f"{ref}={raw}")
    if series_ok:
        F.info['bare_value_series_resistors'] = series_ok
    for ref, raw, v, explicit in vals.get('C', []):
        if not explicit:
            F.add('cap_no_unit', 'SCH-16', 'S3', f"{ref} = '{raw}' has no unit/multiplier",
                  "'100' could mean 100 pF or 100 µF to different people. Write 100p / 100n / 100u.", refs=[ref])
    uniq = {}
    for kind in ('R', 'C'):
        counts = {}
        for ref, raw, v, e in vals.get(kind, []):
            fp = re.sub(r'^.*:', '', nl.comps[ref]['footprint'])
            counts.setdefault((round(v, 15), fp), []).append(ref)
        uniq[kind] = {'unique': len(counts),
                      'singletons': sorted(f"{refs[0]}={nl.comps[refs[0]]['value']} {k[1]}".strip()
                                           for k, refs in counts.items() if len(refs) == 1)}
    F.info['unique_values'] = uniq


def check_dnp(nl, F):
    dnp = sorted(r for r, c in nl.comps.items() if c['dnp'])
    F.info['dnp_parts'] = [f"{r} ({nl.comps[r]['value']})" for r in dnp]
    for r, c in nl.comps.items():
        v = (c['value'] or '').upper()
        if not c['dnp'] and re.search(r'\b(DNP|DNF|NC|NF|NOPOP|NO ?POP|DO NOT (FIT|POPULATE))\b', v):
            F.add('dnp_mismatch', 'SCH-17', 'S2', f"{r} value '{c['value']}' says do-not-fit but the DNP attribute is not set",
                  'Assemblers follow the attribute/BOM, not the value text: the part may be placed.', refs=[r])
        if c['dnp'] and prefix(r) in ('U', 'J', 'IC'):
            F.add('dnp_major_part', 'SCH-17', 'S3', f"{r} ({c['value']}) is marked DNP",
                  'Confirm this IC/connector is really meant to be left off.', refs=[r])


def check_test_points(nl, F):
    tps = [r for r, c in nl.comps.items() if prefix(r) == 'TP' or 'testpoint' in text_of(c).replace('_', '')]
    tp_nets = set()
    for r in tps:
        tp_nets |= nl.comp_nets.get(r, set())
    rails = sorted(n for n in nl.nets if n not in nl.ground and not is_auto(n)
                   and (rail_voltage(n) is not None or is_power_name(n)))
    missing = [n for n in rails if n not in tp_nets]
    F.info['test_points'] = {'count': len(tps), 'rails_without_tp': missing,
                             'ground_tp': bool(tp_nets & nl.ground)}
    if not (tp_nets & nl.ground):
        F.add('no_ground_tp', 'SCH-13', 'S3', 'No test point / measurement pin on ground',
              'A GND pin or loop makes every scope and meter measurement easier and safer.')
    if missing:
        F.add('rails_without_tp', 'SCH-11', 'S3', f"Rails without a test point: {', '.join(missing)}",
              'Add test points on supply rails and key signals to make bring-up fast.', nets=missing)


_ORDER_KEYS = ('mpn', 'manufacturerpartnumber', 'mfrpartnumber', 'mfrpart', 'mfrpn', 'partnumber', 'pn',
               'lcsc', 'lcscpart', 'lcscpartnumber', 'jlcpcbpart', 'jlcpart', 'digikey', 'digikeypartnumber',
               'digikeypn', 'mouser', 'mouserpartnumber', 'ordercode', 'oc', 'manufacturerpn', 'mfgpn')


def check_order_codes(nl, F):
    missing = []
    for r, c in sorted(nl.comps.items()):
        p = prefix(r)
        if c['dnp'] or c['exclude_bom'] or p in ('TP', 'H', 'MH', 'FID', 'NT', 'LOGO', 'G', 'REF', '#PWR', '#FLG'):
            continue
        keys = {re.sub(r'[^a-z]', '', k.lower()) for k, v in c['fields'].items() if (v or '').strip() not in ('', '~')}
        if not keys & set(_ORDER_KEYS):
            missing.append(r)
    if missing:
        F.add('missing_order_codes', 'LAY-20', 'S3',
              f"{len(missing)} part(s) without an order code / MPN field: {', '.join(missing[:30])}"
              + (' ...' if len(missing) > 30 else ''),
              'Without MPNs the assembler or buyer guesses. Add MPN or LCSC/DigiKey fields.', refs=missing[:30])


# ---------------------------------------------------------------- schematic readability (SCHD)
def schematic_stats(root_path):
    stats, seen = [], set()

    def walk(path, sheet_name):
        ap = os.path.abspath(path)
        if ap in seen or not os.path.exists(ap):
            return
        seen.add(ap)
        with open(ap, encoding='utf-8') as fh:
            root = parse_sexpr(fh.read())
        syms = [s for s in kids(root, 'symbol') if val(s, 'lib_id')]
        parts = [s for s in syms if not str(val(s, 'lib_id', '')).startswith('power:')]
        labels = [l[1] for l in kids(root, 'label') if len(l) > 1]
        glabels = [l[1] for l in kids(root, 'global_label') if len(l) > 1]
        counts = {}
        for l in labels + glabels:
            counts[l] = counts.get(l, 0) + 1
        st = {'sheet': sheet_name, 'file': os.path.basename(ap), 'parts': len(parts),
              'power_symbols': len(syms) - len(parts), 'wires': len(kids(root, 'wire')),
              'local_labels': len(labels), 'global_labels': len(kids(root, 'global_label')),
              'hier_labels': len(kids(root, 'hierarchical_label')),
              'same_sheet_label_pairs': sorted(k for k, v in counts.items() if v >= 2)}
        stats.append(st)
        for sh in kids(root, 'sheet'):
            props = {p[1]: p[2] for p in kids(sh, 'property') if len(p) > 2}
            f = props.get('Sheetfile') or props.get('Sheet file')
            n = props.get('Sheetname') or props.get('Sheet name') or f
            if f:
                walk(os.path.join(os.path.dirname(ap), f), n)

    walk(root_path, 'root')
    return stats


def check_readability(stats, F):
    F.info['schematic_sheets'] = stats
    multi = len(stats) >= 3
    thin = [s['sheet'] for s in stats if s['parts'] <= 1 and s['sheet'] != 'root']
    if multi and thin:
        F.add('thin_sheets', 'SCHD-03', 'S4', f"Sheets with <= 1 part: {', '.join(thin)}",
              'One-part sheets connected by labels hide the circuit. Group each block on one sheet.')
    for s in stats:
        if s['same_sheet_label_pairs']:
            n = len(s['same_sheet_label_pairs'])
            F.add('same_sheet_labels', 'SCHD-02', 'S4',
                  f"Sheet '{s['sheet']}': {n} net(s) joined by labels on the same sheet: "
                  f"{', '.join(s['same_sheet_label_pairs'][:12])}{' ...' if n > 12 else ''}",
                  'Prefer wires on the same sheet so the signal flow is visible (labels are fine for power, '
                  'buses, single digital I/O lines and sheet-to-sheet links).')
        lab = s['local_labels'] + s['global_labels']
        if lab >= 10 and lab >= 0.5 * max(s['wires'], 1):
            F.add('label_heavy', 'SCHD-01', 'S4',
                  f"Sheet '{s['sheet']}' is label-heavy: {lab} labels vs {s['wires']} wires",
                  'Heavy label use hides how blocks connect and makes errors hard to spot (guide SCHD-01).')


# ---------------------------------------------------------------- output
SEV_ORDER = {'S1': 0, 'S2': 1, 'S3': 2, 'S4': 3}
SEV_NAME = {'S1': 'Blocker', 'S2': 'Major', 'S3': 'Minor', 'S4': 'Advisory'}


def to_markdown(nl, F, show_nets):
    out = [f"# netlist_lint report", '',
           f"Source: `{os.path.basename(nl.source)}` ({nl.fmt}) · {len(nl.comps)} parts · {len(nl.nets)} nets · "
           f"tool v{VERSION}", '',
           '> Every item is a **lead**. Confirm it (datasheet, schematic, ERC) before reporting it as a finding.', '']
    items = sorted(F.items, key=lambda i: (SEV_ORDER[i['severity']], i['rule']))
    counts = {s: sum(1 for i in items if i['severity'] == s) for s in SEV_ORDER}
    out.append('Leads: ' + ' · '.join(f"{s} {SEV_NAME[s]}: {n}" for s, n in counts.items()))
    out.append('')
    if items:
        out += ['| Sev | Rule | Lead | Why it matters |', '|---|---|---|---|']
        for i in items:
            out.append(f"| {i['severity']} | {i['rule']} | {i['title'].replace('|', '/')} | "
                       f"{i['detail'].replace('|', '/')} |")
        out.append('')
    info = F.info
    if info.get('rails'):
        out += ['## Rails (power_in pins vs decoupling)', '', '| Rail | V (from name) | Power pins | ICs | Caps to GND | Total C |',
                '|---|---|---|---|---|---|']
        for r in info['rails']:
            v = rail_voltage(r['rail'])
            out.append(f"| {r['rail']} | {'' if v is None else f'{v:g}'} | {r['power_pins']} | {', '.join(r['ics'])} | "
                       f"{r['caps']} | {r['total_c'] * 1e6:.3g} µF |")
        out.append('')
    for key, title in (('ground_nets', 'Ground nets'), ('sub_rails', 'Bridged sub-rails'),
                       ('flyback_ok', 'Inductive loads with a clamp'),
                       ('inductive_loads_unchecked', 'Inductive loads to check by hand (switching not identified)'),
                       ('bare_value_series_resistors', 'Low bare-number resistors not on a rail (likely intentional series R)'),
                       ('dnp_parts', 'DNP parts (confirm each)'),
                       ('caps_missing_rating_or_dielectric', 'Caps whose voltage rating or dielectric is not in the data'),
                       ('unconnected_pins_without_nc_flag', 'Unconnected pins without a no-connect flag (usually fine for GPIO)')):
        if info.get(key):
            vals = info[key]
            out.append(f"**{title}:** " + ', '.join(str(v) for v in vals[:60]) + (' ...' if len(vals) > 60 else ''))
            out.append('')
    tp = info.get('test_points')
    if tp:
        out.append(f"**Test points:** {tp['count']} · ground TP: {'yes' if tp['ground_tp'] else 'no'}")
        out.append('')
    uv = info.get('unique_values')
    if uv:
        for kind, d in uv.items():
            out.append(f"**Unique {kind} values (value+footprint):** {d['unique']} · used once: "
                       + ', '.join(d['singletons'][:25]) + (' ...' if len(d['singletons']) > 25 else ''))
        out.append('')
    if info.get('schematic_sheets'):
        out += ['## Schematic sheets', '', '| Sheet | Parts | Wires | Local labels | Global | Hier. |', '|---|---|---|---|---|---|']
        for s in info['schematic_sheets']:
            out.append(f"| {s['sheet']} | {s['parts']} | {s['wires']} | {s['local_labels']} | {s['global_labels']} | {s['hier_labels']} |")
        out.append('')
    if show_nets:
        out += ['## Named nets', '', '| Net | Pins | Connected |', '|---|---|---|']
        for name in sorted(n for n in nl.nets if not is_auto(n))[:300]:
            nodes = nl.nets[name]
            out.append(f"| {name} | {len(nodes)} | {', '.join(pin_desc(n) for n in nodes[:12])}"
                       f"{' ...' if len(nodes) > 12 else ''} |")
        out.append('')
    return '\n'.join(out)


def load(path, fmt):
    ext = os.path.splitext(path)[1].lower()
    if fmt == 'auto':
        if ext == '.xml':
            fmt = 'xml'
        elif ext == '.csv':
            fmt = 'csv'
        elif ext == '.kicad_pcb':
            fmt = 'pcb'
        else:
            fmt = 'kicad'
    if fmt == 'xml':
        comps, nets = load_kicad_xml(path)
    elif fmt == 'csv':
        comps, nets = load_csv(path)
    else:
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        if fmt == 'kicad' and text.lstrip().startswith('<'):
            comps, nets = load_kicad_xml(path)
            fmt = 'xml'
        elif fmt == 'pcb' or text.lstrip().startswith('(kicad_pcb'):
            comps, nets = load_pcb(text)
            fmt = 'pcb'
        else:
            comps, nets = load_kicad_sexpr(text)
    return comps, nets, fmt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('netlist')
    ap.add_argument('--format', default='auto', choices=['auto', 'kicad', 'xml', 'csv', 'pcb'])
    ap.add_argument('--bom', help='BOM CSV to merge values/fields (useful with CSV pin lists)')
    ap.add_argument('--sch', help='root .kicad_sch for readability stats (SCHD rules)')
    ap.add_argument('--json', help="write JSON to this path ('-' = stdout instead of markdown)")
    ap.add_argument('--nets', action='store_true', help='append an index of named nets')
    a = ap.parse_args(argv)
    comps, nets, fmt = load(a.netlist, a.format)
    if a.bom:
        merge_bom(comps, a.bom)
    nl = Netlist(comps, nets, a.netlist, fmt)
    F = Findings()
    for chk in (check_single_pin, check_grounds, check_names, check_pin_names, check_ic_ground, check_outputs,
                check_caps, check_decoupling, check_inductive, check_values, check_dnp, check_test_points,
                check_order_codes):
        try:
            chk(nl, F)
        except Exception as e:  # a broken check must not hide the others
            F.info.setdefault('check_errors', []).append(f"{chk.__name__}: {e}")
    if a.sch:
        try:
            check_readability(schematic_stats(a.sch), F)
        except Exception as e:
            F.info.setdefault('check_errors', []).append(f"schematic_stats: {e}")
    data = {'tool': 'netlist_lint', 'version': VERSION, 'source': a.netlist, 'format': fmt,
            'stats': {'parts': len(nl.comps), 'nets': len(nl.nets),
                      'pins': sum(len(v) for v in nl.nets.values())},
            'leads': sorted(F.items, key=lambda i: (SEV_ORDER[i['severity']], i['rule'])), 'info': F.info}
    if a.json == '-':
        print(json.dumps(data, indent=2, default=str))
        return
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(data, fh, indent=2, default=str)
    print(to_markdown(nl, F, a.nets))
    if F.info.get('check_errors'):
        print('\nCheck errors (report these; results may be incomplete): ' + '; '.join(F.info['check_errors']))


if __name__ == '__main__':
    main()
