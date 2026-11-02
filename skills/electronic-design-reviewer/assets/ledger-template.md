# Design review ledger: <project name>

Keep this file next to the design files. The electronic-design-reviewer skill reads it at
the start of every review and updates it at the end. Edit it freely.

## Project facts (operating envelope)
| Item | Value | Source |
|---|---|---|
| Function | | user |
| Supply / battery | e.g. CR2032, 2.0-3.0 V | user |
| Max load current | | |
| Ambient range | e.g. 0-40 °C indoor | user |
| Lifetime / battery-life target | e.g. ≥ 1 year | user |
| Assembly | hand / PCBA service (which) | user |
| Quantity | | user |
| Fab and its rules | e.g. JLCPCB 2-layer standard | user |
| Stack-up | | fab |
| Safety-relevant voltages | none / describe | user |

## Rule packs and precedence
1. <user/company guide, file> (highest)
2. guide-rosenberg-v5 (bundled default)
3. expert-checks (tier 4, unscored)

## Waivers and accepted risks
| ID | Rule / finding | Scope | Reason | Expires | Date |
|---|---|---|---|---|---|
| W-01 | LAY-17 fiducials | this project | hand assembly | before PCBA order | |

## Findings history
| ID | Sev | Rule | Title | Status | Opened (rev) | Closed (rev) | Evidence of fix |
|---|---|---|---|---|---|---|---|

## Escapes (problems found after a review)
| ID | Symptom | Mechanism | Rule that should catch it | Gap class | Reviewer fix | Promoted to |
|---|---|---|---|---|---|---|

## Learner profile
- Concepts explained: <concept (date)>, …
- Concepts mastered (no explanation needed): …
- Report preferences: e.g. "short S3/S4 tables", "Mermaid diagrams"

## Review log
| Date | Rev | Stage | Verdict | Score | Coverage | Corrections from user |
|---|---|---|---|---|---|---|
