---
name: create-documentation
description: Create or refresh a project's documentation — the README (for product owners and developers), the manuals (for installers and users), the design record (every past plan and decision, gathered into docs/design/) and the knowledge base (the research done and the domain knowledge the project depends on, explained in depth for newcomers, in docs/knowledge/) — after a major change such as a new component, device, deploy step, interface, a merged feature PR, or a round of research. Use when asked to create, update, refresh or write the README, manuals, user guide, install guide, troubleshooting guide, design history, research notes or domain background, or when finishing work that changed how the project is set up, used or understood. Keeps docs in plain language and keeps AI cost low by sending the repo survey to cheaper models.
---

# Create documentation

Four kinds of document, each for its own reader. Keep them apart.

| Document | Reader | Answers |
|---|---|---|
| `README.md` | Product owner, developer | What is this, should I use it, how is it built, what's decided, what's next |
| `docs/manuals/` | Installer, everyday user, whoever fixes it at 2 a.m. | How do I set it up, use it, and fix it |
| `docs/design/` | Developer, future maintainer, the next AI session | What was planned, what was decided, when and why |
| `docs/knowledge/` | Anyone new to the project's domain: a new developer, a tester, a reviewer, the owner's future self | What do I need to understand about the subject itself, what did we research and learn, and where does it come from |

Run this after a **major change**: a new component, device or service; a changed install, deploy or sign-in step; a changed interface; a merged feature PR; a closed batch of issues; a round of research. A typo fix or a refactor that users can't see doesn't need it.

## 1. Find what changed (cheap)

Before reading code, find the delta:

- `git log --oneline <last-docs-commit>..HEAD` and `git diff --stat` on the same range. The last docs commit is `git log -1 --format=%h -- README.md docs/manuals`.
- Open and recently closed issues and PRs (`gh issue list --state all --limit 30`, `gh pr list --state all --limit 15`). Issues feed the README's issues and path-forward lists.
- Existing docs: the README, `docs/`, per-component READMEs, `CLAUDE.md` files.

If nothing user-visible changed since the last docs commit, step 1b finds no plan or decision missing from `docs/design/`, and step 1c finds no research or domain topic missing from `docs/knowledge/`, say so and stop.

## 1b. Gather every design plan and decision (cheap)

Plans and decisions made with the owner often live outside the repo and get lost. Bring all of them into `docs/design/` — every time, not only the ones since the last docs commit. Check `docs/design/` first and add only what isn't there yet.

Sources, in order:

- **Plan files**: `~/.claude/plans/*.md`. The folder is shared by every project, so keep only plans that name this project's files, modules or features. Read the first lines to decide; skip the rest.
- **Memory**: the project's memory folder (`~/.claude/projects/<project-slug>*/memory/`). `project` and `feedback` memories often hold the owner's decisions and the reasons.
- **PR and issue descriptions**: `gh pr list --state all --json number,title,body,mergedAt` and design issues. A PR body usually states what was decided and what was left out.
- **Commit messages** with decisions in the body (`git log --format='%h %ad %s%n%b' --date=short`).
- **Existing docs** that already record decisions (architecture, UX, data docs, ADRs, `CLAUDE.md`). Link these; don't copy them.
- **Past session transcripts** (`~/.claude/projects/<project-slug>*/*.jsonl`), only when the sources above leave a gap. They are large: send them to a `haiku` subagent and ask only for the owner's decisions (what was chosen, what was rejected, the reason, the date), with quotes kept under 15 words.

Write three kinds of file:

- **`docs/design/plans/<YYYY-MM-DD>-<slug>.md`**, one per plan: the goal, the approach, the phases, and a **Status** line at the top (proposed / approved / in progress / done / dropped, with the date and the PR that delivered it). Keep the plan's substance; trim session chatter, tool notes and absolute paths to the user's machine. Plans are history: don't rewrite an old plan to match today's code — add a dated "Outcome" note at the end instead.
- **`docs/design/DECISIONS.md`**, a running log, newest first: date, decision, why, rejected alternatives, and a link to the plan, PR or doc it came from. Never delete an entry; mark a reversed one "Superseded by <date>". Include decisions already recorded in other docs as one line with a link.
- **`docs/design/README.md`**, an index of the plans with their status.

The README's design-decisions section (step 3) summarises `DECISIONS.md` and links it instead of repeating it.

No secrets, personal data or e-mail addresses in these files. Write "the owner" rather than the person's name unless the project already names them.

## 1c. Gather research and domain knowledge

Every project rests on knowledge the code doesn't explain: the physics behind a model, the rules of a sport, a protocol, a regulation, how a market or a trade works, the quirks of a dataset, the result of a comparison. That knowledge is usually studied once — in a research session, a design-plan appendix, a vendor PDF, a long PR thread — and then lives only in someone's head or in a transcript nobody will reopen. Bring it into `docs/knowledge/` so a person who has never met the domain can learn it from the repo. Like step 1b, do this every time, and add only what isn't there yet.

What belongs here:

- **Research done for the project**: web or deep research, papers, standards and books read, products or datasets compared, experiments and validation runs, and what each showed.
- **Domain knowledge the project depends on**: the theory, the vocabulary, the rules, the rules of thumb, and the reference numbers with where they come from.

What doesn't: setup and usage steps (manuals), choices and their reasons (`DECISIONS.md`), code structure (the architecture doc). Link to those instead.

Sources, in order:

- **Research and reference notes already in the repo**: folders such as `docs/reference/`, `docs/research/`, `notes/`; background or appendix sections of design docs; validation reports and data; code comments that cite a paper, standard or dataset. Grep for `source`, `reference`, `paper`, `standard`, `according to`, `doi`, `http`.
- **Plan files and memory** (as in step 1b): their background, research and "what we learned" parts.
- **PR, issue and commit bodies** that explain why a formula, number or rule is what it is.
- **Past session transcripts**, only for gaps: a `haiku` subagent lists the topics researched, the sources consulted (title, author, URL) and the conclusions reached — not the text of the pages.

**Group by topic, not by source.** One file per body of knowledge a newcomer would study together: `docs/knowledge/<topic-slug>.md`. Three notes from three sessions about one subject make one file; one long note covering three subjects makes three files. Keep raw research notes where they are and link them as sources.

Also write **`docs/knowledge/README.md`**: a reading order (start here → foundations → specialised topics), one line per file saying what it teaches and who needs it, and a glossary of the domain's terms in plain words. Move the glossary to `GLOSSARY.md` when it passes about 30 terms.

Each topic file, in this order:

1. **What this is and why the project needs it** — one paragraph, no jargon.
2. **The ideas, built up from zero** — the core of the file, in natural-language prose, not bullet fragments. Start from everyday experience the reader already has, then go one step at a time. Define each term the first time it appears. Explain an idea in words before any equation; after the equation, name each symbol with its unit and work one example with real numbers. Use an analogy where it helps, and say where the analogy stops working. A simple diagram is welcome.
3. **Rules of thumb and typical numbers** — with the usual range and where each number comes from.
4. **Common misconceptions and edge cases** — what newcomers usually get wrong, and where the simple picture breaks down.
5. **How the project uses it** — which component, file or setting depends on this knowledge, and what the project simplified or left out and why (link `DECISIONS.md`).
6. **What we found** — results of research or experiments done for this project, with dates and links to the data.
7. **Open questions** — what isn't known or settled yet.
8. **Sources and further reading** — title, author or organisation, year, link, and what each source is good for.

**Depth test**: a smart reader who has never met the domain reads the file once and can then follow the project's design docs, code comments and test names on this topic without searching elsewhere. If a paragraph only makes sense to an expert, expand it. If a section could be cut without the reader losing anything, cut it.

Rules for knowledge files:

- Write in your own words. Summarise and cite; don't paste source text. Keep any quote under 15 words.
- Never invent a source, number or result. If a fact's source isn't recorded, write "source not recorded". Mark disputed or uncertain claims as such.
- Knowledge files are kept current, not kept as history: when understanding improves, rewrite the explanation, and add a dated line under a **Changes** heading at the bottom ("2026-10-31: replaced the drag estimate with the measured value"). The history of choices stays in `DECISIONS.md`.

## 2. Survey with cheaper models

Reading the repo is most of the token cost. Don't do it yourself on the most expensive model.

- Send the survey to subagents on the **cheapest model that can read accurately** (`model: "haiku"` for extracting facts from docs and config; `"sonnet"` only when it must read and interpret code). Use the read-only Explore agent type.
- Split by area (for example firmware/devices, cloud/backend, frontend/app), one agent each, launched together so they run in parallel. Two to four agents is plenty.
- Give each agent a narrow list of files and ask for a **fact sheet, not prose**: hardware and prerequisites, install steps with exact commands, configuration keys (names, never secret values), everyday tasks, every symptom→fix, limits. Ask for `file:line` citations and "not stated" instead of guesses. Cap the length (~150 lines).
- For step 1c, one agent lists the research and domain topics it finds: for each, the topic, the source files with line ranges, the claims and numbers with their sources, and what the project uses them for.
- Read only the files the fact sheets can't answer, and only the part you need.
- Write the README, manuals and design record yourself, from the fact sheets. Writing them is short; reading is where the tokens go.
- Knowledge files are long and are mostly explanation, so they may be drafted in parallel by `sonnet` subagents, one per topic. Give each the topic's source files, the section order and depth test from step 1c, and the plain-language rules from step 5. Then read every draft yourself: check each number and claim against its source, cut what an expert-only reader would need, and fix the links between files.

## 3. Write the README

For the product owner and developer. Sections, in this order, skipping any that don't apply:

1. **Summary**: two or three sentences. What it is and what it does for the reader.
2. **When to use it** (and who it's for).
3. **How it works**: one diagram at most, and a pointer to the architecture doc if there is one.
4. **Setup across devices**: which device does what, in which order to set them up. Link the installation manual for the steps; don't repeat them.
5. **Quick start**: the shortest path to seeing it work, five to ten steps.
6. **Repository layout**: a table, one line per folder.
7. **Assumptions and where it applies**.
8. **Limitations and where it doesn't apply**.
9. **Known issues**: link the tracker; list the important open ones.
10. **Path forward**: a running list of planned work, newest decisions kept.
11. **Design decisions**: the most important ones, one line each — the decision, the date, and why — then a link to `docs/design/DECISIONS.md` for the full log. Never delete an entry; mark a reversed one as superseded.
12. **Background knowledge**: one sentence on what a newcomer needs to understand about the domain, and a link to `docs/knowledge/README.md`.
13. Conventions, tests, contributing: short.

The path-forward and design-decision lists are **running**: add to them, don't rewrite them. Dates are absolute (`2026-10-25`), never "last week".

## 4. Write the manuals

In `docs/manuals/` (or wherever the project keeps them). Usually:

- **Installation manual** — for whoever deploys it. Shopping list, prerequisites, then numbered steps in the order they must happen, each with the exact command, what you should see, and what to do if you don't. Adding, replacing and removing devices. Updating.
- **User manual** — for whoever uses it day to day. What each screen shows, everyday tasks, what "normal" looks like.
- **Troubleshooting** — symptom first (what the person sees), then likely cause, then the fix. A table works well. Include health checks.

Write for someone who has never seen the project and isn't a developer. Name buttons, screens and log lines exactly as they appear.

## 5. Plain language

- Short sentences. One idea each. Active voice: "Run the script", not "The script should be run".
- Say what something is for before how it works.
- Use the project's own words for things, consistently. Define a term the first time, or link a glossary.
- Exact commands in code blocks; one command per block where the reader will copy it.
- No marketing words (seamless, robust, powerful), no filler ("it's worth noting that").
- State the current state as fact, with the date when it may change: "Since 2026-10-25 each gateway has its own token."

## 6. Check before you finish

- Every command, path, file name, setting and screen name you wrote exists. Check with `ls`/`grep`, not memory.
- Every link resolves to a file in the repo.
- No secrets, tokens, passwords or personal data copied into docs. Placeholders only (`<project-id>`, `<token>`).
- Every plan from step 1b has a file in `docs/design/plans/` and a row in the index, and every decision has a line in `DECISIONS.md`.
- Every research topic from step 1c has a file in `docs/knowledge/` and a line in its README. Each file passes the depth test, each number has a source or says "source not recorded", and no source text is pasted.
- README and manuals don't contradict each other or the component READMEs. Where they overlap, the manual links to the component README instead of copying it.
- Tell the user what changed in the docs, what you couldn't verify, and which issues the change addresses.
