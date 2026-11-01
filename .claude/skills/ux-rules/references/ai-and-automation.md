# AI and automation UX (AI)

This category covers interfaces where a model suggests, generates, decides or acts for the user: assistants, autocomplete, recommenders, agents and generated media. Load it when you audit any feature whose output the user did not write, that learns from behavior, or that acts on the user's behalf. The rules follow four design frameworks and one law (summarized below). The frameworks agree on direction; controlled evidence that following them improves outcomes is thinner, and the grades say so.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| AI-01 | Say what the AI can do and how well it does it | Moderate | Any AI feature at first use: assistants, recommenders, generators |
| AI-02 | Make AI output easy to accept, edit, dismiss, stop and undo | Moderate | Suggestions, autocomplete, generation, agent edits |
| AI-03 | Show sources and explain why | Mixed | Answers from retrieved content, recommendations, decision support |
| AI-04 | Keep people in control of consequential actions; scope down when unsure | Strong | Agents and any AI that sends, spends, deletes or changes things |
| AI-05 | Stream output and show progress for slow AI | Weak | Chat, generation and agent UIs where output takes over about 1 s |
| AI-06 | Collect granular feedback, show its effect, adapt cautiously | Moderate | Recommenders, assistants, personalized feeds, anything that learns |
| AI-07 | Give users global control over personalization, memory and data | Moderate | AI with memory, history, personalization or training use |
| AI-08 | Disclose AI, label synthetic content, avoid passing as human | Strong | Chatbots, voice agents, generated media, published AI text |
| AI-09 | Fail gracefully with a path forward | Moderate | Every AI feature: refusals, tool failures, timeouts, low confidence |

**Frameworks behind the rules (facts checked 2026-10-31).**
- **HAX, Microsoft (CHI 2019).** 18 guidelines in four groups: initially (G1-G2), during interaction (G3-G6), when wrong (G7-G11), over time (G12-G18). Built from 168 candidate guidelines, cut to 35 concepts, then 20, then 18. Validated in four phases: an internal heuristic evaluation (11 team members, 13 products); a study with 49 HCI practitioners on 20 products in 10 categories (785 examples: 313 applications, 277 violations, 89 neutral, 106 not applicable); a rewrite for clarity; a review of the rewrites by 11 experts. This tested relevance and clarity, not whether following the guidelines improves outcomes. Source: Amershi et al. 2019 (see AI-01 [2]).
- **PAIR People + AI Guidebook, Google.** Published 2019-05-08; second edition updated 2021-05-18 with design patterns, case studies and a workshop kit; six chapters follow the product flow. A November 2023 PAIR post describes an update for generative AI (snippet; page blocked). Chapters used here: Mental Models, Explainability + Trust, Feedback + Control, Errors + Graceful Failure.
- **Apple Human Interface Guidelines.** "Machine learning" (merged into one page 2023-05-02; last updated 2026-06-08) and "Generative AI" (new 2025-06-09; updated 2026-06-08).
- **Shneiderman, human-centered AI.** Paper on arXiv in February 2020 (published in the International Journal of Human-Computer Interaction in 2020; volume and pages not checked); book from Oxford University Press in 2022 (snippet). Claim: design for high human control and high automation together; they are separate axes, not a trade-off. Basis of AI-04. arXiv: https://arxiv.org/abs/2002.04087
- **EU AI Act Article 50 (Regulation (EU) 2024/1689).** Applies from 2026-08-02. 50(1): providers must make AI interaction known unless it is obvious to a reasonably observant person. 50(2): providers must mark synthetic audio, image, video and text in machine-readable form. 50(3): deployers inform people exposed to emotion recognition or biometric categorisation. 50(4): deployers disclose deepfakes and AI-written text on matters of public interest, unless a person with editorial responsibility reviewed the text. 50(5): the notice must be clear, given no later than first interaction or exposure, and accessible. Reported grace period: generative systems already on the market before 2026-08-02 have until 2026-12-02 for the 50(2) marking duty (listed on the AI Act timeline page; a June 2026 law-firm alert called it awaiting formal adoption; confirm in the Official Journal). Fines up to EUR 15 million or 3% of worldwide turnover (law-firm alert). The Commission published draft Article 50 guidelines on 2026-05-08. Detail and sources under AI-08.

| Rule | HAX 2019 | PAIR chapter | Apple HIG | Other |
|---|---|---|---|---|
| AI-01 | G1, G2 | Mental Models | Generative AI: Transparency | Kocielnik 2019 |
| AI-02 | G7, G8, G9 | Feedback + Control | ML: Corrections, Multiple options; GenAI: controls | Horvitz 1999 |
| AI-03 | G11 | Explainability + Trust | ML: Attribution, Confidence | Bansal 2021, Buçinca 2021 |
| AI-04 | G10 (G9 for recovery). HAX has no guideline on approving consequential actions; G15 is feedback, see AI-06 | Explainability + Trust, Errors | GenAI: confirm before irreversible actions | Shneiderman 2020, Parasuraman and Riley 1997, EU AI Act Art. 14 |
| AI-05 | None (HAX does not cover latency) | None | GenAI: latency and status text | FBK-01, FBK-02 |
| AI-06 | G13, G14, G15, G16, G18 | Feedback + Control | ML: Explicit and implicit feedback, Limitations | Netflix 2017, Mozilla 2022 |
| AI-07 | G17 (G12 in part) | Feedback + Control | ML: Implicit feedback; GenAI: Privacy | GDPR Art. 7(3) |
| AI-08 | None (HAX dropped "establish that the bot is not human" as too specific) | Mental Models | GenAI: Transparency | EU AI Act Art. 50, C2PA |
| AI-09 | G10 (G9) | Errors + Graceful Failure | GenAI: Errors; ML: Mistakes, Limitations | XSTest 2023 |

HAX G3-G6 (timing, relevance, social norms, bias) are not rules in this file; see FBK (interruptions and notifications), NAV, CHO and A11Y (inclusive design).

---

### AI-01 Say what the AI can do and how well it does it

**What it is.** Before first use and next to risky output, state what the feature handles, what it does not, and how often it errs. Covers HAX G1 (what it can do) and G2 (how well). Put it in the interface, in words tied to the task, not only in marketing or terms of service.

**Why it works.** Satisfaction tracks the gap between expected and actual performance, so inflated expectations turn a decent system into a disappointing one [1]. In two online experiments (150 and 400 participants; 325 analyzed in the second) with a simulated email scheduling assistant fixed at 50% accuracy, three light interventions (an accuracy statement, an example-based explanation, a threshold slider) shifted the beliefs they targeted, and people looked at them for about 15 seconds [1]. They raised acceptance only for the variant people judged worse (7-point acceptance 5.23 vs 4.56 baseline, p < 0.05) [1]. Apple and PAIR give the same advice: state limits before use, show how to get better results, say what the product cannot yet do [3][4]. In the HAX study G2 was relevant but violated more often than applied [2].

**Evidence: Moderate.** One published experiment series (CHI 2019, crowd participants, one task) with a conditional effect, plus agreement across HAX, PAIR and Apple HIG.

**Limitations.**
- The gain appeared only when the system fell short of expectations. Task accuracy and completion time did not change, only perception [1].
- The accuracy statement slightly lowered felt control (p = 0.048) [1].
- At equal 50% accuracy, the variant with more false alarms (high recall) was rated more accurate (7.09 vs 5.75 out of 10) and more acceptable (5.65 vs 5.12 out of 7) than the one that avoided them, against the practitioner habit of avoiding false positives. The authors attribute this to false alarms being cheap to ignore [1]. It conflicts with AI-04 when a wrong action is costly.
- A generic "can make mistakes" footer is common, but no study of its effect was found, and it does not say where the system is weak (inference; Apple asks for specific limits [3]).
- The often-repeated claim that about half of adults cannot write good prompts comes from a 2023 column that names no study [6]. Treat it as opinion (Weak).

**How to measure it works.**
- Expectation gap: ask "how accurate do you expect it to be?" before use and rate quality after; expect the gap to narrow.
- Acceptance and satisfaction items after the first task; drop-off after the first wrong result; lagging: 30-day retention.
- Share of requests that are out of scope (log classifier); expect it to fall.

**Implemented by.**
- Apple HIG (2025): a short tutorial or curated starter suggestions; known limits stated up front; explain why results are weaker [3].
- Google PAIR (2019, 2021): onboard in stages; say what the product can't do yet; avoid implying near-perfect performance [4].
- HAX study examples rated clearly applied: an activity tracker listing exactly which metrics it tracks (G1); a music recommender using hedged wording (G2) [2].
- NN/g (2024): prompt libraries, conversation starters and suggested follow-ups help users learn what a chatbot can do [5].
- Anecdote: major assistants show a short notice under the input box that answers can contain mistakes.

**How to detect it.**
- *Applied:* first-run or empty state names what the feature does and does not do; example prompts or starter chips; limits shown beside the output they affect; hedged wording on uncertain output.
- *Violated:* blank input with no hint; "ask me anything" claims; limits revealed only by failure; one generic disclaimer on every screen; a persona that implies human abilities.
- *In code:* `placeholder=` text with examples; `starterPrompts`, `suggestions`, `examplePrompts`; copy keys `limitations`, `disclaimer`, `beta`; `aria-describedby` hint text.
- *Quick test:* open as a new user. In 30 seconds, can you name one thing it can do, one it cannot, and how reliable it is? Ask for something out of scope: does the reply say so?

**How to implement.**
1. Write a three-line capability note: what it does, what it does not, how reliable by task type. Show it at first run and in an info popover beside the input.
2. Add 3 to 6 example prompts that show the range, including one that shows a boundary.
3. State reliability in task terms ("may miss details in tables"). Use numbers only if measured and stable (see AI-03 on confidence displays).
4. Put the limit beside the risky output (figures, dates, names), where it changes behavior.
5. Choose the error type by recovery cost: if a false hint is cheap to ignore and a miss is costly to find, favor recall [1].
6. Re-announce limits when they change (AI-06) and offer a non-AI path (AI-09).

**Sources.**
[1] Kocielnik, Amershi, Bennett (2019). Will You Accept an Imperfect AI? Exploring Designs for Adjusting End-user Expectations of AI Systems. CHI 2019. https://doi.org/10.1145/3290605.3300641 (PDF: https://www.microsoft.com/en-us/research/uploads/prod/2019/01/chi19_kocielnik_et_al.pdf)
[2] Amershi et al. (2019). Guidelines for Human-AI Interaction. CHI 2019. https://doi.org/10.1145/3290605.3300233 (PDF: https://www.microsoft.com/en-us/research/uploads/prod/2019/01/Guidelines-for-Human-AI-Interaction-camera-ready.pdf)
[3] Apple (2025, updated 2026-06-08). Human Interface Guidelines: Generative AI. https://developer.apple.com/design/human-interface-guidelines/generative-ai
[4] Google PAIR (2019, 2021). People + AI Guidebook, chapter Mental Models. https://pair.withgoogle.com/chapter/mental-models/
[5] Liu, F. (2024-08-02). Prompt Controls in GenAI Chatbots: 4 Main Uses and Best Practices. Nielsen Norman Group. https://www.nngroup.com/articles/prompt-controls-genai/
[6] Nielsen, J. (2023-06-18). AI Is First New UI Paradigm in 60 Years. Nielsen Norman Group. https://www.nngroup.com/articles/ai-paradigm/

---

### AI-02 Make AI output easy to accept, edit, dismiss, stop and undo

**What it is.** Treat AI output as a proposal. Give the user a cheap way to take it, change it, ignore it, stop it while it is being made, and take it back after it is applied. Covers HAX G7 (invoke), G8 (dismiss) and G9 (correct or recover).

**Why it works.** People tolerate imperfect AI when recovery is cheap. Horvitz's 1999 mixed-initiative principles call for efficient invocation and termination and for keeping the cost of poor guesses low [1]. Apple's HIG says people may not mind an automation's mistakes but stop using it if doing the task themselves looks easier [7]. Large products follow this. Gmail Smart Compose shows one inline suggestion only when model confidence passes a threshold, targets 90th-percentile latency under 60 ms, and saved over one billion characters of typing a week in 2019 [2]; Tab accepts it [3]. Smart Reply assisted 10% of mobile replies in Inbox in 2016 with one-tap suggestions [4]. In GitHub Copilot telemetry the acceptance rate averaged 27% and was the best single predictor of perceived productivity (r = 0.24) [5].

**Evidence: Moderate.** Agreement across HAX (G7-G9), Apple HIG and Horvitz, plus large-product telemetry. Controlled evidence on AI assistance itself conflicts (see Limitations). No study of stop or regenerate controls was found.

**Limitations.**
- Easy acceptance also eases rubber-stamping (AI-03, AI-04). Acceptance rate is a weak proxy: r = 0.24 leaves most variance unexplained, and rates vary by language and time of day [5].
- Productivity results conflict. A 2022 trial of 95 recruited programmers (35 finished) found 55.8% faster completion of one task (95% CI 21% to 89%) [6]. A 2025 trial of 16 experienced developers on 246 of their own tasks found 19% slower with AI, while they believed they were 20% faster [8]. Measure locally.
- Undo has gaps: Claude Code rewind does not track files changed only by shell commands or by subagents [9]; sent email and payments cannot be recalled (AI-04).
- Inline suggestions interrupt; cheap dismissal (keep typing, Esc) is part of the rule. Keyboard and screen-reader paths are needed (A11Y).

**How to measure it works.**
- Acceptance rate (accepted / shown), edit-after-accept, dismiss, undo, regenerate and stop rates. Use acceptance as a diagnostic, not a goal.
- Time on task and error rate in a holdout or A/B test. Self-reports mislead: developers guessed 35% against 55.8% measured [6], and guessed the wrong direction in [8].
- Lagging: reverts or defects traced to accepted AI output.

**Implemented by.**
- Google Gmail Smart Compose (2018): inline suggestion, Tab to accept, on by default and can be turned off in settings [2][3].
- Google Smart Reply (2016): one-tap replies the user sends or ignores [4].
- GitHub Copilot (2022): inline completions with accept telemetry [5].
- Apple HIG (2025): put Edit, Undo, Retry or Adjust next to generated content [7].
- Anthropic Claude Code: `/rewind` (or Esc twice) restores code and conversation to a checkpoint taken before each prompt; the 100 most recent are kept [9].

**How to detect it.**
- *Applied:* output appears as a pending proposal; Accept / Edit / Dismiss / Retry sit beside it; keyboard accept and Esc work; Stop while generating; undo after applying.
- *Violated:* output written straight into the document or file; Regenerate but no edit; no Stop on a long run; a blocking modal; accept overwrites the user's text.
- *In code:* `AbortController` / `.abort()` wired to a Stop button; `onAccept`, `onDismiss`, `onRetry`; pending state kept apart from committed state; an undo or history stack; `keydown` handlers for `Tab` and `Escape`.
- *Quick test:* trigger a suggestion. Accept one with the keyboard, ignore another by typing on, edit an accepted one, press Undo. During a long generation press Stop: does it halt within about a second and keep the partial text?

**How to implement.**
1. Render output as a proposal in a pending state; commit only on an explicit act.
2. Provide accept (one key or tap), edit in place, dismiss by continuing or Esc, Retry with a variation, Stop while streaming, and Undo after commit.
3. Keep partial output when the user stops (AI-05); never discard the user's input.
4. Undo at the unit the user thinks in (one suggestion, one agent step); snapshot before multi-file or multi-step changes.
5. Show a suggestion only above a confidence threshold, as Smart Compose does [2]; offer 2 or 3 meaningfully different options when intent is unclear [7].
6. Treat edits and dismissals as feedback signals (AI-06) without extra prompts.

**Sources.**
[1] Horvitz, E. (1999). Principles of Mixed-Initiative User Interfaces. CHI '99. https://erichorvitz.com/chi99horvitz.pdf
[2] Chen et al. (2019). Gmail Smart Compose: Real-Time Assisted Writing. KDD 2019. https://doi.org/10.1145/3292500.3330723 (arXiv: https://arxiv.org/abs/1906.00080)
[3] Google (n.d.). Gmail Help: Smart Compose. https://support.google.com/mail/answer/9116836
[4] Kannan et al. (2016). Smart Reply: Automated Response Suggestion for Email. KDD 2016. https://arxiv.org/abs/1606.04870
[5] Ziegler et al. (2022). Productivity Assessment of Neural Code Completion. MAPS 2022. https://arxiv.org/abs/2205.06537
[6] Peng, Kalliamvakou, Cihon, Demirer (2023). The Impact of AI on Developer Productivity: Evidence from GitHub Copilot. arXiv. https://arxiv.org/abs/2302.06590
[7] Apple (2023-05-02, updated 2026-06-08; 2025-06-09). HIG: Machine learning (Corrections); HIG: Generative AI. https://developer.apple.com/design/human-interface-guidelines/machine-learning ; https://developer.apple.com/design/human-interface-guidelines/generative-ai
[8] Becker, Rush, Barnes, Rein (METR, 2025). Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity. arXiv. https://arxiv.org/abs/2507.09089
[9] Anthropic (n.d.). Claude Code docs: Checkpointing. https://code.claude.com/docs/en/checkpointing

---

### AI-03 Show sources and explain why

**What it is.** Let people see where an answer came from (linked sources, quoted passages, the data used) and why the system chose this result (a short reason, the key inputs). Match depth to the stakes. Covers HAX G11.

**Why it works.** People can check claims and decide when to rely on the system. In the HAX study G11 had one of the highest violation counts, yet participants could imagine explanations helping in most products [1]. PAIR: explanations help users decide when to trust and when to use their own judgment, and a partial explanation is often best [9]. Apple: attribute a result to a plain fact about the user ("Because you've read nonfiction"), not to model internals [10]. Citation UIs have been common since 2023: Bing's launch (2023-02-07) cited sources with links [7]; Google's AI Overviews (2024-05-14) link to sources [8].

**Evidence: Mixed.** Explanations and citations help verification, but they can raise trust without raising accuracy, and citation quality is often poor.

**Limitations.**
- Across three tasks, explanations raised acceptance of AI advice whether or not it was right and did not improve team accuracy (CHI 2021) [2].
- Three "cognitive forcing" designs that make people engage before accepting AI advice reduced overreliance more than simple explanations did (199 participants), but people rated the most effective designs lowest [3].
- Trust in citations is cheap: trust rose with citations even when they were random, and fell when people checked them (AAAI 2025) [5]. People rarely check: in March 2025 browsing data from 900 US adults, 1% of visits to pages with an AI summary clicked a link inside it [6].
- Citations are often wrong: across four 2023 engines, 51.5% of sentences were fully supported by their citations and 74.5% of citations supported their sentence [4].
- Explaining routine low-stakes behavior distracts, and confidence numbers that change no decision add noise [9]. Explaining a ranking can help people game it [1].

**How to measure it works.**
- Citation audit on a sample of answers (method of [4]): share of sentences fully supported; share of citations that support their sentence. Expect both to rise with grounding checks.
- Reliance test with seeded wrong answers: acceptance of wrong versus right answers; expect fewer wrong answers accepted without fewer right ones accepted.
- Source-open rate (baseline in [6]: 1%); time to verify one claim; trust-calibration survey.

**Implemented by.**
- Microsoft Bing (2023-02-07): answers cite sources and link to them [7].
- Google AI Overviews (2024-05-14): links in the overview; Google reports they get more clicks than a plain listing for the same query (self-reported) [8]. Compare [6].
- Perplexity, Bing Chat, NeevaAI and YouChat were the engines audited in [4].
- HAX study example rated clearly applied: a navigation app showing the reason for its route (fastest route) under the route [1].
- PAIR and Apple HIG: partial, data-source and example-based explanations; attribution wording [9][10].

**How to detect it.**
- *Applied:* per-claim citations that open the passage; quote or snippet preview; "because you..." reasons; a scope line ("based on 3 files"); stated uncertainty where it is validated.
- *Violated:* factual claims with no source; a link list at the bottom not tied to claims; citations that do not contain the claim; precise-looking percentages with no meaning; reasons that restate the output.
- *In code:* fields or components named `citations`, `sources`, `annotations`, `footnotes`, `references`, `grounding`; `<cite>`; "Why this?" menu items.
- *Quick test:* ask a question whose answer you know. Open three citations: does each page contain the sentence it supports? Is the source one click away?

**How to implement.**
1. Ground answers in retrieved text; give each passage an ID; require the output to cite IDs per claim.
2. Check support before display: the quoted span exists in the source, or an entailment check passes. Remove or flag unsupported sentences.
3. Show reasons in three tiers: a one-line reason inline, inputs on expand, full detail for high-stakes cases.
4. For decisions with real cost, add a forcing step (the user states a provisional answer first, or confirms after viewing evidence) and test it; users dislike it [3].
5. Show confidence only after verifying that it tracks result quality, and in categories tied to actions [9][10].
6. Say when sources are missing or weak.

**Sources.**
[1] Amershi et al. (2019). Guidelines for Human-AI Interaction. CHI 2019. https://doi.org/10.1145/3290605.3300233
[2] Bansal et al. (2021). Does the Whole Exceed its Parts? The Effect of AI Explanations on Complementary Team Performance. CHI 2021. https://arxiv.org/abs/2006.14779
[3] Buçinca, Malaya, Gajos (2021). To Trust or to Think: Cognitive Forcing Functions Can Reduce Overreliance on AI in AI-assisted Decision-making. Proc. ACM HCI 5 (CSCW1). https://arxiv.org/abs/2102.09692 (DOI 10.1145/3449287)
[4] Liu, Zhang, Liang (2023). Evaluating Verifiability in Generative Search Engines. Findings of EMNLP 2023. https://arxiv.org/abs/2304.09848
[5] Ding et al. (2025). Citations and Trust in LLM Generated Responses. AAAI 2025. https://arxiv.org/abs/2501.01303
[6] Pew Research Center (2025-07-22). Google users are less likely to click on links when an AI summary appears in the results. https://www.pewresearch.org/short-reads/2025/07/22/google-users-are-less-likely-to-click-on-links-when-an-ai-summary-appears-in-the-results/
[7] Mehdi, Y. (2023-02-07). Reinventing search with a new AI-powered Microsoft Bing and Edge. Microsoft. https://blogs.microsoft.com/blog/2023/02/07/reinventing-search-with-a-new-ai-powered-microsoft-bing-and-edge-your-copilot-for-the-web/
[8] Google (2024-05-14). Generative AI in Search. https://blog.google/products/search/generative-ai-google-search-may-2024/
[9] Google PAIR (2019, 2021). People + AI Guidebook, chapter Explainability + Trust. https://pair.withgoogle.com/chapter/explainability-trust/
[10] Apple (2023-05-02, updated 2026-06-08). HIG: Machine learning (Attribution, Confidence). https://developer.apple.com/design/human-interface-guidelines/machine-learning

---

### AI-04 Keep people in control of consequential actions; scope down when unsure

**What it is.** The AI proposes; a person approves anything costly, external or hard to undo. When the AI is unsure what the user wants, it narrows what it does: asks one question, offers a few options, or does less. Covers HAX G10, with G9 for recovery. HAX has no guideline on approving consequential actions; the sources below fill the gap.

**Why it works.** People over-rely on automation. Parasuraman and Riley (1997) named misuse (over-reliance) and disuse [1]. In a 1999 flight-simulator experiment (80 students) people with a reliable but imperfect aid made omission and commission errors and did worse on a monitoring task than people with no aid [2]. A systematic review of 74 studies called automation bias a fairly consistent effect across fields; in four pooled clinical studies wrong advice was followed 26% more often with decision support than without it (risk ratio 1.26, 95% CI 1.11 to 1.44) [3]. Mitigators: accountability, less prominent advice, information instead of commands, updated confidence [3]. Horvitz (1999) gives the scoping rule: act alone only when the probability of the user's goal passes a threshold set by costs and benefits; otherwise ask, offer options or do less [4]. Apple: ask before significant or hard-to-undo actions such as purchases and deletions [8].

**Evidence: Strong.** Replicated research (a 74-study review) and regulation. Required: EU AI Act Art. 14 for high-risk systems (overseers must be able to stay aware of automation bias, override, and stop the system) [5]. Which prompt design works best is less settled.

**Limitations.**
- Prompts wear out. Anthropic calls this approval fatigue and reported an 84% cut in permission prompts from sandboxing in its internal use (2025-10-20) [6]. Ask only when risk is real.
- A confirm button is not oversight if the person cannot judge the action. Forcing designs help but are unpopular (AI-03 [3]).
- Scoping down costs usefulness and the threshold needs tuning. HAX participants found G10 hard to judge in one session [9].
- Training and accountability evidence is mixed [3]; accountable pilots cross-checked more [2].
- Conflicts with AI-02: keep accepting cheap for reversible output, add friction only for consequential actions. See ERR rules on confirming irreversible actions.

**How to measure it works.**
- Seeded-error test: share of wrong AI actions or answers a person accepts (omission and commission).
- Approval rate and dwell time on confirmations (near 100% and near zero seconds signal fatigue); prompts per session.
- Consequential actions executed with no review step; reversal rate; incidents traced to AI actions.
- Audit completeness: can you reconstruct who approved what, and when?

**Implemented by.**
- Anthropic Claude Code: reads without asking; asks before file edits and most shell commands, showing the exact command with Yes / don't ask again / No; modes include `acceptEdits`, `plan`, `dontAsk` and `bypassPermissions`; an auto mode where a classifier reviews actions [7].
- Google Smart Reply (2016): suggests replies; the user sends [10].
- Microsoft Research LookOut (1999): shows its guess of a meeting from an email, lets the user edit and save, and asks a short question when unsure [4].
- Apple HIG (2025): confirmation before purchases and deletions [8].
- Audit trail: Claude Code checkpoints and rewind [7]; EU AI Act Art. 12 requires automatic event logs for high-risk systems (Annex III from 2027-12-02, Annex I from 2028-08-02) [5].

**How to detect it.**
- *Applied:* preview or diff before an action; an explicit approve step for send, pay, delete; a plan shown before running; ambiguity met with a question or 2 to 4 options; an activity log with time, action and approver; scoped permissions; a stop control.
- *Violated:* the agent sends or deletes with no preview; "Allow all" as default; a silent guess on a vague request; no record of actions; confirmation on everything (fatigue) or on nothing; the destructive option focused by default.
- *In code:* `requireApproval`, `confirm(`, `allowedTools`, `permissions`, `dry_run`, `human_in_the_loop`, `auto_approve`, `bypassPermissions`, `--dangerously-skip-permissions`; `audit_log` tables; idempotency keys.
- *Quick test:* ask the AI to send an email or delete a file: does it show exactly what will happen and wait? Give a vague request: does it ask or guess? Find the record of what it did.

**How to implement.**
1. Sort actions: read-only (no prompt); reversible and local (run, offer undo); external or irreversible (preview and approve); destructive (preview, approve, back up first).
2. Make the prompt specific: the exact command, diff, recipient and body, or amount, not a bare "Allow?". Focus the safe choice.
3. When unsure, ask one narrowing question or offer 2 to 4 options. Set a threshold: act alone only when expected benefit clearly exceeds the cost of being wrong [4].
4. Cut prompt volume by design (allow-lists for safe commands, sandboxing, remembered approvals per scope) so each remaining prompt gets read [6][7].
5. Log each action with input, output and approver; snapshot before multi-step changes.
6. Keep a Stop control and a plan or dry-run mode.
7. If a denial leaves the AI stuck, tell it why and what to try instead (AI-09).

**Sources.**
[1] Parasuraman, R., Riley, V. (1997). Humans and Automation: Use, Misuse, Disuse, Abuse. Human Factors 39(2), 230-253. (snippet; paper not opened)
[2] Skitka, Mosier, Burdick (1999). Does automation bias decision-making? Int. J. Human-Computer Studies 51(5). (snippet; paper not opened). Related: Mosier et al. (1997). Automation Bias: Decision Making and Performance in High-Tech Cockpits. NASA. https://ntrs.nasa.gov/citations/20020043179
[3] Goddard, Roudsari, Wyatt (2012). Automation bias: a systematic review of frequency, effect mediators, and mitigators. JAMIA. https://pmc.ncbi.nlm.nih.gov/articles/PMC3240751/
[4] Horvitz, E. (1999). Principles of Mixed-Initiative User Interfaces. CHI '99. https://erichorvitz.com/chi99horvitz.pdf
[5] EU AI Act, Art. 14 (human oversight) and Art. 12 (record-keeping). https://artificialintelligenceact.eu/article/14/ ; https://artificialintelligenceact.eu/article/12/
[6] Anthropic (2025-10-20). Claude Code sandboxing (engineering blog). https://www.anthropic.com/engineering/claude-code-sandboxing
[7] Anthropic (n.d.). Claude Code docs: Configure permissions; Checkpointing. https://code.claude.com/docs/en/permissions ; https://code.claude.com/docs/en/checkpointing
[8] Apple (2025-06-09, updated 2026-06-08). HIG: Generative AI. https://developer.apple.com/design/human-interface-guidelines/generative-ai
[9] Amershi et al. (2019). Guidelines for Human-AI Interaction. CHI 2019. https://doi.org/10.1145/3290605.3300233
[10] Kannan et al. (2016). Smart Reply: Automated Response Suggestion for Email. KDD 2016. https://arxiv.org/abs/1606.04870

---

### AI-05 Stream output and show progress for slow AI

**What it is.** When a response takes more than about a second, show the first words as soon as they exist, show which step the system is on, and let the user stop. Track time to first token (TTFT). HAX has no guideline here; FBK-01 (response-time limits) and FBK-02 (progress indicators) hold the underlying research.

**Why it works.** Perceived waiting ends when useful content starts, not when the last token arrives, and people can read while the rest is written. Anthropic's docs say streaming can significantly improve perceived responsiveness because users see output as it arrives [1][2]. A generation speed of 10 tokens a second (about 450 words a minute) is already faster than people read, so after the first token the bottleneck is TTFT, not speed [3]. Apple advises status text that names the step, such as summarizing the user's notes, over a generic "Processing..." because it makes waiting feel purposeful [4]. The mechanism is inferred from general response-time and progress research (FBK-01, FBK-02), not from a streaming-specific study.

**Evidence: Weak.** No published controlled study of token streaming versus full-response display on perceived wait or satisfaction was found (searches in October 2026 were cut short, so read this as "none found", not "none exists"). Support is vendor documentation and platform guidance.

**Limitations.**
- Streams show unfinished and possibly wrong text. Errors can arrive after the 200 response has started (the Claude API sends `error` events such as `overloaded_error` mid-stream) [2]. See AI-09.
- Reflow, jumping scroll and auto-scroll that fights the reader hurt reading. Per-token live-region updates can flood screen readers (A11Y).
- Structured output (JSON, tables, tool arguments) cannot render meaningfully until complete; tool arguments stream as partial JSON [2].
- Streaming faster than reading speed adds nothing visible [3].
- Fake typing delays to seem human have no evidence behind them and conflict with AI-08.

**How to measure it works.**
- TTFT p50 and p95 from submit to first rendered token; time per output token; total time; abandonment before first token; Stop rate.
- Perceived wait: ask "how long did that feel?" in an A/B of streamed versus buffered output on the same model, with task completion and satisfaction. This is the missing evidence; run it locally.
- Leading: time to first visible acknowledgment (user message shown, status line).

**Implemented by.**
- Anthropic Messages API: `"stream": true` returns server-sent events (`message_start`, `content_block_delta`, `ping`, `error`); the docs recommend streaming for responsiveness [1][2].
- Apple HIG (2025): loading states or background generation, plus specific status text [4].
- Anecdote: major chat assistants stream text and swap Send for Stop while generating.

**How to detect it.**
- *Applied:* text appears within about 1 s and grows; Send becomes Stop; the status names the step ("Searching 3 sources"); partial output kept on stop; a clear done state.
- *Violated:* a spinner for 5 to 10 s, then a wall of text; no Stop; generic "Processing..."; the page jumps while streaming; a stream that ends silently with a truncated answer.
- *In code:* `stream: true`, `text/event-stream`, `EventSource`, `getReader()`, `TextDecoder`, `AbortController`; message states such as `streaming`, `done`, `error`; `aria-live`, `aria-busy`.
- *Quick test:* throttle the network (Slow 3G) and send a long prompt: how long to first visible text? Press Stop mid-stream. Go offline mid-stream: is there an error state with Retry?

**How to implement.**
1. Stream from the server (SSE, or fetch with a ReadableStream) and render incrementally; batch DOM writes per animation frame.
   ```js
   const ac = new AbortController(); stopBtn.onclick = () => ac.abort();
   const res = await fetch('/api/chat', { method: 'POST', body, signal: ac.signal });
   const reader = res.body.getReader(), dec = new TextDecoder();
   for (;;) { const { done, value } = await reader.read(); if (done) break; render(dec.decode(value, { stream: true })); }
   ```
2. Acknowledge at once (show the user's message and a status line within 100 ms) and show first content within about 1 s (FBK-01).
3. Swap Send for Stop; keep partial text on stop and mark it stopped.
4. For multi-step or agent work, name each step and its state. For jobs over about 10 s, show determinate progress or run in the background with a notification (FBK-02).
5. Auto-scroll only while the reader is at the bottom. Announce completion once for screen readers, not every token.
6. Handle mid-stream errors and refusals: keep what is valid, mark the rest incomplete, offer Retry (AI-09).
7. Lower TTFT with a faster model and shorter prompts and outputs; track TTFT per release [1].

**Sources.**
[1] Anthropic (n.d.). Reducing latency. https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-latency
[2] Anthropic (n.d.). Streaming messages. https://platform.claude.com/docs/en/build-with-claude/streaming
[3] Databricks (n.d.). LLM Inference Performance Engineering: Best Practices. https://www.databricks.com/blog/llm-inference-performance-engineering-best-practices
[4] Apple (2025-06-09, updated 2026-06-08). HIG: Generative AI. https://developer.apple.com/design/human-interface-guidelines/generative-ai

---

### AI-06 Collect granular feedback, show its effect, adapt cautiously

**What it is.** Let people react to single outputs in context (thumbs, "show less like this", correct, report). Apply the reaction at once and say what it changes. Change the AI's behavior gradually and announce changes. Covers HAX G13 (learn from behavior), G14 (adapt cautiously), G15 (granular feedback), G16 (convey consequences) and G18 (notify about changes).

**Why it works.** Feedback is the learning signal and gives users agency, but only if it visibly does something. PAIR: acknowledging feedback builds trust, and explaining how it will change the experience works better; be specific about timing and scope [3]. Apple: name each option by its consequence ("Suggest less pop music"), act on feedback immediately and persist it, and update predictions at a pace that fits the user's mental model [2]. Controls that do nothing erode trust. Mozilla's 2022 study of YouTube (22,722 volunteers; snippet) found that "Not interested" prevented about 11% of unwanted recommendations, "Remove from watch history" about 29% and "Don't recommend channel" about 43% (press reports of the study) [5][6]. Netflix replaced 5-star ratings with thumbs in April 2017 and said tests showed a 200% rise in ratings; it said stars confused members because they showed predictions, not averages [4].

**Evidence: Moderate.** Agreement across HAX, PAIR and Apple HIG, plus one large third-party measurement of control effectiveness. The Netflix figure is press-reported with no published method (Weak on its own).

**Limitations.**
- Asking costs attention; keep it optional and ask only when needed [2]. A click is not always "show me more" [3].
- Thumbs are coarse. A bare thumbs-down says little; offer an optional reason.
- Each extra feedback item may move the model less, and some feedback only filters content without tuning the model; say which [3].
- Adapting fast surprises users, and learning from implicit signals narrows exposure; leave room to explore [2]. HAX participants found G14 hard to judge in one session [1].
- The Netflix "200%" is secondhand: outlets disagree on who said it, and "200% more" is ambiguous [4].
- Implicit feedback is sensitive data (AI-07).

**How to measure it works.**
- Control-efficacy audit (Mozilla's approach): after "not interested", count similar items in the next N sessions; expect a sharp drop.
- Feedback rate per 100 outputs, share with a reason, repeat exposure to rejected items, satisfaction after negative feedback.
- A/B test the feedback widget (Netflix-style): rating volume and downstream engagement.
- After model or behavior changes: complaints, churn, support contacts, and whether the change notice was seen.

**Implemented by.**
- Netflix (2017): thumbs up/down replaced stars [4].
- YouTube (2022): Dislike, Not interested, Don't recommend channel, Remove from watch history; tested by Mozilla [5][6].
- HAX study examples rated clearly applied: email "mark as important" (G15); a social network saying that hiding an ad adjusts future ads (G16); a music app updating the list below the current song while keeping the list above fixed (G14); a navigation app using in-app callouts for new features (G18) [1].
- Apple HIG (Machine learning page, updated 2026-06-08): when a limitation is removed, tell people so they return to interactions they had avoided [2].

**How to detect it.**
- *Applied:* per-output thumbs or "show less"; reason chips worded as consequences; an immediate visible change; hidden items stay hidden everywhere; a notice when model or behavior changes; stable ordering while content updates.
- *Violated:* no feedback path; thumbs with no acknowledgement or effect; a rejected item returns elsewhere; the model swapped silently; lists reorder under the user.
- *In code:* `thumbsUp`, `thumbsDown`, `onFeedback`, `not_interested`, `feedback_reason`, `POST /feedback`; `model_version` shown in the UI; `whatsNew` or release-notes modals keyed to a version.
- *Quick test:* give negative feedback on one item. Does the UI change in the same session? Does a similar item show up in another place? Is there a reason picker? After an update, can you tell what changed?

**How to implement.**
1. Add lightweight feedback to every AI output, with an optional one-tap reason list worded as consequences.
2. Acknowledge immediately; apply to the current session; persist across the product.
3. Say what feedback does and does not do (filters your feed at once; may inform tuning later) [3].
4. Combine signals before inferring intent, and keep some exploration [2].
5. Keep the core stable and change the edges; update at the pace users expect [1][2].
6. Announce capability, model or behavior changes in context, and offer a way back to the old behavior where possible.
7. Review feedback on a schedule and publish what changed.

**Sources.**
[1] Amershi et al. (2019). Guidelines for Human-AI Interaction. CHI 2019. https://doi.org/10.1145/3290605.3300233
[2] Apple (2023-05-02, updated 2026-06-08). HIG: Machine learning (Explicit feedback, Implicit feedback, Limitations). https://developer.apple.com/design/human-interface-guidelines/machine-learning
[3] Google PAIR (2019, 2021). People + AI Guidebook, chapter Feedback + Control. https://pair.withgoogle.com/chapter/feedback-controls/
[4] VentureBeat (2017-04-05). Netflix ditches 5-star rating system for thumbs up and thumbs down. https://venturebeat.com/2017/04/05/netflix-ditches-5-star-rating-system-for-thumbs-up-and-thumbs-down (search snippets of other 2017 coverage attribute the 200% figure to Todd Yellin, Netflix's VP of product; this page names a different executive)
[5] Mozilla Foundation (2022-09-20). Does This Button Work? Investigating YouTube's ineffective user controls. https://www.mozillafoundation.org/en/research/library/user-controls/report/ (snippet; page blocked)
[6] Digital Trends (n.d.). Coverage of the Mozilla study. https://digitaltrends.com/computing/youtube-dislike-not-working-mozilla (gives 43% and 11%); Android Authority (n.d.), https://www.androidauthority.com/study-youtube-dislike-button-bad-recommendations-3210676 (snippet; gives 11% and 29%)

---

### AI-07 Give users global control over personalization, memory and data

**What it is.** One findable place where users can see, pause, edit, reset and delete what the AI remembers or learns, plus a mode that records nothing. Covers HAX G17 (global controls), with G12 (short-term memory) as the in-session part. Per-output feedback is AI-06.

**Why it works.** People want to know what is collected and what it changes. HAX folded "change privacy permissions" and "private mode" into G17 and found it relevant but under-applied [1]. PAIR: show what data is collected and where to review and change it, let users update or delete past choices, and offer a reset to the non-personalized default [2]. Apple: tell people how data is gathered and shared, give them ways to restrict it, and disclose how generative features use and store personal data [3]. Law sets a floor: under GDPR Art. 7(3), withdrawing consent must be as easy as giving it [8].

**Evidence: Moderate.** Agreement across HAX, PAIR and Apple HIG, plus consent law. No outcome study (for example, the effect of memory controls on trust or retention) was found.

**Limitations.**
- Few people change settings, so defaults decide outcomes (CHO). On 2020-06-24 Google made auto-delete after 18 months the default for new accounts' Web & App Activity; existing users kept their settings [6].
- Controls can be incomplete: OpenAI noted that deleting a chat does not delete memories saved from it (snippet) [4]. State what each control removes.
- Turning personalization off degrades the product; say so in one line. YouTube notes that with little history, history-based home recommendations are removed [7].
- Derived data (embeddings, profiles, logs) and training use need covering, not only visible history [3].

**How to measure it works.**
- Findability test: users find and switch off memory within a time you set (for example, 90% within 60 seconds).
- Control use: share who view, edit or delete memories; opt-out rate by default setting; deletion verified by audit (data gone from derived stores too).
- Comfort or trust survey items before and after launching controls; support tickets about data.

**Implemented by.**
- ChatGPT memory (2024-02-13): on by default; off switch in Personalization; delete single memories or say "forget"; Temporary Chat neither uses nor creates memories and is not used for training; first offered to a select group of Free and Plus users [4][5].
- Google (reported 2019-05-02): auto-delete for Location History and Web & App Activity after 3 or 18 months, or manual. On 2020-06-24: 18-month default for new accounts' Web & App Activity and 36 months for new YouTube accounts [6][9].
- YouTube: pause watch history in My Activity > Controls > Turn off; set auto-delete there [7].
- HAX study example rated clearly applied: a photo organizer where users turn on location history so the AI can group photos by place (G17) [1].

**How to detect it.**
- *Applied:* a settings page for personalization, memory and data; a list of stored memories with delete; an off toggle per category; a temporary or incognito mode; a retention picker; reset and delete-all; a note in answers when memory was used.
- *Violated:* memory with no off switch; deletion only by emailing support; no view of what is stored; opt-out disables unrelated features; training use not disclosed; controls buried more than 3 taps deep.
- *In code:* settings keys such as `memory_enabled`, `personalization`, `history_enabled`, `retention_days`, `training_opt_out`; `temporary` or `incognito` flags; `DELETE /memories`; export endpoints; consent records with timestamps.
- *Quick test:* from the main screen, find and turn off memory within 60 seconds. Delete one memory. Start a new chat and check it is no longer used. Check that temporary mode saves nothing.

**How to implement.**
1. List everything the AI stores or learns from: history, memories, embeddings, profile signals, logs, training use.
2. Build one Personalization and data page: a toggle per category, view/edit/delete for items, a retention choice, reset to default, delete all.
3. Add a no-record mode inside the chat itself.
4. Make deletion real: remove derived data and indexes, say how long it takes, and test it.
5. Show in context when memory shaped an answer, with a link to edit it (G11 with G17).
6. Collect consent so that withdrawal is as easy as giving it, and default to the more private option when the benefit is unclear (CHO) [8].
7. Explain the cost of turning a control off in one line.

**Sources.**
[1] Amershi et al. (2019). Guidelines for Human-AI Interaction. CHI 2019. https://doi.org/10.1145/3290605.3300233
[2] Google PAIR (2019, 2021). People + AI Guidebook, chapter Feedback + Control. https://pair.withgoogle.com/chapter/feedback-controls/
[3] Apple (2023-05-02, updated 2026-06-08; 2025-06-09). HIG: Machine learning (Implicit feedback); HIG: Generative AI (Privacy). https://developer.apple.com/design/human-interface-guidelines/machine-learning ; https://developer.apple.com/design/human-interface-guidelines/generative-ai
[4] OpenAI (2024-02-13). Memory and new controls for ChatGPT. https://openai.com/index/memory-and-new-controls-for-chatgpt/ (snippet; page blocked)
[5] VentureBeat (2024-02-13). OpenAI upgrades ChatGPT with persistent memory and temporary chat. https://venturebeat.com/ai/openai-upgrades-chatgpt-with-persistent-memory-and-temporary-chat
[6] CNBC (2020-06-24). Google will automatically delete location history by default. https://www.cnbc.com/2020/06/24/google-will-automatically-delete-location-history-by-default.html
[7] YouTube Help (n.d.). Manage your YouTube watch history. https://support.google.com/youtube/answer/95725
[8] GDPR Art. 7 (conditions for consent), paragraph 3. https://gdpr-info.eu/art-7-gdpr/
[9] The Hacker News (2019-05-02). Google will let users auto-delete location and web activity. https://thehackernews.com/2019/05/google-web-location-history.html

---

### AI-08 Disclose AI, label synthetic content, avoid passing as human

**What it is.** Tell people when they are talking to an AI or looking at AI-generated or altered content. Label media so people can see it and tools can read it. Do not use names, faces, voices or typing theatrics that make the system pass as a person. HAX has no guideline for this: its authors dropped "establish that the bot is not human" as too specific to one scenario [1]. The sources are law, Apple and PAIR.

**Why it works.** Human-like cues raise perceived accuracy and lower perceived risk, so a system that passes as human can earn more trust than its accuracy supports (inference). In a 2024 online experiment (2,165 US adults), speech plus text made an LLM seem more human-like and its information more accurate; first-person "I" raised perceived accuracy and lowered perceived risk in one context [2]. PAIR: human-like interfaces invite assumptions of human ability, leading to disappointment or over-reliance; say the product is an algorithm and do not imply near-perfect performance [3]. Apple: never let people believe they are dealing with a human, or with human-written content, when it is AI [4]. From 2026-08-02 it is a duty in the EU under Art. 50 [5][6].

**Evidence: Strong.** Strong as a legal and platform requirement; research on how labels change belief is Mixed (see Limitations). Required: EU AI Act Art. 50, applying from 2026-08-02: 50(1) AI-interaction notice (providers), 50(2) machine-readable marking of synthetic audio, image, video and text (providers; reported grace to 2026-12-02 for systems already on the market), 50(4) deepfake and public-interest text disclosure (deployers), 50(5) clear, first-contact, accessible notice [5][6][11].

**Limitations.**
- Labels can backfire. In two experiments (4,976 participants) an AI-generated label lowered perceived accuracy (about 0.17 points on a 6-point scale in the first) and willingness to share, even for true and human-written headlines, because people assumed full automation. The penalty vanished when the label said AI had only helped [7]. Define what the label means.
- Marking is not proof. SynthID reports only watermarks that are present and cannot flag unmarked AI content; its page says marks are designed to survive edits, not that they survive all [10]. Provenance data helps only if viewers display it (C2PA) [9].
- A one-time notice does not stop overtrust; pair it with AI-03 and AI-04.
- Labels on every item can cause banner blindness (VIS). The Act exempts obvious AI interaction and text reviewed under editorial responsibility; the Commission's draft says a spell-check or cursory sign-off is not enough [5][6].

**How to measure it works.**
- Comprehension test (5 to 8 users, 5-second view): "Is this a person or an AI?" and "Which parts were AI-made?" Set a target (for example, 90% correct).
- Label-noticing rate; misattribution rate; complaints; an audit against the Art. 50 duties that apply to you; check that C2PA manifests or watermarks survive export.

**Implemented by.**
- Google Duplex (2018): the May 2018 blog post called the calls automatic but did not commit to identifying the caller; after the backlash Google said it would build in disclosure (reported 2018-05-10) [8].
- Apple HIG (2025): tell people when and where AI is used [4].
- C2PA Content Credentials: open standard recording origin and edits; specification 2.3; steering committee includes Adobe, Amazon, BBC, Google, Meta, Microsoft, OpenAI, Publicis Groupe, Sony, TikTok and Truepic [9].
- Google SynthID: invisible watermark for images, video, audio and text from Google models; a detector portal opened in 2025 [10].

**How to detect it.**
- *Applied:* the first message or a persistent badge says it is an AI; voice agents say so in speech; AI media carries a visible label and a machine-readable mark; AI-drafted messages are marked before sending; the persona's name and avatar do not pose as a person.
- *Violated:* a human name and photo with no AI notice; fake "typing" delays; AI text under a human byline; synthetic images with no label; disclosure only in terms of service; a vague label such as "assistant".
- *In code:* strings `AI-generated`, `Generated by`, `AI assistant`, `Made with AI`; an `AIBadge`-style component; `c2pa`, `ContentCredentials`, `synthid`; a `setTimeout` before showing a reply to fake typing.
- *Quick test:* start as a new user: is it clear on the first screen or utterance that this is AI? Export a generated image and inspect its metadata with a Content Credentials verifier. Call the voice flow and listen for the notice.

**How to implement.**
1. Decide which Art. 50 duties apply: provider (the interface or generator) or deployer (publishing deepfakes or public-interest text).
2. Disclose in the interface at first contact, in plain words, with a persistent indicator; say it aloud in voice flows. Do not rely on terms of service or a vague label [6].
3. Do not give the AI a human name, photo or fake typing delay. If you use a persona, keep the AI notice visible [3].
4. Mark generated media twice: a visible label and machine-readable provenance (C2PA manifest or watermark) added at generation and kept through export [9][10].
5. Word labels by the AI's role ("AI-generated", "AI-assisted, reviewed by an editor") [7].
6. Make labels accessible: text, contrast, not icon-only [5].
7. Test comprehension, and watch the Commission's final guidelines and code of practice [6].

**Sources.**
[1] Amershi et al. (2019). Guidelines for Human-AI Interaction. CHI 2019. https://doi.org/10.1145/3290605.3300233
[2] Cohn et al. (2024). Believing Anthropomorphism: Examining the Role of Anthropomorphic Cues on Trust in Large Language Models. arXiv. https://arxiv.org/abs/2405.06079
[3] Google PAIR (2019, 2021). People + AI Guidebook, chapter Mental Models. https://pair.withgoogle.com/chapter/mental-models/
[4] Apple (2025-06-09, updated 2026-06-08). HIG: Generative AI (Transparency). https://developer.apple.com/design/human-interface-guidelines/generative-ai
[5] Regulation (EU) 2024/1689, Art. 50 (text as reproduced). https://artificialintelligenceact.eu/article/50/ ; application date, Art. 113: https://artificialintelligenceact.eu/article/113/
[6] GT Alert, gtlaw.com (2026-06). Deepfakes, chatbots, AI-generated text: European Commission details transparency obligations under the AI Act (law-firm summary of the draft Art. 50 guidelines of 2026-05-08; fines). https://www.gtlaw.com/en/insights/2026/6/deepfakes-chatbots-ai-generated-text-european-commission-details-transparency-obligations-under-the-ai-act
[7] Altay, Gilardi (2024-10-01). People are skeptical of headlines labeled as AI-generated, even if true or human-made, because they assume full AI automation. PNAS Nexus 3(10). https://academic.oup.com/pnasnexus/article/doi/10.1093/pnasnexus/pgae403/7795946
[8] Google (2018-05). Google Duplex: An AI System for Accomplishing Real-World Tasks Over the Phone. https://research.google/blog/google-duplex-an-ai-system-for-accomplishing-real-world-tasks-over-the-phone/ ; disclosure statement via Wikipedia, https://en.wikipedia.org/wiki/Google_Duplex (cites The Verge, 2018-05-10; page could not be opened)
[9] C2PA (page updated 2026-01-08). Coalition for Content Provenance and Authenticity. https://c2pa.org/
[10] Google DeepMind (n.d.). SynthID. https://deepmind.google/technologies/synthid/
[11] AI Act implementation timeline (Art. 50(2) date for existing systems). https://artificialintelligenceact.eu/implementation-timeline/

---

### AI-09 Fail gracefully with a path forward

**What it is.** When the AI cannot answer, is unsure, is blocked by policy, or a tool call, timeout or stream fails, say what happened in plain words and offer the next step: rephrase, narrower scope, a manual path, search, or a person. Covers PAIR's Errors + Graceful Failure chapter and HAX G10 (degrade gracefully). The HAX authors folded "fall back to a human" into G10 [8].

**Why it works.** PAIR: errors are inevitable and are chances to learn and to set mental models. Give a path forward, return control to the user with the context to continue, invite feedback, and monitor for dead ends through support reports and in-product metrics [1]. Always keep a non-AI fallback [2]. Apple: when something goes wrong, describe it in plain language and give a clear next step; when a request is blocked, coach with example requests that work; suggest alternatives instead of empty results [3][4]. Silent failure is the worst case: PAIR notes some errors are invisible to both user and system and need dedicated QA [1].

**Evidence: Moderate.** Agreement across PAIR, Apple HIG and HAX. No controlled study of failure-message designs was found.

**Limitations.**
- Over-explaining a refusal can show how to evade it; PAIR advises assuming subversive use [1].
- Suggested alternatives must be safe in high-stakes settings; verify them first [1].
- Over-refusal and unsafe compliance trade off. XSTest measures both with 250 safe prompts and 200 unsafe contrast prompts [5].
- Fallbacks cost money (human handoff), so tier them: retry, rephrase, alternative, non-AI path, person.
- An API refusal is not an error: the Claude API returns HTTP 200 with `stop_reason: "refusal"` and empty content, so error-rate monitoring never sees it [6].

**How to measure it works.**
- Dead-end rate: sessions that end within seconds of an error or refusal with no follow-up action; rephrase success rate; fallback use and completion.
- Over-refusal rate on a benign prompt set (XSTest style), rerun on every model change [5]; refusal events versus fallback-served events [6].
- Silent-failure audit: failed tool calls, truncated streams and mid-stream errors versus what the UI showed; the target is 100% surfaced.
- Handoff rate and resolution; feedback left on failure screens.

**Implemented by.**
- Apple HIG (2025): Image Playground reports that it is unable to use a description, and Apple suggests offering example requests that work better [3].
- Google Duplex (2018): hands off to a human operator when it cannot finish a task [7].
- HAX study example rated clearly applied: an autocomplete offering 3 or 4 suggestions instead of completing the text itself (G10) [8].
- Anthropic API: refusal responses carry a human-readable explanation to display (not parse) and optional fallback to another model [6].
- PAIR (2021): corrected-input checks for unexpected input; independent controls when systems compete [1].

**How to detect it.**
- *Applied:* error and refusal text states the cause and next step; suggested rewrites or example prompts; a button for a manual path, search or a person; partial results kept with an "incomplete" marker; Retry; visible tool-failure status.
- *Violated:* "Something went wrong" alone; a bare "I can't help with that"; a blank reply; an endless spinner; a truncated answer shown as complete; the AI says it succeeded after a failed tool call; the prompt cleared on failure.
- *In code:* `catch` blocks that only toast; ignored `stop_reason` / `finish_reason` values (`refusal`, `max_tokens`, `length`); no handler for stream `error` events such as `overloaded_error`; missing `onError`, `retry`, `fallback`, `handoff`.
- *Quick test:* (1) ask for something out of scope; (2) make a benign borderline request; (3) go offline mid-reply; (4) make a tool fail. Each time: does the UI say what happened and offer something to do?

**How to implement.**
1. List failure modes: out of scope, low confidence, policy refusal, tool error, timeout, truncation, rate limit, mid-stream error, wrong context. For each, write what happened, what it means for the user's data, and the next step.
2. Build a ladder: retry, rephrase hint, narrower or alternative result, non-AI path, person.
3. Return control: keep the user's input and any valid partial output; never clear the prompt.
4. Branch on stop reasons and stream error events, not on empty text; mark truncated output and offer Continue [6].
5. Write refusals that say what cannot be done and what can; show the API's explanation text rather than parsing it [6].
6. Put a feedback hook on failure screens [1].
7. Review dead ends weekly; keep a benign-prompt over-refusal set and run it on each model change [5].

**Sources.**
[1] Google PAIR (2019, 2021). People + AI Guidebook, chapter Errors + Graceful Failure. https://pair.withgoogle.com/chapter/errors-failing/
[2] Google PAIR (2019, 2021). People + AI Guidebook, chapter Mental Models. https://pair.withgoogle.com/chapter/mental-models/
[3] Apple (2025-06-09, updated 2026-06-08). HIG: Generative AI. https://developer.apple.com/design/human-interface-guidelines/generative-ai
[4] Apple (2023-05-02, updated 2026-06-08). HIG: Machine learning (Mistakes, Limitations). https://developer.apple.com/design/human-interface-guidelines/machine-learning
[5] Röttger et al. (2023; NAACL 2024). XSTest: A Test Suite for Identifying Exaggerated Safety Behaviours in Large Language Models. https://arxiv.org/abs/2308.01263
[6] Anthropic (n.d.). Refusals and fallback; Streaming messages. https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback ; https://platform.claude.com/docs/en/build-with-claude/streaming
[7] Google (2018-05). Google Duplex: An AI System for Accomplishing Real-World Tasks Over the Phone. https://research.google/blog/google-duplex-an-ai-system-for-accomplishing-real-world-tasks-over-the-phone/
[8] Amershi et al. (2019). Guidelines for Human-AI Interaction. CHI 2019. https://doi.org/10.1145/3290605.3300233
