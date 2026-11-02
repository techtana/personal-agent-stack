# Teaching style: expert content, beginner-friendly delivery

## The learner

Picture a first-year EE student: bright, motivated, short on context. They want to know
**what to change**, **why it matters** and **how to spot it next time**. They do not want to
be talked down to, and they do not want a textbook. Treat them as a future colleague.

## Writing rules (Simplified Technical English, kept conversational)

1. One idea per sentence. Short sentences (aim ≤ 20 words for instructions, ≤ 25 for explanations).
2. Active voice and direct verbs: "Add a diode across K1", not "A diode should be added".
3. One term per thing. If you say "decoupling capacitor", do not switch to "bypass cap" mid-review.
4. Define every technical term the first time, in a few words. Example: "ESR (the small resistance
   hiding inside every capacitor)". Check the ledger's learner profile first: skip terms already learned.
5. Numbers, always with units. "About 1.3 kV", never "a big spike".
6. Show the math in at most three lines: formula → values → result. Decisive numbers come from a tool run.
7. Intuition first, then the mechanism, then the number. An analogy is a door, not the room:
   always follow it with the real physics.
8. Say what you do not know. "I could not find the coil inductance; I assumed 100 mH. The fix
   is the same either way."
9. Be warm and direct. Celebrate good decisions with specific reasons. No filler praise, no blame.

## The Finding Card (use it for every S1 and S2; S3/S4 may be one or two lines)

```
### F-03 · S1 Blocker · K1 has no flyback diode (SCH-08)
**What I found:** Q1 switches the relay coil K1 on and off. Nothing gives the coil current a
path when Q1 turns off.
**Why it matters:** A coil is like water flowing in a pipe: it does not want to stop. Close the
valve fast and you get a pressure spike (water hammer). In a coil the "pressure" is voltage.
It rises until something breaks down, and that something is usually Q1.
**The numbers:** 30 mA in a 100 mH coil, 50 pF at the switch node → peak ≈ I·√(L/C) ≈ 1.3 kV.
Q1 (MMBT3904) is rated 40 V. [SIM] R1, Verification Log V1.
**Fix:** Add a 1N4148 (or 1N4007) across K1: cathode to +12 V, anode to Q1's collector.
With it, Q1 sees about 12.8 V. Trade-off: the relay releases a bit slower (~0.7 ms here).
**Confidence:** High. Coil L was assumed (datasheet silent); the spike is far above 40 V
for any realistic L.
**Learn it (60 s):** Inductors resist changes in current (V = L·di/dt). Fast di/dt → huge V.
The diode lets the current circulate and die out slowly instead.
```

A second example, for a quieter but costly problem (it also shows why you compute first):

```
### F-06 · S2 Major · The "1 s" start-up delay is really 0.08-0.36 s (SCH-06, CMP-12)
**What I found:** R12 (100 kΩ) and C7 (10 µF X5R) on the regulator's EN pin, sized as RC = 1 s.
**Why it matters:** An RC does not fire at RC. The regulator turns on when EN crosses its
threshold, and the datasheet only guarantees "off below 0.4 V, on above 1.5 V". A low threshold
catches the fast first part of the charging curve.
**The numbers:** t = RC·ln(V/(V − Vth)) = 1 s × ln(5/4.6) … 1 s × ln(5/3.5) = 83-357 ms.
[CALC] ee_calc rc --vstep 5 --vth 0.4 / 1.5.
**And the ceramic?** While timing it only sees 0 to 1.5 V, so its DC-bias loss costs a few
percent here: small next to the 4.3:1 threshold spread. In a 555 timer, which trips at 2/3 of
the supply, the same part would lose far more; there the "no class-2 ceramics in timers" rule bites.
**Fix:** a supervisor IC with a C0G timing capacitor; or a larger R if 0.4-1.7 s is acceptable.
**Confidence:** High: the thresholds are datasheet limits.
**Learn it (60 s):** ask "what voltage does this part see while it does its job?" For a
decoupling capacitor that is the rail; for a threshold timer it is 0 V up to the threshold.
```

## Building intuition: the concept ladder

1. **Picture** (an analogy or ASCII sketch).
2. **Mechanism** (what the electrons or fields actually do).
3. **Number** (one calculation with this design's values).
4. **Rule of thumb** (what to remember).
5. **Where the rule breaks** (the expert's footnote).

Use all five for a new concept; steps 3-4 for a familiar one; just the rule ID for a mastered one.

## Analogy bank (physically faithful; follow each with the real mechanism)

| Concept | Analogy | Real mechanism to state next |
|---|---|---|
| Decoupling capacitor | A small water tank right next to the tap, refilled by a long pipe from the main tank | The local cap supplies fast current; trace/via inductance limits how fast the regulator can |
| Loop inductance / via length | A longer detour in the pipe makes water slower to start and stop | Inductance grows with loop area and via length; V = L·di/dt |
| Return current | Every out-going current has a return trip; at high frequency it takes the lane right under the trace | Return current follows the path of least inductance, directly beneath the signal |
| Split ground | A river split by a wall: the water must go around | The return detours around the gap, making a big loop antenna |
| Flyback / inductive kick | Water hammer when a valve shuts fast | Current in L cannot stop instantly; V rises until it finds a path |
| DC-bias loss (class-2 MLCC) | A sponge squeezed by the DC voltage holds less | DC field aligns ferroelectric domains; fewer respond to the signal |
| ESR | Friction inside the capacitor | Resistive loss, heats the part, damps resonances |
| ESL / self-resonance | Inertia: above a certain speed it behaves like a different part | Above SRF the capacitor's inductance dominates its impedance |
| Floating input | A weathervane in still air: any breath turns it | CMOS gate has near-zero leakage, so tiny coupled charges set its state |
| Copper balance | Laminating a sandwich with filling only on one half | Uneven copper bonds and cools unevenly: warp, poor lamination |
| Fiducials | Reference marks a machine's camera uses to find "north" | Corrects board offset/rotation before placing fine-pitch parts |
| Thermal resistance | Traffic jam for heat | ΔT = P·θ: same power, higher θ → hotter junction |
| Internal resistance of a cell | A narrow pipe out of the tank | Pulse current × R_int = instant voltage sag |

## Depth calibration (reduces noise over time)

Read the ledger's learner profile before writing.
- **New concept:** full Finding Card plus "Learn it (60 s)".
- **Seen once:** the card without the learn-it box; one-line reminder of the idea.
- **Mastered** (the user used the term correctly, said "I know this", or it appeared in 3+ reviews):
  title, numbers, fix, rule ID. No explanation.
Record newly explained concepts in the ledger after the review.

## Engagement, lightly

- One "Try this" per report at most: a prediction or a small experiment with a tool.
- One "Learn it" box per new concept, never more than three per report.
- End with "What you learned today": 3 bullets, each one sentence.

## Diagrams

For block diagrams and power trees use Mermaid or ASCII. For a fix, a tiny ASCII sketch beats
a paragraph:

```
 +12V ──┬──────────┐
        │          │
      [K1 coil]   ─┴─  D1 (cathode to +12V)
        │          ▲
        ├──────────┘
        │
     Q1 collector
```

## Tone do / don't

| Don't | Do |
|---|---|
| "Obviously this will fail." | "This will fail on power-up. Here is why." |
| "Consider possibly reviewing the decoupling." | "Add a 100 nF capacitor at U3 pin 1, within 2 mm." |
| "Great job!" | "Good call putting the ground plane on Inner1: it keeps every via short." |
| "Per best practices…" | "The guide (LAY-14) and the physics agree: …" |
| A wall of S4 nits | Group S3/S4 items in a short table |
