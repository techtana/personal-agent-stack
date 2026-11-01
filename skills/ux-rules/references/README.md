# UX rules catalog: research notes

A catalog of UX design rules and techniques that industry and big-tech teams use, each checked against its
evidence. It serves two readers: a person who wants to know what a rule is, why it works, where it fails, how to
measure it and who has used it; and the `ux-rules` skill (`../SKILL.md`), which uses the same entries to detect
whether a UI applies a rule and to decide whether recommending it is worth it.

Compiled 2026-10-31: 122 rules in 14 categories plus 15 contested or debunked claims. Laws, standards and platform
guidelines change, so check the year next to each claim before quoting it, and re-verify anything legal before
relying on it. "We" in an entry means the researchers who compiled it; notes such as "(snippet)" or "not checked
against the source" mark claims that could not be confirmed from a primary source during the research.

## How the research was done

- **Scope**: rules with evidence behind them, from peer-reviewed HCI and psychology research; standards (WCAG 2.2,
  ISO 9241, NIST SP 800-63B); platform guidelines (Apple Human Interface Guidelines, Material Design, Microsoft
  Fluent and Windows guidance); practitioner research that publishes its method (Nielsen Norman Group, Baymard
  Institute); companies' own papers, engineering blogs and talks; and regulators (FTC, European Commission, CNIL,
  CMA).
- **Verification**: every number, date, study result and company outcome was looked up, with primary sources
  preferred over articles that repeat them. Claims that could not be traced to a primary source are kept and
  marked as such, because knowing that a famous statistic is folklore is useful in a design review.
- **One category per file**, written to one template, with stable rule IDs (for example `FRM-04`).
- `contested-and-debunked.md` collects popular rules the evidence does not support, so the skill can decline to
  recommend them.

## Evidence grades

| Grade | Means |
|---|---|
| **Strong** | Replicated peer-reviewed research, large published controlled experiments, or a formal standard or regulation |
| **Moderate** | Consistent practitioner research with a stated method, one published controlled experiment, or consensus across the major platform guidelines |
| **Mixed** | Studies disagree, the effect depends heavily on context, or replications failed in some conditions |
| **Weak** | Anecdote, case study without a method, or unsourced statistics |

A **Required** note on the evidence line means a standard or law demands the rule in some context (for example
WCAG 2.2 AA under the EU Accessibility Act). A grade describes the evidence for the rule in general; a single
company example inside an entry can be weaker than the rule's grade, and the entry says so.

## What each rule entry contains

| Field | Answers |
|---|---|
| What it is | The rule in one to three sentences |
| Why it works | The mechanism (perception, memory, motor control, motivation, economics) and the key evidence |
| Evidence | Grade, kind and age of the evidence; Required note if any |
| Limitations | Where it does not hold, when it backfires, common misreadings, conflicts with other rules |
| How to measure it works | Metric, method and expected direction |
| Implemented by | Companies and products that applied it, with published outcomes where they exist |
| How to detect it | Applied and violated signals in the UI, grep-able code patterns, a five-minute test |
| How to implement | Concrete steps, web first, with notes for native and desktop |
| Sources | Numbered references with URLs |

## Categories

| Prefix | File | Covers |
|---|---|---|
| PER | `perception-and-cognition.md` | Fitts, Hick, memory and cognitive load, recognition, Gestalt, Jakob's law, aesthetic-usability, serial position, peak-end, goal-gradient, mental models |
| INT | `interaction-and-controls.md` | Signifiers, icon labels, consistency and design systems, mapping and direct manipulation, accelerators, Tesler's law, modes and modals |
| PLT | `platform-mobile-and-touch.md` | Platform conventions (mobile and desktop), thumb reach, target size, responsive layout, gestures, poor networks |
| VIS | `visual-hierarchy-and-layout.md` | Primary action, scanning, readable type, density, banner blindness, the fold, carousels, spacing and color systems |
| CON | `content-and-microcopy.md` | Concise text, plain language, action labels, front-loading, link text, terminology and voice, contextual help |
| FRM | `forms-and-data-entry.md` | Fewer fields, labels, layout, inline validation, input types and autocomplete, forgiving formats, guest checkout, required fields, field errors, sign-in, defaults, multi-step forms |
| FBK | `feedback-and-performance.md` | Response-time limits, progress, skeleton screens, optimistic UI, Core Web Vitals, layout stability, success feedback, notifications |
| ERR | `errors-and-user-control.md` | Constraints, undo, confirming irreversible actions, error messages, never losing work, clear exits |
| NAV | `navigation-and-search.md` | Information scent, visible navigation, wayfinding, consistency, search, filters, URLs and Back, organizing by user tasks |
| ONB | `onboarding-and-engagement.md` | Value before sign-up, activation, contextual teaching, empty states, checklists, templates, habit features, permission requests |
| A11Y | `accessibility.md` | Contrast, color alone, keyboard and focus, semantics and names, user settings and motion, media, cognitive accessibility, inclusive design, testing |
| CHO | `choice-architecture-and-ethics.md` | Defaults, social proof, urgency, pricing, cancellation, deceptive patterns, privacy notices, framing |
| AI | `ai-and-automation.md` | Expectations, accept/edit/dismiss, sources, human control, streaming, feedback, global controls, disclosure, graceful failure |
| MEA | `measurement-and-research.md` | Usability tests, heuristic review, task metrics, questionnaires, HEART, A/B tests, analytics, field performance, CSAT/CES/NPS, IA testing, severity |
| MYTH | `contested-and-debunked.md` | Popular rules the evidence does not support |

Supporting files: `frameworks.md` maps Nielsen, Norman, Shneiderman, ISO 9241-110, WCAG and "Laws of UX" to rule
IDs; `checklists.md` condenses every rule's detection cues by surface for fast scanning.

## Keeping it current

- Add a rule with the same template and the next free number in its category. Never renumber: reports and code
  comments cite IDs. Retire a rule by marking it "Retired (date): reason" instead of deleting it.
- When a source is updated (a new WebAIM Million, a new Baymard benchmark, a court ruling on a consumer rule),
  update the figure, its year and the source, and note the date at the top of this file.
- Add new detection cues to `checklists.md` and, if a cue is a reliable code pattern, to `../scripts/ui_lint.py`.
