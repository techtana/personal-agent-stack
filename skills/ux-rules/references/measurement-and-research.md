# Measuring UX and research methods (MEA)

This category covers how to find out whether a UX rule works: usability tests, inspection methods, task and survey metrics, product analytics, A/B tests, field performance data, information-architecture studies, severity rating and field research. Every other category's "How to measure it works" section points here. Load it when you must pick a method to validate a rule, judge whether a team measures anything, or decide whether a reported UX result can be trusted. In this category "How to detect it" means how to tell that a team or product uses the method, and "How to implement" means how to run it.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| MEA-01 | Run small, iterative usability tests | Moderate | Any interface with reachable users, from paper prototype to live product |
| MEA-02 | Use heuristic evaluation and cognitive walkthroughs as cheap inspection, not as proof | Moderate | Early designs and first-use flows, before or between user tests |
| MEA-03 | Measure task success, time on task and errors | Strong | Benchmarks and design comparisons for any task-based flow |
| MEA-04 | Use standardized questionnaires (SUS, UMUX-Lite, SEQ, NASA-TLX) | Strong | Post-test and in-product attitude measures, tracked over releases |
| MEA-05 | Tie UX to product metrics with HEART and Goals-Signals-Metrics | Moderate | Live products with event logging |
| MEA-06 | Run online controlled experiments (A/B tests) correctly | Strong | Live products with enough traffic per variant |
| MEA-07 | Use behavioral analytics (funnels, retention, rage and dead clicks, masked session replay) | Moderate | Live web and mobile products |
| MEA-08 | Measure performance in the field, not just the lab | Moderate | Web (CrUX, RUM) and native apps |
| MEA-09 | Treat CSAT, CES and NPS with care | Mixed | Survey programs, support and post-purchase flows |
| MEA-10 | Validate information architecture with card sorting, tree testing and first-click tests | Moderate | Navigation and labels for sites and apps |
| MEA-11 | Rate the severity of findings consistently | Moderate | Any findings list from a test, audit or inspection |
| MEA-12 | Observe real use in context (field studies, contextual inquiry, diary studies) | Moderate | Discovery before design; workflows, enterprise tools, multi-day tasks |

---

### MEA-01 Run small, iterative usability tests

**What it is.** Watch 3 to 5 representative users per user group attempt realistic tasks, usually while thinking aloud. Fix what you saw, then test again. The value comes from repeating the cycle, not from one large study.

**Why it works.**
- Nielsen and Landauer's model says n users find N(1 - (1 - L)^n) of the N problems, where L is the share one user finds. Across their projects L averaged 31%, so five users find about 85% (1 - 0.69^5 = 0.84) [1]. Nielsen advises three rounds of five over one round of fifteen: each round checks the last round's fixes and reaches problems the old ones hid [1].
- Iteration pays. In four case studies Nielsen measured a median 38% gain in a usability metric per redesign and 165% from first to last version, with 8 to 10 test users per version [2].
- Think-aloud makes reasoning visible and needs about a day to collect data from a handful of users [3]. RITE goes further: fix a problem as soon as one participant exposes it and the fix is clear. In the Age of Empires II tutorial case (2002), six more participants needed no changes after the fixes made with ten [4].

**Evidence: Moderate.** Simulations and practitioner studies, 1993 to 2012. They agree that small rounds find the common problems. They disagree on whether five users is enough, so treat "5 users = 85%" as an average, not a guarantee (Mixed for that figure).

**Limitations.**
- L varies. With L = 0.10 the model gives 41% for five users; with L = 0.20, 67% (our calculation). Faulkner drew random 5-user sets from 60 real participants: they found 55% to 99% of problems; the weakest 10-user set found 80% and the weakest 20-user set 95% [5]. Spool and Schroeder (2001) concluded that open-ended tasks on web sites need far more than five users [6]. A later analysis reports 10 +/- 2 users for 80% (snippet) [8].
- Think-aloud changes behavior and supports weak statistics [3]. Use about 20 users for quantitative studies and 3 to 4 per group when groups differ sharply [1][7].
- A report nobody acts on adds nothing. RITE needs a team that can change the build within hours and has few decision makers [4].

**Fit and cost.**
- *Good at validating:* whether people understand and complete a flow: labels, navigation, forms, onboarding, error recovery (INT, NAV, FRM, CON, ONB, ERR rules). Not rates or small effects.
- *Needs:* 5 users per round per user group (3 minimum), 2 to 3 rounds. No traffic.
- *Rough cost:* low to medium. About a day of sessions per round [3], plus recruiting and incentives (estimate).

**How to measure it works.**
- Leading: new problems per round should fall; share of last round's problems verified fixed; unaided completion of core tasks should rise.
- Lagging: task success and SUS across versions (MEA-03, MEA-04); support contacts and drop-off at the tested step (MEA-07).
- Method check: if round 2 still shows many new serious problems, discovery has not saturated. Add tasks or users.

**Implemented by.**
- Microsoft, Age of Empires II tutorial (2002): RITE with ten participants and fixes between sessions, then six sessions needing no change [4]. One published case.
- Nielsen's four projects (1993): home banking, cash register, security and hypertext systems, 3 to 5 versions each, median +38% per version [2].

**How to detect it.**
- *Applied:* dated test plans, task lists, session notes or recordings, and a findings list whose items link to tickets and to later design changes.
- *Violated:* design choices justified by opinion; one large test just before launch with no time to fix; only colleagues as participants.
- *In code or repo:* folders or labels such as `usability`, `user-research`, `findings`, `test-plan`, `think-aloud`; issue labels `usability`, `ux-research`; PRs that cite a session.
- *Quick test:* ask for the last three test dates, who took part, and one change each produced. No answer means not applied.

**How to implement.**
1. Write 3 to 5 task scenarios from real user goals. Keep interface labels out of the wording.
2. Recruit 5 participants per distinct user group who match real users, not colleagues. Include assistive-technology users (see the A11Y testing rule).
3. Run sessions with think-aloud. Stay quiet, do not help, and note task success and the point where each user got lost [3].
4. Debrief the same day: list problems, rate severity (MEA-11), fix the top ones, retest within days. Plan at least three versions [2].
5. Where the team can change the build in hours, use RITE: fix after one clear observation and finish with six sessions that need no change [4].

**Sources.**
[1] Nielsen, J. (2000). Why You Only Need to Test with 5 Users. Nielsen Norman Group. https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/ (model from Nielsen and Landauer 1993, INTERCHI '93; that paper not opened)
[2] Nielsen, J. (1993). Iterative User-Interface Design. IEEE Computer 26(11), 32-41. NN/g summary: https://www.nngroup.com/articles/iterative-design/
[3] Nielsen, J. (2012). Thinking Aloud: The #1 Usability Tool. NN/g. https://www.nngroup.com/articles/thinking-aloud-the-1-usability-tool/
[4] Medlock, Wixon, Terrano, Romero and Fulton (2002). Using the RITE Method to Improve Products: A Definition and a Case Study. UPA 2002 (paper not opened). Summary: Sauro, J. Ten Things to Know About the RITE Method. MeasuringU. https://measuringu.com/rite-method/
[5] Faulkner, L. (2003). Beyond the five-user assumption: Benefits of increased sample sizes in usability testing. Behavior Research Methods, Instruments, & Computers 35(3), 379-383. https://pubmed.ncbi.nlm.nih.gov/14587545/
[6] Spool, J. and Schroeder, W. (2001). Testing web sites: five users is nowhere near enough. CHI 2001 Extended Abstracts, 285-286. https://dblp.uni-trier.de/rec/conf/chi/SpoolS01.html (record only; abstract seen on a bibliography page, snippet; secondary sources disagree on 18 vs 49 users, and full text was not opened)
[7] Nielsen, J. (2012). How Many Test Users in a Usability Study? NN/g. https://www.nngroup.com/articles/how-many-test-users/
[8] Communications of the ACM (2012). Sample size in usability studies. https://cacmb4.acm.org/magazines/2012/4/147354-sample-size-in-usability-studies/fulltext (snippet; page returned 403)

---

### MEA-02 Use heuristic evaluation and cognitive walkthroughs as cheap inspection, not as proof

**What it is.** In a heuristic evaluation (HE), 3 to 5 evaluators each inspect an interface alone against a set of heuristics (usually Nielsen's ten) and log violations. In a cognitive walkthrough (CW), evaluators step through a task action by action and ask whether a first-time user would know what to do. Both find likely problems without users.

**Why it works.**
- Evaluators miss different problems, so pooling raises coverage. Across six case studies one evaluator found on average 42% of the major and 32% of the minor problems [1]. NN/g advises 3 to 5 independent evaluators, each working 1 to 2 hours before seeing the others' findings [2]. Nielsen and Molich's 1990 experiments are reported to show single evaluators finding 20% to 51% (snippet; the scan was not readable) [3].
- CW (Wharton et al. 1994) targets learnability for first-time and walk-up use. At each step it asks: will the user try the right effect, notice the correct action, link it to the effect, and see progress after acting [4].

**Evidence: Moderate.** Comparison and reliability studies from 1990 to 2014 agree that inspection needs no users and that results vary widely by evaluator. None shows that inspection findings predict user outcomes on their own.

**Limitations.**
- Evaluator effect: in a review of 11 studies, any two evaluators analyzing the same system agreed on only 5% to 65% of problems (abstract seen secondhand) [5]. When 19 professionals analyzed the same five sessions, each of the nine in the moderated group reported on average 33% of the problems that group found collectively [6]. Four evaluators found 93 problems in four videos; about a fifth were found by all four and nearly half by one [7].
- HE lists skew to minor problems: 59 major and 152 minor across six interfaces [1]. A heuristic violation is not always a problem. Heuristics are guidelines, and trade-offs can justify breaking one; confirm with user research first [2].
- CW gives no estimate of how often or how badly a problem occurs, fits one to four tasks per session, and relies on evaluators' self-report [4].

**Fit and cost.**
- *Good at validating:* clear violations of rules in other categories (consistency, feedback, error messages, labels, first-use flows) before a test. Not whether users succeed or prefer a design.
- *Needs:* 3 to 5 evaluators with usability or domain knowledge, 1 to 2 hours each [2]. No users or traffic.
- *Rough cost:* low; a few person-days including consolidation (estimate).

**How to measure it works.**
- Hit rate: share of inspection findings later confirmed by user tests (MEA-01) or analytics (MEA-07). Compare findings per evaluator-hour with findings per test-hour.
- Reliability: overlap between evaluator pairs. Low overlap means add evaluators, not trust one list.

**Implemented by.**
- Nielsen and Molich introduced HE in 1990; NN/g's current procedure uses independent passes, then a merged list [2].
- No company outcome figures found. The evidence comes from research comparisons, not product results.

**How to detect it.**
- *Applied:* a dated review listing each issue with heuristic, location, screenshot, severity and evaluator initials; more than one reviewer; a merged list.
- *Violated:* one person's audit presented as proof; no independent passes; heuristics cited without evidence; "passed heuristic review" used as a launch gate.
- *In code or repo:* `heuristic-evaluation`, `ux-audit`, `walkthrough`; headings such as "Consistency and standards"; issue labels naming heuristics.
- *Quick test:* count the evaluators and check they worked independently. With one evaluator, treat the output as hypotheses.

**How to implement.**
1. Fix the scope (one flow, one user group, one device) and the heuristic set (Nielsen's ten plus the platform guideline).
2. Have 3 to 5 evaluators work alone for 1 to 2 hours, two passes each, logging heuristic, location and evidence [2].
3. For a CW, write the user goal and the correct action sequence, then answer the four questions for every step. Record each failure as a short story [4].
4. Merge, de-duplicate and rate severity together (MEA-11). Label each finding "hypothesis" until a test confirms it.
5. Send severe or disputed items to a usability test (MEA-01) or an experiment (MEA-06).

**Sources.**
[1] Nielsen, J. (1992, summary 1995). Usability Problems Found by Heuristic Evaluation (from Finding usability problems through heuristic evaluation, CHI '92). NN/g. https://www.nngroup.com/articles/usability-problems-found-by-heuristic-evaluation/
[2] Moran, K. and Gordon, K. (2023). How to Conduct a Heuristic Evaluation. NN/g. https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/
[3] Nielsen, J. and Molich, R. (1990). Heuristic evaluation of user interfaces. CHI '90. https://blogs.fu-berlin.de/hci2023/files/2023/06/Nielsen-and-Molich-1990-Heuristic-evaluation-of-user-interfaces.pdf (image-only scan; the 20% to 51% range comes from secondary summaries, snippet)
[4] Wharton, Rieman, Lewis and Polson (1994). The Cognitive Walkthrough Method: A Practitioner's Guide. In Nielsen and Mack (Eds.), Usability Inspection Methods, 105-140. Wiley. Summary of the four questions and limits: UXPA Usability Body of Knowledge. http://www.usabilitybok.org/cognitive-walkthrough/
[5] Hertzum, M. and Jacobsen, N. E. (2001). The Evaluator Effect: A Chilling Fact About Usability Evaluation Methods. International Journal of Human-Computer Interaction 13(4), 421-443. https://doi.org/10.1207/s15327590ijhc1304_05 (abstract seen via a search summary, snippet; publisher page returned 403)
[6] Hertzum, Molich and Jacobsen (2014). What you get is what you see: revisiting the evaluator effect in usability tests. Behaviour & Information Technology 33(2), 144-162. https://econpapers.repec.org/RePEc:taf:tbitxx:v:33:y:2014:i:2:p:144-162
[7] Jacobsen, Hertzum and John (1998). The evaluator effect in usability studies: Problem detection and severity judgments. University of Copenhagen research profile (venue not stated on the page). https://researchprofiles.ku.dk/en/publications/the-evaluator-effect-in-usability-studies-problem-detection-and-s/

---

### MEA-03 Measure task success, time on task and errors

**What it is.** Define key tasks with clear end states. Record whether each user completes them (task success), how long it takes (time on task) and what slips occur (errors, extra steps). These are the effectiveness and efficiency measures of ISO 9241-11:2018.

**Why it works.**
- ISO 9241-11:2018 defines usability as the extent to which specified users reach specified goals with effectiveness, efficiency and satisfaction in a specified context of use. Effectiveness is accuracy and completeness; efficiency is resources spent against results achieved [1].
- Behavior is not the same as opinion. SUS correlates only r = .24 with task performance, about 6% of the variance, so satisfaction scores cannot stand in for performance [2].
- Benchmarks make results comparable. Across 1,189 tasks from 115 usability tests and 3,472 users, the average completion rate was 78% [3].

**Evidence: Strong.** Defined in ISO 9241-11:2018 (a voluntary standard) and used across decades of HCI measurement practice [1][4].

**Limitations.**
- Small samples give wide intervals. Adjusted-Wald 95% intervals (our calculation): 5 of 5 successes means 51% to 100%; 16 of 20 means 58% to 93%; 80 of 100 means 71% to 87%. Report the interval, not only the percentage [4].
- Time data is right-skewed. Report the median or geometric mean, not the arithmetic mean (standard advice in [4]; not re-checked here).
- "Success" needs a correct answer fixed before testing. Vague tasks make the metric meaningless. Think-aloud prompts change behavior and the method supports weak statistics, so collect timings in sessions run without it [8].
- Lab tasks are artificial. Check that lab gains carry over with production metrics (MEA-05, MEA-07).

**Fit and cost.**
- *Good at validating:* rules that claim fewer errors or faster completion: fewer fields (FRM), shortcuts and accelerators (INT), navigation changes (NAV), error messages (ERR). Also comparing two designs or a release with its baseline.
- *Needs:* about 20 users for a quantitative study [5]; more to detect small differences between designs (do a power calculation). Unmoderated tools reach this cheaply.
- *Rough cost:* medium. Task and scoring protocol, 20+ recruits, analysis (estimate). A benchmark can be repeated each release.

**How to measure it works.**
- Per task: success with 95% interval, median or geometric-mean time, errors per task. Compare with the previous release and with the 78% average [3].
- Pair with SEQ per task (MEA-04). Success and SEQ correlate around r = .5, so high success with a low SEQ means the path works but feels hard [6].

**Implemented by.**
- Google: Task success is one of the five HEART categories, covering efficiency, effectiveness and error rate [7].
- MeasuringU's pooled data set (1,189 tasks) is a public benchmark teams can compare against [3].

**How to detect it.**
- *Applied:* a test report with task list, success criteria, per-task success, time and error counts with intervals; the same table repeated each release.
- *Violated:* "users liked it" or "4 of 5 succeeded" with no definition of success or no times.
- *In code or repo:* events `task_started`, `task_completed`, `task_failed`; `time_on_task`, `error_rate`; `performance.mark(` and `performance.measure(` around flows; `success_criteria` in test plans.
- *Quick test:* ask for per-task success rates and how "success" is defined.

**How to implement.**
1. Pick 5 to 10 tasks tied to business goals. Write each end state ("order number shown").
2. Fix scoring rules before testing: unaided and correct counts as success; partial credit; when the clock stops; give-up rule; error types.
3. Run about 20 participants for a benchmark [5]. Log time with a timer, not memory.
4. Report success with an adjusted-Wald interval, times as median or geometric mean, and errors per task [4].
5. In production, mirror the tasks with start and success events and track completion (MEA-07).

**Sources.**
[1] ISO (2018). ISO 9241-11:2018 Ergonomics of human-system interaction, Part 11: Usability: Definitions and concepts. https://www.iso.org/standard/63500.html (page returned 403; definitions paraphrased from the published abstract)
[2] Sauro, J. The System Usability Scale page. MeasuringU. https://measuringu.com/sus/
[3] Sauro, J. What Is A Good Task-Completion Rate? MeasuringU (undated page). https://measuringu.com/task-completion/
[4] Sauro, J. and Lewis, J. R. (2016). Quantifying the User Experience: Practical Statistics for User Research (2nd ed.). Morgan Kaufmann. https://www.sciencedirect.com/book/9780128023082/quantifying-the-user-experience (book not opened; page returned 403)
[5] Nielsen, J. (2012). How Many Test Users in a Usability Study? NN/g. https://www.nngroup.com/articles/how-many-test-users/
[6] Sauro, J. 10 Things to Know About the Single Ease Question (SEQ). MeasuringU. https://measuringu.com/seq10/
[7] Rodden, K., Hutchinson, H. and Fu, X. (2010). Measuring the User Experience on a Large Scale. CHI 2010. https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/36299.pdf
[8] Nielsen, J. (2012). Thinking Aloud: The #1 Usability Tool. NN/g. https://www.nngroup.com/articles/thinking-aloud-the-1-usability-tool/

---

### MEA-04 Use standardized questionnaires (SUS, UMUX-Lite, SEQ, NASA-TLX)

**What it is.** Validated short surveys with fixed wording, known scoring and published norms. SUS (10 items, 0 to 100) rates a whole product. UMUX-Lite has 2 items. SEQ is one 7-point item after each task. NASA-TLX rates workload on six scales. Use them instead of home-made questions.

**Why it works.**
- Fixed items with published reliability and norms let you compare with other products and with your own earlier releases. John Brooke made SUS in 1986 (published 1996); it uses 10 items on a 5-point scale scored 0 to 100. The mean over about 500 studies is 68 [1][2]. In Sauro's grade curve 68 is the 50th percentile, 80.8 to 84.0 is an A (90th to 95th percentile), and 51.6 or less is an F [2].
- UMUX-Lite (a capability item and an ease item) correlated r = .83 with SUS and r = .72 with NPS, and a regression predicts SUS from it [3]. SEQ averages 5.3 to 5.6 over more than 400 tasks and 10,000 users, and Sauro and Dumas (2009) found it as good as or better than two other one-item post-task scales (SMEQ and UME) [4].
- NASA-TLX (Hart and Staveland 1988) rates mental, physical and temporal demand, performance, effort and frustration, each on a 100-point range. The full version weights the scales through 15 pairwise comparisons; "raw TLX" skips the weights [5].

**Evidence: Strong.** For SUS: decades of validation and hundreds of studies. Moderate for UMUX-Lite and SEQ (fewer, newer studies). NASA-TLX: heavy use since 1988.

**Limitations.**
- SUS is not diagnostic. It was not designed to find specific problems and tracks task performance only modestly (r = .24) [1].
- The 68 benchmark mixes many product types. Compare like with like and report an interval. SUS can be scored from as few as two people, but small samples are imprecise [1].
- Wording changes, scale direction, timing (after a test or in-product) and product familiarity move scores. The original UMUX had mixed-tone items that produced an artificial two-factor structure [3].
- Ratings come from people who agree to answer; non-respondents are missing (see MEA-09).

**Fit and cost.**
- *Good at validating:* overall perceived usability after a redesign (SUS); whether one task got easier (SEQ); whether a design adds load (NASA-TLX), for example complex forms or AI review tasks. Not which rule or element caused the change.
- *Needs:* no traffic. Report an interval; as a rule of thumb (estimate) use 20 or more per version to see moderate differences.
- *Rough cost:* very low. Two to five minutes per respondent and free instruments.

**How to measure it works.**
- Track score with interval per release; compare with 68 and the prior version. Check SEQ against success and time per task (expect about r = .5) to confirm respondents answer sensibly [4].
- If SUS rises while task success or retention does not, check who was surveyed and when (response bias).

**Implemented by.**
- Google's HEART examples: a weekly in-product satisfaction survey on a 7-point scale for iGoogle; after a redesign satisfaction dipped, then recovered, which the team read as change aversion [6].
- NASA Ames's Human Performance Group developed the TLX over three years and more than 40 lab simulations; it is now used across fields [5].

**How to detect it.**
- *Applied:* a post-test form with the ten SUS statements, a score out of 100 in the report, SEQ after each task, results compared with 68.
- *Violated:* a home-made "rate us 1 to 5"; "satisfaction 4.2/5" with no baseline or n; SUS with altered items or wrong scoring.
- *In code or repo:* fields `sus`, `umux_lite`, `seq`, `nasa_tlx`; survey tools (Qualtrics, Typeform, Google Forms) containing the item text (grep `use this system frequently`, or the SEQ question about how difficult or easy the task was).
- *Quick test:* check scoring: odd items minus 1, even items 5 minus the response, sum times 2.5 [1].

**How to implement.**
1. Give SUS once, after the whole session, with the ten items unchanged (replace "system" with the product name only). Score as above [1].
2. Ask SEQ after every task: "Overall, how difficult or easy was the task to complete?" on 7 points [4]. Use UMUX-Lite when only two items fit in-product [3].
3. Use NASA-TLX (raw version is common) for high-load tasks and report the six subscales, not only a total [5].
4. Report mean with interval, compare with 68 and the last release, and add one open question ("what made it hard?").
5. Pair every score with behavior (MEA-03) before acting on it.

**Sources.**
[1] Sauro, J. The System Usability Scale page. MeasuringU. https://measuringu.com/sus/ (original: Brooke, J. (1996). SUS: A "quick and dirty" usability scale. In Usability Evaluation in Industry, Taylor and Francis; chapter not opened)
[2] Sauro, J. Interpreting SUS scores. MeasuringU. https://measuringu.com/interpret-sus-score/
[3] Sauro, J. Measuring usability with the UMUX-Lite. MeasuringU. https://measuringu.com/umux-lite/ (original: Lewis, Utesch and Maher (2013), CHI 2013; not opened)
[4] Sauro, J. 10 Things to Know About the Single Ease Question (SEQ). MeasuringU. https://measuringu.com/seq10/ (original: Sauro and Dumas (2009), CHI 2009; not opened)
[5] Hart, S. G. and Staveland, L. E. (1988). Development of NASA-TLX (Task Load Index): Results of Empirical and Theoretical Research. In Hancock and Meshkati (Eds.), Human Mental Workload, 139-183. North-Holland. Summary read: https://en.wikipedia.org/wiki/NASA-TLX (NASA's own page, https://humansystems.arc.nasa.gov/groups/tlx/, refused the connection; chapter not opened)
[6] Rodden, K., Hutchinson, H. and Fu, X. (2010). Measuring the User Experience on a Large Scale. CHI 2010. https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/36299.pdf

---

### MEA-05 Tie UX to product metrics with HEART and Goals-Signals-Metrics

**What it is.** HEART is five categories for user-centered metrics: Happiness, Engagement, Adoption, Retention and Task success. Goals-Signals-Metrics (GSM) is the process: state the goal, name the observable signals, then define the metrics.

**Why it works.**
- Common business metrics (PULSE: page views, uptime, latency, seven-day active users, earnings) are indirect or ambiguous. A rise in page views can mean a popular feature or lost users. Seven-day actives can rise while retention collapses [1].
- GSM makes a team agree on goals before choosing numbers. Signals should move only when the experience gets better or worse, and metrics should be ratios or per-user averages, not raw counts [1].
- Google applied it to more than 20 products. Gmail's engagement metric was the share of active users who visited on five or more days in a week, found strongly predictive of long-term retention. After the iGoogle redesign, satisfaction dipped and recovered. Maps compared error rates in an A/B test of a single search box [1].

**Evidence: Moderate.** One CHI 2010 paper from one company, widely copied. It is a framework with case examples; no controlled test shows that HEART improves decisions.

**Limitations.**
- Not every category fits. Engagement may mean little for tools people must use at work [1].
- The authors say metrics suit launched products and do not replace early research; triangulate with usability and field studies [1] (see MEA-01, MEA-12).
- Logs show what, not why. They need bot filtering and complete event logging, which is not default for AJAX apps [1].
- Optimizing engagement can conflict with user welfare (see CHO). Engagement here means depth or frequency of use, not time spent.

**Fit and cost.**
- *Good at validating:* whether a change moved the outcome it was meant to move; links ONB (activation), NAV (findability) and FBK (speed) rules to product outcomes.
- *Needs:* a live product with event logging and enough users per period for stable ratios (thousands of weekly users is a workable floor; estimate).
- *Rough cost:* medium. A half-day goals workshop per feature, instrumentation work and a dashboard (estimate).

**How to measure it works.**
- Every metric has an owner, a goal, a target and a review date, and a decision cites it. Retire metrics nobody acts on.
- Check that a leading metric predicts a lagging one in your data, as Gmail's five-day metric did for retention [1].

**Implemented by.**
- Google (2010): HEART and GSM on more than 20 products, including Gmail, iGoogle, Maps and Finance [1].
- Other teams adopt HEART (widely repeated; no published outcomes found).

**How to detect it.**
- *Applied:* a metrics doc or dashboard organized by H, E, A, R, T with goal and signal per metric; per-feature adoption and retention charts; roadmap items citing a metric.
- *Violated:* a PULSE-only dashboard (page views, daily users, revenue); metrics without goals; "shipped" counted as success.
- *In code or repo:* a tracking plan (`tracking-plan`, `events.yaml`); events such as `signup_completed`, `feature_adopted`, `task_completed`; calls `analytics.track(`, `posthog.capture(`, `amplitude.track(`, `mixpanel.track(`, `gtag('event'`, `dataLayer.push(`.
- *Quick test:* pick a dashboard metric and ask what goal it tracks and what the team would do if it dropped.

**How to implement.**
1. Write the feature's goal in one user-centered sentence. Use the five categories as prompts.
2. List signals (logged actions or survey answers) for success and failure. Mark which are not logged yet.
3. Turn signals into metrics: per user or percentage, with a time window (weekly, 30 days), bots filtered [1].
4. Instrument one event per signal and record names and definitions in a tracking plan.
5. Review before and after launches and in A/B tests (MEA-06).

**Sources.**
[1] Rodden, K., Hutchinson, H. and Fu, X. (2010). Measuring the User Experience on a Large Scale: User-Centered Metrics for Web Applications. CHI 2010. https://research.google/pubs/measuring-the-user-experience-on-a-large-scale-user-centered-metrics-for-web-applications/ (full text: https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/36299.pdf)

---

### MEA-06 Run online controlled experiments (A/B tests) correctly

**What it is.** Randomly assign users to control or treatment, measure metrics declared in advance, and decide with statistics. Done correctly, this is the one method that shows a live change caused an effect.

**Why it works.**
- Randomization removes confounders. In 2012 a Bing engineer tested lengthening ad title lines, an idea that had sat in the backlog for more than six months. Revenue rose 12%, over $100M a year in the US, without significantly hurting key user-experience metrics [1].
- Intuition is poor. A review co-authored by Kohavi states that more than half of ideas fail to improve the metrics they target, and 90% or more fail in some domains [2]. Microsoft has reported about one third positive, one third flat and one third negative (snippet) [3].
- Scale: Bing runs over 10,000 experiments a year [1]. Thomke estimates some 25,000 tests a year at Booking.com [4].

**Evidence: Strong.** Randomized experiments, with pitfalls documented across several large companies in the KDD literature and the 2020 book. The success-rate figures are company self-reports.

**Limitations.**
- Sample ratio mismatch (SRM): the observed split differs from the planned split (chi-squared test; one public tool alarms at p < 0.01). About 6% of Microsoft experiments and about 10% of LinkedIn's triggered experiments had SRM. An SRM means do not trust the result [5].
- Peeking: stopping at the first significant result inflates false positives. In one worst-case simulation a nominal 5% became 26.1% [6][2]. Fix the sample size first, using n of about 16 x variance / delta^2 per variant, or use sequential methods [6][2].
- Twyman's law: a surprising result is usually an error. Bing's +12% passed because a "too good to be true" alert triggered checks, and the test was replicated [1][7].
- Novelty and primacy: effects drift as users learn. Run whole weeks (two weeks is typical) and look at the trend, not only the total [2].
- Metrics: use one overall evaluation criterion (OEC) plus guardrails, metrics that must not degrade (latency, errors, sessions per user). Revenue alone is insufficient [1].
- Ethics: Facebook's 2012 emotional-contagion study (689,003 users, January 11 to 18, 2012) changed what News Feed showed. Users were not told; the authors cited Facebook's Data Use Policy as consent. Effects were tiny (d = 0.001 to 0.02). PNAS attached an Editorial Expression of Concern on July 3, 2014, and the lead author apologized (snippet) [8][9]. Get review for tests that touch emotion, money or access, and do not test deceptive patterns (see CHO).

**Fit and cost.**
- *Good at validating:* the causal effect of copy, layout, defaults, onboarding steps and speed changes (MEA-08) on behavior. Poor for rare events, tiny audiences and "why" questions.
- *Needs:* traffic. Rule of thumb n of about 16 x p(1-p) / delta^2 per variant, where delta is the smallest absolute change worth detecting [6]. Our calculation: 5% baseline conversion and a 10% relative lift needs about 30,400 users per variant; a 5% lift needs about 121,600. Low-traffic products should use MEA-01 and MEA-03.
- *Rough cost:* medium to high at first (assignment, logging, statistics, review). Cheap per test once the platform exists; Kohavi stresses that per-experiment overhead must be small [1].

**How to measure it works.**
- Run A/A tests on a new platform and check SRM on every experiment. Track the share of experiments with valid results and the lift that holdouts confirm after launch.
- Leading: experiments per week with a valid readout. Lagging: cumulative lift on the OEC.

**Implemented by.**
- Microsoft Bing: over 10,000 experiments a year; the ad-title test gave +12% revenue [1].
- Booking.com: some 25,000 tests a year (Thomke 2020, HBR opening) [4].
- Duolingo: its Q2 2022 shareholder letter credits an "A/B test everything" approach (as cited by Larsen et al.) [2].

**How to detect it.**
- *Applied:* an experiment registry with hypothesis, primary metric, guardrails, sample size, dates and SRM check; feature flags with variants; written results including losers.
- *Violated:* before-and-after comparisons called tests; many variants or metrics with only winners reported; stopping when the dashboard turns green; two-day tests; no SRM check.
- *In code:* `ldClient.variation(`, `statsig.checkGate(`, `getExperiment(`, `growthbook.isOn(`, `getFeatureValue(`, `posthog.getFeatureFlag(`, `optimizelyClient.activate(`, `client.getTreatment(`, `useExperiment(`; fields `experiment_id`, `variant`, `exposure`; native: Firebase Remote Config and A/B Testing.
- *Quick test:* find one flag with variants. Check an exposure event fires once per user at assignment and that allocations sum to 100%.

**How to implement.**
1. Before launch write the hypothesis, primary metric (OEC), 2 to 5 guardrails, minimum detectable effect and run length.
2. Compute sample size and run whole weeks, usually two. Do not stop early unless you use a sequential method [2][6].
3. Randomize on a stable user ID. Log exposure when the user first sees the difference. Avoid overlapping tests on one surface.
4. Before reading results, check SRM and logging. Run an A/A test when the platform is new.
5. Decide on interval and guardrails. Replicate surprising wins (Twyman's law).
6. Review tests that touch emotion, price, safety or vulnerable users before launch.

**Sources.**
[1] Kohavi, R., Tang, D. and Xu, Y. (2020). Trustworthy Online Controlled Experiments, ch. 1 "Introduction and Motivation". Cambridge University Press. https://assets.cambridge.org/97811087/24265/excerpt/9781108724265_excerpt.pdf
[2] Larsen, N., Stallrich, J., Sengupta, S., Deng, A., Kohavi, R. and Stevens, N. T. (2023). Statistical Challenges in Online Controlled Experiments: A Review of A/B Testing Methodology. The American Statistician. https://arxiv.org/pdf/2212.11366.pdf
[3] Kohavi, R. (2012). Online Controlled Experiments: Introduction, Learnings, and Humbling Statistics. ACM RecSys 2012 slides. https://www.slideshare.net/slideshow/online-controlled-experiments-introduction-learnings-and-humbling-statistics/14339953 (snippet; not opened)
[4] Thomke, S. (2020). Building a Culture of Experimentation. Harvard Business Review, March-April 2020. https://hbr.org/2020/03/building-a-culture-of-experimentation (only the opening summary was readable)
[5] Fabijan, A. et al. (2019). Diagnosing Sample Ratio Mismatch in Online Controlled Experiments. KDD 2019. https://www.lukasvermeer.nl/publications/papers/2019/07/25/diagnosing-sample-ratio-mismatch-in-online-controlled-experiments.html ; prevalence and threshold from Vermeer's SRM FAQ: https://lukasvermeer.nl/srm/docs/faq/
[6] Miller, E. How Not To Run an A/B Test (undated). https://www.evanmiller.org/how-not-to-run-an-ab-test.html
[7] Twyman's law (summary with Kohavi references). Wikipedia. https://en.wikipedia.org/wiki/Twyman%27s_law
[8] Kramer, A. D. I., Guillory, J. E. and Hancock, J. T. (2014). Experimental evidence of massive-scale emotional contagion through social networks. PNAS 111(24), 8788-8790. https://pmc.ncbi.nlm.nih.gov/articles/PMC4066473/ (page notes the Expression of Concern of July 3, 2014)
[9] Marketing Magazine (2014). Head researcher apologises for controversial Facebook experiment. https://www.marketingmag.com.au/social-digital/head-researcher-apologises-for-controversial-facebook-experiment/ (snippet; not opened)

---

### MEA-07 Use behavioral analytics: funnels, cohorts and retention, rage and dead clicks, session replay with privacy masking

**What it is.** Instrument what users do in production. Funnels show where people drop between steps. Cohort and retention curves show who comes back. Rage clicks, dead clicks, quick backs and excessive scrolling flag frustration. Session replay and heatmaps show the cause.

**Why it works.**
- Logs cover every user where tests cover a handful, and Retention separates new from returning users in a way raw seven-day-active counts do not [1].
- Frustration signals tell you which sessions to watch. Microsoft Clarity defines rage clicks as repeated clicks in a clustered area within a short time, dead clicks as clicks with no response, quick backs as moving to a new page then quickly returning, and excessive scrolling as scrolling faster than normal content reading [2]. Clarity does not publish the thresholds.

**Evidence: Moderate.** Vendor documentation, the HEART paper and wide practitioner use. No controlled study found that rage-click counts predict revenue. The privacy risk is well documented (Strong). Required (privacy part): consent for non-essential cookies and tracking in the EEA and UK under the ePrivacy Directive Art. 5(3) and GDPR; Clarity has enforced a consent signal for EEA, UK and Swiss traffic since October 31, 2025 [4][6]. This is not legal advice.

**Limitations.**
- Shows what, not why. Consent decliners, ad blockers and bots skew the data. Rage clicks also come from slow responses or habit, so verify in a replay before acting.
- Replay leaks data. In 2017 Princeton researchers found session-replay scripts on 482 of the top 50,000 sites. Passwords, card details (one checkout leaked a CVV) and displayed health data were captured despite redaction. No vendor masked displayed page content by default, and redaction tied to field types or CSS classes broke when sites changed [3].
- Without consent, Clarity features that depend on cookies, such as recordings and funnels, may be limited. Consent is treated as valid for up to 9 months [4].
- Clarity masks input boxes and dropdowns in every mode but does not mask content inside style sheets [5].

**Fit and cost.**
- *Good at validating:* whether a fix removed friction at a step: form errors (FRM), findability (NAV), slow responses (FBK), unclear signifiers causing dead clicks (INT), activation and retention (ONB).
- *Needs:* replays work at any traffic. Watch 10 to 20 sessions per hypothesis (estimate). Funnel and cohort rates need hundreds to thousands of users per step to be stable (estimate).
- *Rough cost:* low to medium. Tag install, consent banner, masking review and weekly triage. Clarity retains recordings 30 days, favorites up to 9 months [7].

**How to measure it works.**
- Frustration rate: share of sessions per page with rage or dead clicks; expect it to fall after a fix. Funnel step conversion and D1/D7/D30 retention by cohort.
- Audit the tool: compare event counts with server logs, and review replays of login and checkout for leaked data.

**Implemented by.**
- Microsoft Clarity: rage click, dead click, quick back and excessive scrolling filters; Strict, Balanced (default) and Relaxed masking; Android, iOS, Flutter and React Native SDKs [2][5][8].
- Google HEART: Gmail's five-or-more-days metric predicted retention [1].
- Vendors in the 2017 study: Yandex, FullStory, Hotjar, UserReplay, Smartlook, SessionCam [3].

**How to detect it.**
- *Applied:* a funnel dashboard and retention chart; replay tool with inputs masked; consent banner that gates the tag; privacy policy that mentions session recording.
- *Violated:* replay tag loads before consent; names, card fields or health data visible in replays; dashboards of page views only.
- *In code:* `clarity(`, `www.clarity.ms/tag`, `data-clarity-mask`, `data-clarity-unmask`, `consentv2`, `static.hotjar.com`, `hj(`, `data-hj-suppress`, `fullstory`, `fs-exclude`, `LogRocket.init`, `ph-no-capture`; funnel events `checkout_step`.
- *Quick test:* open a replay of checkout. Confirm card, email, name and address fields and displayed totals are masked. Decline consent and confirm the tag sets no cookies.

**How to implement.**
1. Define 3 to 5 funnels for core tasks and one event per step. Add cohort and retention charts.
2. Install the replay tool behind the consent banner. Use the strictest masking that still lets you diagnose, mask personal elements by selector or attribute, and exclude payment and health pages [3][5].
3. Triage weekly: sort pages by rage or dead clicks, watch 10 to 20 sessions per hypothesis, file findings with severity (MEA-11).
4. Confirm each fix with a before-and-after rate or an A/B test (MEA-06).
5. Set retention, access control and deletion rules, and disclose recording in the privacy policy.

**Sources.**
[1] Rodden, K., Hutchinson, H. and Fu, X. (2010). Measuring the User Experience on a Large Scale. CHI 2010. https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/36299.pdf
[2] Microsoft (2026, page dated 2026-05-21). Filters overview, Microsoft Clarity documentation. https://learn.microsoft.com/en-us/clarity/filters/clarity-filters
[3] Englehardt, S., Acar, G. and Narayanan, A. (2017). No boundaries: Exfiltration of personal data by session-replay scripts. Princeton CITP blog, November 15, 2017. https://blog.citp.princeton.edu/2017/11/15/no-boundaries-exfiltration-of-personal-data-by-session-replay-scripts/
[4] Microsoft (2026, page dated 2026-05-21). Consent management, Microsoft Clarity documentation. https://learn.microsoft.com/en-us/clarity/setup-and-installation/consent-management
[5] Microsoft. Masking content, Microsoft Clarity documentation. https://learn.microsoft.com/en-us/clarity/setup-and-installation/clarity-masking
[6] European Union (2002, consolidated 2009). Directive 2002/58/EC (ePrivacy), Article 5(3). https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02002L0058-20091219 (page text did not load; cited from general knowledge)
[7] Microsoft. Session list, Microsoft Clarity documentation. https://learn.microsoft.com/en-us/clarity/session-recordings/session-list
[8] Microsoft. Microsoft Clarity documentation hub (lists the mobile SDKs). https://learn.microsoft.com/en-us/clarity/

---

### MEA-08 Measure performance in the field, not just the lab

**What it is.** Collect performance metrics from real users (real-user monitoring and the Chrome UX Report, CrUX) and judge them at the 75th percentile. Use lab tools such as Lighthouse to debug and to test before release, not to report how users fare.

**Why it works.**
- A lab run uses one device, one network and one location, usually with a cold cache. Field data covers real devices, networks, caches, personalization and interactions, and is a distribution, not one number [1].
- Core Web Vitals are judged at the 75th percentile of page loads, split by mobile and desktop. Good means LCP of 2.5 s or less, INP of 200 ms or less and CLS of 0.1 or less [2].
- Some metrics cannot be measured in the lab. INP depends on when users choose to interact. Total Blocking Time is a lab proxy that misses tap delay. Lab LCP waits for full load, while field LCP stops at the first interaction [1].

**Evidence: Moderate.** Consistent documentation from the platform owner; the lab and field gap follows from how each is collected. Business impact comes from case studies. Not required, but Google Search uses CrUX data in its page experience signal [3].

**Limitations.**
- CrUX includes only eligible origins (public, with enough visitors) and Chrome users. Small sites and users who cannot load the page at all are missing; lab tests cover them [1][3].
- The web-vitals library reports INP only after an interaction, may fire a callback more than once, and cannot see inside iframes [4].
- Speed is not the whole experience; a fast page can still confuse. See FBK-05 for thresholds and fixes.

**Fit and cost.**
- *Good at validating:* FBK rules on speed, responsiveness and layout stability, and any claim that a change made the UI faster. Compare releases and segments (device, country).
- *Needs:* CrUX needs a public origin with enough visitors. Your own collection needs enough page loads per segment for a stable 75th percentile (thousands; estimate).
- *Rough cost:* low. CrUX, PageSpeed Insights and Search Console are free; the web-vitals library adds a small script; you pay for beacon storage.

**How to measure it works.**
- Compare 75th-percentile LCP, INP and CLS before and after releases, by device and country.
- Tie speed to business metrics with an experiment. Vodafone (2021) split paid traffic 50/50 (about 34K visits a day per version); the version with 31% better field LCP had 8% more sales, a 15% better lead-to-visit rate and 11% better cart-to-visit rate [5].
- Cross-check: a Lighthouse score that rises while the field 75th percentile does not means the lab setup is unrepresentative.

**Implemented by.**
- Google: CrUX and the Core Web Vitals program [2][3].
- Vodafone (2021): measured LCP on real sessions with `PerformanceObserver` and ran the 50/50 test above [5].

**How to detect it.**
- *Applied:* a dashboard of 75th-percentile LCP, INP and CLS by device from RUM or CrUX; field alerts; beacons sent to an endpoint.
- *Violated:* only Lighthouse scores in CI; "95 in Lighthouse" offered as proof; averages instead of percentiles.
- *In code:* `import {onLCP, onINP, onCLS} from 'web-vitals'`, `web-vitals/attribution`, `new PerformanceObserver(` with `largest-contentful-paint`, `layout-shift` or `event`, `navigator.sendBeacon(`; native: Android vitals in Play Console, MetricKit (`MXMetricManager`) on iOS, Firebase Performance.
- *Quick test:* open PageSpeed Insights for the URL and compare its field-data and lab sections. Ask where last week's 75th-percentile INP is.

**How to implement.**
1. Read CrUX or PageSpeed Insights for your origin and top URLs. Note the 75th percentile per metric and device [2][3].
2. Add the web-vitals library (attribution build). Send each metric with `navigator.sendBeacon()` plus page, device and release ID. Batch and flush on `visibilitychange` [4].
3. Chart the 75th percentile by template, device and country, and alert on regressions.
4. Run Lighthouse or WebPageTest in CI to debug and enforce budgets; reproduce field worst cases with a slow device and throttled network [1].
5. Validate large speed changes with an A/B test on business metrics (MEA-06) [5].

**Sources.**
[1] Google. Why lab and field data can be different (and what to do about it). web.dev. https://web.dev/articles/lab-and-field-data-differences
[2] Google. Web Vitals. web.dev. https://web.dev/articles/vitals
[3] Google. Chrome UX Report (CrUX). Chrome for Developers. https://developer.chrome.com/docs/crux
[4] GoogleChrome. web-vitals library (README). https://github.com/GoogleChrome/web-vitals
[5] Google (2021-03-17). Vodafone case study. web.dev. https://web.dev/case-studies/vodafone

---

### MEA-09 Treat CSAT, CES and NPS with care

**What it is.** CSAT asks how satisfied a customer is with an interaction or product. CES (Customer Effort Score) asks how easy it was to get something done. NPS asks how likely they are to recommend, 0 to 10, and is scored as the percentage of promoters (9 to 10) minus detractors (0 to 6). Each is a single-item survey metric.

**Why it works.**
- Dixon, Freeman and Toman (2010) argued that delighting customers does less for loyalty than reducing the effort they spend, and proposed CES for that [1]. Reichheld (2003) argued that the "would you recommend" question beats other loyalty questions as a predictor of growth [2]. Both claims were widely adopted. The data sections of both articles were not readable here, so no figures from them are given.
- Cheap, short and easy to trend, these scores are useful as coarse health signals. Google's HEART lists satisfaction and likelihood to recommend under Happiness [3].

**Evidence: Mixed.** The scores measure what they ask. The claims that one of them predicts growth better than others are contested, and the scores do not diagnose design problems.

**Limitations.**
- Predictive claim: Keiningham et al. (2007, Journal of Marketing) questioned whether NPS reliably predicts company growth, and Hayes (2008) found no evidence that the recommend question beats other loyalty questions [4]. Reichheld later warned of overuse and urged de-linking NPS from pay [4]. See also the MYTH entry on NPS.
- Noise: with 100 responses, 50% promoters and 20% detractors, the 95% interval on an NPS of 30 is about +/-15 points; with 400 responses, about +/-8 (our calculation). Movements of a few points are noise.
- Grouping 0 to 10 into three buckets discards information. One question cannot say what to fix [4].
- CES was built for service interactions. It says little about a product's learnability or discoverability.
- Response rates are falling and users resent frequent prompts [4].

**Fit and cost.**
- *Good at validating:* only coarse outcomes: relationship health (NPS), interaction quality (CSAT), friction in support and self-service flows (CES). Weak for validating any one design rule; use MEA-03, MEA-04 and MEA-07.
- *Needs:* roughly 100 to 400 responses per segment per period for +/-15 to +/-8 points on NPS (our calculation).
- *Rough cost:* low for tooling. The hidden cost is survey fatigue and misuse in targets and pay.

**How to measure it works.**
- Test the score against behavior in your own data (repeat purchase, churn, referrals). If it does not relate, stop using it for decisions.
- Track response rate and who answers; code open-text answers into themes.

**Implemented by.**
- Google HEART includes satisfaction and likelihood to recommend as Happiness metrics, tracked by weekly in-product survey on iGoogle [3].
- UMUX-Lite correlates r = .72 with NPS in MeasuringU's write-up, so a two-item usability scale can stand in for NPS in a test [5].
- No verified outcome figures for CES programs found (the Gartner page returned 403).

**How to detect it.**
- *Applied:* survey text with the 0 to 10 recommend question, an ease item such as "made it easy", or a satisfaction item; results reported with n, interval and segments; verbatims read.
- *Violated:* NPS shown without n or interval; scores tied to bonuses; pop-ups on every visit; a score cited as proof that a redesign worked.
- *In code:* `nps`, `csat`, `ces`; 0 to 10 radio groups; widgets such as Delighted, Qualtrics, Medallia, Hotjar surveys; `survey.show(` triggers; grep `likely to recommend`.
- *Quick test:* check when and how often the survey appears, and whether an open-text "why" follows.

**How to implement.**
1. Match the metric to the question: CES after support or self-service flows, CSAT after transactions, NPS quarterly at relationship level, SEQ or SUS in design tests (MEA-04).
2. Ask once, right after the event, with an open-text "why"; cap frequency per user.
3. Report n, interval and segment splits. Do not compare across industries or survey modes.
4. Validate against behavior; read verbatims weekly; keep scores out of pay.
5. Treat changes smaller than the interval as no change.

**Sources.**
[1] Dixon, M., Freeman, K. and Toman, N. (2010). Stop Trying to Delight Your Customers. Harvard Business Review, July-August 2010. https://hbr.org/2010/07/stop-trying-to-delight-your-customers (only the opening read; data section not opened)
[2] Reichheld, F. F. (2003). The One Number You Need to Grow. Harvard Business Review 81(12), 46-54. https://hbr.org/2003/12/the-one-number-you-need-to-grow (only the opening read)
[3] Rodden, K., Hutchinson, H. and Fu, X. (2010). Measuring the User Experience on a Large Scale. CHI 2010. https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/36299.pdf
[4] Keiningham, T. L., Cooil, B., Andreassen, T. W. and Aksoy, L. (2007). A Longitudinal Examination of Net Promoter and Firm Revenue Growth. Journal of Marketing 71(3), 39-51 (publisher page returned 403; not opened). Critique summarized in Wikipedia, Net promoter score (includes Hayes 2008 and Reichheld's later remarks). https://en.wikipedia.org/wiki/Net_promoter_score
[5] Sauro, J. Measuring usability with the UMUX-Lite. MeasuringU. https://measuringu.com/umux-lite/

---

### MEA-10 Validate information architecture with card sorting, tree testing and first-click tests

**What it is.** Card sorting asks users to group and name content, which generates a structure. Tree testing asks users to find items in a text-only hierarchy, which evaluates a structure. First-click testing records where users click first on a screen or mock-up for a task.

**Why it works.**
- Each method isolates one cause: structure (tree test), grouping and labels (card sort), visible entry points (first click). NN/g describes tree testing as evaluating a hierarchy with no layout, design or content, and says card sorting is a poor way to evaluate a hierarchy [1].
- Card sorts need enough people to be stable. Tullis and Wood's results, as reported by Nielsen: correlation with the final result is 0.75 for 5 participants, 0.90 for 15, 0.95 for 30 and 0.98 for 60. He recommends 15, or 30 for large projects [2].
- First clicks predict success. A write-up on MeasuringU reports that users whose first click went down the right path succeeded 87% of the time, against 46% after a wrong first click. It names no original source. Bailey, Wolfson et al. (2009) is the usual attribution, but that paper could not be opened [3].

**Evidence: Moderate.** Practitioner research with stated methods (NN/g, Tullis and Wood 2004). The first-click figures are widely repeated, correlational and not traced to a paper that could be opened.

**Limitations.**
- Tree tests omit visual design, mega-menus and search, and tools often accept only leaf nodes as correct answers [1].
- Card sorts show how people group items, not which items matter most; participants may sort by surface features.
- 87% versus 46% is a correlation. Wrong first clicks can be recovered, and tasks must be realistic.
- NN/g gives no fixed sample for tree tests: a few participants for qualitative, more for quantitative [1]. No verified number was found.

**Fit and cost.**
- *Good at validating:* NAV rules (organize by user mental model, information scent, consistent navigation) and CON terminology, before and after a restructure.
- *Needs:* card sort 15 per user group (30 for large projects) [2]. Tree test: a few moderated or a larger unmoderated sample [1]. First-click: MeasuringU's example used 13 users and 80% intervals [3]; use more for stable rates (estimate).
- *Rough cost:* low. Unmoderated tools, one to three days each, no build needed (estimate).

**How to measure it works.**
- Tree test: success rate, directness and time per task, compared with the current tree [1]. First click: share of correct first clicks per task.
- Live check: search use, quick backs (MEA-07) and time to complete top tasks after launch.
- MeasuringU's example (13 users): three tasks were significantly faster on the new navigation; several were similar; three were slower or varied widely [3].

**Implemented by.**
- No company outcome figures found for card sorts or tree tests.
- MeasuringU's write-up compares old and new navigation with first-click tasks and 13 users (results above) [3].

**How to detect it.**
- *Applied:* labels traceable to a card-sort report; a tree-test results table (task, success, directness); a documented sitemap with test dates.
- *Violated:* navigation that mirrors the org chart or internal jargon; labels never tested; a restructure launched without a findability baseline.
- *In code or repo:* `card-sort`, `tree-test`, `treejack`, `optimalsort`, `chalkmark`, `first-click`, `sitemap`; analytics events `search_no_results`, `nav_click` by label.
- *Quick test:* give five people three target tasks and watch their first click against the intended path.

**How to implement.**
1. List top tasks from analytics, support tickets and interviews.
2. Run an open card sort with 15 participants per user group to draft groups and labels [2].
3. Run a tree test on the draft and the current tree with the same tasks. Iterate until success and directness reach target [1].
4. Run first-click tests on screens or mock-ups for the top tasks and fix the most common wrong clicks [3].
5. After launch, watch search use, quick backs and funnel drop-off, and re-test yearly.

**Sources.**
[1] Laubheimer, P. (2023-08-06). NN/g article on tree testing. Nielsen Norman Group. https://www.nngroup.com/articles/tree-testing/ (exact title not captured)
[2] Nielsen, J. (2004-07-18). Card Sorting: How Many Users to Test. NN/g (reporting Tullis and Wood 2004). https://www.nngroup.com/articles/card-sorting-how-many-users-to-test/
[3] Sauro, J. (2011-10-19). MeasuringU page on first-click testing (exact title not captured). https://measuringu.com/first-click/ (the 87% and 46% figures appear without attribution; Bailey, Wolfson et al. 2009, a paper on performance-based usability testing metrics, not opened)

---

### MEA-11 Rate the severity of findings consistently

**What it is.** Give every usability finding a severity so teams can order fixes. Nielsen's scale: 0 not a problem, 1 cosmetic, 2 minor, 3 major, 4 usability catastrophe. Use a written rubric and several independent raters.

**Why it works.**
- Severity combines frequency (how often), impact (how hard to overcome) and persistence (whether users are bothered once or repeatedly). Nielsen adds market impact for problems that hurt a product's standing even when easy to overcome [1].
- Raters disagree, so one opinion is not enough. Nielsen calls a single evaluator's ratings too unreliable to trust and suggests the mean from about three evaluators, around 30 minutes each [1]. In a study with four evaluators watching four sessions, no problem appeared in all four top-10 severity lists [2]. In a 2014 study, of problems reported by several evaluators, 24% (moderated) and 30% (unmoderated) were rated critical by one and minor by another [3].

**Evidence: Moderate.** The scale is a 1994 practitioner standard. Research shows low rater agreement; no study shows that one scale yields better outcomes.

**Limitations.**
- Ratings express judgment. Do not read meaning into small gaps such as 2.7 versus 3.0.
- Severity is not priority. Priority also weighs effort, risk and strategy, so a cheap level-2 fix can beat a costly level-3. A level-4 finding blocks release [1].
- With 5 test users, frequency estimates are coarse (one user is 20%).
- Accessibility barriers can block a user group entirely; rate them by impact on that group (see A11Y).

**Fit and cost.**
- *Good at validating:* nothing directly. It ranks findings from MEA-01, MEA-02, MEA-07 and MEA-12, and helps decide which rules to apply first.
- *Needs:* about three independent raters [1]. No traffic.
- *Rough cost:* low; about 30 minutes per rater [1].

**How to measure it works.**
- Inter-rater agreement: share of findings where raters differ by two or more levels. Time to fix by severity; share of level 3 and 4 fixed within the agreed window.
- After launch, check that high-severity fixes moved MEA-03 or MEA-07 metrics.

**Implemented by.**
- Nielsen's 0 to 4 scale (1994) is used in NN/g reports; many teams use variants such as critical, serious, minor [1][3].
- No company outcome data found.

**How to detect it.**
- *Applied:* a findings list with severity column, a rubric with an example per level, rater initials, and a severity-by-effort view.
- *Violated:* everything "high"; severity set by the loudest voice; no rubric; effort mixed into severity ("quick win" as low severity).
- *In code or repo:* labels `severity:major`, `sev-3`, `usability-catastrophe`; a `severity` column in audit CSV or JSON; `P0` to `P3` with written definitions.
- *Quick test:* take five findings, ask two people to rate them independently, and compare.

**How to implement.**
1. Write a rubric. Score frequency (all, some, few users), impact (blocks, slows, annoys) and persistence (once, repeats); add market impact; give one example per level [1].
2. Have three raters score independently, then discuss any gap of two or more levels and take the mean or a consensus [1].
3. Store severity beside the evidence: screenshot, count of users affected, source method.
4. Prioritize by severity and effort: fix level 4 before release, plan level 3, batch level 2, park level 1 [1]. Re-rate after fixes.
5. Review the rubric yearly against outcomes.

**Sources.**
[1] Nielsen, J. (1994-11-01). Severity Ratings for Usability Problems. Nielsen Norman Group. https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/
[2] Jacobsen, N. E., Hertzum, M. and John, B. E. (1998). The evaluator effect in usability studies: Problem detection and severity judgments. University of Copenhagen research profile (venue not stated on the page). https://researchprofiles.ku.dk/en/publications/the-evaluator-effect-in-usability-studies-problem-detection-and-s/
[3] Hertzum, M., Molich, R. and Jacobsen, N. E. (2014). What you get is what you see: revisiting the evaluator effect in usability tests. Behaviour & Information Technology 33(2), 144-162. https://econpapers.repec.org/RePEc:taf:tbitxx:v:33:y:2014:i:2:p:144-162

---

### MEA-12 Observe real use in context: field studies, contextual inquiry and diary studies

**What it is.** Study people in their own setting. Contextual inquiry combines observation with interviews of a small sample of users. Field studies also include direct observation, customer-site visits and ethnography. A diary study has participants log activities over days or weeks.

**Why it works.**
- Context shows what a lab hides: distractions, noise, other people, workarounds, existing tools, users' own vocabulary and mental models, and problems you would not think to ask about [1].
- Diary studies capture behavior and experience over time and in context, which suits products used across days, such as meal delivery or buying a phone plan [2].
- Google's HEART authors say behavior metrics should be triangulated with usability and field studies [3]. NN/g places field and diary studies in the "strategize" stage, before design [4].

**Evidence: Moderate.** Consistent guidance from NN/g and the HEART paper, and a place in the human-centred design process (ISO 9241-210:2019 lists understanding the context of use as a core activity; voluntary; not opened [5]). No controlled study measuring outcome gains was found.

**Limitations.**
- Field methods have not become cheaper at the pace of other usability methods, and observers can change behavior. Remote sessions cannot show context outside the camera. Confidential or dangerous settings may need other methods [1].
- Diary studies lose participants and burden them, so over-recruit and set a realistic minimum entry rate [2].
- Small samples give themes, not prevalence. Size findings with surveys or analytics (MEA-07) [4].

**Fit and cost.**
- *Good at discovering and checking:* whether rules from ONB, NAV, CON, AI and PLT match real workflows, devices and places; unmet needs; context-specific failures.
- *Needs:* NN/g gives no fixed field-study sample; contextual inquiry uses "a small sample" [1]. Diary studies: about 5 to 12 people for a small homogeneous topic, 12 to 30 for a large discovery project, 30 to 50 for very broad groups [2].
- *Rough cost:* medium to high. NN/g's incentive guideline is about $40 an hour of total commitment for a general US sample; diary studies need a pilot [2].

**How to measure it works.**
- Count requirements and design decisions traced to observations, and "surprises" per session (things the team did not expect).
- Check coverage: did the sample include each user type and environment?
- Later, compare adoption of features designed from field data with those from internal ideas, if the team tags the source.

**Implemented by.**
- No verified company outcome figures found. NN/g documents the methods and costs (2024) [1][2].

**How to detect it.**
- *Applied:* field notes, photos, workflow diagrams and journey maps that cite observed sessions; a research repository with dates, sites and participants; roadmap items that cite observations.
- *Violated:* personas written from assumptions; requirements only from stakeholders; "we know our users" with no recent site visit.
- *In code or repo:* `field-notes`, `contextual-inquiry`, `diary-study`, `journey-map`, `affinity`; research tags in the tracker.
- *Quick test:* ask when a team member last watched a user work in their own setting, and what changed because of it.

**How to implement.**
1. Write the research question and the context to observe: where, when, with which tools and people.
2. Recruit by segment. For diaries use the sample sizes above and over-recruit [2].
3. Contextual inquiry: visit, watch real tasks while interviewing, photograph artifacts with permission, ask for demonstrations [1].
4. Diary: choose a logging channel, set a minimum entry rate, split incentives by milestones, review entries as they arrive, and finish with an interview [2].
5. Synthesize into workflows and pain points, then turn them into tasks for MEA-01 and MEA-03 and metrics for MEA-05.

**Sources.**
[1] Farrell, S. and Fessenden, T. (2024-01-12). NN/g article on field studies. Nielsen Norman Group. https://www.nngroup.com/articles/field-studies/ (exact title not captured)
[2] Flaherty, K. (2024-03-29). Diary Studies: Understanding Long-Term User Behavior and Experiences. NN/g. https://www.nngroup.com/articles/diary-studies/
[3] Rodden, K., Hutchinson, H. and Fu, X. (2010). Measuring the User Experience on a Large Scale. CHI 2010. https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/36299.pdf
[4] Nielsen Norman Group. When to Use Which User-Experience Research Methods (original by Christian Rohrer, 2014; author and year not checked against the source). https://www.nngroup.com/articles/which-ux-research-methods/
[5] ISO (2019). ISO 9241-210:2019 Human-centred design for interactive systems. https://www.iso.org/standard/77520.html (not opened)
