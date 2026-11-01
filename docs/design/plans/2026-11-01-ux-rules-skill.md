**Status:** done 2026-11-01 ([PR #13](https://github.com/techtana/personal-agent-stack/pull/13)); the move into
`skills/` and the second eval round are still open.

# `/ux-rules`: a researched UX rule catalog as a skill

Reconstructed from the PR #13 description; no separate plan file was written.

## Goal

Research proven UX rules from industry and academic sources, organise them by category, and package them as a skill
that checks a UI (source code, a running page, screenshots or a desktop app) against them. For each missing rule the
skill decides whether it is worth applying here, how to build it in the actual stack, and how to check that it worked.

## Approach

- **Catalog** (`references/`): 122 rules in 14 categories (perception, interaction, platform and touch, layout,
  content, forms, feedback and performance, errors, navigation, onboarding, accessibility, choice architecture and
  ethics, AI features, measurement), plus 15 contested or debunked "rules". Each entry: what it is, why it works,
  evidence grade, limits, how to measure it, who implemented it, how to detect it, how to implement it, sources.
  `checklists.md` is the quick-scan entry point; `frameworks.md` maps Nielsen, Norman, Shneiderman, ISO 9241-110,
  WCAG and Laws of UX to rule IDs.
- **Scripts**: `ui_lint.py` (static scan of web and Tk/Qt code, including theme-token contrast), `contrast.py` (WCAG
  ratio and the nearest passing colour), `measure_page.js` (live-page probe), `pixel_colors.py` (colours from
  screenshots).
- **Evals**: two cases in the `claude plugin eval` layout: a checkout page with planted deceptive patterns, and a
  review of `scripts/tray.py`.
- Research agents checked figures against primary sources where they could; untraced claims are marked. Legal notes
  are dated 2026-10-31 and are not legal advice.

## Outcome

- 2026-11-01: one eval run each with Sonnet subagents: 19/19 assertions with the skill, 18/19 without, at about 1.5x
  the tokens. Most assertions did not discriminate; the skill's gains were per-fix verification, evidence grades and
  refusing to A/B-test deceptive patterns. Sharper assertions were added for a second round, which has not run.
- 2026-11-01: the commit that moves the skill into `skills/` (`a8400c9`) is on the PR branch only; on `main` the skill
  lives in `.claude/skills/ux-rules/`.
- 2026-11-01: the research fan-out (ten parallel agents) ran out of WebSearch budget and hit the session limit; see
  `memory/lessons.md`.
