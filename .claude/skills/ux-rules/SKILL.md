---
name: ux-rules
description: Audit and improve a UI against a research-backed catalog of about 120 proven UX rules from industry and academic research (Nielsen heuristics, Fitts and Hick, WCAG 2.2, forms, feedback and latency, errors and undo, navigation and search, onboarding, AI and agent UX, deceptive patterns and the consumer-protection rules against them). Detects which rules a screen, flow, codebase, screenshot or live app applies or violates, with evidence; then decides whether each missing rule is worth applying here, how to build it in the actual stack, and how to measure the effect. Use whenever the user asks to review, critique, audit or improve the UX, UI, usability, accessibility, conversion, onboarding, forms or design of something they built or are building, including "is this good UX?", "why do users drop off here?", "check my sign-up flow", "make this page better", a design review before shipping, or choosing which UX practices a new feature should follow, even if they never say "UX".
argument-hint: "[path | URL | screenshot | flow] [focus]"
allowed-tools: Read, Grep, Glob, Bash(python .claude/skills/ux-rules/scripts/*), Bash(uv run python .claude/skills/ux-rules/scripts/*)
---

# UX rules: detect, judge, recommend

This skill turns a researched catalog of UX rules into an audit with evidence and a short list of changes worth
making. The catalog lives in `references/` next to this file: `checklists.md` for scanning, `README.md` for how
the research was done. Every rule has the same fields: what it is, why it works, evidence grade, limitations, how
to measure it, who implemented it, how to detect it, and how to implement it.

Two failure modes to avoid. A checklist dump: forty findings, no priorities, and advice that ignores who the product
is for. And taste dressed up as rules: "I'd make this bigger". Every finding names a rule ID, says what was seen and
where, and every recommendation says why it is worth doing here.

## 1. Pin down the context (cheap)

Rules depend on context: an expert tool used all day wants density and shortcuts; a first-time consumer flow wants
guidance and few choices. Before judging anything, settle:

- **Product and users**: who uses it, how often, novice or expert, on what devices; consumer or internal tool.
- **Primary tasks**: the two or three jobs the screen or flow exists for.
- **Goal and constraints**: what the owner wants to move (completion, errors, conversion, support load), plus
  platform, brand, legal (accessibility law, consumer protection) and deliberate trade-offs.
- **Artifact**: source code, a running app or URL, screenshots, a design file export, or a written flow.

Read the project's README or docs for this first. Ask the user only when the answer changes which rules apply
(for example, whether a tool is internal or public); otherwise state your assumption in the report and move on.

## 2. Pick the rules that apply

The catalog is large (about 800 KB), so never read whole category files. Scan with `references/checklists.md`,
using the sections the surface needs, then pull single entries for the rules that look violated or that you can't
judge: `Grep "^### FRM-04" -A 60` in `references/` returns one entry with its evidence, limitations, fix and
measure.

| What you are reviewing | Checklist sections | Category files for full entries |
|---|---|---|
| Any UI | Every screen, always | – |
| Form, sign-up, sign-in, settings | Forms and sign-in; Errors | `forms-and-data-entry.md`, `errors-and-user-control.md` |
| Checkout, pricing, subscriptions, consent, cookies | Checkout, pricing, subscriptions, consent | `choice-architecture-and-ethics.md`, `forms-and-data-entry.md` |
| Page layout, landing or marketing page, docs | Layout and copy | `visual-hierarchy-and-layout.md`, `content-and-microcopy.md` |
| Navigation, menus, search, lists, structure | Navigation, search, lists | `navigation-and-search.md`, `perception-and-cognition.md` |
| Dashboard, data-dense or expert tool | Layout and copy; Feedback | `interaction-and-controls.md`, `visual-hierarchy-and-layout.md` |
| Loading, slow operations, notifications | Feedback, loading, performance | `feedback-and-performance.md` |
| Mobile app or responsive web | Mobile and touch; Accessibility pass | `platform-mobile-and-touch.md`, `accessibility.md` |
| Desktop app (Tk, Qt, WPF, Electron, tray apps) | Desktop apps; Accessibility pass | `platform-mobile-and-touch.md`, `interaction-and-controls.md` |
| First run, empty states, activation, retention | First run and engagement | `onboarding-and-engagement.md` |
| AI features: chat, copilots, agents, recommendations | AI features | `ai-and-automation.md` |
| Accessibility review or a compliance question | Accessibility pass | `accessibility.md` (its intro states the legal baseline) |
| Planning how to measure impact or run research | – | `measurement-and-research.md` |
| A design rationale quotes a "rule" (3 clicks, 7±2, the fold) | Myths in design rationales | `contested-and-debunked.md` |

**Core set** (well supported and relevant to almost any UI; always check): FBK-01 immediate feedback, FBK-02
progress for waits, ERR-02 undo, ERR-03 confirm only irreversible actions, ERR-04 error messages, ERR-06 clear
exits, A11Y-01 contrast, A11Y-03 keyboard and focus, A11Y-04 names and semantics, A11Y-10 text alternatives,
PLT-03 target size, INT-01 signifiers, VIS-01 one clear primary action, CON-02 plain language, CON-03 specific
action labels, PER-04 recognition over recall, CHO-06 no deceptive patterns.

Say which categories you skipped and why, in one line. Skipping onboarding for a settings dialog is a decision,
not an oversight.

## 3. Collect evidence

Look at the real thing whenever you can. Code shows intent; the running UI shows what users get. Use what the
artifact allows, cheapest first. Scripts are in `scripts/` in this skill's folder; `<skill>` below means that
folder (the base directory shown when the skill loads). They are standard-library Python, except
`pixel_colors.py`, which needs Pillow.

**Source code**
- `python <skill>/scripts/ui_lint.py <paths>` lists pattern candidates (placeholder-only labels, removed focus
  outlines, click handlers on divs, pre-checked consent, fake countdowns, confirmshaming, paste blocking, missing
  `autocomplete`, small fonts and targets, low-contrast color pairs, theme or design-token pairs that fail
  contrast, stock Yes/No dialogs in Tk and Qt). Each candidate is a lead: open the code and confirm before you
  report it (for token pairs, check which colors are really used together). A clean run proves little.
- Then read the screens' components for what patterns can't see: the flow's steps, what happens on error, slow
  calls without loading states, destructive actions, empty states, copy.
- `python <skill>/scripts/contrast.py FG BG --fix` for any color pair you are unsure about.

**Running web UI** (dev server, staging, or the built-in browser)
- Run `scripts/measure_page.js` in the page (paste it into a page-evaluate tool, or serve the skill folder and
  `eval` the fetched text). It returns rendered target sizes against WCAG 2.5.8, real text contrast, controls
  without accessible names, placeholder-only fields, zoom blocking, open overlays on load, competing primary
  buttons, vague links, pre-checked consent, timing and layout shift. With `FOCUS_CHECK = true` it also finds
  controls with no visible focus. Give the tab a real viewport size first; a hidden tab reports zero.
- Quick tests that need no tools: tab through the page without a mouse; resize to 320 px wide; zoom to 200%;
  submit the main form empty and with one wrong field; throttle the network to slow 3G and click everything that
  loads; delete something and look for undo; try to leave every dialog with Esc.

**Screenshots or design exports**
- Judge hierarchy, grouping, labels, copy, states and conventions by eye.
- Measure instead of guessing: `pixel_colors.py shot.png --box x0,y0,x1,y1` gives text and background colors for
  `contrast.py`; estimate sizes from a known reference (a 16 px body line, a 44 pt iOS bar) and divide by the
  screenshot's scale factor.
- Ask for missing states (error, empty, loading, success) rather than assume them.

**Desktop apps** (Tk, Qt, WPF, Electron): read the UI code and, if you can launch it, screenshot it. Check
keyboard traversal and mnemonics, a visible focus highlight, Enter for the default button and Esc to close
dialogs, a UI thread that never blocks (work in threads; FBK-01), DPI scaling, high-contrast and dark themes,
tooltips on icon buttons, and the platform's tray or menu-bar conventions (PLT-01). Follow the failure paths
too: what the user sees when start-up fails (missing config, import error) or a background job fails, and
whether status and numbers shown are true (ERR-04, PER-11).

**Flows and specs**: walk the flow step by step as a first-time user and as a returning one. At each step ask
what the user is trying to do, whether they can see how, whether they will know it worked, and what happens if
they get it wrong (a cognitive walkthrough, MEA-02).

Record evidence as you go: `file:line`, URL plus selector, screenshot plus region, or the measured value. Never
paste personal data seen in a live app into the report.

## 4. Judge each rule

Give every rule you checked one status:

- **Applied**: evidence shows it is done well.
- **Partly applied**: done in places, or done but weakly (a progress bar without cancel).
- **Violated**: evidence shows the opposite.
- **Not applicable**: the rule's "applies to" doesn't fit this product or surface.
- **Can't tell**: the evidence isn't available (no running app, no error state). Say what would settle it.
  "Can't tell" is better than a guess.

For each Violated or Partly applied rule, rate severity on Nielsen's 0–4 scale from frequency (how many users,
how often), impact (inconvenience versus blocked or harmed) and persistence (once, or every time):
4 catastrophe (blocks the task, loses data or money, misleads about price, consent or cancellation, or locks
people out), 3 major, 2 minor, 1 cosmetic. Rate the problem, not the rule: the same rule can be a 1 on a
settings screen and a 4 in checkout. Your rating is one evaluator's judgment, and evaluators disagree a lot
(MEA-11); say so, and where a fix is expensive suggest that the owner or a second person re-rate the top items.

## 5. Decide whether to recommend

A violated rule is not automatically a recommendation. Ask, in order:

1. **Does it apply here?** Check the rule's "Applies to" and "Limitations" against step 1. Density beats
   whitespace in an expert dashboard; a platform convention can outrank an internal one.
2. **Is it required?** Accessibility law (the EU Accessibility Act through EN 301 549, the US ADA Title II rule
   and Section 508 reference WCAG 2.0 to 2.1 AA; WCAG 2.2 AA covers them all and is the UK public-sector minimum;
   dates and scope are in the intro of `accessibility.md`), consumer protection (dark-pattern, pricing and
   cancellation rules in `choice-architecture-and-ethics.md`) or platform review. Required means recommend, at
   least for the scope the law covers, whatever an A/B test might say. Say "check with counsel" rather than give
   legal advice.
3. **How strong is the evidence?** Strong or Moderate: recommend when the impact is worth it. Mixed: test first.
   Weak: mention only as an option. If the advice matches an entry in `contested-and-debunked.md`, don't give it.
4. **Is the impact worth the effort?** Severity and reach against effort (S: under a day, M: days, L: weeks) and
   risk (regressions, conflicts with other rules; the rule's Limitations name them).
5. **Is it in the user's interest?** Never recommend anything that works by misleading or pressuring people, even
   if it lifts a metric. Flag deceptive patterns you find as severity 4.

Verdicts: **Recommend**, **Test first** (name the test, the metric and the decision rule), **Not recommended**
(say why: not applicable, weak evidence, cost over benefit, conflicts with a deliberate choice, or manipulative).
Rules already applied need no verdict; mention the important ones so the owner knows what to keep.

## 6. Say how to implement it, and how to know it worked

For each recommendation, adapt the rule's "How to implement" to this codebase: the file and component, the change,
and a snippet when it helps. Then give a two-level check from the rule's "How to measure it works":

- **Right away**: what to re-run or try (the lint or probe, a keyboard pass, a screen reader, a 320 px resize).
- **Outcome**: the metric that should move (task success, errors per form, completion, support tickets, retention)
  and the method (five-user test, A/B test with guardrails, before/after analytics), from
  `measurement-and-research.md`. Say when traffic is too low for an A/B test and a usability test fits better.

## 7. Report

Keep it proportional: a single dialog doesn't need forty findings. Report every Violated and Can't-tell rule that
matters, and only the Applied rules worth keeping. Use this structure:

```markdown
# UX review: <product or screen>

**Scope:** what was reviewed (files, URL, screenshots), how (code read, lint, live probe, keyboard pass), date.
**Context:** users, platform, primary tasks, goal. Mark assumptions as assumptions.

## Summary
Three to five bullets: the biggest problems, what already works, the first fixes.

## Fix first
| # | Rule | Problem and evidence | Severity | Evidence grade | Verdict | Effort |
|---|---|---|---|---|---|---|

## Findings
### <Category>
- **<ID> <rule name>: Violated, severity 3.** What you saw and where (`file:line`, selector, screenshot region).
  Why it matters, in one line, with the rule's evidence. **Fix:** the change in this codebase. **Check:** right
  away / outcome metric and method.
- **<ID> <rule name>: Applied.** The evidence, in one line.

## Not recommended
- <ID>: why not here.

## Couldn't check
- What, why, and what would settle it.

## Measuring the impact
Baseline to capture now, method, and the result that would confirm the change.
```

## 8. Applying fixes (only when asked)

Fix the highest severity first, smallest change first. Keep one rule per commit so each can be measured or
reverted. Re-run the lint or probe and the quick tests after each fix, and show before and after (a screenshot or
the probe's numbers). Copy changes and anything that touches consent, pricing or cancellation go to the owner for
approval before they ship.

## Reference map

| File | Prefix | Rules | Use it for |
|---|---|---|---|
| `references/checklists.md` | – | – | Detection cues by surface and a code grep sheet; start here |
| `references/README.md` | – | – | Research method, evidence grades, category index |
| `references/frameworks.md` | – | – | Nielsen, Norman, Shneiderman, ISO 9241-110, WCAG, Laws of UX mapped to rule IDs |
| `references/perception-and-cognition.md` | PER | 11 | Fitts, Hick, memory, Gestalt, Jakob, peak-end, mental models |
| `references/interaction-and-controls.md` | INT | 7 | Signifiers, icons, consistency, mapping, accelerators, modes |
| `references/platform-mobile-and-touch.md` | PLT | 6 | Platform conventions, thumb reach, target size, responsive, gestures |
| `references/visual-hierarchy-and-layout.md` | VIS | 9 | Primary action, scanning, type, density, fold, carousels |
| `references/content-and-microcopy.md` | CON | 7 | Plain language, labels, link text, terminology, help |
| `references/forms-and-data-entry.md` | FRM | 13 | Fields, labels, validation, input types, sign-in |
| `references/feedback-and-performance.md` | FBK | 8 | Response times, progress, optimistic UI, Core Web Vitals |
| `references/errors-and-user-control.md` | ERR | 6 | Prevention, undo, confirmation, messages, exits |
| `references/navigation-and-search.md` | NAV | 8 | Scent, visible nav, wayfinding, search, filters, URLs |
| `references/onboarding-and-engagement.md` | ONB | 8 | Value first, activation, empty states, checklists, habits |
| `references/accessibility.md` | A11Y | 10 | WCAG 2.2 AA essentials, legal baseline, inclusive design, testing |
| `references/choice-architecture-and-ethics.md` | CHO | 8 | Defaults, social proof, pricing, cancellation, dark patterns |
| `references/ai-and-automation.md` | AI | 9 | Human-AI interaction guidelines, with the HAX mapping |
| `references/measurement-and-research.md` | MEA | 12 | Usability tests, questionnaires, HEART, A/B tests, severity |
| `references/contested-and-debunked.md` | MYTH | 15 | Popular rules the evidence doesn't support |
