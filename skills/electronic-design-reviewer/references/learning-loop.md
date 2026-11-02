# Learning loop: get better from feedback while asking for almost none

The aim is a reviewer that rarely needs correcting, and never needs the same correction twice.
It works like a run-to-run controller: every review is a run, every user correction is a
measurement, and an update is a small, deliberate adjustment with a deadband so one noisy
data point does not swing the system.

## 1. Feedback budget

- **Zero requests by default.** Never ask "was this helpful?" or for ratings.
- **At most one question** per correction, and only to settle its scope
  ("Is this a rule for all your boards, or just this one?"). If the user is away, take the
  narrower scope (this project) and say so.
- **Prevent the feedback in the first place:** load the ledger and learned rules before
  reviewing; respect waivers; verify before asserting; label confidence; run the quality gate.

## 2. Feedback events (detect them passively in the conversation)

| Event | What it sounds like | What to do |
|---|---|---|
| **Dispute** | "That's wrong, the ULN2003 has internal diodes" | Re-verify with evidence. If the user is right: retract plainly, thank them, record a false-positive lesson. If the evidence says otherwise: explain once, respectfully, and offer the test that settles it. |
| **Waiver** | "Hand-assembled prototype, skip fiducials" | Record a project waiver (scope, reason, expiry such as "until production"). Stop raising it for this project. |
| **Escape** | "The board resets when the relay switches off" (a problem the review missed) | Run escape analysis (section 3). Highest-value feedback. |
| **Preference** | "Shorter please", "skip the capacitor lessons" | Update the learner profile / report preferences. |
| **Confirmation** | "Fixed F-03, you were right" | Mark the finding fixed after you verify it in the new revision; optional note in the review log. |

## 3. Escape analysis (when a defect got past the review)

1. **Symptom and conditions:** what happened, when, how often.
2. **Mechanism:** the physics that produced it (show the numbers if you can; simulate if it helps).
3. **Rule mapping:** which guide rule or expert check should have caught it?
4. **Gap class** — exactly one:
   - `rule-missing` → write a new learned rule.
   - `rule-not-applied` → the rule existed, the review skipped it → change the procedure
     (e.g. "always run recipe R9 when a coin cell powers a radio").
   - `check-too-weak` → the check ran but could not see it → strengthen the check (new
     netlist_lint/pcb_check heuristic, new sim recipe, lower threshold). When you can edit the
     toolkit, add a fixture and a test to `tests/test_toolkit.py` and run it, so the fix cannot regress.
   - `input-missing` → the needed fact was not available → add it to the intake questions.
5. **Fix for the design** (what the user does now) and **fix for the reviewer** (what changes).
6. **Regression check:** the concrete test that would have caught it, run on every future review.
7. Record in the ledger's Escapes table; promote immediately (section 4).

## 4. Promotion rules (the deadband)

Lessons start narrow and widen only with evidence:

- **Project scope (default):** waivers, project facts, one-off disputes.
- **Promote to a global learned rule when ANY is true:**
  1. the user says it applies generally;
  2. the same pattern appears in two different projects;
  3. it is an escape with a clear mechanism (misses are expensive; promote at once).
- **Never promote** anything that weakens a hard limit (abs max, safety, physics). A user can
  waive such an item for one project as `accepted-risk`, explicitly, never globally.
- **Keep the list short:** at most 25 learned rules. Merge similar ones; delete rules a later
  guide version covers. Each rule must be general, testable, and carry its regression check.

## 5. Formats

**Learned rule** (lives in SKILL.md §11 so every future review loads it):
```
- LR-007 (2026-11-14, escape) — When a coin cell powers a radio, run R9 at end-of-life
  R_int (≥100 Ω) and cold; fail if V(min) < brown-out + 0.1 V. Why: TX bursts browned out
  the MCU in the field. Check: pulse-sag result in the Verification Log.
```

**Project ledger** (`design-review-ledger.md` next to the design; template in
`assets/ledger-template.md`): project facts and operating envelope, rule packs and precedence,
waivers and accepted risks, finding history, escapes, learner profile, review log with a
"corrections this review" count.

The corrections count per review is the loop's own control chart. It should trend to zero.
If it rises, look for a pattern (a new domain, a missing input, a weak check) before patching
individual rules.

## 6. Where to store lessons (adapt to the host)

Pick the first option that works; tell the user in one line what you stored and where.

1. **Project ledger:** write/update `design-review-ledger.md` beside the design when you can
   write there (local project, linked folder, repository). Otherwise attach the updated ledger
   to your reply and ask the user to keep it with the project files; read it back next time.
2. **Global learned rules (SKILL.md §11):**
   - Skill folder writable (e.g. `~/.claude/skills/…` in Claude Code): edit §11 directly and
     bump the version in the SKILL.md title (patch for wording, minor for a new rule).
   - Host offers a skill-update proposal tool: propose the complete updated SKILL.md
     (whole file, every section kept) for the user to approve.
   - Neither: output a short "Lesson card" in the exact learned-rule format and ask the user to
     add it to the skill when convenient.
3. **The host's own memory** may only be used as the host's rules allow (often: only when the
   user explicitly asks you to remember something).

## 7. Anti-patterns

- Asking for feedback after every review.
- Storing anecdotes ("John's board had a bad cap") instead of rules.
- Over-fitting: one complaint disables a whole class of checks.
- Silently dropping a finding the user disliked without recording why.
- Letting a learned rule override a hard limit.
- Re-raising a waived item (unless the waiver expired or the risk changed; then say why).
