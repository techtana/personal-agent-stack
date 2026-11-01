# Onboarding, activation and engagement (ONB)

This category covers the first minutes and first weeks: when to ask for an account, how to define and speed up activation, how to teach, what to show when there is nothing to show, setup checklists, templates, streaks and reminders, and permission requests. Load it when auditing sign-up, first-run, empty screens, notification or permission prompts, and retention features. Several famous numbers in this area are unsourced folklore; the entries say which. Measurement methods are in MEA, manipulative variants are in CHO.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| ONB-01 | Deliver value before asking for commitment | Moderate | apps and sites with accounts or sign-up walls |
| ONB-02 | Define activation and shorten time-to-value | Weak | products with retention goals (SaaS, consumer apps) |
| ONB-03 | Teach in context, not with up-front tutorials | Moderate | first-run flows, new-feature announcements |
| ONB-04 | Design empty states that explain and offer the first action | Moderate | lists, dashboards, tables, results pages |
| ONB-05 | Use setup checklists with visible progress | Moderate | products that need several setup steps |
| ONB-06 | Offer templates and sample content instead of a blank canvas | Weak | creation tools, editors, workspaces, dashboards |
| ONB-07 | Use habit features only where the habit serves the user | Mixed | apps whose value depends on repeated use |
| ONB-08 | Ask for permissions in context, with a reason | Moderate | mobile apps, browsers and PWAs, desktop apps |

---

### ONB-01 Deliver value before asking for commitment

**What it is.** Let people use the core of the product before asking them to create an account, and ask for registration at the point where saving, sharing or buying needs it (lazy registration, gradual engagement).

**Why it works.**
- A sign-up form asks for commitment when people know least about the value. Wroblewski's "gradual engagement" (2008) starts with a light interaction and asks for details later: Jumpcut asked for name and email only when publishing, Geni created an account while the user built a family tree, TripIt began from a forwarded booking email [1].
- Apple's HIG: require an account only if core functionality needs one; delay sign-in as long as possible because people often abandon apps that force it; a shopping app can let people browse and ask at checkout [2].
- Anecdote: Spool (2009) reports a major retailer that replaced a Register button with Continue and made registration optional; purchasing customers rose 45%, worth an extra $15 million in month one and $300 million in year one. The retailer is unnamed and no method is given [3].
- Duolingo lets people start a lesson before signing up. Secondary reports quote its growth lead crediting a later sign-up screen with about +20% daily active users, and later refinements (a "Later" button, then a wall) with +8.2% (snippet). We could not open the primary source [4].

**Evidence: Moderate.** Platform guidance plus practitioner cases; the headline numbers are unverified anecdotes (Weak). Guest-checkout evidence is in FRM.

**Limitations.**
- Not for products where identity is the product (banking, health records, messaging) or where state cannot be kept without an account.
- Anonymous progress is lost when storage is cleared, so offer a clear way to save it [1][2]. Fewer captured emails means fewer reminders. Anonymous access invites abuse; rate-limit it.
- A late wall feels like bait and switch if the value was oversold; say why at the prompt [2]. Apple requires apps that create accounts to let people delete them [2].
- Conflicts: ONB-08 (do not stack permission asks on the sign-up moment); CHO (no forced sign-up just to see a price).

**How to measure it works.**
- Visitor-to-activated rate (ONB-02), not just visitor-to-sign-up; sign-up rate at the late prompt; D1 and D7 retention; revenue per visitor; share of anonymous users who later convert.
- Guard metrics: abuse and spam, support tickets about lost data. A/B test sign-up-first against value-first.

**Implemented by.**
- Apple HIG shopping example [2]. Jumpcut, Geni (claimed "five million profiles in five months", no conversion data) and TripIt, 2008 [1].
- Duolingo [4] and Spool's unnamed retailer [3]: both anecdotes.

**How to detect it.**
- *Applied:* the first screen shows the product or a sample; a core action works without an account; "Continue as guest" or "Skip for now"; sign-up appears after a result ("Save your progress").
- *Violated:* a login wall before any content; an email gate before showing the product; a mandatory account for a read-only feature; sign-up demanded on first launch.
- *In code:* auth guards on root routes (`requireAuth`, `if (!user) redirect('/login')`, middleware matchers covering `/`). Applied: Firebase `signInAnonymously()` with `linkWithCredential`, Supabase `signInAnonymously`.
- *Quick test:* open the product in a private window; count taps and seconds to the first meaningful action; note where an account is first demanded.

**How to implement.**
1. Define the first valuable action (ONB-02) and let anonymous users do it.
2. Store progress under an anonymous ID. At the first save, share or purchase, prompt ("Create an account to keep this") and link the anonymous data to the new account.
3. Explain the benefit on the sign-up screen; offer passkeys or social sign-in (FRM). Keep a "Later" option and re-ask at the next natural point, not on a timer.
4. A/B test and watch the guard metrics.

**Sources.**
[1] Wroblewski, L. (2008-05-05). Web form design (excerpt on gradual engagement). A List Apart. https://alistapart.com/article/signupforms
[2] Apple. Human Interface Guidelines: Managing accounts. https://developer.apple.com/design/human-interface-guidelines/managing-accounts
[3] Spool, J. M. (2009-01-14). The $300 million button. UIE (now Center Centre). https://articles.centercentre.com/three_hund_million_button/
[4] Taplytics. How Duolingo A/B tested delayed sign-ups to drive growth (quotes Gotthilf, citing First Round). https://taplytics.com/blog/duolingo-ab-test-onboarding (snippet; the page failed to load for me)

---

### ONB-02 Define activation and shorten time-to-value

**What it is.** Pick the earliest user action that predicts long-term retention (the activation milestone), measure the share of new users who reach it and how fast, and remove the steps that stand between sign-up and that action.

**Why it works.**
- Retention is shaped early, so teams need a leading indicator they can act on. Rachitsky and Timen (2022) define activation rate as users who reach the milestone divided by users who completed sign-up. A good milestone is predictive (reachers retain at least twice as well) and actionable [1].
- Their reader survey (500+ responses, self-selected) gives activation rates of mean 34% and median 25% across products, and mean 36% and median 30% for SaaS. About 6% of respondents used a time-bound definition, with a median of 10 days [1].
- Famous milestones: Facebook "7 friends in 10 days" (Chamath Palihapitiya) and Slack "2,000 messages" (Stewart Butterfield), with similar claims for Twitter (follow a set number of accounts) and Dropbox (save a first file). The 2022 post cites none of them; it calls Facebook's milestone "classic" and credits Adriel Frederick [1]. We found no primary source or dataset for any of them.

**Evidence: Weak.** Practitioner convention. The famous thresholds are unsourced and correlational, and the benchmark comes from a reader survey.

**Limitations.**
- Correlation is not causation: people who invite seven friends may already be committed. Test a nudge toward the milestone with a randomised experiment before calling it causal.
- Goodhart's law: "When a measure becomes a target, it ceases to be a good measure" (Strathern, 1997) [2]. Pushing invites or messages can create spam, forced steps and fake activity (CHO).
- One milestone rarely fits every persona; team products need a per-account definition. Time windows such as 10 days are conventions; fit them to the usage cycle.
- Shortening time-to-value must not skip required steps (consent, security); defer optional ones (ONB-01, ONB-05).

**How to measure it works.**
- Activation rate by weekly cohort; median time to activate; funnel drop-off between sign-up and the milestone.
- Retention curves for activated against non-activated users, then a randomised test of a nudge to confirm the causal effect. Guard metrics: complaints, unsubscribes, spam reports. Re-validate quarterly.

**Implemented by.**
- Facebook, Slack, Twitter and Dropbox milestones are widely repeated with no primary source (anecdotes).
- No named company data in the Lenny's Newsletter benchmark [1].

**How to detect it.**
- *Applied:* the post-sign-up screen has one primary action toward the product's core job; guidance or progress toward it; an analytics event for the milestone; steps after it are skippable.
- *Violated:* a long preference quiz and tours before any action; a dashboard with many equal options and no first action; no event for the milestone.
- *In code:* analytics calls such as `track('activated')`, `first_*` events and a `signup_completed` to `core_action` funnel; onboarding step arrays with many entries; onboarding experiment flags.
- *Quick test:* sign up as a new user with a stopwatch; count clicks and seconds until you finish the core job; list every step you could defer.

**How to implement.**
1. List three to five candidate early actions (invite, create, import, connect, finish a first task).
2. For past cohorts, compare retention of users who did and did not do each; shortlist those with about a 2x lift that you can influence [1].
3. Pick one; define activation rate and time to activate; instrument the events.
4. Cut or defer every step before it that is not required (ONB-01, ONB-03 to ONB-06).
5. A/B test a nudge to the milestone and keep it only if retention improves. Review quarterly and replace the milestone if gaming appears.

**Sources.**
[1] Rachitsky, L., & Timen, Y. (2022-10-25). What is a good activation rate. Lenny's Newsletter. https://www.lennysnewsletter.com/p/what-is-a-good-activation-rate
[2] Wikipedia. Goodhart's law (gives Strathern, M. (1997). "Improving ratings": audit in the British university system. European Review 5(3), 305-321). https://en.wikipedia.org/wiki/Goodhart%27s_law

---

### ONB-03 Teach in context rather than with up-front tutorials

**What it is.** Show help at the moment and place it is needed, triggered by what the user is doing, instead of a slide deck or tour before they have tried anything.

**Why it works.**
- NN/g's 2020 between-subjects test (70 participants, four iOS apps): reading the deck-of-cards tutorial did not improve task success (91% against 94% for those who skipped it, not significant) or speed (93.5 s against 85.2 s, not significant, and excluding the reading time). Readers rated tasks harder (4.92 against 5.49 on a 1 to 7 ease scale, p = 0.047) [1].
- NN/g argues that up-front tutorials ("push revelations") interrupt, get skipped and are forgotten because users want to start and must memorise the content; help that appears when actions signal need ("pull revelations") works better [2]. This is argument, not a study.
- Apple's HIG: onboarding should be fast and optional; teach by doing; prefer short contextual tips (TipKit) to a long flow; do not re-show a skipped tutorial automatically but keep it findable [3].
- NN/g (2014): short-term memory fades in about 20 seconds; show tips one at a time at the relevant section. Users in a tablet study did not realise an overlay was a hint and tried to tap its icons [4].

**Evidence: Moderate.** One quantitative NN/g test (2020) plus NN/g analyses and Apple guidance. The test compared a tutorial with none; it did not test contextual help against a tutorial.

**Limitations.**
- Four iOS apps and simple tasks [1]. Novel interaction paradigms (such as AR) can justify a short walkthrough [2]; complex professional tools may need training offered on demand.
- Repeated or blocking hints annoy (FBK, interruptions). Tooltips must be dismissible and keyboard reachable (A11Y).
- Conflicts: ONB-04 (an empty state already teaches), ONB-08 (do not stack permission prompts into the first-run tour).

**How to measure it works.**
- Between-subjects test of new users with and without the tutorial: task success, time, ease rating [1].
- Tutorial skip and completion rates; hint dismissal against follow-through (did the user do the hinted action in that session); adoption of hinted features; time to first key action (ONB-02); support tickets by topic.

**Implemented by.**
- Apple recommends TipKit contextual tips [3]. NN/g's review of Productive, Chase, Reflectly, Any.do, Fitplan, MindNode and other apps describes patterns, not outcomes [5].

**How to detect it.**
- *Applied:* no slide carousel before first use, or one with a visible Skip; tips anchored to controls, one at a time, dismissible; interactive practice; a Help entry to revisit.
- *Violated:* four to six swipe cards at first launch; a mandatory tour; chains of coach marks; instructions that vanish before the user can act.
- *In code:* first-run flags (`hasSeenOnboarding`, `localStorage.getItem('tour')`); libraries (`intro.js`, `shepherd.js`, `react-joyride`, `driver.js`); Android `ViewPager2` with `TabLayoutMediator` as an intro; iOS `UIPageViewController` intro. Applied: TipKit `Tip`.
- *Quick test:* fresh install; count screens before the first usable one; check each is skippable; use the app and note whether help appears at the point of need.

**How to implement.**
1. Make the UI self-explanatory first: labels (NAV-01), empty states (ONB-04).
2. Drop the up-front slide deck unless the interface is unfamiliar.
3. Add hints triggered by behaviour (first visit to a feature, hesitation): one at a time, short, dismissible, with dismissal remembered.
4. Teach by doing: low-stakes practice or sample content (ONB-06). Keep "Show tips again" in Help.
5. Test with new users with and without the hints; keep what improves success or ease.

**Sources.**
[1] Kendrick, A. (2020-03-08). Mobile tutorials: wasted effort or efficiency boost? NN/g. https://www.nngroup.com/articles/mobile-tutorials/
[2] Laubheimer, P. (2023-02-12). NN/g article on onboarding tutorials versus contextual help. https://www.nngroup.com/articles/onboarding-tutorials/
[3] Apple. Human Interface Guidelines: Onboarding. https://developer.apple.com/design/human-interface-guidelines/onboarding
[4] Harley, A. (2014-02-16). NN/g article on instructional overlays and coach marks for mobile apps. https://www.nngroup.com/articles/mobile-instructional-overlay/
[5] Kendrick, A. (2020-06-21). Mobile-app onboarding: an analysis of components and techniques. NN/g. https://www.nngroup.com/articles/mobile-app-onboarding/

---

### ONB-04 Design empty states that explain and offer the first action

**What it is.** When a list, dashboard or result set has nothing to show, say what the area is for, why it is empty, and give one clear action (or a sample) to fill it.

**Why it works.**
- NN/g (2021) gives an empty state three jobs: communicate system status (loading, error or truly empty), give learning cues, and give a direct pathway to the key task. Examples: DataDog's favorites area invites users to star favorites; Loggly offers two pathways, adding log sources or exploring with demo data [1].
- Apple's HIG: if a tab's content is unavailable, explain why instead of hiding or disabling the tab [2].
- GitHub's Primer "Blankslate" component: a heading and description of what is missing, one primary action leading to a creation flow, an optional secondary link, a welcoming tone, and meaning that does not live only in the graphic [3][4].
- Mechanism: the next step is least obvious on the screen with the least content; text plus an action replaces recall.

**Evidence: Moderate.** Guideline consensus (NN/g, Apple, GitHub); we found no experiment or outcome data. Material's empty-state page could not be read by my tool.

**Limitations.**
- First use, no results (NAV-05), error and "no permission" need different content. Do not show "No records" while data loads; use a skeleton (FBK). NN/g's example flashes that message before items appear [1].
- An illustration without text fails screen-reader and low-vision users [4]. A call to action the user cannot use (read-only role) frustrates; hide it or explain.
- Too much instruction turns the empty state into a tutorial; keep to one action (ONB-03).

**How to measure it works.**
- Call-to-action click-through (clicks divided by empty-state views); time to the first item created (ONB-02); drop-off on empty screens.
- Compare day-1 retention with and without the new empty state in an A/B test (a before/after comparison is confounded). For no-results screens, reformulation rate and exits (NAV-05).

**Implemented by.**
- GitHub Primer Blankslate [3][4]; DataDog, Microsoft Power BI and Loggly examples [1].
- GitHub's empty-repository page lists setup commands; Trello, Dropbox and Slack show first-run prompts in empty areas. These are observed patterns we could not source; no outcomes found.

**How to detect it.**
- *Applied:* empty screens carry a heading, one or two sentences, one primary button and an optional "Learn more" or "Use sample data"; loading is shown separately; a zero-result filter offers "Clear filters".
- *Violated:* a blank area; bare "No data" or "No records"; an empty table showing only headers; an empty state that flashes during loading; a button that creates nothing.
- *In code:* `items.length === 0` or `isEmpty` branches with no markup; library defaults left in place (Ant Design `Empty`, MUI DataGrid `noRowsOverlay`); components named `EmptyState`, `Blankslate`, `ZeroState`.
- *Quick test:* sign up fresh; open every top-level screen and ask "what is this, why is it empty, what do I do?"; filter a list to zero.

**How to implement.**
1. Inventory every collection screen and its empty variants (first use, no results, error, no permission).
2. First use: one sentence on what goes here and the benefit, one primary button that names the action ("Create your first project"), and an optional secondary link or sample data (ONB-06).
3. No results: echo what was searched and offer to clear filters or try alternatives (NAV-05).
4. Keep the text in HTML (decorative art gets `alt=""`); show a loading skeleton first and swap in the empty state only when the response is empty.
```html
<section class="empty"><h2>No projects yet</h2>
  <p>Projects hold your tasks and files.</p><a class="btn-primary" href="/projects/new">Create your first project</a></section>
```

**Sources.**
[1] Kaplan, K. (2021-09-19). NN/g article on designing empty states in complex applications (3 guidelines). https://www.nngroup.com/articles/empty-state-interface-design/
[2] Apple. Human Interface Guidelines: Tab bars. https://developer.apple.com/design/human-interface-guidelines/tab-bars
[3] GitHub Primer. Blankslate component. https://primer.style/product/components/blankslate/
[4] GitHub Primer. Blankslate guidelines. https://primer.style/product/components/blankslate/guidelines/

---

### ONB-05 Use setup checklists with visible progress

**What it is.** Break setup into a short list (three to seven steps) with a visible "n of m" progress indicator. Each step links to the place it is done, and steps that are genuinely complete are already ticked.

**Why it works.**
- Endowed progress: Nunes and Drèze (2006, Journal of Consumer Research 32(4)) report that giving people artificial advancement toward a goal raises persistence. Their example turns an eight-step task into a ten-step task with two steps already credited, which raises the likelihood of finishing and shortens the time to finish. The effect depends on perceived progress, not on avoiding wasted credit [1]. We read the abstract only; we could not verify the car-wash completion rates.
- Related effects: goal gradient (effort rises near a goal; PER) and the Zeigarnik effect, which is contested (MYTH).
- NN/g notes that progress indicators that start fast and end slow reduce drop-off in surveys [2].

**Evidence: Moderate.** One published field experiment on loyalty cards (2006), indirect for software. We found no peer-reviewed test of onboarding checklists; vendor claims are unsourced.

**Limitations.**
- Credit must be real. A bar that starts at 60% for no reason is deceptive (CHO); count steps that truly happened (account created, email verified).
- Long or mandatory checklists feel like homework; make them dismissible and resumable. Ticking items is a proxy; optimise activation (ONB-02), not tick-count (Goodhart).
- Profile-completeness meters can push people to share more data than they need (CHO).
- The original paper reports moderators (why the head start is given; the currency of progress) [1]. Items a user cannot act on (needs an admin) frustrate.

**How to measure it works.**
- Per-step completion and drop-off; checklist completion rate; time to complete; dismissal rate.
- A/B test with and without the checklist on activation (ONB-02) and D7 retention; guard metric: support tickets per step.

**Implemented by.**
- LinkedIn (profile strength meter), Shopify (setup guide), Asana and Notion (getting-started tasks) are commonly cited. We did not open their pages and found no published outcomes, so treat them as patterns, not evidence.
- The research source is the car-wash loyalty-card experiment [1].

**How to detect it.**
- *Applied:* a collapsible "Get started: 2 of 5 done" card with real steps already ticked, each item linking to the exact screen; it can be dismissed and goes away when done.
- *Violated:* a checklist of 15 or more items; non-actions such as "Read the docs"; progress stuck at 0%; no dismiss control.
- *In code:* components named `Checklist`, `GettingStarted`, `SetupGuide`, `OnboardingProgress`; `<progress value max>` or `role="progressbar"` with `aria-valuenow`; stored fields like `onboarding_steps` or `completed_at`.
- *Quick test:* new account: is there a checklist; does progress start above zero from a real step; does each item deep-link to the task; can you dismiss and resume?

**How to implement.**
1. Choose three to five steps that lead to the activation milestone (ONB-02), not feature tours.
2. Pre-credit real completed steps so progress starts above zero. Order the rest by value, then effort.
3. Make each item one action with a deep link and sensible defaults. Show "n of m" and a bar that updates at once; celebrate briefly and respect reduced motion (A11Y).
4. Allow dismissing, collapsing and resuming; hide the card when done. A/B test it.
```html
<section aria-labelledby="gs"><h2 id="gs">Get started: 2 of 5 done</h2>
  <progress value="2" max="5" aria-labelledby="gs"></progress></section>
```

**Sources.**
[1] Nunes, J. C., & Drèze, X. (2006). The endowed progress effect: how artificial advancement increases effort. Journal of Consumer Research 32(4), 504-512. https://academic.oup.com/jcr/article/32/4/504/1789867 (abstract only)
[2] Sherwin, K. (2014-10-26). NN/g article on progress indicators. https://www.nngroup.com/articles/progress-indicators/

---

### ONB-06 Offer templates and sample content instead of a blank canvas

**What it is.** Offer a starting point (templates, a sample project, demo data) next to a "Blank" option, so people see a working example instead of an empty canvas.

**Why it works.**
- Recognising a good example is easier than producing one from nothing (recognition over recall; PER). The pattern is near-universal: Notion's gallery lists 30,000+ templates from 22,932 creators (page read 2026-10-31) [1]. Canva, Google Docs and Figma Community run similar galleries; we could not open their pages.
- NN/g's empty-state article shows demo data as one of two ways out of an empty screen [2].
- Research on design examples cuts both ways: shown examples help, but people can copy an example's flaws ("design fixation", Jansson and Smith, 1991) [3].

**Evidence: Weak.** Wide adoption, but we found no controlled study or published outcome (activation, retention) for templates in these products. The Notion page makes no outcome claims [1].

**Limitations.**
- Fixation and sameness: templates can steer everyone to similar output (inference from [3]).
- Sample content that cannot be removed pollutes real data; offer one-click removal (ERR).
- Many templates add choice cost (MYTH debates choice overload); show a short curated set first.
- A template that does not match the user's job adds steps; keep "Blank" equally easy. Community templates need quality control and clear licences.

**How to measure it works.**
- Share of new items started from a template; activation (ONB-02) and D7 retention by start type, via A/B test (users who pick templates differ from those who do not).
- Time to first published or shared item; sample-data deletion rate; template searches with no result (gaps).

**Implemented by.**
- Notion template gallery (creators can be featured and paid; no outcomes published) [1]. Loggly's demo-data pathway [2].
- Canva, Google Docs template gallery and Figma Community exist, but we did not verify any claims about them.

**How to detect it.**
- *Applied:* a "New" dialog that shows templates with previews and an equally visible Blank option; a sample project in a fresh workspace; a "Use sample data" toggle; sample content labelled as such.
- *Violated:* a blank page with a cursor only; templates buried in menus; sample content indistinguishable from real data.
- *In code:* a `templates/` directory or `/templates` route; `createFromTemplate`, `template_id`; seed code for new tenants (`seedSampleData`, `demo_data`); flags such as `is_sample`.
- *Quick test:* create a new item: are templates offered in the same dialog; is Blank equally visible; can you delete all sample content in one action?

**How to implement.**
1. Find the three to five most common first jobs (from the activation analysis, ONB-02).
2. Build realistic templates with preview thumbnails and show them in the New dialog next to Blank.
3. Mark sample content clearly and provide one-click "Remove sample data".
4. If you ask the user's goal at sign-up (skippable), recommend matching templates. Let users save their own work as templates.
5. A/B test start type against activation.

**Sources.**
[1] Notion. Template gallery. https://www.notion.com/templates (read 2026-10-31)
[2] Kaplan, K. (2021-09-19). NN/g article on designing empty states in complex applications. https://www.nngroup.com/articles/empty-state-interface-design/
[3] Jansson, D. G., & Smith, S. M. (1991). Design fixation. Design Studies 12(1), 3-11 (not checked against the source; not opened)

---

### ONB-07 Use habit features (streaks, reminders) only where the habit serves the user

**What it is.** Use streaks, reminders and similar prompts only when regular use is something the user wants, keep users in control of them, and avoid shame and pressure.

**Why it works.**
- The Fogg Behavior Model says a behaviour happens when motivation, ability and a prompt come together at the same moment [1]. My reading: a reminder is a prompt and a streak adds motivation.
- Duolingo's published numbers (2022): learners with a 7-day streak are 3.6 times more likely to complete their course (correlational); a new streak animation raised 7-day retention of brand-new learners by 1.7%; allowing up to two Streak Freezes raised daily active learners by 0.38% (relative) [2].
- Mazal (former Duolingo CPO, 2023): daily active users grew 4.5x in four years, current-user retention rose 21% over the same period, daily churn among the best users fell by over 40%, and the share of daily active users on 7+ day streaks almost tripled to over half. The post gives no effect size for Streak Freeze; leaderboards raised learning time 17% (not labelled an A/B test) [3]. We found no churn figure for Streak Freeze and no widget result in either post.
- A literature review of empirical gamification studies (Hamari et al., 2014) concluded that effects are positive but depend heavily on context and users [4] (abstract not opened; summary not checked against the source).

**Evidence: Mixed.** Company-reported effects are small and mostly correlational; the wider literature depends on context; we found no controlled study of streak harm or benefit.

**Limitations.**
- Selection bias: engaged users build streaks; streaks do not necessarily cause engagement [3].
- Fits products where repetition is the user's goal (language, fitness, meditation); poor fit for utilities and banking.
- Loss framing creates anxiety and rewards quantity over quality. Snapstreaks (a count of consecutive days two friends exchange Snaps; it ends when a day is missed, with an hourglass warning before expiry) are the usual cautionary case [5]. Concerns come from advocates and regulators (leads we did not open: UK ICO Children's Code, EU Parliament 2023 addictive-design resolution).
- Reminder volume drives opt-outs (FBK, interruptions); guilt copy and paid streak rescues are CHO issues. Avoid pressure mechanics for children.

**How to measure it works.**
- Outcome first: goal attainment (lessons finished, workouts done), not opens. Then D7 and D30 retention, DAU/MAU, notification opt-out and uninstall rates, reminder-to-action rate.
- Survival analysis of streak breaks (churn or return). Guard metrics: user-reported pressure (survey), complaints. Expect small effects (+0.38% to +1.7% in [2]).

**Implemented by.**
- Duolingo: streaks, Streak Freeze (up to two), streak animations; effects above [2][3].
- Snapchat: Snapstreaks (cautionary) [5]. We did not verify fitness-app examples.

**How to detect it.**
- *Applied:* the user sets reminder time and frequency; reminders and streak display can be switched off in settings; a forgiveness mechanism (rest day, freeze); encouraging copy; the streak counts the user's own stated goal.
- *Violated:* guilt copy ("You'll lose your 100-day streak!"); no off switch or a buried one; escalating reminder frequency; streaks on actions unrelated to the goal.
- *In code:* `streak`, `streakCount`, `lastActiveDate`, `freeze`; scheduled notifications (`UNCalendarNotificationTrigger`, `WorkManager`, `AlarmManager`); Android `NotificationChannel` per reminder type; settings toggles for reminders.
- *Quick test:* find the setting that stops reminders and count taps; read the last three notification texts for loss or shame language; skip a day and see what the app says.

**How to implement.**
1. Ask whether the habit serves a goal the user stated. If not, do not add it.
2. Use the lightest prompt: a reminder at a time the user chooses, with frequency and mute controls that honour OS notification settings.
3. Add forgiveness (freeze, rest day) and positive copy; never charge to hide or rescue a loss without disclosure (CHO).
4. Track goal attainment and wellbeing guard metrics, not just opens. Skip pressure mechanics for minors.

**Sources.**
[1] Fogg, B. J. Fogg Behavior Model (B = MAP). https://behaviormodel.org/ (the 2009 paper by Fogg is the formal source; not opened)
[2] Mansur, O. (2022-01-31). The habit-building research behind your Duolingo streak. Duolingo blog. https://blog.duolingo.com/how-duolingo-streak-builds-habit/
[3] Mazal, J. (2023-02-28). How Duolingo reignited user growth. Lenny's Newsletter. https://www.lennysnewsletter.com/p/how-duolingo-reignited-user-growth
[4] Hamari, J., Koivisto, J., & Sarsa, H. (2014). Does gamification work? HICSS 2014. https://doi.org/10.1109/HICSS.2014.377 (DOI resolves to IEEE Xplore; abstract not read)
[5] Wikipedia. Snapchat (describes how Snapstreaks work; no criticism or studies on that page). https://en.wikipedia.org/wiki/Snapchat

---

### ONB-08 Ask for permissions in context, with a reason

**What it is.** Ask for a permission (notifications, location, camera, contacts, microphone) when the user triggers the feature that needs it, with a specific reason, and keep the app working if they decline.

**Why it works.**
- Context-free prompts are mostly refused. Chrome desktop telemetry (web.dev, updated 2024-06-17): 77% of permission prompts were shown without a signal of user intent, and only 12% of those were allowed; after a user interaction the allow rate rose to 30% [1]. These are different contexts, not a controlled test.
- Cluster (Mulligan, TechCrunch, 2014-04-04): push opt-in was under 40% when asked at launch without explanation and 66% after the benefit was explained; photo access was 67% when asked right after creating a Cluster and 89% after the user tapped the camera icon and Choose Photos. Company tests; no sample sizes [2].
- Apple's HIG: ask when the feature needs it; do not ask at launch unless the app cannot function; purpose strings should be one specific sentence [3]. Onboarding guidance repeats this [5].
- Android: ask in context, show a rationale with a "no thanks" option, treat two denials as permanent, keep the app usable, and do not nag or push people to Settings [4].

**Evidence: Moderate.** Consensus across Apple, Google and Chrome guidance plus browser telemetry; the cleanest grant-rate comparison is company-reported.

**Limitations.**
- A pre-permission screen cannot replace a good reason. Apple bans lookalike screens, incentives, an "Allow" label on the pre-alert button, and a cancel that prevents the system alert [3]; Android says to include "no thanks" [4]. Follow each platform's rule.
- If the app cannot work without the permission (a navigation app and location), asking early is fine [3][5].
- On iOS the system alert normally appears once per permission, and later changes happen in Settings (general platform behaviour, not from the page we read).
- Stacking several prompts causes fatigue; ask one at a time and never during account creation (ONB-01). Consent that is coerced is a CHO issue.

**How to measure it works.**
- System grant rate (grants divided by system prompts shown); pre-prompt accept rate; share of permanent denials (`Notification.permission`, iOS `authorizationStatus`, Android permission flags).
- Feature use after grant; later notification opt-outs and uninstalls. A/B test request-at-launch against in-context with retention as the guard.

**Implemented by.**
- Cluster (2014) [2]. Chrome's guidance: prompt after a user gesture, offer alternatives such as typing an address [1].
- Apple and Android platform guidance [3][4].

**How to detect it.**
- *Applied:* a button ("Use my location", "Turn on reminders") triggers the request; a short reason precedes or sits in the purpose string; one permission at a time; the feature degrades gracefully after refusal.
- *Violated:* several system dialogs on first launch; a prompt on page load; vague purpose strings ("needed for a better experience"); pre-alert buttons labelled "Allow"; the app blocks after denial; repeated re-asking.
- *In code:* iOS `Info.plist` keys (`NSCameraUsageDescription`, `NSLocationWhenInUseUsageDescription`, `NSContactsUsageDescription`) and `requestAuthorization` calls inside `application(_:didFinishLaunchingWithOptions:)` (violation) rather than a button handler; Android `requestPermissions` or `RequestPermission` in `onCreate`, `shouldShowRequestPermissionRationale`; web `Notification.requestPermission()`, `navigator.geolocation.getCurrentPosition` or `getUserMedia` on load; `navigator.permissions.query`.
- *Quick test:* fresh install, cold launch: count system dialogs before the first value; deny each and check the app still works; read each purpose string aloud.

**How to implement.**
1. List each permission and the exact feature that needs it.
2. Trigger the request from that feature's button, never at launch; on the web only after a user gesture [1][3][4].
3. Write purpose strings as one specific, active sentence [3]. If the reason is not obvious, show a short pre-prompt with a neutral "Continue" (iOS) or a "Not now" option (Android) [3][4].
4. On denial, explain what is unavailable where the user tries the feature; keep the rest working; do not re-ask repeatedly [4].
```kotlin
val askCamera = registerForActivityResult(ActivityResultContracts.RequestPermission()) { ok -> if (ok) startScan() else showManualEntry() }
scanButton.setOnClickListener { askCamera.launch(Manifest.permission.CAMERA) }
```

**Sources.**
[1] web.dev. Web permissions best practices (last updated 2024-06-17). https://web.dev/articles/permissions-best-practices
[2] Mulligan, B. (2014-04-04). The right way to ask users for iOS permissions. TechCrunch. https://techcrunch.com/2014/04/04/the-right-way-to-ask-users-for-ios-permissions/
[3] Apple. Human Interface Guidelines: Privacy. https://developer.apple.com/design/human-interface-guidelines/privacy
[4] Android Developers. Request runtime permissions. https://developer.android.com/training/permissions/requesting
[5] Apple. Human Interface Guidelines: Onboarding. https://developer.apple.com/design/human-interface-guidelines/onboarding
