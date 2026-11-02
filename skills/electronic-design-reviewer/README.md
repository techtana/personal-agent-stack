# electronic-design-reviewer toolkit

Optional companion files for the **electronic-design-reviewer** skill. The skill works without
them (its SKILL.md is self-contained); with them, reviews are faster and the numbers are
computed by tested code instead of ad-hoc arithmetic.

## Where to put it

The skill looks for this folder (named `electronic-design-reviewer-toolkit` or containing
`scripts/netlist_lint.py`) in this order:
1. next to SKILL.md (a local skill folder, e.g. `~/.claude/skills/electronic-design-reviewer/`);
2. among the conversation's files: attached, Project files, a linked folder on your computer,
   or a repository;
3. not found → the skill uses its inline procedures.

## Contents

| Path | What it is |
|---|---|
| `scripts/netlist_lint.py` | Schematic checks on a KiCad netlist (.net/.xml), a .kicad_pcb, or a CSV pin list. Each hit maps to a guide rule ID. |
| `scripts/pcb_check.py` | Layout checks on a .kicad_pcb: plane assignment, Inner1 traces, one via per ground pad, decap distance, fiducials, markers, vias, paste, copper balance, IR drop. |
| `scripts/ee_calc.py` | 19 calculators (RC, MLCC DC bias, SRF, PDN impedance, divider, resistor power, Tj, LDO, trace R/width, via, annular ring, microstrip, I2C pull-up, crystal caps, battery life, flyback, hot-plug, pulse sag). |
| `scripts/compliance_score.py` | Assessment template, weighted guide compliance, coverage and verdict gate. |
| `references/guide-rosenberg-v5.md` | Full rule pack (95 rules) with why/teach notes and page references. |
| `references/expert-checks.md` | ~60 senior-engineer checks beyond the guide (power, battery, MCU, analog, RF, drivers, safety/EMC, DFM, test, supply chain). |
| `references/verification-playbook.md` | Connector discovery, SpiceBridge recipes R1-R10, KiCad commands, fallbacks, verification log. |
| `references/evidence-and-research.md` | Evidence tags, source tiers, conflict resolution, datasheet checklist. |
| `references/teaching-style.md` | The mentor voice: Finding Card examples, analogy bank, depth calibration. |
| `references/report-template.md` | Report structure and the assessment JSON format. |
| `references/learning-loop.md` | Feedback events, escape analysis, promotion rules, storage. |
| `references/guide-ingestion.md` | Turning any new guide or company standard into a rule pack. |
| `assets/sim/*.cir` | ngspice netlists for the SpiceBridge recipes (flyback, MLCC timing, PDN, LC filter, part stress, tolerance, hot-plug, coin-cell sag, op-amp stability). |
| `assets/ledger-template.md` | Per-project review ledger (facts, waivers, findings, escapes, learner profile). |
| `evals/` | Three test cases with graders (seeded-fault netlist, MLCC timing decision, relay escape). |
| `tests/test_toolkit.py` | 19 regression tests for the scripts (run `python3 tests/test_toolkit.py`). |

All scripts are Python 3.8+ standard library only. Every script prints `-h` help.

## Quick start

```
python3 scripts/netlist_lint.py my_board.net --sch my_board.kicad_sch
python3 scripts/pcb_check.py my_board.kicad_pcb
python3 scripts/ee_calc.py mlcc --c 10u --vrated 6.3 --vbias 5 --dielectric X5R --size 0603
python3 scripts/compliance_score.py --rules references/guide-rosenberg-v5.md --stage schematic --template > assessment.json
```

Script output is a list of **leads**, not verdicts: the reviewer confirms each one before
reporting it. `pcb_check.py` geometry is approximate (beta).

The rule pack paraphrases *The Electronic Product Development Checklist* v5 by Hans Rosenberg
(hans-rosenberg.com), supplied by the user. Refer to the original for exact wording.
