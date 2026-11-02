#!/usr/bin/env python3
"""ee_calc.py - deterministic engineering calculators for the electronic-design-reviewer skill.

Every command prints the formula, the inputs and the result with units, so a
review can show its math. Add --json (before the command) for machine output.

Number input: SI suffixes f p n u(µ) m k M/meg G and RKM codes (4k7, 4u7, 1R5).
Here 'm' = milli and 'M' = mega (EE habit). In SPICE netlists 'M' means milli:
write 'meg' there.

Commands (run `ee_calc.py <command> -h` for options):
  rc           RC time constant, cutoff, time-to-threshold (nominal vs derated C)
  mlcc         Class-2 MLCC DC-bias risk screen and effective capacitance
  srf          Self-resonant frequency: capacitor (C+ESL) or inductor (L+Cpar)
  pdn-z        Impedance vs frequency of a decoupling network
  divider      Resistor divider: nominal, worst case, current, source impedance
  r-power      Resistor dissipation vs temperature-derated rating
  tj           Junction temperature from power and thermal resistance
  ldo          Linear regulator dissipation, Tj, efficiency, dropout headroom
  trace-res    DC resistance, voltage drop and loss of a copper trace
  trace-width  IPC-2221 trace width for a current and temperature rise
  via          Via inductance (guide curve + Johnson formula) and barrel resistance
  annular      Annular ring / pad diameter for a via or drilled pad
  microstrip   Microstrip impedance (IPC-2141A) or width for a target impedance
  i2c-pullup   I2C pull-up resistor range (NXP UM10204)
  crystal      Crystal load capacitors from CL and stray capacitance
  battery      Battery life from sleep current plus periodic events
  flyback      Inductive turn-off spike without clamp; decay with diode/Zener
  hotplug      Hot-plug inrush current and capacitor overshoot (series RLC)
  pulse-sag    Cell voltage sag under a load pulse, with optional buffer cap
"""
import argparse
import json
import math
import re
import sys

RHO_CU_20C = 1.724e-8      # ohm*m, annealed copper at 20 C
ALPHA_CU = 0.00393         # 1/K
UM_PER_OZ = 34.79          # copper thickness per oz/ft^2
E12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]
E24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
       3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1]

_MULT = {'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'μ': 1e-6,
         'm': 1e-3, 'k': 1e3, 'K': 1e3, 'M': 1e6, 'meg': 1e6, 'MEG': 1e6,
         'Meg': 1e6, 'G': 1e9, 'g': 1e9, 'R': 1.0, 'r': 1.0}
_NUM_RE = re.compile(
    r'([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)\s*(meg|MEG|Meg|[fpnuµμmkKMGgRr])?(\d*)\s*([A-Za-z%°]*)')


def parse_si(text):
    """Parse '4.7u', '4u7', '10k', '1meg', '1R5', '100nF', '20mA', '1e-6' to float."""
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip().replace('Ω', '')
    for word in ('ohms', 'Ohms', 'ohm', 'Ohm'):
        s = s.replace(word, '')
    m = re.fullmatch(r'[Rr](\d+)', s)
    if m:
        return float('0.' + m.group(1))
    m = _NUM_RE.fullmatch(s)
    if not m:
        raise ValueError(f"cannot parse number {text!r}")
    num, mult, frac, _unit = m.groups()
    if frac:
        if '.' in num or not mult:
            raise ValueError(f"cannot parse number {text!r}")
        num = num + '.' + frac
    return float(num) * (_MULT[mult] if mult else 1.0)


def parse_mm(text):
    s = str(text).strip().lower().replace('mm', '')
    return float(s)


_PREFIX = [(1e9, 'G'), (1e6, 'M'), (1e3, 'k'), (1.0, ''), (1e-3, 'm'),
           (1e-6, 'µ'), (1e-9, 'n'), (1e-12, 'p'), (1e-15, 'f')]


def eng(x, unit='', sig=4):
    """Engineering notation with SI prefix: eng(0.00047,'F') -> '470 µF'."""
    if x is None:
        return 'n/a'
    if x == 0 or not math.isfinite(x):
        return f"{x:g} {unit}".strip()
    ax = abs(x)
    if unit == 'Hz' and ax < 1:          # avoid 'mHz' being misread as MHz
        return f"{x:.{sig}g} Hz"
    for scale, p in _PREFIX:
        if ax >= scale * 0.9995:
            return f"{x / scale:.{sig}g} {p}{unit}".strip()
    scale, p = _PREFIX[-1]
    return f"{x / scale:.{sig}g} {p}{unit}".strip()


def nearest_series(x, series=E12, mode='nearest'):
    """Nearest standard value from an E-series (mode: nearest|below|above)."""
    if x <= 0:
        return None
    decade = 10 ** math.floor(math.log10(x))
    cands = []
    for d in (decade / 10, decade, decade * 10):
        cands += [round(v * d, 12) for v in series]
    if mode == 'below':
        cands = [c for c in cands if c <= x * 1.0000001]
        return max(cands) if cands else None
    if mode == 'above':
        cands = [c for c in cands if c >= x * 0.9999999]
        return min(cands) if cands else None
    return min(cands, key=lambda c: abs(math.log(c / x)))


class Report:
    def __init__(self, title):
        self.title = title
        self.lines = []
        self.data = {}
        self.notes = []

    def line(self, label, text):
        self.lines.append((label, text))

    def put(self, **kw):
        self.data.update(kw)

    def note(self, text):
        self.notes.append(text)

    def emit(self, as_json):
        if as_json:
            out = {'calc': self.title, 'results': self.data, 'notes': self.notes,
                   'lines': [f"{a}: {b}" for a, b in self.lines]}
            print(json.dumps(out, indent=2, default=str))
            return
        print(f"== {self.title} ==")
        w = max((len(a) for a, _ in self.lines), default=0)
        for a, b in self.lines:
            print(f"{a.ljust(w)} : {b}")
        for n in self.notes:
            print(f"note: {n}")


# ---------------------------------------------------------------- commands

def cmd_rc(a):
    r = Report('RC time constant')
    R, C = parse_si(a.r), parse_si(a.c)
    tau = R * C
    fc = 1 / (2 * math.pi * tau)
    r.line('Formula', 'tau = R*C ; fc = 1/(2*pi*R*C) ; t_th = -tau*ln(1 - Vth/Vstep)')
    r.line('Inputs', f"R = {eng(R, 'Ω')}, C = {eng(C, 'F')}")
    r.line('tau (nominal C)', eng(tau, 's'))
    r.line('fc (nominal C)', eng(fc, 'Hz'))
    r.put(tau_s=tau, fc_hz=fc)
    tau_e = None
    if a.ceff:
        Ce = parse_si(a.ceff)
        tau_e = R * Ce
        r.line('C effective', f"{eng(Ce, 'F')} ({Ce / C * 100:.0f}% of nominal)")
        r.line('tau (effective C)', f"{eng(tau_e, 's')} ({(tau_e / tau - 1) * 100:+.0f}%)")
        r.line('fc (effective C)', eng(1 / (2 * math.pi * tau_e), 'Hz'))
        r.put(tau_eff_s=tau_e, fc_eff_hz=1 / (2 * math.pi * tau_e), c_ratio=Ce / C)
        r.note('Derate C over the voltage it sees while it times (0 V up to the threshold), not at '
               'its final voltage.')
    if a.vstep is not None and a.vth is not None:
        vs, vt = parse_si(a.vstep), parse_si(a.vth)
        if not (0 < vt < vs):
            r.note('time-to-threshold needs 0 < Vth < Vstep (charging from 0 V)')
        else:
            k = -math.log(1 - vt / vs)
            r.line('t to Vth (nominal)', f"{eng(tau * k, 's')} (Vstep {vs:g} V, Vth {vt:g} V)")
            r.note('A delay ends when the input crosses its threshold, not at RC: run this at the '
                   "threshold's datasheet min and max.")
            r.put(t_th_s=tau * k)
            if tau_e:
                r.line('t to Vth (effective)', eng(tau_e * k, 's'))
                r.put(t_th_eff_s=tau_e * k)
    return r


_SIZE_MM3 = {'0201': 0.6 * 0.3 * 0.3, '0402': 1.0 * 0.5 * 0.5, '0603': 1.6 * 0.8 * 0.8,
             '0805': 2.0 * 1.25 * 1.25, '1206': 3.2 * 1.6 * 1.6, '1210': 3.2 * 2.5 * 2.5,
             '1812': 4.5 * 3.2 * 2.5, '2220': 5.7 * 5.0 * 2.5}
_TEMPCO = {'X5R': '±15% over -55..+85 °C', 'X7R': '±15% over -55..+125 °C',
           'X6S': '±22% over -55..+105 °C', 'X7S': '±22% over -55..+125 °C',
           'X8R': '±15% over -55..+150 °C', 'X7T': '+22/-33% over -55..+125 °C',
           'Y5V': '+22/-82% over -30..+85 °C', 'Z5U': '+22/-56% over +10..+85 °C'}


def cmd_mlcc(a):
    r = Report('MLCC DC-bias screen')
    C, vr, vb = parse_si(a.c), parse_si(a.vrated), parse_si(a.vbias)
    diel = (a.dielectric or '').upper().replace('NPO', 'NP0')
    ratio = vb / vr
    r.line('Inputs', f"C = {eng(C, 'F')}, rated {vr:g} V, DC bias {vb:g} V "
                     f"({ratio * 100:.0f}% of rating), dielectric {diel or 'unknown'}, "
                     f"size {a.size or 'unknown'}")
    r.put(bias_ratio=ratio)
    if vb > vr:
        r.line('Verdict', 'FAIL: DC bias exceeds the voltage rating (guide CMP-04).')
        r.put(risk='FAIL')
        return r
    if diel in ('C0G', 'NP0', 'U2J', 'CH'):
        r.line('Risk', 'NONE: class 1 dielectric; capacitance does not drop with DC bias.')
        r.put(risk='NONE')
        return r
    density = None
    if a.size and a.size in _SIZE_MM3:
        density = (C * 1e6) * vr / _SIZE_MM3[a.size]
        r.line('CV density', f"{density:.1f} µF·V/mm³ (higher = thinner dielectric layers = more loss)")
    if density is None:
        risk = 'HIGH' if ratio >= 0.5 else 'MEDIUM' if ratio >= 0.25 else 'LOW'
    elif (ratio >= 0.5 and density >= 10) or (density > 30 and ratio >= 0.25):
        risk = 'HIGH'
    elif ratio >= 0.5 or (density >= 10 and ratio >= 0.25) or density > 30:
        risk = 'MEDIUM'
    else:
        risk = 'LOW'
    span = {'HIGH': (0.15, 0.60), 'MEDIUM': (0.50, 0.85), 'LOW': (0.80, 1.0)}[risk]
    r.put(risk=risk, screen_retained_range=span, cv_density=density)
    r.line('Risk', f"{risk} (screening only; class-2 assumed)" if not diel else risk)
    r.line('Screening range', f"expect roughly {span[0] * 100:.0f}-{span[1] * 100:.0f}% of nominal "
                              f"-> {eng(C * span[0], 'F')} to {eng(C * span[1], 'F')}")
    if diel in _TEMPCO:
        r.line('Temperature code', f"{diel}: {_TEMPCO[diel]} (adds to the DC-bias loss)")
    if a.retained:
        k = parse_si(a.retained)
        if k > 1:
            k /= 100.0
        r.line('From datasheet curve', f"{k * 100:.0f}% retained -> C_eff = {eng(C * k, 'F')}")
        r.put(c_eff=C * k)
    r.note("Guide anchor: X5R can lose ~84% at rated voltage; class 2/3 also drift with "
           "temperature. Get the real curve for the exact MPN (Murata SimSurfing, TDK, "
           "Samsung, KEMET K-SIM) before trusting a number.")
    r.note('Use the bias the part sees while it does its job: the rail for decoupling, but only '
           '0 V up to the threshold for an RC timer.')
    if risk == 'HIGH':
        r.note("Fix options: higher voltage rating, bigger package, more parts in parallel, "
               "or (timing/filters/coupling) C0G, film or polymer per guide CMP-11/12/14.")
    return r


def cmd_srf(a):
    r = Report('Self-resonant frequency')
    if a.c and a.esl:
        C, L = parse_si(a.c), parse_si(a.esl)
        f0 = 1 / (2 * math.pi * math.sqrt(L * C))
        r.line('Part', f"capacitor {eng(C, 'F')} with ESL {eng(L, 'H')}")
        r.line('Formula', 'f_srf = 1/(2*pi*sqrt(ESL*C))')
        r.line('SRF', eng(f0, 'Hz'))
        r.put(srf_hz=f0)
        esr = parse_si(a.esr) if a.esr else 0.0
        if a.esr:
            r.line('|Z| at SRF', f"{eng(esr, 'Ω')} (= ESR)")
        if a.f:
            f = parse_si(a.f)
            w = 2 * math.pi * f
            z = complex(esr, w * L - 1 / (w * C))
            kind = 'capacitive' if f < f0 else 'INDUCTIVE (above SRF)'
            r.line(f"|Z| at {eng(f, 'Hz')}", f"{eng(abs(z), 'Ω')} - {kind}")
            r.put(z_at_f=abs(z), above_srf=f > f0)
        r.note('Above its SRF a capacitor behaves like an inductor (guide CMP-02). '
               'Mounting pads and vias add ESL: use the mounted value, not just the part.')
    elif a.l and a.cpar:
        L, Cp = parse_si(a.l), parse_si(a.cpar)
        f0 = 1 / (2 * math.pi * math.sqrt(L * Cp))
        r.line('Part', f"inductor {eng(L, 'H')} with parasitic C {eng(Cp, 'F')}")
        r.line('Formula', 'f_srf = 1/(2*pi*sqrt(L*Cpar))')
        r.line('SRF', eng(f0, 'Hz'))
        r.put(srf_hz=f0)
        if a.f:
            f = parse_si(a.f)
            r.line('Operating f', f"{eng(f, 'Hz')} = {f / f0 * 100:.1f}% of SRF")
            r.put(f_over_srf=f / f0)
            if f > f0:
                r.note('Above SRF the inductor acts as a CAPACITOR (guide CMP-23).')
            elif f > f0 / 3:
                r.note('Within ~3x of SRF the inductance is already distorted; pick a higher-SRF part.')
    else:
        raise SystemExit('srf: give --c and --esl (capacitor) or --l and --cpar (inductor)')
    return r


def _parse_branch(text, n):
    parts = [p.strip() for p in text.split(',')]
    if len(parts) < n:
        raise SystemExit(f"bad branch spec {text!r}")
    vals = [parse_si(p) for p in parts[:n]]
    count = int(parts[n]) if len(parts) > n and parts[n] else 1
    return vals, count


def cmd_pdn_z(a):
    r = Report('Decoupling network impedance |Z(f)|')
    caps = [_parse_branch(c, 3) for c in a.cap]
    reg = _parse_branch(a.reg, 2)[0] if a.reg else None
    fmin, fmax = parse_si(a.fmin), parse_si(a.fmax)
    n = a.points
    freqs = [fmin * (fmax / fmin) ** (i / (n - 1)) for i in range(n)]

    def ztot(f):
        w = 2 * math.pi * f
        y = 0j
        for (C, esr, esl), cnt in caps:
            y += cnt / complex(esr, w * esl - 1 / (w * C))
        if reg:
            R, L = reg
            y += 1 / complex(R, w * L)
        return 1 / y

    zs = [abs(ztot(f)) for f in freqs]
    desc = ', '.join(f"{cnt}x[{eng(C, 'F')}, ESR {eng(esr, 'Ω')}, ESL {eng(esl, 'H')}]"
                     for (C, esr, esl), cnt in caps)
    r.line('Branches', desc + (f"; regulator R {eng(reg[0], 'Ω')} + L {eng(reg[1], 'H')}" if reg else ''))
    i_min = min(range(n), key=lambda i: zs[i])
    r.line('Minimum |Z|', f"{eng(zs[i_min], 'Ω')} at {eng(freqs[i_min], 'Hz')}")
    peaks = [(freqs[i], zs[i]) for i in range(1, n - 1) if zs[i] > zs[i - 1] and zs[i] > zs[i + 1]]
    for f, z in peaks:
        r.line('Anti-resonance peak', f"{eng(z, 'Ω')} at {eng(f, 'Hz')}")
    dec = []
    f = 10 ** math.ceil(math.log10(fmin))
    while f <= fmax * 1.0001:
        dec.append((f, abs(ztot(f))))
        f *= 10
    r.line('|Z| per decade', ' | '.join(f"{eng(f, 'Hz', 3)}: {eng(z, 'Ω', 3)}" for f, z in dec))
    r.put(min_z=zs[i_min], f_min_z=freqs[i_min], peaks=peaks, decades=dec)
    if a.target:
        zt = parse_si(a.target)
        bad, start = [], None
        for f, z in zip(freqs, zs):
            if z > zt and start is None:
                start = f
            if z <= zt and start is not None:
                bad.append((start, f))
                start = None
        if start is not None:
            bad.append((start, freqs[-1]))
        if bad:
            r.line('Above target', '; '.join(f"{eng(s, 'Hz', 3)}-{eng(e, 'Hz', 3)}" for s, e in bad)
                   + f" (target {eng(zt, 'Ω')})")
        else:
            r.line('Above target', f"none - |Z| stays below {eng(zt, 'Ω')} from {eng(fmin, 'Hz')} to {eng(fmax, 'Hz')}")
        r.put(target=zt, above_target=bad)
        r.note('Target impedance rule of thumb: Z_target = allowed ripple (V) / load current step (A).')
    if a.csv:
        with open(a.csv, 'w') as fh:
            fh.write('freq_hz,z_ohm\n')
            for f, z in zip(freqs, zs):
                fh.write(f"{f:.6g},{z:.6g}\n")
        r.line('CSV', a.csv)
    r.note('Analytic equivalent of SpiceBridge recipe R3. Use mounted ESL (part + pads + vias).')
    return r


def cmd_divider(a):
    r = Report('Resistor divider')
    vin, R1, R2 = parse_si(a.vin), parse_si(a.r1), parse_si(a.r2)
    tol, vtol = a.tol / 100.0, a.vin_tol / 100.0
    vout = vin * R2 / (R1 + R2)
    vmin = vin * (1 - vtol) * R2 * (1 - tol) / (R1 * (1 + tol) + R2 * (1 - tol))
    vmax = vin * (1 + vtol) * R2 * (1 + tol) / (R1 * (1 - tol) + R2 * (1 + tol))
    i = vin / (R1 + R2)
    rth = R1 * R2 / (R1 + R2)
    r.line('Formula', 'Vout = Vin*R2/(R1+R2) ; Rth = R1||R2')
    r.line('Inputs', f"Vin {vin:g} V (±{a.vin_tol:g}%), R1 {eng(R1, 'Ω')}, R2 {eng(R2, 'Ω')} (±{a.tol:g}%)")
    r.line('Vout nominal', eng(vout, 'V'))
    r.line('Vout worst case', f"{eng(vmin, 'V')} .. {eng(vmax, 'V')} ({(vmin / vout - 1) * 100:+.1f}% / {(vmax / vout - 1) * 100:+.1f}%)")
    r.line('Divider current', f"{eng(i, 'A')} (continuous drain: matters on batteries)")
    r.line('Power', f"R1 {eng(i * i * R1, 'W')}, R2 {eng(i * i * R2, 'W')}")
    r.line('Source impedance', f"{eng(rth, 'Ω')} (what an ADC input sees)")
    r.put(vout=vout, vmin=vmin, vmax=vmax, i=i, p_r1=i * i * R1, p_r2=i * i * R2, rth=rth)
    if rth > 10e3:
        r.note('High source impedance: check the ADC datasheet max source impedance; '
               'add a capacitor at the ADC pin (charge reservoir) or a buffer.')
    return r


def cmd_r_power(a):
    r = Report('Resistor power vs rating')
    R = parse_si(a.r)
    if a.i:
        I = parse_si(a.i)
        P = I * I * R
        how = f"P = I^2*R = ({eng(I, 'A')})^2 * {eng(R, 'Ω')}"
    elif a.v:
        V = parse_si(a.v)
        P = V * V / R
        how = f"P = V^2/R = ({V:g} V)^2 / {eng(R, 'Ω')}"
    else:
        raise SystemExit('r-power: give --i or --v')
    r.line('Formula', how)
    r.line('Dissipation', eng(P, 'W'))
    r.put(p_w=P)
    if a.rating:
        rating = parse_si(a.rating)
        ta, knee, tmax = a.ta, a.knee, a.tmax
        der = rating if ta <= knee else max(0.0, rating * (tmax - ta) / (tmax - knee))
        util = P / der if der > 0 else float('inf')
        r.line('Rating', f"{eng(rating, 'W')} at <= {knee:g} °C; derated to {eng(der, 'W')} at {ta:g} °C "
                         f"(linear to 0 at {tmax:g} °C)")
        r.line('Utilization', f"{util * 100:.0f}% of derated rating")
        verdict = ('FAIL - exceeds rating (guide CMP-17, S1)' if util > 1 else
                   'THIN - above ~60%: hot part, drifts, shorter life' if util > 0.6 else 'OK')
        r.line('Verdict', verdict)
        r.put(derated_w=der, utilization=util, verdict=verdict.split(' ')[0])
        r.note('Many derating guidelines target <= 50-60% of the derated rating. '
               'Check the datasheet derating curve and pulse ratings (guide CMP-20).')
    return r


def cmd_tj(a):
    r = Report('Junction temperature')
    P = parse_si(a.p)
    tj = a.ta + P * a.theta
    r.line('Formula', 'Tj = Ta + P*theta')
    r.line('Inputs', f"P {eng(P, 'W')}, theta {a.theta:g} °C/W, Ta {a.ta:g} °C")
    r.line('Tj', f"{tj:.1f} °C")
    r.put(tj_c=tj)
    if a.tjmax is not None:
        m = a.tjmax - tj
        r.line('Margin', f"{m:.1f} °C below Tj(max) {a.tjmax:g} °C" if m >= 0 else
               f"EXCEEDS Tj(max) by {-m:.1f} °C")
        r.put(margin_c=m)
    r.note('theta_JA in datasheets is measured on a JEDEC test board; your copper area changes it. '
           'Use the datasheet layout guidance or a thermal sim for anything within ~20 °C of Tj(max).')
    return r


def cmd_ldo(a):
    r = Report('Linear regulator (LDO)')
    vin, vout, iout = parse_si(a.vin), parse_si(a.vout), parse_si(a.iout)
    iq = parse_si(a.iq) if a.iq else 0.0
    P = (vin - vout) * iout + vin * iq
    eff = vout * iout / (vin * (iout + iq)) if iout > 0 else 0.0
    r.line('Formula', 'P = (Vin - Vout)*Iout + Vin*Iq ; eff = Vout*Iout/(Vin*Iin)')
    r.line('Inputs', f"Vin {vin:g} V, Vout {vout:g} V, Iout {eng(iout, 'A')}, Iq {eng(iq, 'A')}")
    r.line('Dissipation', eng(P, 'W'))
    r.line('Efficiency', f"{eff * 100:.1f}%")
    r.put(p_w=P, efficiency=eff)
    if a.theta is not None:
        tj = a.ta + P * a.theta
        r.line('Tj', f"{tj:.1f} °C (Ta {a.ta:g} °C, theta {a.theta:g} °C/W)")
        r.put(tj_c=tj)
        if a.tjmax is not None and tj > a.tjmax - 20:
            r.note(f"Tj within 20 °C of Tj(max) {a.tjmax:g} °C: add copper, lower Vin, or use a switcher.")
    if a.dropout is not None:
        vmin = parse_si(a.vin_min) if a.vin_min else vin
        head = vmin - vout - parse_si(a.dropout)
        r.line('Dropout headroom', f"{head:+.3f} V at Vin(min) {vmin:g} V "
                                   f"({'OK' if head >= 0 else 'IN DROPOUT - output will sag'})")
        r.put(headroom_v=head)
    return r


def _copper_t(a):
    if a.t_um:
        return a.t_um * 1e-6
    return a.oz * UM_PER_OZ * 1e-6


def cmd_trace_res(a):
    r = Report('Trace DC resistance')
    w, L = parse_mm(a.w) * 1e-3, parse_mm(a.l) * 1e-3
    t = _copper_t(a)
    rho = RHO_CU_20C * (1 + ALPHA_CU * (a.temp - 20))
    R = rho * L / (w * t)
    r.line('Formula', 'R = rho(T)*L/(w*t) ; rho(T) = 1.724e-8*(1 + 0.00393*(T - 20)) ohm*m')
    r.line('Inputs', f"w {w * 1e3:g} mm, L {L * 1e3:g} mm, t {t * 1e6:.1f} µm, T {a.temp:g} °C")
    r.line('Resistance', eng(R, 'Ω'))
    r.put(r_ohm=R)
    if a.i:
        I = parse_si(a.i)
        r.line('At current', f"{eng(I, 'A')}: drop {eng(I * R, 'V')}, loss {eng(I * I * R, 'W')}")
        r.put(v_drop=I * R, p_w=I * I * R)
        if a.vrail:
            vr = parse_si(a.vrail)
            r.line('Drop vs rail', f"{I * R / vr * 100:.2f}% of {vr:g} V (compare with the load's supply tolerance)")
    r.note('Use FINISHED copper thickness from your fab (outer layers are often plated up). '
           'Guide LAY-27: check IR drop on high-current, low-voltage rails.')
    return r


def cmd_trace_width(a):
    r = Report('Trace width for current (IPC-2221)')
    I = parse_si(a.i)
    k = 0.024 if a.internal else 0.048
    area_mil2 = (I / (k * a.dt ** 0.44)) ** (1 / 0.725)
    t_mil = (a.t_um / 25.4) if a.t_um else a.oz * UM_PER_OZ / 25.4
    w_mil = area_mil2 / t_mil
    w_mm = w_mil * 0.0254
    r.line('Formula', 'I = k*dT^0.44*A^0.725 (A in mil^2; k = 0.048 external, 0.024 internal)')
    r.line('Inputs', f"I {eng(I, 'A')}, dT {a.dt:g} °C, copper {t_mil * 25.4:.1f} µm, "
                     f"{'internal' if a.internal else 'external'} layer")
    r.line('Minimum width', f"{w_mm:.3f} mm ({w_mil:.1f} mil)")
    r.put(width_mm=w_mm, width_mil=w_mil, area_mil2=area_mil2)
    r.note('IPC-2221 is a conservative legacy chart. IPC-2152 is more accurate (and usually '
           'allows narrower internal traces near planes). Also check IR drop with trace-res.')
    return r


def cmd_via(a):
    r = Report('Via inductance and resistance')
    h, d = parse_mm(a.h), parse_mm(a.d)
    guide_ph = 227.8 * h ** 1.676
    h_in, d_in = h / 25.4, d / 25.4
    johnson_nh = 5.08 * h_in * (math.log(4 * h_in / d_in) + 1)
    t = a.plating_um * 1e-3
    ro, ri = d / 2, max(d / 2 - t, 0)
    area_mm2 = math.pi * (ro ** 2 - ri ** 2)
    R = RHO_CU_20C * (h * 1e-3) / (area_mm2 * 1e-6)
    r.line('Inputs', f"length {h:g} mm, drill {d:g} mm, plating {a.plating_um:g} µm")
    r.line('Guide curve fit', f"L ≈ 228*h^1.68 pH -> {guide_ph:.0f} pH "
                              f"(fit to the guide's 45 pH @0.38 mm and 501 pH @1.6 mm)")
    r.line('Johnson formula', f"L = 5.08*h*(ln(4h/d)+1) nH (inches) -> {johnson_nh * 1000:.0f} pH")
    r.line('Barrel resistance', eng(R, 'Ω'))
    r.put(l_guide_ph=guide_ph, l_johnson_ph=johnson_nh * 1000, r_ohm=R)
    if a.i:
        I = parse_si(a.i)
        r.line('At current', f"{eng(I, 'A')}: drop {eng(I * R, 'V')}, loss {eng(I * I * R, 'W')}")
    r.note('The two models assume different return paths, so absolute values differ; both show '
           'inductance growing faster than length. That is why the guide puts the ground plane on '
           'the layer right below the signal layer (LAY-04) and gives every ground pad its own via (LAY-14).')
    return r


def cmd_annular(a):
    r = Report('Annular ring / pad size')
    drill = parse_mm(a.drill)
    if a.pad:
        pad = parse_mm(a.pad)
        ring = (pad - drill) / 2
        r.line('Formula', 'ring = (pad - drill)/2')
        r.line('Result', f"pad {pad:g} mm, drill {drill:g} mm -> ring {ring:.3f} mm")
        r.put(ring_mm=ring)
        if ring < a.min_ring:
            r.note(f"Ring below {a.min_ring:g} mm minimum (guide LAY-08 default 0.175 mm); check your fab.")
    else:
        ring = a.ring
        pad = drill + 2 * ring
        r.line('Formula', 'pad = drill + 2*ring')
        r.line('Result', f"drill {drill:g} mm + 2 x {ring:g} mm -> pad {pad:.3f} mm")
        r.put(pad_mm=pad)
    return r


def _z_microstrip(w, h, t, er):
    arg = 5.98 * h / (0.8 * w + t)
    if arg <= 1:
        return float('nan')
    return 87.0 / math.sqrt(er + 1.41) * math.log(arg)


def cmd_microstrip(a):
    r = Report('Microstrip impedance (IPC-2141A approximation)')
    h, er, t = parse_mm(a.h), a.er, a.t_um * 1e-3
    r.line('Formula', 'Z0 = 87/sqrt(er+1.41) * ln(5.98*h/(0.8*w+t))')
    if a.w:
        w = parse_mm(a.w)
        z = _z_microstrip(w, h, t, er)
        r.line('Inputs', f"w {w:g} mm, h {h:g} mm, t {t:.3f} mm, er {er:g}")
        r.line('Z0', f"{z:.1f} Ω")
        r.put(z0=z, w_mm=w)
    elif a.target:
        lo, hi = 0.01 * h, 3 * h
        if not _z_microstrip(lo, h, t, er) > a.target > _z_microstrip(hi, h, t, er):
            raise SystemExit('target impedance outside the formula range for this stack-up')
        for _ in range(100):
            mid = (lo + hi) / 2
            if _z_microstrip(mid, h, t, er) > a.target:
                lo = mid
            else:
                hi = mid
        w = (lo + hi) / 2
        r.line('Inputs', f"target {a.target:g} Ω, h {h:g} mm, t {t:.3f} mm, er {er:g}")
        r.line('Width', f"{w:.3f} mm ({w / 0.0254:.1f} mil)")
        r.put(w_mm=w, z0=a.target)
    else:
        raise SystemExit('microstrip: give --w or --target')
    ratio = w / h
    if not 0.1 <= ratio <= 2.0:
        r.note(f"w/h = {ratio:.2f} is outside the formula's 0.1-2.0 validity range.")
    r.note('Accuracy ~±5-10%. Solder mask lowers Z0 a few ohms. Final widths come from your '
           "fab's stack-up calculator (guide LAY-03).")
    return r


def cmd_i2c(a):
    r = Report('I2C pull-up range (NXP UM10204)')
    vdd, cb = parse_si(a.vdd), parse_si(a.cb)
    tr = {'standard': 1000e-9, 'fast': 300e-9, 'fastplus': 120e-9}[a.mode]
    iol = parse_si(a.iol) if a.iol else (20e-3 if a.mode == 'fastplus' else 3e-3)
    vol = parse_si(a.vol) if a.vol else (0.4 if vdd > 2 else 0.2 * vdd)
    rmin = (vdd - vol) / iol
    rmax = tr / (0.8473 * cb)
    r.line('Formula', 'Rmin = (VDD - VOL)/IOL ; Rmax = tr/(0.8473*Cb)')
    r.line('Inputs', f"VDD {vdd:g} V, Cb {eng(cb, 'F')}, mode {a.mode} (tr {eng(tr, 's')}), "
                     f"IOL {eng(iol, 'A')}, VOL {vol:g} V")
    r.line('Range', f"{eng(rmin, 'Ω')} .. {eng(rmax, 'Ω')}")
    r.put(rmin=rmin, rmax=rmax)
    if rmin > rmax:
        r.line('Verdict', 'IMPOSSIBLE: bus capacitance too high for this mode. Reduce Cb, slow the '
                          'bus, or use a bus buffer / active pull-up.')
        r.put(pick=None)
    else:
        target = math.sqrt(rmin * rmax)
        pick = nearest_series(target, E12)
        if not rmin <= pick <= rmax:
            pick = nearest_series(rmax, E12, 'below')
        r.line('Suggested', f"{eng(pick, 'Ω')} (E12, near the geometric middle)")
        r.put(pick=pick)
    r.note('Count ALL pull-ups on the bus: breakout boards often add their own; parallel '
           'pull-ups can drop below Rmin.')
    return r


def cmd_crystal(a):
    r = Report('Crystal load capacitors')
    cl, cs = parse_si(a.cl), parse_si(a.cstray)
    cext = 2 * (cl - cs)
    r.line('Formula', 'CL = C1*C2/(C1+C2) + Cstray  ->  C1 = C2 = 2*(CL - Cstray)')
    r.line('Inputs', f"CL {eng(cl, 'F')}, Cstray {eng(cs, 'F')} (pins + traces; 2-5 pF typical)")
    if cext <= 0:
        r.line('Result', 'Stray capacitance already exceeds CL: check the crystal choice.')
        r.put(cext=None)
        return r
    pick = nearest_series(cext, E24)
    cl_act = pick / 2 + cs
    r.line('Ideal C1 = C2', eng(cext, 'F'))
    r.line('Nearest E24', f"{eng(pick, 'F')} -> CL actual {eng(cl_act, 'F')}")
    r.put(cext=cext, pick=pick, cl_actual=cl_act)
    if a.c1m and a.c0:
        c1m, c0 = parse_si(a.c1m), parse_si(a.c0)
        ppm = c1m / 2 * (1 / (c0 + cl_act) - 1 / (c0 + cl)) * 1e6
        r.line('Frequency pull', f"{ppm:+.1f} ppm from the load mismatch")
        r.put(pull_ppm=ppm)
    r.note('Use C0G/NP0 capacitors (guide CMP-11). Keep crystal traces short with ground '
           'around them (guide LAY-11). Radios need tight total ppm: check the IC datasheet.')
    return r


def cmd_battery(a):
    r = Report('Battery life estimate')
    cap_ah = parse_si(a.capacity)
    if cap_ah > 50:
        cap_ah /= 1000.0
        r.note('capacity > 50 interpreted as mAh')
    sleep = parse_si(a.sleep)
    contrib = [('sleep', sleep)]
    for ev in a.event or []:
        parts = [p.strip() for p in ev.split(',')]
        if len(parts) < 3:
            raise SystemExit('--event needs CURRENT,DURATION_S,PERIOD_S')
        I, dur, per = parse_si(parts[0]), parse_si(parts[1]), parse_si(parts[2])
        name = parts[3] if len(parts) > 3 else f"{eng(I, 'A')} for {eng(dur, 's')} every {eng(per, 's')}"
        contrib.append((name, (I - sleep) * dur / per))
    for ex in a.extra or []:
        nm, val = (ex.split('=', 1) + [''])[:2] if '=' in ex else ('extra', ex)
        contrib.append((nm, parse_si(val)))
    i_avg = sum(c for _, c in contrib)
    sd = cap_ah * (a.self_discharge / 100.0) / 8760.0
    if sd > 0:
        contrib.append(('self-discharge (equiv.)', sd))
    i_tot = i_avg + sd
    usable = cap_ah * a.derate
    hours = usable / i_tot
    r.line('Formula', 'life = capacity*derate / (I_avg + self-discharge equivalent)')
    r.line('Capacity', f"{cap_ah * 1000:g} mAh x derate {a.derate:g} = {usable * 1000:.0f} mAh usable")
    for nm, c in contrib:
        r.line(f"  {nm}", f"{eng(c, 'A')} ({c / i_tot * 100:.1f}%)")
    r.line('Average current', eng(i_tot, 'A'))
    r.line('Life', f"{hours / 24:.0f} days = {hours / 8760:.2f} years")
    r.put(i_avg_a=i_tot, life_days=hours / 24, life_years=hours / 8760,
          breakdown={nm: c for nm, c in contrib})
    if a.target_years:
        ok = hours / 8760 >= a.target_years
        r.line('Target', f"{a.target_years:g} years -> {'MET' if ok else 'NOT MET'}")
        r.put(target_met=ok)
    r.note('Derate for cold, end-of-life cut-off voltage and pulse loading (cell datasheet). '
           'Do not forget leakage: electrolytic caps (guide CMP-06), dividers, pull-ups, LEDs.')
    return r


def cmd_flyback(a):
    r = Report('Inductive turn-off (flyback)')
    I, L, C = parse_si(a.i), parse_si(a.l), parse_si(a.cpar)
    R = parse_si(a.r) if a.r else 0.0
    vs = parse_si(a.vsup) if a.vsup else 0.0
    vf = parse_si(a.vf)
    E = 0.5 * L * I * I
    r.line('Inputs', f"I {eng(I, 'A')}, L {eng(L, 'H')}, Cpar {eng(C, 'F')}, R {eng(R, 'Ω')}, Vsup {vs:g} V")
    r.line('Stored energy', f"E = L*I^2/2 = {eng(E, 'J')}")
    w0 = 1 / math.sqrt(L * C)
    alpha = R / (2 * L)
    if alpha < w0:
        wd = math.sqrt(w0 * w0 - alpha * alpha)
        A, B = -vs, (I / C - alpha * vs) / wd
        best_t, best_v = 0.0, 0.0
        for k in range(1, 4001):
            t = k * (2 * math.pi / wd) / 4000
            v = vs + math.exp(-alpha * t) * (A * math.cos(wd * t) + B * math.sin(wd * t))
            if v > best_v:
                best_t, best_v = t, v
        r.line('No clamp: peak', f"{eng(best_v, 'V')} at the switch, {eng(best_t, 's')} after turn-off "
                                 f"(ring {eng(wd / 2 / math.pi, 'Hz')})")
        r.put(v_peak_noclamp=best_v, t_peak_s=best_t, f_ring_hz=wd / 2 / math.pi)
    else:
        r.line('No clamp', 'overdamped by R: peak ~ Vsup + I*R')
        r.put(v_peak_noclamp=vs + I * R)
    r.line('Simple bound', f"I*sqrt(L/C) = {eng(I * math.sqrt(L / C), 'V')} above supply")
    if R > 0:
        t_d = (L / R) * math.log(1 + I * R / vf)
    else:
        t_d = L * I / vf
    r.line('Diode clamp', f"switch sees ~{eng(vs + vf, 'V')}; current decays in {eng(t_d, 's')}")
    r.put(v_clamp_diode=vs + vf, t_decay_diode_s=t_d)
    if a.vz:
        vz = parse_si(a.vz)
        t_z = (L / R) * math.log(1 + I * R / (vz + vf)) if R > 0 else L * I / (vz + vf)
        r.line('Zener + diode', f"switch sees ~{eng(vs + vz + vf, 'V')}; current decays in {eng(t_z, 's')} "
                                f"(faster relay release)")
        r.put(v_clamp_zener=vs + vz + vf, t_decay_zener_s=t_z)
    r.note('Compare the no-clamp peak with the transistor V(BR)CEO / VDS(max): the coil will '
           'avalanche or arc the switch (guide SCH-08, S1). Recipe R1 simulates this.')
    return r


def cmd_hotplug(a):
    r = Report('Hot-plug inrush (series RLC step)')
    V, L, C = parse_si(a.v), parse_si(a.l), parse_si(a.c)
    R = parse_si(a.r) + (parse_si(a.esr) if a.esr else 0.0)
    alpha = R / (2 * L)
    w0 = 1 / math.sqrt(L * C)
    zeta = alpha / w0
    r.line('Inputs', f"V {V:g} V, L {eng(L, 'H')}, R_total {eng(R, 'Ω')}, C {eng(C, 'F')}")
    r.line('Damping', f"zeta = (R/2)*sqrt(C/L) = {zeta:.3f} "
                      f"({'underdamped: rings' if zeta < 1 else 'overdamped'})")
    if zeta < 1:
        wd = w0 * math.sqrt(1 - zeta * zeta)
        tp = math.atan2(wd, alpha) / wd
        ip = V / (wd * L) * math.exp(-alpha * tp) * math.sin(wd * tp)
        vpk = V * (1 + math.exp(-alpha * math.pi / wd))
    elif abs(zeta - 1) < 1e-9:
        tp = 1 / alpha
        ip = V / (L * alpha * math.e)
        vpk = V
    else:
        s1 = -alpha + math.sqrt(alpha * alpha - w0 * w0)
        s2 = -alpha - math.sqrt(alpha * alpha - w0 * w0)
        tp = math.log(s2 / s1) / (s1 - s2)
        ip = V / (L * (s1 - s2)) * (math.exp(s1 * tp) - math.exp(s2 * tp))
        vpk = V
    r.line('Peak current', f"{eng(ip, 'A')} at {eng(tp, 's')}")
    r.line('Capacitor peak', f"{eng(vpk, 'V')} ({(vpk / V - 1) * 100:.0f}% overshoot)")
    r.put(zeta=zeta, i_peak_a=ip, t_peak_s=tp, v_peak=vpk)
    if zeta < 0.5:
        r.note('Low-ESR ceramics on a cable input can ring to ~2x the input voltage. Add damping '
               '(bulk electrolytic/polymer with ESR, series R) or a TVS (expert check EXP-PWR-02).')
    return r


def cmd_pulse_sag(a):
    r = Report('Supply sag under a load pulse')
    vc, ri, I, T = parse_si(a.vcell), parse_si(a.rint), parse_si(a.i), parse_si(a.t)
    v_nocap = vc - I * ri
    r.line('Inputs', f"cell {vc:g} V, R_int {eng(ri, 'Ω')}, pulse {eng(I, 'A')} for {eng(T, 's')}")
    r.line('No buffer cap', f"V = Vcell - I*R_int = {eng(v_nocap, 'V')}")
    r.put(v_nocap=v_nocap)

    def v_end(C, re_):
        tau = (ri + re_) * C
        vcap = vc - I * ri * (1 - math.exp(-T / tau))
        return (vc * re_ + vcap * ri - I * ri * re_) / (ri + re_)

    re_ = parse_si(a.esr) if a.esr else 0.05
    if a.c:
        C = parse_si(a.c)
        v = v_end(C, re_)
        r.line('With buffer cap', f"{eng(C, 'F')} (ESR {eng(re_, 'Ω')}): V(min) = {eng(v, 'V')} "
                                  f"at the end of the pulse (tau = {eng((ri + re_) * C, 's')})")
        r.put(v_min_cap=v)
    if a.vmin:
        vmin = parse_si(a.vmin)
        r.line('Required minimum', f"{vmin:g} V")
        if v_nocap >= vmin:
            r.line('Needed C', 'none - the cell alone stays above the minimum')
        elif v_end(10.0, re_) < vmin:
            r.line('Needed C', 'not reachable: ESR/pulse too large - lower ESR or shorter pulse')
        else:
            lo, hi = 1e-9, 10.0
            for _ in range(200):
                mid = math.sqrt(lo * hi)
                if v_end(mid, re_) >= vmin:
                    hi = mid
                else:
                    lo = mid
            r.line('Needed C', f">= {eng(hi, 'F')} (pick next standard value up, low-leakage type)")
            r.put(c_needed=hi)
    r.note('Use end-of-life and cold R_int from the cell datasheet. Buffer-cap leakage drains '
           'the battery: check it (guide CMP-06). SpiceBridge recipe R9 simulates this.')
    return r


# ---------------------------------------------------------------- CLI

def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--json', action='store_true', help='machine-readable output')
    sub = p.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('rc', help='RC time constant')
    s.add_argument('--r', required=True)
    s.add_argument('--c', required=True, help='nominal capacitance')
    s.add_argument('--ceff', help='effective capacitance after DC bias / temperature')
    s.add_argument('--vstep')
    s.add_argument('--vth')
    s.set_defaults(fn=cmd_rc)

    s = sub.add_parser('mlcc', help='class-2 MLCC DC-bias screen')
    s.add_argument('--c', required=True)
    s.add_argument('--vrated', required=True)
    s.add_argument('--vbias', required=True)
    s.add_argument('--dielectric', help='X5R, X7R, C0G ...')
    s.add_argument('--size', help='EIA inch code: 0402, 0603, 0805, 1206, 1210 ...')
    s.add_argument('--retained', help='fraction or %% retained, from the manufacturer curve')
    s.set_defaults(fn=cmd_mlcc)

    s = sub.add_parser('srf', help='self-resonant frequency')
    s.add_argument('--c')
    s.add_argument('--esl')
    s.add_argument('--esr')
    s.add_argument('--l')
    s.add_argument('--cpar')
    s.add_argument('--f', help='operating frequency to evaluate')
    s.set_defaults(fn=cmd_srf)

    s = sub.add_parser('pdn-z', help='decoupling network impedance')
    s.add_argument('--cap', action='append', required=True, help='"C,ESR,ESL[,count]" (repeat)')
    s.add_argument('--reg', help='"R,L" regulator output model')
    s.add_argument('--fmin', default='1k')
    s.add_argument('--fmax', default='1G')
    s.add_argument('--points', type=int, default=600)
    s.add_argument('--target', help='target impedance')
    s.add_argument('--csv', help='write the sweep to CSV')
    s.set_defaults(fn=cmd_pdn_z)

    s = sub.add_parser('divider', help='resistor divider')
    s.add_argument('--vin', required=True)
    s.add_argument('--r1', required=True, help='top resistor')
    s.add_argument('--r2', required=True, help='bottom resistor')
    s.add_argument('--tol', type=float, default=1.0, help='resistor tolerance %%')
    s.add_argument('--vin-tol', type=float, default=0.0, help='input tolerance %%')
    s.set_defaults(fn=cmd_divider)

    s = sub.add_parser('r-power', help='resistor power vs rating')
    s.add_argument('--r', required=True)
    s.add_argument('--i')
    s.add_argument('--v', help='voltage across the resistor')
    s.add_argument('--rating', help='rated power, e.g. 0.1 or 100m')
    s.add_argument('--ta', type=float, default=25.0, help='ambient °C')
    s.add_argument('--knee', type=float, default=70.0, help='derating starts, °C')
    s.add_argument('--tmax', type=float, default=155.0, help='zero power at, °C')
    s.set_defaults(fn=cmd_r_power)

    s = sub.add_parser('tj', help='junction temperature')
    s.add_argument('--p', required=True)
    s.add_argument('--theta', type=float, required=True, help='°C/W')
    s.add_argument('--ta', type=float, default=25.0)
    s.add_argument('--tjmax', type=float)
    s.set_defaults(fn=cmd_tj)

    s = sub.add_parser('ldo', help='linear regulator')
    s.add_argument('--vin', required=True)
    s.add_argument('--vout', required=True)
    s.add_argument('--iout', required=True)
    s.add_argument('--iq')
    s.add_argument('--theta', type=float)
    s.add_argument('--ta', type=float, default=25.0)
    s.add_argument('--tjmax', type=float, default=125.0)
    s.add_argument('--dropout')
    s.add_argument('--vin-min')
    s.set_defaults(fn=cmd_ldo)

    for name, fn in (('trace-res', cmd_trace_res),):
        s = sub.add_parser(name, help='trace DC resistance')
        s.add_argument('--w', required=True, help='width, mm')
        s.add_argument('--l', required=True, help='length, mm')
        s.add_argument('--oz', type=float, default=1.0)
        s.add_argument('--t-um', type=float, help='copper thickness µm (overrides --oz)')
        s.add_argument('--temp', type=float, default=25.0)
        s.add_argument('--i')
        s.add_argument('--vrail')
        s.set_defaults(fn=fn)

    s = sub.add_parser('trace-width', help='IPC-2221 width for current')
    s.add_argument('--i', required=True)
    s.add_argument('--dt', type=float, default=10.0, help='allowed rise °C')
    s.add_argument('--oz', type=float, default=1.0)
    s.add_argument('--t-um', type=float)
    s.add_argument('--internal', action='store_true')
    s.set_defaults(fn=cmd_trace_width)

    s = sub.add_parser('via', help='via inductance and resistance')
    s.add_argument('--h', required=True, help='via length mm (board or layer-pair thickness)')
    s.add_argument('--d', default='0.3', help='drill mm')
    s.add_argument('--plating-um', type=float, default=20.0)
    s.add_argument('--i')
    s.set_defaults(fn=cmd_via)

    s = sub.add_parser('annular', help='annular ring / pad size')
    s.add_argument('--drill', required=True)
    s.add_argument('--ring', type=float, default=0.175)
    s.add_argument('--pad')
    s.add_argument('--min-ring', type=float, default=0.175)
    s.set_defaults(fn=cmd_annular)

    s = sub.add_parser('microstrip', help='microstrip impedance')
    s.add_argument('--h', required=True, help='dielectric height to plane, mm')
    s.add_argument('--er', type=float, default=4.3)
    s.add_argument('--t-um', type=float, default=35.0)
    s.add_argument('--w', help='trace width mm')
    s.add_argument('--target', type=float, help='target ohms -> solve width')
    s.set_defaults(fn=cmd_microstrip)

    s = sub.add_parser('i2c-pullup', help='I2C pull-up range')
    s.add_argument('--vdd', required=True)
    s.add_argument('--cb', required=True, help='bus capacitance')
    s.add_argument('--mode', choices=['standard', 'fast', 'fastplus'], default='fast')
    s.add_argument('--iol')
    s.add_argument('--vol')
    s.set_defaults(fn=cmd_i2c)

    s = sub.add_parser('crystal', help='crystal load capacitors')
    s.add_argument('--cl', required=True)
    s.add_argument('--cstray', default='3p')
    s.add_argument('--c0', help='shunt capacitance (for pull estimate)')
    s.add_argument('--c1m', help='motional capacitance (for pull estimate)')
    s.set_defaults(fn=cmd_crystal)

    s = sub.add_parser('battery', help='battery life')
    s.add_argument('--capacity', required=True, help='Ah (0.22) or mAh (220)')
    s.add_argument('--sleep', required=True, help='sleep current')
    s.add_argument('--event', action='append', help='CURRENT,DURATION_S,PERIOD_S[,name] (repeat)')
    s.add_argument('--extra', action='append', help='name=CURRENT always-on drain (repeat)')
    s.add_argument('--derate', type=float, default=0.8)
    s.add_argument('--self-discharge', type=float, default=1.0, help='%% per year')
    s.add_argument('--target-years', type=float)
    s.set_defaults(fn=cmd_battery)

    s = sub.add_parser('flyback', help='inductive turn-off')
    s.add_argument('--i', required=True, help='coil current at turn-off')
    s.add_argument('--l', required=True)
    s.add_argument('--cpar', default='50p', help='switch-node capacitance')
    s.add_argument('--r', help='coil resistance')
    s.add_argument('--vsup', help='coil supply')
    s.add_argument('--vf', default='0.8')
    s.add_argument('--vz', help='Zener voltage for a Zener+diode clamp')
    s.set_defaults(fn=cmd_flyback)

    s = sub.add_parser('hotplug', help='hot-plug inrush')
    s.add_argument('--v', required=True)
    s.add_argument('--l', default='1u', help='cable/source inductance (~1 µH per metre of pair)')
    s.add_argument('--r', default='0.05', help='source + cable + connector resistance')
    s.add_argument('--c', required=True)
    s.add_argument('--esr')
    s.set_defaults(fn=cmd_hotplug)

    s = sub.add_parser('pulse-sag', help='cell sag under a pulse')
    s.add_argument('--vcell', required=True)
    s.add_argument('--rint', required=True)
    s.add_argument('--i', required=True)
    s.add_argument('--t', required=True)
    s.add_argument('--c')
    s.add_argument('--esr')
    s.add_argument('--vmin')
    s.set_defaults(fn=cmd_pulse_sag)
    return p


def main(argv=None):
    p = build_parser()
    a = p.parse_args(argv)
    try:
        rep = a.fn(a)
    except ValueError as e:
        raise SystemExit(f"error: {e}")
    rep.emit(a.json)


if __name__ == '__main__':
    main()
