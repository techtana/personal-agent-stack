# Design review ledger: relay-board (pump controller)

## Project facts (operating envelope)
| Item | Value | Source |
|---|---|---|
| Function | ATtiny1616 switches a 12 V diaphragm pump through relay K1 | user |
| Supply / battery | USB 5 V (logic + relay coil); separate 12 V adapter for the pump via J2 | user |
| Max load current | pump ~0.4 A running | user |
| Ambient range | indoor 15-30 °C | user |
| Assembly | hand assembly | user |
| Quantity | 2 | user |
| Fab and its rules | JLCPCB 2-layer standard | user |

## Rule packs and precedence
1. guide-rosenberg-v5 (bundled default)
2. expert-checks (tier 4)

## Waivers and accepted risks
| ID | Rule / finding | Scope | Reason | Expires | Date |
|---|---|---|---|---|---|
| W-01 | LAY-17 fiducials | this project | hand assembly | before any PCBA order | 2026-10-25 |

## Findings history
| ID | Sev | Rule | Title | Status | Opened (rev) | Closed (rev) | Evidence of fix |
|---|---|---|---|---|---|---|---|
| F-01 | S1 | SCH-08 | K1 coil had no flyback diode | fixed | A | B | D1 1N4148W across coil, cathode to VBUS (netlist rev B) |
| F-02 | S3 | SCH-11 | No test point on VBUS | open | A | | |

## Escapes (problems found after a review)
| ID | Symptom | Mechanism | Rule that should catch it | Gap class | Reviewer fix | Promoted to |
|---|---|---|---|---|---|---|

## Learner profile
- Concepts explained: flyback diode (2026-10-24), decoupling capacitor (2026-10-24), DC-bias derating (2026-10-25)
- Concepts mastered: -
- Report preferences: short tables for minor items

## Review log
| Date | Rev | Stage | Verdict | Score | Coverage | Corrections from user |
|---|---|---|---|---|---|---|
| 2026-10-24 | A | schematic | NOT READY | 78% | 81% | 0 |
| 2026-10-25 | B | schematic | READY | 93% | 84% | 0 |
