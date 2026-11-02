# Expert checks beyond the guide

The guide is deliberately condensed: it leaves detailed circuit design, assembly and test
out of scope. A senior reviewer still checks these. Run the modules that match the design
(Phase F). Report hits as **expert findings**: tier 4 weight for ranking, outside the guide
compliance score, but counted in the verdict by severity like any other finding.

Each check: ID, default severity, how to verify, what to look for and why.

## Contents
PWR power · BAT battery and low power · DIG digital and MCU · ANA analog and sensors ·
RF wireless · DRV drivers and inductive loads · SAF protection, safety, EMC, thermal ·
MFG manufacturing · TST test and bring-up · SUP supply chain · DOC documentation

---

## PWR - Power entry and regulation

**EXP-PWR-01 — Input protection** · S2 (S1 if users can plug in the wrong supply) · verify: schematic, TVS datasheet
Reverse polarity (series Schottky: simple, costs its forward drop; P-MOSFET "ideal diode": low loss).
TVS: standoff voltage ≥ max normal input; clamping voltage at the expected surge current below
every downstream absolute maximum.

**EXP-PWR-02 — Hot-plug inrush and overshoot** · S2 · verify: sim R8, `ee_calc.py hotplug`
Cable inductance + low-ESR ceramics ring to nearly 2× the input on hot-plug. Damp it (bulk
electrolytic/polymer with ESR, series R, TVS) or soft-start with a load switch.

**EXP-PWR-03 — Regulator output capacitor and stability** · S1 when outside the stable range · verify: datasheet "output capacitor" section; `ee_calc.py mlcc`
Value, type and ESR window per datasheet. Use the EFFECTIVE capacitance after DC bias: a
"10 µF" X5R may be 3 µF at the output voltage and fall below the stable minimum.

**EXP-PWR-04 — Linear regulator heat and dropout** · S2 · verify: `ee_calc.py ldo`
P = (Vin − Vout)·Iout. Check dropout at the LOWEST input (battery end-of-life, USB droop).

**EXP-PWR-05 — Switching regulator layout** · S2 · verify: layout vs datasheet example
Input capacitor right at VIN/GND (the hot loop); small switch-node copper; feedback divider at
the IC and its trace away from the switch node and inductor.

**EXP-PWR-06 — Back-powering through I/O pins** · S2 · verify: trace every signal that crosses between domains that can be off
A logic high into an unpowered IC powers it through its ESD diodes: odd resets, leakage, latch-up.
Common with power-gated sensors and USB-sensing dividers.

**EXP-PWR-07 — Brown-out and power-on reset** · S2 · verify: MCU datasheet BOR levels
Brown-out detection on, at a threshold above every part's minimum operating voltage on that rail.

**EXP-PWR-08 — Ferrite beads** · S3 · verify: bead impedance vs DC bias curve
Bead impedance collapses with DC current. A bead + capacitor is an LC that can peak; damp it.

**EXP-PWR-09 — Sequencing** · S2 · verify: datasheets of multi-rail parts (FPGAs, some ADCs)

**EXP-PWR-10 — Clean rails for sensitive circuits** · S3 · verify: LDO PSRR at the switcher frequency; RC/LC filters
Regulator PSRR drops at high frequency; ADC references and radios need filtering.

## BAT - Battery and low power

**EXP-BAT-01 — Current budget closes** · S2 · verify: `ee_calc.py battery --target-years`
Count every always-on path: sleep current, regulator Iq, dividers, pull-ups held low, LEDs,
sensor standby, electrolytic leakage (guide CMP-06), self-discharge.

**EXP-BAT-02 — Battery-sense divider** · S3 · verify: `ee_calc.py divider`
Either switch it (MOSFET) or use high values with a capacitor at the ADC pin. Mind ADC source impedance.

**EXP-BAT-03 — Regulator choice for battery life** · S3 · verify: datasheet Iq and dropout
µA-class Iq, or run directly from the cell if every part tolerates its full voltage range.

**EXP-BAT-04 — Pulse capability and sag** · S2 · verify: sim R9, `ee_calc.py pulse-sag`
Coin cells have tens to hundreds of ohms internal resistance (worse when cold or old). Radio
bursts can trip brown-out. A low-leakage buffer capacitor fixes it.

**EXP-BAT-05 — Lithium cells** · S1 if a bare cell has no protection · verify: schematic, charger datasheet, cell datasheet
Protection (over/under-voltage, over-current, short), a charger with thermistor input, no
charging outside the cell's temperature window (commonly 0-45 °C), charge current per the cell.

**EXP-BAT-06 — Sleep-current measurement access** · S3 · verify: schematic
A 0 Ω link, jumper or shunt footprint in the supply path makes the current budget measurable.

**EXP-BAT-07 — Reverse insertion** · S2 · verify: holder type and protection
User-replaceable cells will be inserted backwards eventually.

## DIG - Digital and MCU

**EXP-DIG-01 — Boot, strap and reset pins** · S1 if the part cannot boot · verify: datasheet pin table
Strap levels set; reset pin per datasheet (pull-up, capacitor if allowed); reset trace short (LAY-11).

**EXP-DIG-02 — Programming and debug access** · S2 · verify: schematic
SWD/JTAG/UART reachable, with GND and target-voltage reference.

**EXP-DIG-03 — Crystal circuit** · S2 · verify: `ee_calc.py crystal`; oscillator datasheet
Load capacitors from CL and stray capacitance (C0G, guide CMP-11); crystal ESR and drive level
within the oscillator's limits; short, guarded traces (LAY-11).

**EXP-DIG-04 — I2C and other open-drain buses** · S2 · verify: `ee_calc.py i2c-pullup`
Pull-ups sized for bus capacitance and speed; one set per bus (breakout boards add their own);
pull-up voltage matches every device's input range.

**EXP-DIG-05 — Logic levels between domains** · S1 if an abs max is exceeded · verify: VIH/VIL/VOH/VOL and abs max
"5 V tolerant" only as stated in the datasheet, and often only while the part is powered.

**EXP-DIG-06 — Unused pins** · S3 · verify: datasheet recommendation
Pure inputs tied in hardware (guide SCH-15); configurable GPIO set by firmware: list them for the user.

**EXP-DIG-07 — USB** · S2 · verify: schematic and layout
ESD protection at the connector; USB-C sink: a separate 5.1 kΩ pull-down on EACH CC pin;
D+/D− as a 90 Ω differential pair; VBUS capacitance at attach within the USB limit (10 µF
for USB 2.0 devices) unless soft-started.

**EXP-DIG-08 — Signal integrity** · S3 · verify: edge rate vs trace length; layout
Series termination on fast edges driving long traces; unbroken return path under every fast signal.

## ANA - Analog and sensors

**EXP-ANA-01 — Op-amp ranges** · S2 · verify: datasheet input common-mode and output swing under load
"Rail-to-rail" has conditions. Single-supply circuits need a valid bias point.

**EXP-ANA-02 — Op-amp stability** · S2 · verify: sim R10
Capacitive loads (cables, ADC inputs) erode phase margin; use an isolation resistor. Check
decompensated op-amps are used at a stable gain.

**EXP-ANA-03 — ADC driving** · S2 · verify: ADC datasheet (max source impedance, sampling time)
The sampling capacitor kicks charge back into the source. A local RC charge reservoir or a
buffer is often required. Add an anti-alias filter where the signal has out-of-band content.

**EXP-ANA-04 — Voltage references** · S2 · verify: datasheet stability vs load capacitance
Some references oscillate with the "wrong" capacitor. Decouple per datasheet.

**EXP-ANA-05 — High-impedance nodes** · S3 · verify: layout, cleaning, guard rings
Surface leakage and flux residue shift megaohm nodes; guard rings help.

**EXP-ANA-06 — Tolerance stack-up** · S2 · verify: sim R6 worst case; `ee_calc.py divider --tol`
Every threshold (UVLO, battery cut-off, comparator trip) checked at the tolerance extremes.

**EXP-ANA-07 — Ratiometric measurement** · S3 · verify: schematic
Excite a resistive sensor from the same reference the ADC uses: supply noise then cancels.

## RF - Wireless

**EXP-RF-01 — Antenna region** · S1 if it breaks the radio · verify: module/antenna datasheet layout
Copper keep-out exactly as specified, antenna at the board edge, no parts or planes where forbidden.

**EXP-RF-02 — Matching network footprint** · S3 · verify: schematic
A pi-network footprint (populate 0 Ω + DNP) lets you tune the antenna after the first build.

**EXP-RF-03 — 50 Ω feedline** · S2 · verify: fab stack-up calculator; `ee_calc.py microstrip` (estimate)

**EXP-RF-04 — Crystal accuracy** · S2 · verify: radio IC datasheet total ppm (tolerance + temperature + ageing)

**EXP-RF-05 — Ground stitching** · S3 · verify: layout
Stitching vias along RF traces and board edges; no floating copper (guide LAY-07).

**EXP-RF-06 — Radio supply** · S2 · verify: reference design decoupling; switcher placement (PLC-06)

## DRV - Drivers and inductive loads

**EXP-DRV-01 — Clamp choice** · S3 · verify: sim R1
A plain diode makes relays release slowly; a Zener in series speeds release (check the switch rating).

**EXP-DRV-02 — MOSFET gate drive** · S2 · verify: RDS(on) at your actual VGS
VGS(th) is where the FET barely starts to conduct, not where it is fully on. At 3.3 V drive use a
part with RDS(on) specified at 2.5 V or 3.3 V. Add a gate pull-down so it stays off while the MCU resets.

**EXP-DRV-03 — BJT base drive** · S3 · verify: `ee_calc.py`, datasheet hFE at your current
For saturation, design for a forced beta of about 10-20, not the typical hFE.

**EXP-DRV-04 — Driver ICs (ULN2003 type)** · S1 if COM is wrong · verify: netlist_lint `driver_com`
COM must connect to the load supply for the internal clamps to work. Check total package dissipation.

**EXP-DRV-05 — Motors, pumps, solenoids and contact-switched inductive loads** · S2 · verify: netlist_lint `contact_load_no_suppression` / `load_no_flyback`; stall current; bulk capacitance at the driver
Opening relay contacts on an inductive load draws an arc and a voltage spike: contact wear and
EMI that resets nearby logic, typically at turn-OFF. Put a diode across a DC load (or an RC
snubber/TVS across the contacts for AC), and keep the load's return current out of the logic
ground path.

**EXP-DRV-06 — High-current return paths** · S2 · verify: layout
On one ground plane (guide SCH-05), place parts so big return currents do not flow under
sensitive circuits.

## SAF - Protection, safety, EMC, thermal

**EXP-SAF-01 — Hazardous voltage** · S1 · verify: IEC 62368-1 creepage/clearance tables; certified parts
Above about 60 V DC or 30 V rms / 42.4 V peak: creepage and clearance by working voltage,
pollution degree and material group; fusing; isolation slots. Say clearly that an AI review is
not a safety certification; recommend a qualified review and compliance testing.

**EXP-SAF-02 — ESD on user-touchable parts** · S2 · verify: TVS placement right at the connector, short path to ground

**EXP-SAF-03 — Fuse and PTC selection** · S2 · verify: voltage rating, breaking capacity, I²t vs inrush, PTC hold/trip vs temperature

**EXP-SAF-04 — EMC basics** · S2 · verify: layout
No plane slots under fast traces; clocks short and away from connectors; filtered cable entries;
small switching loops.

**EXP-SAF-05 — Thermal layout** · S2 · verify: `ee_calc.py tj`; datasheet thermal-pad via pattern
Hot parts away from electrolytics (lifetime, guide CMP-09) and temperature sensors.

## MFG - Manufacturing (DFM/DFA)

**EXP-MFG-01 — Assembly method fit** · S2 · verify: ask (hand vs service); package sizes
Hand assembly: prefer 0603 or larger, avoid leadless and BGA parts without reflow tools.
Assembly service: use parts from its library where possible (cost and lead time).

**EXP-MFG-02 — Tombstoning** · S3 · verify: pad copper symmetry on 0402/0201
Unequal heat sinking lifts one end. Use thermal reliefs on plane-connected small pads.

**EXP-MFG-03 — Vias in pads** · S2 · verify: fab capability
Open vias in pads wick solder away. Use filled-and-capped vias or microvias (guide LAY-02), or move them.

**EXP-MFG-04 — Polarity and pin-1 marks** · S3 · verify: silkscreen visible after assembly

**EXP-MFG-05 — Edge clearance** · S3 · verify: parts and copper away from V-score/routed edges

## TST - Test and bring-up

**EXP-TST-01 — Bring-up plan** · S3 · verify: schematic options
Current-limited first power-up; 0 Ω links to isolate blocks; measure rails at test points
before fitting expensive parts.

**EXP-TST-02 — Probe-friendly test points** · S3 · verify: size, labels, ground nearby (guide SCH-11, LAY-23)

## SUP - Supply chain

**EXP-SUP-01 — Lifecycle and stock** · S2 (S1 if obsolete with no alternative) · verify: parts connector or distributor
Avoid NRND/EOL/obsolete parts; stock several times the build quantity; second source for critical parts.

**EXP-SUP-02 — Authorized sources for ICs** · S3 · verify: distributor
Marketplace "equivalents" can be clones that miss specs.

## DOC - Documentation

**EXP-DOC-01 — Design intent recorded** · S4 · verify: notes on the schematic or in the ledger
Non-obvious choices, assembly variants (DNP options) and test notes written down.
