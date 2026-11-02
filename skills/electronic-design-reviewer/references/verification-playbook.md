# Verification playbook: connectors, simulation recipes, fallbacks

Read this in Phase B (automated sweeps) and Phase E (quantitative verification).
Goal: every decisive number comes from a tool run you can name in the Verification Log.

## Contents
1. Connector discovery (and privacy)
2. Capability map
3. SpiceBridge workflow
4. Simulation recipes R1-R10
5. KiCad: MCP tools and kicad-cli
6. Parts and distributor connectors
7. Fallbacks when a tool is missing
8. Verification Log format

---

## 1. Connector discovery (and privacy)

Do this once per review, silently, before Phase B.

1. Search the available tools (tool search, if the host has one) for: `spicebridge`,
   `kicad`, `digikey`, `mouser`, `octopart`, `lcsc`, `jlcpcb`, `browser`.
2. Tool names carry a host prefix. Examples: `mcp__spicebridge__run_transient` (local),
   `mcp__remote-devices__spicebridge__run_transient` (proxied from the user's computer).
   This playbook uses the base names (`run_transient`). Read each tool's schema before the
   first call: parameter names differ between versions.
3. Record what is available in the Verification Log header, e.g.
   `Tools: SpiceBridge (local) ✓ · KiCad MCP ✓ · DigiKey ✓ · kicad-cli ✗`.
4. If a tool errors: fix the input and retry once. Then fall back (section 7) and lower the
   evidence tag. Never report a simulation that did not complete.

**Privacy.** A public hosted SpiceBridge endpoint sends the netlist to someone else's server.
Use a local instance for proprietary circuits, or ask once before sending. Never upload design
files to online viewers or third-party services without the user's OK. Respect any folders or
drives the user has put off-limits.

## 2. Capability map

| Need | SpiceBridge | KiCad side | Fallback (always available) |
|---|---|---|---|
| Netlist sanity | `validate_netlist` | ERC (`kicad-cli sch erc`, MCP `validate_schematic`/ERC tool) | `scripts/netlist_lint.py` |
| Bias point, part stress | `run_dc_op`, `measure_dc`, `measure_power` | - | `ee_calc.py r-power / tj / ldo / divider` |
| Frequency response, impedance | `run_ac_analysis`, `measure_gain`, `measure_bandwidth` | - | `ee_calc.py pdn-z / srf / rc` |
| Transients (flyback, inrush, sag) | `run_transient`, `measure_transient` | - | `ee_calc.py flyback / hotplug / pulse-sag` |
| Tolerances | `run_worst_case`, `run_monte_carlo` | - | `ee_calc.py divider --tol` (worst case) |
| Pass/fail vs spec | `compare_specs` | - | compare in the report table |
| Before/after a fix | `modify_component` then re-run | - | re-run the calculator |
| Picture for the learner | `draw_schematic` | - | ASCII sketch in the report |
| Model from datasheet | `create_model`, `list_models` | - | simplified macromodel (R10 style) |
| Layout facts | - | DRC (`kicad-cli pcb drc`), MCP board tools | `scripts/pcb_check.py` |
| Part data, lifecycle | - | MCP `suggest_jlcpcb_alternatives` (availability) | distributor search via web |

## 3. SpiceBridge workflow

1. **Cut out the question.** Simulate only the subcircuit that decides a finding, plus the
   parasitics that matter (ESR, ESL, coil resistance, switch capacitance, source resistance).
   Start from a template in `assets/sim/` and change values to match the design.
2. **Use real values.** Effective capacitance after DC bias (CMP-03), worst-case supply,
   end-of-life battery resistance, hot ambient.
3. `create_circuit` with the netlist (title line first, `.end` last). If the tool wants the
   analysis inside the netlist, use the "Suggested analysis" line from the template;
   otherwise let `run_*` add it. Then `validate_netlist`.
4. Run the analysis (`run_dc_op` / `run_ac_analysis` / `run_transient`).
5. Measure (`measure_*`) and judge with `compare_specs` against a criterion taken from the
   guide rule or the datasheet (write the criterion down BEFORE you look at the result).
6. Show the fix: `modify_component` (or edit the netlist) and re-run. Before/after numbers
   are the most convincing teaching material you have.
7. Tolerances: `run_worst_case` for anything with a threshold (UVLO, battery monitor, filter
   corner); `run_monte_carlo` when the spread shape matters.
8. `draw_schematic` when a picture will help the learner. `delete_circuit` when done.

**SPICE traps to watch (and teach):** node `0` is ground. `M` means milli in SPICE; write
`meg` for mega. A floating node (no DC path) makes the operating point fail; add a large
resistor to ground. Very fast edges need a small maximum time step, or the peak is missed.
Vendor PSpice/LTspice models may not run in ngspice unchanged; say so if you substitute a
simplified model, and drop the evidence confidence accordingly.

## 4. Simulation recipes R1-R10

Each recipe: when to run it → template → what to measure → pass criterion → what to teach.
Analytic cross-checks are given so a missing simulator never blocks the review.

### R1 Relay/solenoid flyback (SCH-08, SCH-18)
- **When:** any coil switched by a transistor or MOSFET.
- **Template:** `assets/sim/r1_relay_flyback.cir` (set VSUP, LCOIL, RCOIL from the relay datasheet;
  coil L is often not given: 0.1-1 H is typical for small relays, so state the assumption).
- **Measure:** max V(drain) after turn-off, with and without D1; release time (coil current decay).
- **Pass:** peak below 80% of the switch's VCEO / VDS rating.
- **Cross-check:** `ee_calc.py flyback --i <I> --l <L> --r <R> --vsup <V> [--vz <Zener>]`.
- **Teach:** a coil's current cannot change instantly. Without a path, the voltage rises until
  something breaks down. The diode gives the current a loop. A Zener in series speeds release.

### R2 RC delay to a threshold, with a class-2 MLCC (CMP-03, CMP-12, SCH-06)
- **When:** an RC sets a delay, filter corner or reset/enable timing.
- **First find the threshold** the RC drives (EN, reset, comparator, 555 at 2/3 Vcc) and its
  datasheet min/max. The delay is t = −RC·ln(1 − Vth/Vstep), not RC.
- **Then derate C over the voltage it sees while timing** (0 → Vth), not at its final voltage.
- **Template:** `r2_rc_timer_mlcc.cir`. Run with nominal C, then effective C; measure the time
  V(out) crosses Vth (both datasheet limits). **Pass:** delay window inside the spec.
- **Cross-check:** `ee_calc.py rc --r R --c C --ceff Ceff --vstep V --vth Vth` (run at Vth min and max).
- **Teach:** threshold spread often dominates; the dielectric matters most when the capacitor
  sees a large share of its rating while timing. Use C0G/film or a supervisor for accuracy.

### R3 Decoupling network impedance (SCH-07, CMP-01, CMP-02, PLC-02)
- **When:** a fast digital IC, radio, FPGA or ADC rail; or decoupling looks thin.
- **Template:** `r3_pdn_impedance.cir` (use mounted ESL: roughly 0.5-1 nH for 0402/0603 with vias).
- **Measure:** |V(rail)| = |Z| over 1 kHz-1 GHz; peaks and the band above target.
- **Pass:** |Z| ≤ Z_target = allowed ripple ÷ load current step, over the band the IC draws current.
- **Cross-check:** `ee_calc.py pdn-z --cap "C,ESR,ESL[,n]" ... --target Z`.
- **Teach:** each capacitor is only a capacitor below its self-resonance; parallel parts with
  different resonances create anti-resonance peaks between them.

### R4 LC filter with real inductor losses (CMP-22, CMP-23)
- **Template:** `r4_lc_filter_q.cir`. **Measure:** gain peak at f0 and the -3 dB point vs load.
- **Pass:** peaking and corner inside spec at min and max load.
- **Teach:** Q decides how much the filter rings; real inductors bring their own resistance.

### R5 DC operating point and part stress (SCH-18, CMP-17, CMP-24)
- **Template:** `r5_dc_stress_led_driver.cir` (pattern: drive circuit + load). **Measure:**
  `run_dc_op`, then `measure_power` per resistor and semiconductor; currents through LEDs/diodes.
- **Pass:** each part ≤ ~50-60% of its (temperature-derated) rating; no current above datasheet max.
- **Cross-check:** `ee_calc.py r-power`, `tj`, `ldo`.

### R6 Threshold tolerance: dividers, UVLO, battery monitors (EXP-ANA-06)
- **Template:** `r6_divider_worst_case.cir` with `run_worst_case` (resistor tolerance, source range).
- **Pass:** the threshold window stays inside the requirement at both extremes.
- **Cross-check:** `ee_calc.py divider --tol 1 --vin-tol 5`.

### R7 IR drop of a power path (LAY-12, LAY-27)
- No netlist needed: `pcb_check.py board.kicad_pcb --ir NET FROM.PAD TO.PAD --current I`
  (tracks only; pours ignored, so the result is conservative) or `ee_calc.py trace-res`.
- **Pass:** drop + regulator tolerance stays inside the load's supply range.

### R8 Hot-plug inrush and overshoot (EXP-PWR-02)
- **When:** a cable-fed input (DC jack, screw terminal, USB) with ceramic input caps.
- **Template:** `r8_hotplug_inrush.cir`. **Measure:** max V(vin), max I(VSENSE).
- **Pass:** peak below every abs-max on the input node (with margin); inrush within connector/fuse ratings.
- **Cross-check:** `ee_calc.py hotplug`.

### R9 Battery pulse sag (EXP-BAT-04)
- **When:** coin cells or small batteries feeding radio bursts, LEDs, motors.
- **Template:** `r9_coin_cell_pulse.cir`. Run fresh (RINT ~10-30 Ω) and end-of-life/cold
  (100 Ω or more, from the cell datasheet).
- **Measure:** min V(vbat) during the pulse. **Pass:** above the brown-out threshold + margin.
- **Cross-check:** `ee_calc.py pulse-sag --vmin <BOR>` (also reports the needed buffer C).

### R10 Op-amp stability with capacitive load (EXP-ANA-02)
- **Template:** `r10_opamp_cap_load.cir`. Prefer the vendor model or `create_model` from GBW,
  slew rate and output resistance. **Measure:** overshoot and settling of a small step.
- **Pass:** overshoot < ~20% (phase margin > ~45°), or per the circuit's need.

## 5. KiCad: MCP tools and kicad-cli

**Read-only first.** Prefer tools that validate, export or report (ERC/DRC, netlist, BOM,
validate_schematic, validate_symbol_library, board info). Do NOT call tools that change the
design (set_*, update_*, snap_*, sync_*, auto-placement, auto-route) unless the user asked
for that change. If they did, snapshot the project first (e.g. `snapshot_project`).

`suggest_jlcpcb_alternatives` (when present) is useful evidence for supply-chain findings.

**kicad-cli (KiCad 8+; check `kicad-cli <cmd> --help` if a flag fails):**
```
kicad-cli sch export netlist --format kicadsexpr -o design.net design.kicad_sch
kicad-cli sch erc --format json --severity-all -o erc.json design.kicad_sch
kicad-cli pcb drc --format json --schematic-parity --severity-all -o drc.json board.kicad_pcb
kicad-cli sch export bom -o bom.csv design.kicad_sch
```
No KiCad at all? `netlist_lint.py` and `pcb_check.py` read the project files directly
(`.kicad_pcb` carries pad nets, so `netlist_lint.py board.kicad_pcb` works without a netlist export).

## 6. Parts and distributor connectors

For every IC and every part in a finding, fetch: lifecycle (Active / NRND / Obsolete), stock,
the datasheet link, and the parameters you rely on (voltage rating, dielectric, tolerance,
temperature range, package). Before recommending a replacement part, confirm it exists, is
active and fits the footprint. Never invent an MPN.

Manufacturer DC-bias simulators (Murata SimSurfing, TDK, Samsung, KEMET K-SIM) often do not
render through a plain page fetch. Use a browser tool if one is available; otherwise say the
value is from `ee_calc.py mlcc` screening and mark confidence Medium.

## 7. Fallbacks when a tool is missing

| Missing | Do this | Evidence tag |
|---|---|---|
| Simulator | Analytic calc with `ee_calc.py` (same physics, simpler model) | `[CALC]` instead of `[SIM]` |
| KiCad export | `netlist_lint.py` / `pcb_check.py` on the raw files | `[EDA]` (script) |
| Only a PDF/image schematic | Read it visually; zoom dense areas; build a net table by hand for critical nets | `[VISUAL]` (lower confidence) |
| Parts connector | Web search the manufacturer page and distributor listings | `[RESEARCH]` |
| Nothing can verify it | Mark the rule `unverified`, name the missing input, give the user the 1-step check | none |

If a local ngspice exists (e.g. Claude Code on the user's machine), the templates run as
`ngspice -b file.cir` after adding the suggested analysis line.

## 8. Verification Log format

One row per check that produced evidence. The report's credibility lives here.

| # | Question | Tool / method | Inputs (key values) | Result | Tag |
|---|---|---|---|---|---|
| V1 | K1 coil turn-off peak | SpiceBridge run_transient (R1) | 12 V, 400 Ω coil, 100 mH assumed, 50 pF | ~1.3 kV without D1; 12.8 V with D1 | [SIM] |
| V2 | C2 effective C at 3.3 V | ee_calc mlcc (screen) | 10 µF 6.3 V X5R 0603 | HIGH risk, 1.5-6 µF | [CALC] |

Header line: tool availability, rule pack(s) used, assumptions (ambient, supply range).
