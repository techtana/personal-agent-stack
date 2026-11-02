# Rule pack: The Electronic Product Development Checklist v5 (Hans Rosenberg, Aug 2025)

This is the default **house standard** for reviews. It is a paraphrased, checkable version
of the user-supplied guide (hans-rosenberg.com). Page numbers point to the original PDF.
When the user attaches the PDF, quote it sparingly and cite the page. Do not reproduce it.

## How to use this pack

- **Rule header format** (machine-read by `scripts/compliance_score.py`, keep it exact):
  `#### ID — Title` then one metadata line in backticks:
  `` `sev: S2 · w: 5 · phase: schematic · applies: always · verify: netlist_lint · page: 6` ``
- **sev** = default severity when the rule fails (S1 blocker … S4 advisory). Raise or lower it
  for the actual consequence in this design, and say why.
- **w** = scoring weight = severity base (S1 10, S2 5, S3 2, S4 1) × 1.5 where the guide itself
  stresses the point ("crucial", "critical", "NO TRACES!"). That is the compliance weighting.
- **applies** = condition. If it is false for this design, status = `na` with the reason.
- **verify** = the fastest trustworthy way to check it (script, calc, sim recipe, datasheet,
  visual, ERC/DRC, or ask the user).
- **Status values:** `pass` · `partial` · `fail` · `na` · `unverified` (say what input is missing)
  · `waived` (user-accepted deviation, recorded in the ledger).

**Stage → phases to score:** concept → framework · schematic → framework, schematic, components
· placement → + mechanics, placement, library · layout → + layout · release → all phases.

## Contents
1. Framework: Think 5 Steps Ahead (FW-01…06)
2. Drawing the schematic (SCHD-01…06)
3. Schematic checklist (SCH-01…18)
4. Real-world components (CMP-01…24)
5. Board outline and mechanics (MECH-01…04)
6. Component placement (PLC-01…07)
7. Library check (LIB-01…03)
8. Layout (LAY-01…27)

---

## 1. Framework: Think 5 Steps Ahead (page 3)

Ask these about every block. They drive the "why" behind many findings.

#### FW-01 — Pre-mortem on each block
`sev: S3 · w: 2 · phase: framework · applies: always · verify: judgment · page: 3`
- **Check:** For each block, list what could go wrong. Where you are unsure, add options
  (jumpers, DNP alternates) or plan a small prototype.
- **Teach:** Cheap options on the first board turn a respin into a resistor swap.

#### FW-02 — Easy to assemble
`sev: S3 · w: 2 · phase: framework · applies: always · verify: judgment · page: 3`
- **Check:** Clever but slow-to-build ideas are bad for production and repair.

#### FW-03 — Reliability and lifespan
`sev: S2 · w: 5 · phase: framework · applies: always · verify: ee_calc tj/r-power; datasheet · page: 3`
- **Check:** Thermal load, ageing, maximum voltage and current are considered for every block.
- **Teach:** Most field failures are heat or overstress that a two-line calculation would have shown.

#### FW-04 — Combine functions
`sev: S4 · w: 1 · phase: framework · applies: always · verify: judgment · page: 3`
- **Check:** Could one part do two jobs? "The best part is no part."

#### FW-05 — Keep it simple
`sev: S4 · w: 1 · phase: framework · applies: always · verify: judgment · page: 3`
- **Check:** Find the simplest solution that meets the spec (KISS).

#### FW-06 — Fewer unique parts
`sev: S4 · w: 1 · phase: framework · applies: always · verify: netlist_lint (unique_values) · page: 3`
- **Check:** Consolidate resistor/capacitor values where the circuit allows.
- **Teach:** Every unique value is a reel, a feeder slot and a sourcing risk.

---

## 2. Drawing the schematic (page 5)

#### SCHD-01 — Minimize labels
`sev: S4 · w: 1 · phase: schematic · applies: always · verify: netlist_lint --sch (label_heavy) · page: 5`
- **Check:** Labels only for power/ground symbols, buses, single digital I/O or control lines,
  and links between sheets that each hold a complete block.
- **Teach:** A schematic is a picture of signal flow. Labels turn it into a lookup puzzle, and
  puzzles hide errors.

#### SCHD-02 — Wires, not labels, on the same sheet
`sev: S4 · w: 1 · phase: schematic · applies: always · verify: netlist_lint --sch (same_sheet_labels) · page: 5`
- **Check:** Place blocks so a wire can be drawn instead of a same-sheet label.

#### SCHD-03 — One block per sheet, kept together
`sev: S4 · w: 1 · phase: schematic · applies: always · verify: netlist_lint --sch (thin_sheets); visual · page: 5`
- **Check:** Related circuitry sits on one sheet (use a bigger sheet if needed). No one-part sheets.

#### SCHD-04 — Few crossing connections
`sev: S4 · w: 1 · phase: schematic · applies: always · verify: visual · page: 5`

#### SCHD-05 — Sheets ordered input to output
`sev: S4 · w: 1 · phase: schematic · applies: multi-sheet design · verify: visual · page: 5`

#### SCHD-06 — Block diagram for large projects
`sev: S4 · w: 1 · phase: schematic · applies: more than ~4 sheets or several boards · verify: visual · page: 5`

---

## 3. Schematic checklist (page 6)

#### SCH-01 — Nets with only one pin
`sev: S2 · w: 5 · phase: schematic · applies: always · verify: netlist_lint (single_pin_net, unconnected_power_pin); ERC · page: 6`
- **Check:** Every labelled or wired net reaches at least two pins. A power pin left open is S1.
- **Pass:** No one-pin named nets; open pins are deliberate (no-connect flag, datasheet allows it).
- **Teach:** A one-pin net is a wire to nowhere: usually a typo in a label.

#### SCH-02 — Every labelled net verified
`sev: S2 · w: 5 · phase: schematic · applies: design uses labels · verify: netlist_lint --nets (same_label_different_sheets) · page: 6`
- **Check:** Each label connects exactly what was intended. Local labels with the same text on
  different sheets are separate nets.

#### SCH-03 — Electrolytic polarity and voltage
`sev: S1 · w: 10 · phase: schematic · applies: polarized capacitors present · verify: netlist_lint (polarized_cap_*); datasheet · page: 6`
- **Check:** + terminal at the higher potential; rated voltage above the worst-case voltage.
- **Teach:** Reverse bias grows a conductive path through the oxide: the part heats and vents.

#### SCH-04 — No "double names"
`sev: S2 · w: 8 · phase: schematic · applies: always · verify: netlist_lint (name_variants, double_rail_names, generic_rail_names) · page: 6`
- **Check:** One physical net has one name (not VCC on one sheet and 5V on another; not GND/AGND/DGND by accident).
- **Teach:** The tool connects names, not intentions. Two names = two unconnected nets.

#### SCH-05 — One ground
`sev: S2 · w: 8 · phase: schematic · applies: always · verify: netlist_lint (ground_split); pcb_check (split_plane) · page: 6`
- **Check:** A single ground net and plane. Separate grounds only across galvanic isolation.
  Datasheet advice to split grounds is overruled by this guide (record it under "Where sources disagree").
- **Teach:** Return current flows back the lowest-impedance way, right under its signal. A split
  forces it to detour, making a loop antenna and coupling noise.

#### SCH-06 — Every IC datasheet applied
`sev: S2 · w: 5 · phase: schematic · applies: ICs present · verify: datasheet research (per part) · page: 6`
- **Check:** Required external parts, pin strapping, unused-pin handling and layout notes from
  each datasheet are implemented (except the split-ground advice, see SCH-05).
- **Fail as S1** when a missing item stops the part working (e.g. missing required output cap).

#### SCH-07 — Enough decoupling
`sev: S2 · w: 5 · phase: schematic · applies: ICs present · verify: netlist_lint (no_decoupling, thin_decoupling, no_bulk); datasheet; ee_calc pdn-z; sim R3 · page: 6`
- **Check:** Every supply pin has its local capacitor per datasheet, plus bulk capacitance per rail.

#### SCH-08 — Clamp diodes on relay coils
`sev: S1 · w: 10 · phase: schematic · applies: relays, solenoids or other coils switched by a transistor · verify: netlist_lint (no_flyback, flyback_reversed, driver_com); ee_calc flyback; sim R1 · page: 6`
- **Check:** A diode across every coil (cathode to the supply side), or a driver with internal
  clamps whose COM pin connects to the coil supply.
- **Teach:** A coil resists changes in current. Switch it off and it raises the voltage until the
  current finds a path, often straight through your transistor.

#### SCH-09 — Fuses where needed
`sev: S2 · w: 5 · phase: schematic · applies: external power input, batteries with high fault current, mains · verify: judgment; datasheet · page: 6`
- **Check:** Protection against shorts and overloads where a fault could overheat wiring or cells (S1 for mains and lithium packs).

#### SCH-10 — Copied blocks re-checked
`sev: S2 · w: 5 · phase: schematic · applies: blocks reused from other projects · verify: netlist_lint (name collisions); ask · page: 6`
- **Check:** Net names in pasted blocks do not merge with existing nets by accident.

#### SCH-11 — Test points on what matters
`sev: S3 · w: 2 · phase: schematic · applies: always · verify: netlist_lint (rails_without_tp) · page: 6`
- **Check:** Rails, key currents (shunts/links) and key signals can be probed easily.

#### SCH-12 — Options for uncertain circuits
`sev: S3 · w: 2 · phase: schematic · applies: any block the designer is unsure of · verify: ask; DNP list · page: 6`
- **Check:** Jumpers, 0 Ω links or DNP alternates let you try configurations without a respin.

#### SCH-13 — Ground measurement point
`sev: S3 · w: 2 · phase: schematic · applies: always · verify: netlist_lint (no_ground_tp) · page: 6`

#### SCH-14 — Transformer and common-mode choke orientation
`sev: S1 · w: 10 · phase: schematic · applies: transformers or common-mode chokes present · verify: datasheet dot convention vs symbol pin map · page: 6`
- **Check:** Winding phasing matches the dots. In a common-mode choke each line runs through its
  own winding in the same direction. Wired with one winding reversed, it blocks the wanted
  differential signal and lets the common-mode noise through: the opposite of its job.

#### SCH-15 — No floating inputs
`sev: S2 · w: 5 · phase: schematic · applies: always · verify: netlist_lint (floating_input, undriven_net); datasheet · page: 6`
- **Check:** Unused logic, enable and ADC inputs are tied to a defined level (or use a documented internal pull).
- **Teach:** A floating CMOS input is a weathervane in still air: any nearby field flips it, and
  halfway levels make both input transistors conduct at once.

#### SCH-16 — Values sanity-checked
`sev: S2 · w: 5 · phase: schematic · applies: always · verify: netlist_lint (missing_multiplier, value_not_set, cap_no_unit) · page: 6`
- **Check:** No missing multipliers (10 vs 10k), no default values, units on every capacitor.

#### SCH-17 — Mounted / not-mounted set correctly
`sev: S2 · w: 5 · phase: schematic · applies: always · verify: netlist_lint (dnp_mismatch, dnp list) + ask · page: 6`
- **Check:** DNP attributes match intent; "DNP" written in a value field is not enough.

#### SCH-18 — Every part inside its operating limits
`sev: S1 · w: 10 · phase: schematic · applies: always · verify: stress table from datasheets + ee_calc + sim R5 · page: 6`
- **Check:** Worst-case voltage, current, power and temperature for each part stay inside the
  recommended operating conditions (never near absolute maximum).

---

## 4. Real-world components (pages 7-12)

Capacitor properties (page 7):

#### CMP-01 — ESR suits the job
`sev: S2 · w: 5 · phase: components · applies: capacitors in filters, resonators, RF, regulator outputs · verify: datasheet; sim R3/R4 · page: 7`
- **Check:** Low ESR (high Q) where losses matter; an ESR window where a regulator needs it for stability.

#### CMP-02 — Used below self-resonance
`sev: S3 · w: 2 · phase: components · applies: capacitors at high frequency · verify: ee_calc srf; ee_calc pdn-z · page: 7`
- **Check:** Above its self-resonant frequency a capacitor acts as an inductor.

#### CMP-03 — DC-bias loss of class 2/3 ceramics accounted for
`sev: S2 · w: 8 · phase: components · applies: X5R/X7R/Y5V-type MLCCs · verify: netlist_lint (dc_bias); ee_calc mlcc; maker DC-bias curve · page: 7-8`
- **Check:** Effective capacitance at the working voltage (and temperature) still meets the need.
  X5R can lose about 84% at rated voltage.
- **Teach:** In ferroelectric ceramics the DC field locks the tiny dipoles in place, so fewer of
  them can follow the signal. Fewer helpers, less capacitance.

#### CMP-04 — Voltage rating with margin
`sev: S2 · w: 5 · phase: components · applies: all capacitors · verify: netlist_lint (cap_overvoltage, cap_margin) · page: 7`
- **Check:** Rated voltage above worst-case voltage including spikes. Exceeding it is S1.

#### CMP-05 — Temperature coefficient
`sev: S2 · w: 5 · phase: components · applies: capacitors where value matters · verify: dielectric code; datasheet · page: 7-8`
- **Check:** Class 2/3 drift is acceptable over the operating range (worst case seen ~70% between
  25 and 75 °C).

#### CMP-06 — Leakage acceptable
`sev: S2 · w: 5 · phase: components · applies: electrolytics; battery-powered or high-impedance circuits · verify: datasheet leakage spec; ee_calc battery · page: 7`
- **Check:** Electrolytic leakage does not drain a battery, upset a timer or bias a high-impedance node.

#### CMP-07 — Polarity respected
`sev: S1 · w: 10 · phase: components · applies: polarized capacitors · verify: see SCH-03 · page: 7`

#### CMP-08 — Microphonics considered
`sev: S3 · w: 2 · phase: components · applies: vibration plus sensitive analog signal paths · verify: judgment · page: 7`
- **Check:** Class 2/3 MLCCs are piezoelectric; keep them out of sensitive signal paths in vibrating products.

#### CMP-09 — Electrolytic lifetime
`sev: S2 · w: 5 · phase: components · applies: aluminum electrolytics in long-life or hot products · verify: datasheet (hours at temperature, ripple current) · page: 7, 10`
- **Check:** Rated life at the real temperature and ripple current covers the product life.

#### CMP-10 — Price compared
`sev: S4 · w: 1 · phase: components · applies: always · verify: distributor search · page: 7`

Choosing capacitor types (pages 8-10):

#### CMP-11 — C0G/NP0 for precision roles
`sev: S2 · w: 5 · phase: components · applies: accurate filters, RF matching, oscillators, PLL loop filters, low-distortion coupling · verify: BOM dielectric · page: 8`

#### CMP-12 — No class 2/3 ceramics in timing or signal coupling
`sev: S2 · w: 5 · phase: components · applies: RC timers, audio/signal coupling · verify: BOM dielectric; ee_calc rc --ceff; sim R2 · page: 8`
- **Check:** Their voltage dependence shortens time constants and adds distortion.
- **Teach:** How much depends on the voltage the capacitor sees while it times. A 555 (trips at
  2/3 of the supply) suffers badly; a low-threshold enable pin barely does, but there the
  threshold spread dominates: delay = −RC·ln(1 − Vth/V). Compute both before judging.

#### CMP-13 — Class 2 decoupling sized for the loss
`sev: S3 · w: 2 · phase: components · applies: class-2 decoupling caps · verify: ee_calc mlcc · page: 8`
- **Check:** Choose a larger value or a much higher voltage rating than the rail (the guide's
  author runs 100 nF/100 V X7R parts up to ~35 V).

#### CMP-14 — Polymer for large capacitance
`sev: S4 · w: 1 · phase: components · applies: large MLCC banks · verify: judgment · page: 8, 10`
- **Check:** Aluminum polymer often beats a big MLCC bank: no bias loss, low ESR.

#### CMP-15 — Film where stability or high voltage is needed
`sev: S4 · w: 1 · phase: components · applies: precision, high voltage or low-loss roles · verify: BOM · page: 9`
- **Check:** Polypropylene for the lowest loss.

#### CMP-16 — Silvered mica only when justified
`sev: S4 · w: 1 · phase: components · applies: extreme stability needs · verify: BOM · page: 10`

Resistors (page 11):

#### CMP-17 — Resistor power and voltage within rating
`sev: S1 · w: 15 · phase: components · applies: always · verify: ee_calc r-power; sim R5 measure_power · page: 11`
- **Check:** Dissipation and voltage inside the (temperature-derated) rating. The guide calls this crucial.

#### CMP-18 — Low-noise resistor types in sensitive analog paths
`sev: S3 · w: 2 · phase: components · applies: low-noise or low-distortion analog · verify: BOM technology · page: 11`
- **Check:** Thin film, metal film or wirewound where 1/f excess noise or distortion matters; no carbon types.

#### CMP-19 — Power resistors can shed their heat
`sev: S2 · w: 5 · phase: components · applies: resistors dissipating significant power · verify: ee_calc tj/r-power; layout copper · page: 11`
- **Check:** Heatsink-mount parts or copper area. Large copper adds capacitance: mind the signal frequency.

#### CMP-20 — Pulse ratings where peaks occur
`sev: S2 · w: 5 · phase: components · applies: inrush, surge or pulse loads · verify: datasheet pulse curve · page: 11`

Inductors (pages 11-12):

#### CMP-21 — DC-DC inductor per converter datasheet
`sev: S2 · w: 5 · phase: components · applies: switching regulators · verify: datasheet (type, saturation current, DCR) · page: 11`

#### CMP-22 — RF/filter inductor losses simulated
`sev: S3 · w: 2 · phase: components · applies: RF matching or LC filters · verify: sim R4 with Q model · page: 12`

#### CMP-23 — Inductor self-resonance well above use frequency
`sev: S2 · w: 5 · phase: components · applies: inductors in AC/RF paths · verify: ee_calc srf --l --cpar · page: 12`
- **Check:** Above its SRF an inductor acts as a capacitor.

Semiconductors (page 12):

#### CMP-24 — Semiconductor heat, current and power
`sev: S1 · w: 10 · phase: components · applies: transistors, diodes, MOSFETs, Zeners, regulators · verify: ee_calc tj/ldo; sim R5 · page: 12`
- **Check:** Each part can carry its current and get rid of its heat with margin.

---

## 5. Board outline and mechanics (page 12)

#### MECH-01 — Outline known before placement
`sev: S3 · w: 2 · phase: mechanics · applies: always · verify: ask; Edge.Cuts present · page: 12`

#### MECH-02 — Mounting holes
`sev: S2 · w: 5 · phase: mechanics · applies: board is screwed or bolted in place · verify: pcb_check (no_mounting_holes) · page: 12`

#### MECH-03 — Interface parts where the enclosure needs them
`sev: S2 · w: 5 · phase: mechanics · applies: connectors, buttons, LEDs, displays · verify: ask; mechanical drawing · page: 12`

#### MECH-04 — Heatsinks and thermal interfaces planned
`sev: S2 · w: 5 · phase: mechanics · applies: parts needing heatsinks · verify: ask; layout · page: 12`

---

## 6. Component placement (pages 12-13)

#### PLC-01 — Each circuit block placed as a group
`sev: S3 · w: 3 · phase: placement · applies: always · verify: visual · page: 12`
- **Check:** Main part first, its support parts around it, routed with few vias and short traces.

#### PLC-02 — Decoupling caps as close as possible
`sev: S2 · w: 8 · phase: placement · applies: ICs present · verify: pcb_check (decap_far) · page: 12`
- **Teach:** Every millimetre of path adds loop inductance, and inductance blocks exactly the fast
  current the capacitor is there to supply.

#### PLC-03 — Support parts placed to avoid crossings
`sev: S3 · w: 2 · phase: placement · applies: always · verify: visual (ratsnest) · page: 12`

#### PLC-04 — Unshielded inductors not in line
`sev: S2 · w: 5 · phase: placement · applies: two or more inductors · verify: pcb_check (inductor_proximity); datasheet shielding · page: 12`

#### PLC-05 — Board order follows the schematic signal path
`sev: S3 · w: 2 · phase: placement · applies: signal chains · verify: visual · page: 13`
- **Check:** Blocks 1-2-3-4 on the schematic sit 1-2-3-4 on the board, with the shortest links
  for high-dynamic-range analog.

#### PLC-06 — Aggressors away from victims
`sev: S2 · w: 5 · phase: placement · applies: switchers, fast digital, radios, ADCs, sensors · verify: visual; pcb_check positions · page: 13`
- **Check:** DC/DC converters and switching logic kept away from receivers, ADCs and sensitive
  sensors; shield cans if demands are high.

#### PLC-07 — Conflicts between PLC-05 and PLC-06 decided on purpose
`sev: S4 · w: 1 · phase: placement · applies: when both apply · verify: ask · page: 13`

---

## 7. Library check (pages 13-14)

#### LIB-01 — 1:1 print footprint check
`sev: S2 · w: 8 · phase: library · applies: before first build or new footprints · verify: ask (user does it); offer the procedure · page: 13`
- **Check:** Print the placed board at 1:1, confirm scale with a ruler on the outline, lay the real parts on it.

#### LIB-02 — Pinouts match the datasheet
`sev: S1 · w: 10 · phase: library · applies: always · verify: datasheet pin table vs symbol and footprint; netlist pinfunctions · page: 13`
- **Check:** Pin numbers, pad numbers and package variant agree for every part.

#### LIB-03 — Connector pinouts, incl. ribbon-cable mirroring
`sev: S1 · w: 10 · phase: library · applies: connectors and cables · verify: mating-side drawing; cable pin-1 mapping · page: 14`

---

## 8. Layout (pages 14-18)

Stack-up and layers (pages 14-16):

#### LAY-01 — Layer count fits the job
`sev: S3 · w: 2 · phase: layout · applies: always · verify: pcb_check (copper_layers) · page: 14`
- **Check:** 2 layers for simple boards; 4 layers when complex or when high-frequency grounding matters (much better grounding).

#### LAY-02 — Advanced vias only when needed
`sev: S4 · w: 1 · phase: layout · applies: BGA/fine pitch · verify: fab notes · page: 14`
- **Check:** Microvias (allowed in pads) and buried vias cost more; use them only when required.

#### LAY-03 — Stack-up heights confirmed for impedance control
`sev: S2 · w: 5 · phase: layout · applies: controlled-impedance traces (RF, USB, Ethernet, fast clocks) · verify: fab stack-up; ee_calc microstrip · page: 14`

#### LAY-04 — Ground plane next to the busiest AC layer
`sev: S2 · w: 8 · phase: layout · applies: always · verify: pcb_check (no_l2_plane, gnd_zone_coverage); ee_calc via · page: 15`
- **Check:** The plane sits on the layer closest to the layer carrying most AC signals.
- **Teach:** Short via to the plane = low inductance. The guide's example: 0.38 mm to Inner1 is
  ~45 pH; going through a 1.6 mm board is ~501 pH, over 11 times more.

#### LAY-05 — 2-layer assignment
`sev: S2 · w: 5 · phase: layout · applies: 2-layer boards · verify: pcb_check (no_bottom_plane, bottom_traces) · page: 15`
- **Check:** Top: parts, signals, supplies. Bottom: ground plane with as few traces as possible.

#### LAY-06 — 4-layer assignment
`sev: S2 · w: 8 · phase: layout · applies: 4+ layer boards · verify: pcb_check (traces_on_l2, split_plane, no_l2_plane) · page: 15`
- **Check:** Inner1 = solid ground, only via holes, NO traces. Inner2 = supply/connecting traces
  with the rest ground-filled and stitched to Inner1. Bottom = traces if needed, otherwise ground
  stitched with many vias. (Parts on both sides: bottom carries parts and traces too.)

#### LAY-07 — No floating copper on RF boards
`sev: S2 · w: 5 · phase: layout · applies: RF or radio boards (S3 otherwise) · verify: pcb_check (floating_copper) · page: 16`
- **Teach:** An unconnected copper island is a resonator waiting for a frequency.

Board technology (page 16):

#### LAY-08 — Fab design rules entered
`sev: S2 · w: 5 · phase: layout · applies: always · verify: pcb_check (thin_track, via_ring); DRC settings vs fab · page: 16`
- **Check:** Defaults that suit standard processes: track 0.15 mm, space 0.15 mm, drill 0.25-0.3 mm,
  annular ring 0.175 mm (0.3 mm drill → 0.65 mm pad). Your fab's published rules win for manufacturability.

#### LAY-09 — All secondary rules checked for volume production
`sev: S3 · w: 2 · phase: layout · applies: series production · verify: ask; fab DFM report · page: 16`

Layout order (pages 16-17), checked by its result:

#### LAY-10 — Ground plane poured first, over the whole board
`sev: S2 · w: 5 · phase: layout · applies: always · verify: pcb_check (gnd_zone_coverage) · page: 16`

#### LAY-11 — Critical signals routed first, short and guarded
`sev: S2 · w: 5 · phase: layout · applies: analog/RF/sensor inputs, crystals, reset lines · verify: visual; pcb_check track lengths · page: 16`

#### LAY-12 — High-current supply traces wide and short
`sev: S2 · w: 5 · phase: layout · applies: large power consumers · verify: ee_calc trace-width/trace-res; pcb_check --ir · page: 16`

#### LAY-13 — Blocks routed, then links between blocks
`sev: S4 · w: 1 · phase: layout · applies: always · verify: visual · page: 16-17`

#### LAY-14 — Each ground connection has its own via
`sev: S2 · w: 8 · phase: layout · applies: always · verify: pcb_check (shared_ground_via, ground_pad_no_via, pour_no_near_via, top_ground_pour_2layer) · page: 16-17`
- **Check:** Every ground pad gets its own via to the plane. On 2-layer boards that via is the only
  ground path (no extra top-copper route). Same for supply pads to a power plane, with the via
  next to the decoupling cap. The guide calls this critical.
- **Teach:** Shared vias make many currents share one inductance, so they push each other's noise
  around (common-impedance coupling).

Final layout checklist (pages 17-18):

#### LAY-15 — DRC clean
`sev: S1 · w: 10 · phase: layout · applies: always · verify: KiCad DRC (kicad-cli pcb drc) · page: 17`

#### LAY-16 — Connectivity complete
`sev: S1 · w: 10 · phase: layout · applies: always · verify: DRC unconnected items; schematic parity · page: 17`

#### LAY-17 — Fiducials
`sev: S3 · w: 2 · phase: layout · applies: machine assembly · verify: pcb_check (few_fiducials, no_local_fiducials) · page: 17`
- **Check:** Three global fiducials far apart near corners, plus three local ones around fine-pitch areas.

#### LAY-18 — Text and version on the board
`sev: S3 · w: 2 · phase: layout · applies: always · verify: pcb_check (no_version_text) · page: 17`

#### LAY-19 — Layer markers
`sev: S3 · w: 2 · phase: layout · applies: multilayer boards (S4 on 2-layer) · verify: pcb_check (layer_markers) · page: 17`
- **Check:** Numbers 1..N in copper on each layer, stacked at one spot.

#### LAY-20 — Order codes on all parts
`sev: S3 · w: 2 · phase: layout · applies: assembly service or BOM handover · verify: netlist_lint (missing_order_codes) · page: 17`

#### LAY-21 — Ground points for measuring
`sev: S3 · w: 2 · phase: layout · applies: always · verify: netlist_lint (no_ground_tp); visual · page: 17`

#### LAY-22 — Smallest vias only where forced
`sev: S3 · w: 2 · phase: layout · applies: always · verify: pcb_check (smallest_vias_everywhere) · page: 17`

#### LAY-23 — Test points named
`sev: S3 · w: 2 · phase: layout · applies: test points present · verify: visual (silkscreen) · page: 17`

#### LAY-24 — Paste layer correct
`sev: S2 · w: 5 · phase: layout · applies: SMD assembly · verify: pcb_check (pads_without_paste) · page: 17`
- **Check:** Every pad that needs solder has a stencil opening; pads that must stay bare have none.

#### LAY-25 — Copper balance
`sev: S3 · w: 2 · phase: layout · applies: always (most important for 4+ layers) · verify: pcb_check (copper_imbalance, layer_imbalance) · page: 18`
- **Check:** Similar copper across layers and regions; fill unused space with stitched ground.

#### LAY-26 — Room to assemble
`sev: S2 · w: 5 · phase: layout · applies: always · verify: DRC courtyards; assembler rules · page: 18`

#### LAY-27 — DC resistance of high-current paths
`sev: S2 · w: 5 · phase: layout · applies: high current or low-voltage/high-current rails · verify: pcb_check --ir; ee_calc trace-res · page: 18`
- **Check:** IR drop stays inside the load's supply tolerance (FPGA cores are the classic victim).

---

Out of the guide's scope (pages 18): manufacturer choice, assembly process, test and
measurement. The skill's expert checks (references/expert-checks.md) cover these at lower weight.
