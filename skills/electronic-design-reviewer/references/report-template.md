# Review report template

Use this structure every time. Order matters: the user should know what to do within
30 seconds, and find the proof when they want it.

Deliver it in the host's document format when one exists (a document artifact or a shared
doc); otherwise as a Markdown file next to the design. Chat replies get the 30-second part
plus a link or the file.

```markdown
# Design review: <project> <rev> — <stage>
<date> · Reviewer: Claude (electronic-design-reviewer v<x.y.z>) · Rule pack: <name(s), precedence>
Inputs reviewed: <files> · Tools: <SpiceBridge ✓/✗ · KiCad ✓/✗ · parts ✓/✗>

## 1. Verdict
**<NOT READY | READY AFTER FIXES | INCOMPLETE | READY>** — <one sentence why>.
Guide compliance <score>% · coverage <coverage>% of applicable rules · open: S1 <n> · S2 <n> · S3 <n> · S4 <n>

### Fix these first
1. <ref des + concrete action + why in ≤ 12 words> (F-xx)
2. …
3. …

## 2. What I think this design does
<3-5 sentences: function, power tree, key interfaces.> <Block diagram, Mermaid or ASCII.>
Assumptions: <ambient, supply range, assembly method, quantity>. Tell me if any is wrong.

## 3. Findings
### S1 — Blockers (will damage, endanger, or stop the board)
<Finding Cards>
### S2 — Major (likely respin, missed spec or intermittent failure)
<Finding Cards>
### S3 — Minor (manufacturing, test, cost) and S4 — Advisory
| ID | Sev | Rule | Finding | Fix |
|---|---|---|---|---|

## 4. What you did well
- <specific good decision + why it is right + rule ID it satisfies>

## 5. Where sources disagree
| Topic | Guide says | Other source says | What I applied and why |
|---|---|---|---|

## 6. Guide compliance matrix
<output of scripts/compliance_score.py: phase table + rule table>

## 7. Expert findings outside the guide
<EXP-* items, same card/table format, tier-4 weighting noted>

## 8. Verification log
<table from verification-playbook §8; every [SIM]/[CALC]/[EDA] claim appears here>

## 9. What you learned today
- <concept 1, one sentence>
- <concept 2>
- <concept 3>
Try this: <one prediction or small experiment>

## 10. Open questions (max 3, only ones that change the verdict)
1. …

## Sources
- [Title](URL)
```

## Finding IDs and statuses

- IDs `F-01`, `F-02`, … are stable across re-reviews of the same project (keep them in the ledger).
- Expert findings use the same sequence; their rule column shows `EXP-…`.
- Status: `open` · `fixed` (verified in a later revision) · `waived` (user decision, ledger) ·
  `accepted-risk` (S1 the user explicitly accepts; never silently).

## Assessment JSON for scripts/compliance_score.py

Build it while you review (start from `--template`), then score:

```json
{
  "project": "sensor-node", "rev": "A", "stage": "schematic",
  "rules": [
    {"id": "SCH-03", "status": "fail", "evidence": "[EDA] netlist_lint polarized_cap_reversed: C4", "findings": ["F-01"]},
    {"id": "SCH-05", "status": "pass", "evidence": "[EDA] single GND net"},
    {"id": "SCH-14", "status": "na", "evidence": "no transformers or CMCs"},
    {"id": "LIB-01", "status": "unverified", "evidence": "needs a 1:1 print by the user"}
  ],
  "findings": [
    {"id": "F-01", "severity": "S1", "status": "open", "rule": "SCH-03", "title": "C4 reversed"}
  ]
}
```

Rule status: `pass`, `partial`, `fail`, `na` (with the reason in evidence), `unverified`
(name the missing input), `waived`. A rule failed by any open finding is `fail` or `partial`.

## Re-reviews

When a new revision arrives: load the ledger, re-check every open finding first (mark
`fixed` only with evidence), then review changed areas fully and unchanged areas with the
automated sweeps. Lead the report with "Since last review: fixed <n>, still open <n>, new <n>."
