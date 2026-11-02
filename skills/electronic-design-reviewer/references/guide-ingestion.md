# Ingesting a user-supplied guide into a rule pack

Use when the user gives a design guide, company standard, checklist or customer
requirement (PDF, doc, wiki page) that is not already a rule pack. The bundled default is
`guide-rosenberg-v5.md`.

## Steps

1. **Read all of it** (every page; figures too: numbers often live in figures).
2. **Extract atomic, checkable rules.** One rule = one thing that can pass or fail.
   Split compound sentences; merge duplicates; keep the guide's own numbers.
3. **Paraphrase.** Do not copy long passages. Keep a page reference for each rule.
4. **Give stable IDs** with a short prefix per guide (e.g. `ACME-SCH-01`). Never renumber
   later; retire IDs instead, so ledger history stays valid.
5. **Set severity** from the consequence the guide describes and its wording:
   "must / never / critical / damage / safety" → S1 or S2; "should" → S2 or S3;
   "consider / tip / nice" → S3 or S4. Physics decides when the wording is vague.
6. **Set weight** = severity base (S1 10, S2 5, S3 2, S4 1) × 1.5 where the guide stresses the point.
7. **Set phase** (framework, schematic, components, mechanics, placement, library, layout,
   release) and an **applies** condition.
8. **Choose a verify method:** a bundled script check, `ee_calc.py`, a sim recipe, datasheet,
   ERC/DRC, visual, or "ask the user".
9. **Add a one-line "Teach"** where the reason is not obvious.
10. **Validate** with `compliance_score.py --rules <new pack> --stage release --template`:
    every rule must parse (it prints the rule list). Fix headers that do not parse.

## Header format (exact)

```
#### ACME-LAY-04 — Ground plane under every RF trace
`sev: S2 · w: 5 · phase: layout · applies: RF boards · verify: visual; pcb_check gnd_zone_coverage · page: 12`
- **Check:** …
- **Teach:** …
```

## Precedence and storage

- Ask the user once for the order when several guides apply (e.g. customer spec > company
  standard > Rosenberg checklist). Record it in the ledger. Pass rule packs to the scorer in
  that order: the first pack wins on duplicate IDs.
- Save the new pack next to the design (`design-review-rules-<guide>.md`) or attach it to
  the reply. The skill's own folder may be read-only.
- Show the user a short summary: rule count by phase and severity, plus at most three
  severity calls you were unsure about. One round of confirmation, then proceed.

## Example conversions

| Guide sentence | Rule |
|---|---|
| "All connectors that leave the enclosure must have ESD protection rated to IEC 61000-4-2 level 4." | `ACME-SCH-07 — ESD protection on external connectors` · S2 · schematic · verify: schematic + TVS datasheet |
| "Keep switching regulators at least 20 mm from the antenna." | `ACME-PLC-03 — Switcher ≥ 20 mm from antenna` · S2 · placement · verify: pcb_check positions / measure |
| "Prefer 0603 or larger for hand-assembled prototypes." | `ACME-CMP-11 — 0603+ passives for hand assembly` · S4 · components · applies: hand assembly |
