# Feedback, system status and performance (FBK)

Covers how an interface tells people what it is doing and how fast it does it: response-time limits, progress indicators, skeleton screens, optimistic updates, Core Web Vitals, layout stability, outcome messages and interruptions. Load it when auditing loading states, async actions, perceived speed, toasts, notifications or page-speed work. FBK-05 grades each famous speed-and-revenue statistic separately. Most are Weak, so check the grade before quoting a number.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| FBK-01 | Acknowledge every action at once | Strong | any interactive UI: web, mobile, desktop |
| FBK-02 | Show progress for longer waits, with a way to cancel | Moderate | operations over about 2 s: uploads, exports, installs, background jobs |
| FBK-03 | Use skeleton screens where the layout is predictable | Mixed | full-page, list and card loads of about 1 to 10 s |
| FBK-04 | Update the UI optimistically for low-risk actions | Weak | reversible actions that rarely fail: like, toggle, add, reorder |
| FBK-05 | Meet Core Web Vitals and treat speed as a feature | Moderate | websites and web apps; native apps use the same ideas |
| FBK-06 | Keep the layout stable while it loads | Moderate | pages with images, ads, web fonts, banners or async content |
| FBK-07 | Confirm outcomes with non-blocking feedback that stays long enough to read | Moderate | save, send, delete and sync actions in any UI |
| FBK-08 | Interrupt only when it matters | Moderate | push, email, in-app alerts, modals, badges |

---

### FBK-01 Acknowledge every action at once

**What it is.** Every tap, click or key press produces a visible change within about 0.1 s: a pressed state, a new label, a spinner, or the result itself. The interface never looks idle while it works.

**Why it works.**
- Perception: a reply within about 0.1 s feels instant and caused by the user. About 1 s keeps the flow of thought. About 10 s is the limit of attention. Nielsen set out these limits in 1993, citing Miller (1968) and Card, Robertson and Mackinlay (1991), and said in 2014 that they still hold for web apps [1][2][3].
- Heuristic 1: when people can see system status, they learn what their last action did and pick the next step [4].
- Field evidence: Google gave one group of search users extra server delay and kept a control group. Daily searches per user fell 0.20% at +100 ms (4 weeks), 0.29% at +200 ms and 0.59% at +400 ms (6 weeks). The loss grew with exposure (0.74% in the second half of the 400 ms test) and was still 0.21% in the five weeks after the delay was removed [5].
- Google's RAIL guidance asked for feedback on any action slower than 50 ms and for input-to-result within 100 ms [6]. INP now measures this: good is 200 ms or less at the 75th percentile [7].
- The "Doherty threshold" (400 ms) comes from IBM terminal studies. Thadhani (1981) and Doherty and Thadhani (1982) tied sub-second response to higher programmer productivity (snippet) [8][9]. We could not open the 1982 report, so we could not confirm that it states 400 ms. Kent Beck notes that no research puts a break at exactly 400 ms [10]. Laws of UX cites "IBM Systems Journal 1982" [11]. The 1982 document we found is an IBM report (form GE20-0752-00) [9], so that citation looks wrong.

**Evidence: Strong.** Response-time psychology since 1968 (58 years old) plus a large controlled field experiment (Google, 2009, 17 years old). The 0.1 / 1 / 10 s limits are bands. The 400 ms figure on its own is Weak.

**Limitations.**
- Miller (1968) gave limits by task type and framed the question as "response time to what?". A later critic asked for experimental data (snippet) [2]. Treat the limits as bands, not cliffs.
- Feedback does not replace speed. Google's losses came from real delay, not from missing feedback (see FBK-05).
- Under about 1 s a spinner or skeleton can flicker and feel worse than a small inline change [12].
- An instant "success" for an action that can fail misleads. Show a pending state, or use FBK-04 with ERR-02.
- We found no test of artificial delays added to look thorough. Do not add them without testing.

**How to measure it works.**
- Leading: INP at the 75th percentile (CrUX, or `web-vitals` in your own RUM), target 200 ms or less; long-task count; frames from input to first visible change in a 60 fps screen recording (6 frames is 100 ms).
- Behaviour: double-submit and duplicate-request rate, rage clicks per session, tickets about duplicates. Expect all to fall.
- Lagging: task completion and return rate. A latency-injection test like Google's prices delay for your own product [5].

**Implemented by.**
- Google Search (2009): ran and published the delay experiments [5]. Google's Chrome team later published RAIL and made INP a Core Web Vital in 2024 [6][7].
- Instagram (2011): started the photo upload before the user tapped Share, so most of the work was done by the time they tapped (see FBK-04).
- Gmail: shows "Message sent" with Undo and View message right after Send (see FBK-07).

**How to detect it.**
- *Applied:* buttons show a pressed state on tap and a changed label or spinner within 100 ms; submit controls lock during the request; a pending item or the result appears in place; navigation shows a cue (top bar, skeleton) at once.
- *Violated:* click, then nothing for a second or more, then the page jumps; primary buttons stay clickable during a request and people click twice; frozen UI from long main-thread tasks; no hover, active or focus styles.
- *In code:* `:active`, `:focus-visible`; `aria-busy="true"`; `disabled={isPending}`, `useTransition`, `useFormStatus`; handlers that `await` before changing UI state; `web-vitals` `onINP`; `PerformanceObserver` with `type: 'event'`. Native: Android `StrictMode` violations or ANRs from click handlers that block the main thread; iOS `UIButton.Configuration.showsActivityIndicator`.
- *Quick test:* throttle the network (a DevTools custom profile with about 2 s latency), click every primary control once and record the screen at 60 fps. Any control with more than 6 frames before a visible change fails. Then double-click each submit button and look for duplicates.

**How to implement.**
1. Style `:active` and `:focus-visible` for every interactive element (CSS only, no JS).
2. In every async handler, change the UI in the same tick, before the first `await`: set a pending flag, change the label ("Saving..."), show an inline spinner.
3. Guard against double submit: ignore repeat clicks while pending (use `aria-disabled="true"` plus a guard so keyboard focus stays on the button) and send an idempotency key to the server.
4. Pick the indicator by expected wait: under 1 s a state change only; 1 to 10 s spinner or skeleton (FBK-03); over 10 s progress and Cancel (FBK-02) [1].
5. Keep the main thread free: split long tasks (`scheduler.yield()` or chunked `setTimeout`), move heavy work to a Web Worker, defer third-party scripts.
6. Report INP from the field with `web-vitals` and alert at 200 ms.
```js
btn.addEventListener('click', async () => {
  if (btn.getAttribute('aria-disabled') === 'true') return;
  btn.setAttribute('aria-disabled', 'true'); btn.textContent = 'Saving...'; // before the await
  try { await save(); } finally { btn.removeAttribute('aria-disabled'); btn.textContent = 'Save'; }
});
```

**Sources.**
[1] Nielsen, J. (1993, updated 2014). Response Times: The 3 Important Limits. Nielsen Norman Group. https://www.nngroup.com/articles/response-times-3-important-limits/
[2] Miller, R. B. (1968). Response time in man-computer conversational transactions. AFIPS Fall Joint Computer Conference, pp. 267-277. https://doi.org/10.1145/1476589.1476628 (bibliographic details and abstract line seen in search results; paper not read)
[3] Card, S. K., Robertson, G. G., Mackinlay, J. D. (1991). The information visualizer, an information workspace. CHI '91, pp. 181-186. https://dblp1.uni-trier.de/rec/conf/chi/CardRM91.html (cited by Nielsen [1] for the limits; we did not read the paper)
[4] Nielsen, J. (1994, reviewed 2024). 10 Usability Heuristics for User Interface Design. NN/g. https://www.nngroup.com/articles/ten-usability-heuristics/
[5] Brutlag, J. (2009). Speed Matters for Google Web Search. Google, 22 June 2009. https://services.google.com/fh/files/blogs/google_delayexp.pdf
[6] Google. Measure performance with the RAIL model. web.dev. https://web.dev/articles/rail
[7] Google. Interaction to Next Paint (INP). web.dev. https://web.dev/articles/inp
[8] Thadhani, A. J. (1981). Interactive user productivity. IBM Systems Journal 20(4), 407-423. https://doi.org/10.1147/sj.204.0407 (snippet)
[9] Doherty, W. J., Thadhani, A. J. (1982). The Economic Value of Rapid Response Time. IBM report GE20-0752-00. https://www.vm.ibm.com/devpages/jelliott/evrrt1.html (found in search results; page would not open because of a certificate error)
[10] Beck, K. The Precious Eyeblink. https://newsletter.kentbeck.com/p/the-precious-eyeblink
[11] Laws of UX. Doherty Threshold. https://lawsofux.com/doherty-threshold/
[12] Tankala, S. (2023). Skeleton Screens 101. NN/g. https://www.nngroup.com/articles/skeleton-screens/

---

### FBK-02 Show progress for longer waits, with a way to cancel

**What it is.** When an operation takes more than a few seconds, show that work is under way and how far along it is (percent, step, item count or time left). Past about 10 s, also show a clear way to stop it.

**Why it works.**
- Nielsen's guidance: for waits of about 2 to 10 s a busy cursor or small counter is enough, and a full percent-done bar can distract. Above about 10 s use a percent-done indicator. The 2014 update adds a clearly marked way to interrupt [1].
- Myers (CHI '85) tested percent-done indicators. People preferred the system that had them and kept preferring an inaccurate bar to none (snippet). One perceived-time effect was not statistically significant (snippet), so the case rests on preference and reduced uncertainty, not on proven shorter perceived time [2].
- Bar behaviour changes perceived duration. Harrison et al. (UIST '07) had people compare bars of equal real length. A secondary summary says stalls early in a run were tolerated more than stalls near the end, and a bar that starts slowly and speeds up felt best (snippet) [3].
- Harrison, Yeo and Hudson (CHI '10): ribbing that moved backwards and slowed down cut perceived duration by about 11% against a plain bar in the final experiment [4].
- Progress updates count as status messages that assistive technology must be able to announce without moving focus [5].

**Evidence: Moderate.** A 41-year-old preference study, two lab studies (2007, 2010) with modest effects, and consistent practitioner guidance. Required: WCAG 2.2 SC 4.1.3 (AA) for exposing progress to assistive technology.

**Limitations.**
- Perceived-time effects are small (about 11% at best) and come from short lab waits. They do not rescue a slow process.
- A bar that stalls, jumps back or sits at 99% is worse than an honest indeterminate indicator. When the total is unknown, show steps or counts ("3 of 12 files") instead of an invented percent (design judgement).
- For waits under about 2 s a bar adds noise [1].
- Cancel must be real: stop the work, clean up partial results, keep what is safe to keep (ERR-05, ERR-06).
- Looping or moving indicators fall under WCAG 2.2 SC 2.2.2 (A) when they run over 5 s beside other content. A loader that is the only content is exempt [6].

**How to measure it works.**
- Leading: wait-rating question ("How long did that feel?", 5-point) and estimated-versus-actual duration in moderated tests; cancel and retry rates.
- Lagging: abandonment during the operation, repeat attempts, support contacts about "stuck" uploads, completion rate of long tasks.
- A/B: spinner versus determinate progress on one long task; compare abandonment.

**Implemented by.**
- No company outcome data found. Percent-done indicators with cancel are standard in OS file copy, browser downloads and cloud-storage upload panels (anecdotal; not individually checked).
- Harrison's 2010 paper reports that its best design beat the plain solid-colour bar, and bars in modern interfaces including Mac OS X, on perceived duration [4].

**How to detect it.**
- *Applied:* determinate bar or "x of y" counter for uploads, exports, installs and imports; remaining-time estimate; Cancel visible after about 10 s; progress survives navigation; a completion message follows (FBK-07).
- *Violated:* endless spinner on an upload or export; bar stuck at 99% or restarting; full-screen blocker with no Cancel; "Please wait" with no sign of life; long job that cannot be left and resumed.
- *In code:* `<progress`, `role="progressbar"`, `aria-valuenow`, `aria-valuetext`; `xhr.upload.onprogress`, `ProgressEvent`; `fetch(..., { signal })` with `AbortController`; Material `LinearProgressIndicator`; SwiftUI `ProgressView(value:)`; Android `ProgressBar` with `isIndeterminate`; a Cancel handler that calls `abort()`.
- *Quick test:* throttle to Slow 3G and start the slowest task (upload, export, report). Within 2 s, is there activity? After 10 s, is there a progress measure and a Cancel? Press Cancel: does the work stop and the UI recover?

**How to implement.**
1. Choose by expected wait: under 1 s only the pressed state; 1 to 10 s spinner or skeleton (FBK-03); over 10 s or known size, determinate indicator plus Cancel [1].
2. Drive the bar with real signals: bytes sent, items processed, job status from polling or server-sent events. If none exist, show stages or counts.
3. Never move the bar backwards. Avoid long stalls at the end. Show a range for unstable estimates ("about 1 to 2 min").
4. Wire Cancel to `AbortController` on the client and a cancel route on the server. Ask for confirmation only if cancelling destroys significant work (ERR-03).
5. For jobs over about 30 s, let people leave and notify them when done (FBK-08) (design judgement).
6. Markup: `<progress value="40" max="100">` with a label. Announce milestones politely through a `role="status"` region, not every percent [5].

**Sources.**
[1] Nielsen, J. (1993, updated 2014). Response Times: The 3 Important Limits. NN/g. https://www.nngroup.com/articles/response-times-3-important-limits/
[2] Myers, B. A. (1985). The importance of percent-done progress indicators for computer-human interfaces. CHI '85, pp. 11-17. https://dblp.uni-trier.de/rec/conf/chi/Myers85.html (details from search snippets; paper not read)
[3] Harrison, C., Amento, B., Kuznetsov, S., Bell, R. (2007). Rethinking the progress bar. UIST '07, pp. 115-118. https://www.chrisharrison.net/index.php/Research/ProgressBars (project page; results from secondary summaries, e.g. https://www.osnews.com/story/19430/rethinking-the-progress-bar/) (snippet)
[4] Harrison, C., Yeo, Z., Hudson, S. E. (2010). Faster progress bars: manipulating perceived duration with visual augmentations. CHI '10, pp. 1545-1548. https://doi.org/10.1145/1753326.1753556 ; abstract mirror: https://www.sciweavers.org/node/59788
[5] W3C. Understanding SC 4.1.3 Status Messages (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
[6] W3C. Understanding SC 2.2.2 Pause, Stop, Hide (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html

---

### FBK-03 Use skeleton screens where the layout is predictable

**What it is.** While content loads, show grey blocks in the shape of the final layout (image, title, text lines, cards) instead of a blank page or a spinner. Real content replaces the blocks in place.

**Why it works.**
- The argument (the evidence splits, see below): a spinner points attention at the clock; a skeleton shows structure and implies progress. Wroblewski (17 September 2013) removed most spinners from the Polar app this way after users complained it felt slow. The post reports no measured effect [1].
- For: Mejtoft, Långström and Söderström (ECCE 2018): users rated a fictional news site with skeletons higher than the spinner version on perceived speed and ease of navigation (abstract; snippet) [2]. Costa and Belém (IHC 2025 poster): 21 participants, six loading styles, fixed 5 s wait. Skeleton did best (48% judged the wait fast); a blank page did worst (52.4% judged it slow or very slow); looping indicators beat determinate ones; combining styles did not help [3].
- Against: Viget (19 October 2017) showed 136 people an animated GIF of equal length: spinner (39), skeleton (39) or blank screen (58). Skeleton had the longest perceived wait (2.82 s, against 2.41 s spinner and 2.29 s blank) and the fewest saying it loaded quickly (59%, against 74% and 66%). Viget suggests novelty, unfamiliarity, or benefit only at very short waits [4].
- Practitioner guidance (NN/g, 4 June 2023): use for full-page loads under 10 s; spinners for single modules; a progress bar above 10 s; neither under 1 s; avoid frame-only skeletons [5].

**Evidence: Mixed.** Three comparisons (2017, 2018, 2025) disagree, and the two whose size we could check are small (136 and 21 people). The original claim (2013) is an observation, not a measurement.

**Limitations.**
- The studies we could check use simulated loads (GIFs, mock sites). The effect may depend on novelty and on how long the wait is.
- A skeleton does not fix a slow load. After about 10 s switch to progress or an error [5].
- A placeholder that does not match the final layout disorients people and shifts content on swap (see FBK-06). Variable content (comments, search results) is hard to mirror.
- Shimmer can distract. WCAG 2.2 SC 2.2.2 (A) wants a pause, stop or hide control for animation that starts automatically, runs over 5 s and sits beside other content, unless essential. A loader that is the only content is exempt; shimmer next to live page chrome is a grey area [6].
- Not for uploads, exports or processing: use progress with Cancel (FBK-02) [5].

**How to measure it works.**
- Perceived wait: ask "How long did the page take?" and "It loaded quickly" (Likert) in a between-subjects test, as Viget did [4].
- Leading: LCP, CLS (must not get worse), time to first content.
- Lagging: bounce during load, task start rate.

**Implemented by.**
- Polar (2013): replaced most spinners with blank-page placeholders [1]. No metrics published.
- Medium and LinkedIn are named as skeleton users in the 2025 poster [3]. No outcome data for either.

**How to detect it.**
- *Applied:* grey placeholders with the same sizes as the final elements; no jump when content arrives; fast loads show no flash; an error state exists if loading fails.
- *Violated:* blank white page during load; centred spinner for a full page; placeholders that do not match the layout; endless shimmer after a failed request; a skeleton flashing for a 200 ms response.
- *In code:* `Skeleton` components (MUI `<Skeleton>`, shadcn/ui, `react-loading-skeleton`), Tailwind `animate-pulse`, `@keyframes shimmer`, Bootstrap `.placeholder`, Next.js `loading.js` / `loading.tsx`, `<Suspense fallback=`, SwiftUI `.redacted(reason: .placeholder)`, Android Shimmer; `aria-busy="true"`; `prefers-reduced-motion`.
- *Quick test:* throttle to Slow 4G and hard-reload. Take screenshots at 0.5, 1 and 3 s. Compare placeholder geometry with the loaded page: any visible shift? Then enable "reduce motion" and check the shimmer stops.

**How to implement.**
1. Use skeletons only for full-page, list or card loads expected to take 1 to 10 s with a known layout. Under 1 s show nothing new or keep the old content. Over 10 s add progress [5].
2. Render the placeholder from the same layout component with fixed heights and aspect ratios so the swap causes no shift (FBK-06).
3. Replace blocks in place and show sections as they arrive.
4. Add a timeout path: after about 10 s show progress or a message, and an error state with Retry (ERR-04).
5. Accessibility: `aria-busy="true"` on the loading region and one visually hidden `role="status"` "Loading" message, not one per block. Turn shimmer off under `prefers-reduced-motion` and stop animating after about 5 s.
```css
.skeleton { background: #e5e7eb; border-radius: 4px; }
@media (prefers-reduced-motion: no-preference) { .skeleton { animation: pulse 1.6s ease-in-out infinite; } }
@keyframes pulse { 50% { opacity: .5; } }
```

**Sources.**
[1] Wroblewski, L. (2013, 17 Sep). Mobile Design Details: Avoid The Spinner. LukeW. https://www.lukew.com/ff/entry.asp?1797
[2] Mejtoft, T., Långström, S., Söderström, U. (2018). The effect of skeleton screens: users' perception of speed and ease of navigation. 36th European Conference on Cognitive Ergonomics (ECCE 2018). https://doi.org/10.1145/3232078.3232086 (abstract via search snippet; paper not read)
[3] Costa, A. R. S. F., Belém, F. C. (2025). A Percepção do Tempo de Espera em Aplicações Digitais: Um Estudo Comparativo de Estratégias de Carregamento. IHC 2025 (posters and demos), Belo Horizonte. https://sol.sbc.org.br/index.php/ihc_estendido/article/download/37767/37549
[4] Viget (2017, 19 Oct). A Bone to Pick with Skeleton Screens. https://www.viget.com/articles/a-bone-to-pick-with-skeleton-screens
[5] Tankala, S. (2023, 4 Jun). Skeleton Screens 101. NN/g. https://www.nngroup.com/articles/skeleton-screens/
[6] W3C. Understanding SC 2.2.2 Pause, Stop, Hide (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html

---

### FBK-04 Update the UI optimistically for low-risk actions

**What it is.** Show the expected result of an action at once (the like count goes up, the new item appears, the toggle flips) and confirm with the server in the background. If the server refuses, roll back and say so.

**Why it works.**
- It takes the network round trip out of the visible wait, so the 0.1 s and 1 s limits (FBK-01) hold even on slow links.
- Instagram (Mike Krieger, Warm Gun conference, December 2011) began uploading a photo as soon as the user picked a filter and moved to the share screen, then attached the caption and other details afterwards. Most of the work was done by the time they tapped Share. Krieger said it was worth it even if the data is thrown away on cancel [1].
- React ships a primitive for this. `useOptimistic` shows the optimistic value only while an Action is pending, then renders the real value. If the Action throws, the UI returns to the previous state [2].
- Data libraries document the pattern with rollback: TanStack Query (`onMutate`, `setQueryData`, `onError` restore, `onSettled` refetch) [3] and SWR (`optimisticData`, `rollbackOnError` on by default) [4].

**Evidence: Weak.** Company practice (2011, 15 years old) and library documentation. We found no controlled study comparing optimistic and pessimistic updates, and no published failure-rate threshold. The benefit follows from the response-time evidence in FBK-01.

**Limitations.**
- Do not use it for payments, bookings, legal commitments, irreversible deletes, or actions with effects on other people (sending a message). Use a pending state or a confirmation (ERR-03; WCAG 3.3.4 for financial and legal pages).
- Failure needs a visible message, a retry, and the user's input kept (FBK-07, ERR-05). A silent rollback looks like a bug.
- Race conditions: cancel in-flight refetches before writing the optimistic value [3]; use a reducer when the base state can change during the wait [2].
- Showing "Sent" before a message is sent is misleading. Show a pending style (dimmed, "Sending") until confirmed.
- Offline use needs a queue and sync, not just a flag.

**How to measure it works.**
- Leading: time from input to UI change (target under 100 ms); rollback rate per action (if it climbs, stop being optimistic for that action; set the threshold from your data).
- Lagging: task completion time, duplicate-action rate, "it didn't save" tickets.
- A/B: optimistic versus wait-for-server on one toggle or list action; compare completion time and error reports.

**Implemented by.**
- Instagram (2011): early upload plus background processing [1]. No outcome numbers published.
- Library support: React `useOptimistic` [2], TanStack Query [3], SWR [4]; Apollo `optimisticResponse` and Relay optimistic updaters exist (APIs known, docs not opened).

**How to detect it.**
- *Applied:* with the network throttled, a like or toggle changes at once; a new comment or message appears dimmed, then settles; a deleted item disappears with an Undo.
- *Violated:* a spinner on a like button; the whole list reloads after a toggle; the UI waits for the server before flipping a switch. The reverse fault: "Payment successful" shown before the server confirms.
- *In code:* `useOptimistic`, `optimisticResponse`, `optimisticData`, `rollbackOnError`, `onMutate` with `setQueryData` and an `onError` restore; absence of these where a handler does `await api...` and only then `setState`.
- *Quick test:* set DevTools to "Offline", tap a like or toggle. The UI should change at once, then roll back with a message. Repeat on Slow 4G: the change should stay.

**How to implement.**
1. Classify each action. Optimistic only if it is reversible, almost always succeeds, involves no money or legal effect, and affects no one else.
2. Update local state at once with a temporary ID and a pending style. Send the request.
3. On success, swap in the server data. On failure, restore the snapshot, show a non-blocking error with Retry (FBK-07), and keep the user's input (ERR-05).
4. Serialise or cancel concurrent requests for the same record.
5. Pair destructive but reversible actions with Undo (ERR-02).
```jsx
const [likes, addLike] = useOptimistic(count, (n, delta) => n + delta);
function onLike() {
  startTransition(async () => {
    addLike(1);              // shows now
    await api.like(id);      // on throw, UI returns to `count`
  });
}
```

**Sources.**
[1] Instagram's secret to super-quick photo uploads: send fast, match data later. The Next Web, 1 May 2012 (reports Mike Krieger's Warm Gun 2011 talk). https://thenextweb.com/news/instagrams-secret-to-super-quick-photo-uploads-send-fast-match-data-later
[2] React. useOptimistic. https://react.dev/reference/react/useOptimistic
[3] TanStack Query. Optimistic Updates. https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates
[4] SWR. Mutation and Revalidation (optimistic updates). https://swr.vercel.app/docs/mutation

---

### FBK-05 Meet Core Web Vitals and treat speed as a feature

**What it is.** Treat speed and responsiveness as product requirements. Pass Core Web Vitals (good LCP, INP and CLS) at the 75th percentile of real users, mobile and desktop separately, and keep them passing.

**Why it works.**
- Current thresholds: LCP good at 2.5 s or less, poor above 4.0 s. INP good at 200 ms or less, poor above 500 ms. CLS good at 0.1 or less, poor above 0.25. A page passes when its 75th-percentile value is good on all three metrics. INP replaced First Input Delay as a Core Web Vital in March 2024 [1][2][3][4].
- Mechanism: delay lowers use. The cleanest evidence is Google's 2009 delay experiment (below) [5].
- Search: Google says its ranking systems use Core Web Vitals, gives them no stated weight, and says relevance still decides. It tells site owners to treat the scores as a tool for users, not an SEO target [6].
- Business claims, graded one by one:

| Claim (year) | What the source shows | Grade |
|---|---|---|
| Google, Brutlag (2009): +100 to +400 ms cuts searches per user by 0.2% to 0.6% | Delayed group versus control group, 4 to 6 weeks; effect grew over time and persisted after removal [5] | Strong |
| Deloitte, Google and 55 (2020): 0.1 s faster mobile gives +8.4% retail and +10.1% travel conversion, +9.2% retail spend | 37 brand sites, over 30 million mobile sessions, 30 days in late 2019. Observational. Gains only when every page in the journey improved all four metrics by 0.1 s. Google commissioned it [7] | Moderate |
| Vodafone (2021): LCP 31% better gave +8% sales, +15% lead-to-visit, +11% cart-to-visit | 50/50 A/B test on one landing page, about 34K visits a day per arm, versions otherwise identical; test length not stated [8] | Moderate |
| Akamai (2017): 100 ms delay cuts conversion 7%; 2 s delay raises bounce 103% | Vendor retail report on SOASTA data. We could not open it (HTTP 403). Coverage disagrees on what the 103% compares [9] (snippet) | Weak |
| Amazon: +100 ms costs 1% of sales (Linden, 2006) | One slide in a Stanford talk saying Amazon "found something similar in our tests". No method, sample or duration [10] | Weak |
| Google: +500 ms cuts traffic 20% (Mayer, 2006) | The test showed 30 results instead of 10; page time rose from 0.4 s to 0.9 s and traffic and revenue fell about 20%. Content changed too, so it is confounded [11]. Brutlag later isolated delay and found much smaller effects [5] | Weak |
| Pinterest (2017): perceived wait down 40%, SEO traffic and signups up 15% | Medium post not opened (HTTP 403). A 2018 talk summary gives other figures (about 30% faster, signups +15%, SEO +10%), says individual optimisations were A/B tested, and does not say the migration was. "Wait time" is a custom RUM metric, not a perception study [12][13] | Weak |
| BBC: each extra second loses 10% of users | Traced by WPO Stats to a Creative Bloq feature whose text we could not read. No method or date found [14] | Weak |
| Google/SOASTA (2017): bounce probability rises with load time | Neural net on undisclosed data (90% prediction accuracy). The 2017 text says 1 s to 7 s gives +113%; the current page says 1 s to 10 s gives +123%. "53% leave after 3 s" comes from a 2016 sample of 3,700 mobile sites. The widely quoted "32%, 90%, 106%" series was not on the pages we opened, and the 90% in the article is model accuracy [15][16] | Weak |

**Evidence: Moderate.** Strong that latency lowers engagement (Google, 2009). Moderate for the two A/B and observational studies. Weak for the headline revenue figures. The thresholds are Google's convention for field data, not a standard.

**Limitations.**
- We found no study showing a behavioural cliff at 2.5 s, 200 ms or 0.1. Treat thresholds as targets, not laws.
- Passing does not guarantee ranking or conversion [6].
- Vendor case studies are self-selected successes, and Google funded the Deloitte study.
- Lab tools (Lighthouse) can pass while field data fails. INP needs real interactions.
- Metrics can be gamed (hiding content to improve LCP) without helping users. Keep task completion as the top measure (see MEA).
- Conflicts: lazy-loading the hero image or showing a skeleton instead of content can hurt LCP (FBK-03); ad and tag revenue can hurt INP and CLS.

**How to measure it works.**
- Leading: field p75 for LCP, INP, CLS per page template and device (CrUX, or `web-vitals` in RUM); share of loads that are good on all three; Lighthouse CI budgets to catch regressions.
- Lagging: conversion, bounce, searches or sessions per user.
- Best method: an A/B test of a speed change, or a latency-injection test on a random group as Google ran [5], to learn your own price of delay.

**Implemented by.**
- Google Search (2009): published the delay experiments [5].
- Vodafone (2021): moved a widget from client-side to server-side rendering, server-rendered critical HTML, optimised images; LCP 31% better, sales +8% in the A/B test [8].
- Yahoo! JAPAN News (2021): fixed CLS on article pages; see FBK-06.
- Pinterest (2017): created a performance team and A/B-tested individual optimisations; outcome figures are Weak above [13].

**How to detect it.**
- *Applied:* PageSpeed Insights field data shows "Good" for all three; the LCP image is preloaded with high priority; images have dimensions; scripts are deferred; taps respond at once.
- *Violated:* hero image lazy-loaded; render-blocking CSS or JS in `<head>`; multi-megabyte JS bundles with long tasks; late-injected content; unsized images.
- *In code:* `fetchpriority="high"`, `<link rel="preload" as="image"`, `loading="lazy"` on the first image (anti-pattern), `<script src=` without `async` or `defer`, `web-vitals` (`onLCP`, `onINP`, `onCLS`), `PerformanceObserver` types `largest-contentful-paint`, `layout-shift`, `event`, `lighthouserc`, `next/image` with `priority`.
- *Quick test:* open PageSpeed Insights for the key URL and read the mobile field-data block. Then run Lighthouse (mobile) and note the LCP element, long tasks and layout shifts.

**How to implement.**
1. Measure field p75 for each metric by template and fix the worst template first.
2. LCP: cut server time (cache, CDN), send critical HTML from the server, preload the LCP image with `fetchpriority="high"`, never lazy-load it, serve right-sized responsive images. Vodafone's changes were server rendering and image work [8].
3. INP: break up long tasks, defer or drop third-party scripts, keep handlers light (FBK-01).
4. CLS: see FBK-06.
5. Put budgets in CI and alert on p75 regressions.
6. Prefer changes you can validate on your own traffic.

**Sources.**
[1] Google. Web Vitals. web.dev. https://web.dev/articles/vitals
[2] Google. Largest Contentful Paint (LCP). web.dev. https://web.dev/articles/lcp
[3] Google. Interaction to Next Paint (INP). web.dev. https://web.dev/articles/inp
[4] Google. Cumulative Layout Shift (CLS). web.dev. https://web.dev/articles/cls ; INP launch note: https://web.dev/blog/inp-cwv-launch
[5] Brutlag, J. (2009). Speed Matters for Google Web Search. https://services.google.com/fh/files/blogs/google_delayexp.pdf
[6] Google Search Central. Understanding page experience in Google Search results. https://developers.google.com/search/docs/appearance/page-experience
[7] Deloitte, 55, Google (2020, 24 Jun). Milliseconds make millions. web.dev. https://web.dev/case-studies/milliseconds-make-millions
[8] Vodafone case study (2021, 17 Mar). web.dev. https://web.dev/case-studies/vodafone
[9] Akamai (2017). Spring 2017 State of Online Retail Performance. https://www.akamai.com/fr/newsroom/press-release/akamai-releases-spring-2017-state-of-online-retail-performance-report (snippet; page not opened)
[10] Linden, G. (2006). Make Data Useful (Stanford talk, slide 16), copy at https://docs.google.com/presentation/d/1r5sZSaS39mrAn5KTe271EGBlOZrMr_bR/htmlpresent ; see also http://glinden.blogspot.com/2006/12/slides-from-my-talk-at-stanford.html
[11] Linden, G. (2006, Nov). Marissa Mayer at Web 2.0. Geeking with Greg. http://glinden.blogspot.com/2006/11/marissa-mayer-at-web-20.html
[12] Meder, S., Antonov, V., Chang, J. (2017, 3 Mar). Driving user growth with performance improvements. Pinterest Engineering. https://medium.com/pinterest-engineering/driving-user-growth-with-performance-improvements-cfc50dafadd7 (snippet; HTTP 403)
[13] Kadlec, T. (2018). Notes on Making Pinterest Fast at Perfmatters. https://timkadlec.com/remembers/2018/03/notes-on-making-pinterest-fast-at-perfmatters/
[14] WPO Stats. BBC load abandonment. https://wpostats.com/2017/03/03/bbc-load-abandonment (links to http://www.creativebloq.com/features/how-the-bbc-builds-websites-that-scale, text not readable)
[15] Think with Google (2017, Feb). Find Out How You Stack Up to New Industry Benchmarks for Mobile Page Speed (PDF of the original). https://www.thinkwithgoogle.com/_qs/documents/57/mobile-page-speed-new-industry-benchmarks.pdf
[16] Think with Google (updated version). https://business.google.com/ca-en/think/marketing-strategies/mobile-page-speed-new-industry-benchmarks/

---

### FBK-06 Keep the layout stable while it loads

**What it is.** Content already on screen does not move unexpectedly as images, ads, fonts, banners and data arrive. Space is reserved in advance.

**Why it works.**
- Mechanism (no controlled study found): when content shifts under the pointer or the eye, people lose their place and tap the wrong thing.
- Cumulative Layout Shift quantifies it. Each shift scores impact fraction times distance fraction. CLS is the worst burst of shifts (shifts less than 1 s apart, window up to 5 s). Good is 0.1 or less, poor above 0.25, at the 75th percentile [1].
- Common causes: images and video without dimensions, ads and embeds that resize, content injected above existing content, web fonts that swap in at a different size, animations of layout properties, banners that push content [1][2].
- Case: Yahoo! JAPAN News reserved space for the article hero image using aspect-ratio boxes. Lab CLS fell from about 0.2 to 0 and poor-CLS URLs in Search Console fell 98%. Page views per session rose 15.1%, session duration 13.3%, and bounce rate fell 1.72 percentage points. This was a before-and-after comparison, not an A/B test [3].

**Evidence: Moderate.** A defined, widely measured Google metric and one before-and-after case (2021, 5 years old). No controlled study of misclick or comprehension effects found. No WCAG criterion covers layout shift directly.

**Limitations.**
- Shifts that follow a user's own action (opening a menu) are expected. The fault is movement the user did not cause.
- Reserved space that stays empty (an ad that never fills) looks broken. Size slots for the smallest likely content and show a placeholder if nothing loads [2].
- `font-display: optional` avoids late font swaps but may show the fallback font on a first visit [2].
- A lab run can miss shifts that happen later in a real session. Field data is the check.
- A skeleton that does not match the final layout causes the shift it was meant to prevent (FBK-03).

**How to measure it works.**
- Leading: CLS p75 per template (CrUX, or `web-vitals` `onCLS` with `layout-shift` entries and their `sources`); DevTools "Layout Shift Regions".
- Behaviour: misclicks and rage clicks near late-loading elements; bounce on article pages.
- Lagging: pages per session and session duration (Yahoo! JAPAN moved both) [3].

**Implemented by.**
- Yahoo! JAPAN News (2021): hero-image space reserved using the aspect ratio from the backend API; effects above [3].
- Google's web.dev guidance lists the fixes below [2]. No other company outcome data checked.

**How to detect it.**
- *Applied:* images carry `width` and `height` or a CSS `aspect-ratio`; ad and embed slots have a `min-height`; banners overlay or have reserved space; fonts use metric-matched fallbacks; text does not jump as the page loads.
- *Violated:* text moves as images load; a button slides away just before the click; a cookie banner pushes the page down after 1 to 2 s; a "related articles" block appears above the text you are reading; font swap reflows paragraphs.
- *In code:* `<img` or `<iframe` without `width` and `height`; no `aspect-ratio`; `font-display: swap` without `size-adjust` or `ascent-override`; `prepend(`, `insertBefore(` for banners; animating `top`, `left`, `height`, `margin` instead of `transform`; ad containers without `min-height`; `contain-intrinsic-size`.
- *Quick test:* in Chrome DevTools, enable Rendering > "Layout Shift Regions", throttle to Slow 4G with 4x CPU slowdown, and reload. Blue flashes mark shifts. Check Lighthouse CLS.

**How to implement.**
1. Set `width` and `height` on every image and video (or CSS `aspect-ratio`). Keep the same ratio across `srcset` candidates [2].
2. Reserve space for ads, embeds and iframes with `min-height` or `aspect-ratio`. Keep the space (with a placeholder) if no ad loads [2].
3. Do not insert content above what the user is reading unless they asked for it. Use overlays for banners, or reserve their space.
4. Fonts: preload critical fonts; use `font-display: optional` or a fallback matched with `size-adjust`, `ascent-override`, `descent-override`, `line-gap-override` [2].
5. Animate with `transform` and `opacity`, not layout properties.
6. Make pages eligible for the back/forward cache so repeat navigations restore without shifts [2].
```html
<img src="hero.jpg" width="1200" height="600" alt="..." style="max-width:100%;height:auto">
```

**Sources.**
[1] Google. Cumulative Layout Shift (CLS). web.dev. https://web.dev/articles/cls
[2] Google. Optimize Cumulative Layout Shift. web.dev. https://web.dev/articles/optimize-cls
[3] Yahoo! JAPAN News case study (updated 2021-03-09). web.dev. https://web.dev/case-studies/yahoo-japan-news

---

### FBK-07 Confirm outcomes with non-blocking feedback that stays long enough to read

**What it is.** After a save, send, delete or sync, show a short message that does not block input, says what happened, stays long enough to read, offers Undo or View when useful, and is announced to screen readers.

**Why it works.**
- People need to know the action took effect. Heuristic 1 asks for prompt feedback on system status [1].
- Blocking dialogs cost attention. NN/g lists the costs of modal dialogs: interruption, extra interaction, lost context, and training users to ignore them [2].
- Material's snackbar spec (Material 1 archive) sets the pattern: one line of text, at most one action, one at a time, no input blocking, times out by itself, and must not be the only way to reach a core feature [3]. The Material Components for Web snackbar defaults to 5 s and allows 4 to 10 s [4].
- Gmail shows "Message sent" with Undo and View message at the bottom left; the Undo window can be 5, 10, 20 or 30 s [5].
- WCAG 2.2 SC 4.1.3 (AA) requires status messages to be exposed to assistive technology without moving focus. Use `role="status"` for results and `role="alert"` for errors [6].
- WCAG 2.2 SC 2.2.1 (A): where content sets a time limit, users must be able to turn it off, adjust it, or extend it, with exceptions [7].

**Evidence: Moderate.** Material guidance (the platform guide we could read; Apple's pages were not readable) and a formal accessibility criterion. No controlled study of toast duration found. Required: WCAG 2.2 SC 4.1.3 (AA).

**Limitations.**
- Timed messages exclude slow readers and screen-reader users. Errors and messages that need action must persist (ERR-04).
- An auto-dismissing message is a time limit under a strict reading of SC 2.2.1. Auditors differ on whether it applies. Pause the timer on hover and focus, and keep the outcome visible elsewhere (sent folder, activity log) [7].
- Payments and legal actions need a persistent confirmation page and an email, not a toast.
- Stacks of toasts, or a toast for every keystroke-level save, become noise. Queue one at a time [3].
- Native: prefer a Snackbar to Toast on Android when the message can sit in the context of the action [8].

**How to measure it works.**
- Leading: in a usability test, ask "Did it save?" right after the action; screen-reader pass (is it announced?); keyboard pass (can Undo be reached before it vanishes?).
- Behaviour: duplicate-action rate, Undo use rate, tickets saying "I'm not sure it sent".
- Lagging: repeat submissions, support contacts.

**Implemented by.**
- Gmail: "Message sent" with Undo and View message; Undo Send was in Labs from 19 March 2009 and left Labs in 2015 [5][9].
- Google Material (snackbar component; defaults above) [3][4].

**How to detect it.**
- *Applied:* a short past-tense message near an edge ("Draft saved", "3 conversations archived"), 4 to 10 s on screen, Undo for reversible actions, timer paused on hover or focus, one message at a time, announced by a screen reader.
- *Violated:* a modal "Success! OK" dialog; a toast gone in under 2 s; an error shown only as a vanishing toast; no feedback at all after Save; a toast that screen readers do not announce or that keyboard users cannot reach; stacked toasts.
- *In code:* `role="status"`, `aria-live="polite"`, `aria-atomic`, `role="alert"` for errors; `autoHideDuration`, `duration:` values under 4000; toast libraries (`sonner`, `react-hot-toast`, MUI `Snackbar`); `window.alert(` used for success; Android `Snackbar.make(..., LENGTH_LONG)` with `setAction("Undo"`; Android 10+ `AccessibilityManager.getRecommendedTimeoutMillis` (API known, docs page not re-read).
- *Quick test:* do a save and a delete. Time the message with a stopwatch (4 s or more?). Turn on NVDA, VoiceOver or TalkBack and confirm it is announced. Tab to the Undo action before the message disappears.

**How to implement.**
1. Add one live region at page load: `<div role="status" aria-live="polite">`. Change its text when the action finishes. If the same text repeats, clear then set it so it is re-announced [4].
2. Write specific past-tense text: "Draft saved", not "Success".
3. Show for 4 to 10 s [4]; use the longer end for longer text (design judgement). Pause the timer on hover and focus. Never auto-dismiss an error or a message that asks for action.
4. Add Undo or View for reversible actions (ERR-02). The action must be keyboard reachable.
5. One at a time. Keep it clear of the primary controls; move a floating action button up instead of covering it [3].
6. Keep a durable record elsewhere for important outcomes (sent items, order page, activity log).
```html
<div id="status" role="status" aria-live="polite" class="visually-hidden"></div>
<script>
function announce(msg){ const s = document.getElementById('status'); s.textContent = ''; setTimeout(() => s.textContent = msg, 50); }
</script>
```

**Sources.**
[1] Nielsen, J. (1994, reviewed 2024). 10 Usability Heuristics. NN/g. https://www.nngroup.com/articles/ten-usability-heuristics/
[2] Fessenden, T. (2017, 23 Apr). Modal & Nonmodal Dialogs: When (& When Not) to Use Them. NN/g. https://www.nngroup.com/articles/modal-nonmodal-dialog/
[3] Material Design (1). Snackbars & toasts. https://m1.material.io/components/snackbars-toasts.html
[4] Material Components for Web v14. Snackbar README. https://raw.githubusercontent.com/material-components/material-components-web/v14.0.0/packages/mdc-snackbar/README.md
[5] Google. Unsend an email (Gmail Help). https://support.google.com/mail/answer/1284885
[6] W3C. Understanding SC 4.1.3 Status Messages (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
[7] W3C. Understanding SC 2.2.1 Timing Adjustable (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html
[8] Material Components for Android. Snackbar. https://raw.githubusercontent.com/material-components/material-components-android/master/docs/components/Snackbar.md
[9] Gmail Blog (2009, 19 Mar), "New in Labs: Undo Send" (listing only): https://gmail.googleblog.com/2009/03/ ; Labs exit in 2015 is reported in Wikipedia, Gmail, citing The Next Web (23 June 2015): https://en.wikipedia.org/wiki/Gmail (primary announcement not opened)

---

### FBK-08 Interrupt only when it matters

**What it is.** Notifications, modals, badges and alerts appear only when they are relevant, timely and under the person's control: separate types, adjustable frequency, quiet hours, easy to turn off.

**Why it works.**
- Interruptions cost something. In a lab experiment, Mark, Gudith and Klocke (CHI 2008) found interrupted work was done faster but with more reported stress, frustration, workload, time pressure and effort (abstract; paper not re-opened this session) [1].
- The "23 minutes to recover" figure is widely attributed to Gloria Mark. We could not trace it to a primary source, and the 2008 paper above reports speed and stress, not a resumption time (as far as its abstract reports). Treat the figure as Weak. Her 2005 field study (CHI '05) is the usual primary source for resumption gaps in real work; we could not read it [2].
- Content and variety matter. Duolingo's bandit algorithm (Yancey and Settles, KDD 2020) chooses which reminder template each user sees, because fresh templates work better and repeated ones desensitise users. In an online A/B test it raised daily active users 0.5% and new-user retention 2% over a strong random baseline [3]. This shows better content helps. It does not show that sending more helps.
- Platforms give control to users. Android 8.0 (API 26) requires every notification from an app targeting API 26 or higher to belong to a channel. Users set importance and sound per channel. The app cannot change a channel's importance after creation [4]. iOS 15 (2021) added a scheduled Notification Summary and interruption levels (Apple pages not readable this session; unverified).
- WCAG 2.2 SC 2.2.4 (AAA): users can postpone or suppress interruptions except emergencies [5].

**Evidence: Moderate.** One lab experiment on interruption (2008, 18 years old; abstract only), one large A/B result on notification content (2020), platform designs, and a AAA criterion. Required: nothing at AA; WCAG 2.2 SC 2.2.4 is AAA.

**Limitations.**
- Interruption studies come from knowledge work. Their link to consumer notifications is indirect.
- Duolingo's result is about which message to send, not how many.
- Time-sensitive and safety messages must still break through. Over-suppression hides urgent information.
- Teams are tempted to raise volume for short-term engagement. We found no verified long-term opt-out data in this review.
- Related: asking for permission at the right moment (see ONB); guilt-trip or fake-urgency notifications (see CHO); non-blocking in-app messages (FBK-07).

**How to measure it works.**
- Leading: opt-out and permission-revoke rate within the first week; per-channel disable rate; notification-to-session rate.
- Lagging: uninstall rate, retention, DAU (the Duolingo test used DAU and new-user retention) [3].
- Guardrails in every notification A/B test: unsubscribe, mute and permission-off rates. Survey a one-item "too many?" question.

**Implemented by.**
- Duolingo (2020): bandit optimisation of daily reminders, +0.5% DAU, +2% new-user retention [3].
- Android (Android 8.0): notification channels with user-controlled importance [4].
- Apple (iOS 15, 2021): Notification Summary and interruption levels (unverified).

**How to detect it.**
- *Applied:* a settings screen lists notification types with separate switches and frequency; permission is requested after the user has seen value; quiet hours or a digest option; high-importance reserved for time-bound events; no pop-up over content on load.
- *Violated:* a permission prompt on first load; the same push every day; marketing sent on the transactional channel; newsletter modals mid-article; every notification at maximum importance; one switch for everything.
- *In code:* `Notification.requestPermission()` or `pushManager.subscribe` at page load; Android `NotificationChannel(` with `IMPORTANCE_HIGH` for all types, or a single channel; `setPriority(PRIORITY_MAX)`; iOS `requestAuthorization` at launch and `interruptionLevel = .timeSensitive` used widely; a notification settings route (`ACTION_CHANNEL_NOTIFICATION_SETTINGS`).
- *Quick test:* on first run, count permission prompts and modals in the first 2 minutes. Open notification settings: can one type be turned off without the rest? On Android, open the app's system notification settings and count channels and their importance.

**How to implement.**
1. List every message and sort it: transactional (user asked), time-sensitive, or informational/marketing. Map each to its own channel or setting.
2. Reserve high-interruption delivery for time-bound items only.
3. Ask for permission in context, after the user has seen the value (see ONB).
4. Give per-type controls in the app and a deep link to system settings (`ACTION_CHANNEL_NOTIFICATION_SETTINGS`) [4].
5. Cap frequency, batch low-priority items into a digest, and respect quiet hours and Focus modes.
6. Vary content to avoid desensitisation [3]. Track opt-outs as guardrails.
```kotlin
val ch = NotificationChannel("orders", "Order updates", NotificationManager.IMPORTANCE_DEFAULT)
ch.description = "Shipping and delivery changes"
notificationManager.createNotificationChannel(ch)   // one channel per type
```

**Sources.**
[1] Mark, G., Gudith, D., Klocke, U. (2008). The cost of interrupted work: more speed and stress. CHI '08, pp. 107-110. https://doi.org/10.1145/1357054.1357072 (bibliographic data checked at https://api.crossref.org/works/10.1145/1357054.1357072 ; findings from the abstract, not re-opened)
[2] Mark, G., Gonzalez, V. M., Harris, J. (2005). No task left behind? Examining the nature of fragmented work. CHI '05, pp. 321-330. https://doi.org/10.1145/1054972.1055017 (bibliographic data only; "23 minutes" claim not found in any source we could open)
[3] Yancey, K. P., Settles, B. (2020). A Sleeping, Recovering Bandit Algorithm for Optimizing Recurring Notifications. KDD '20. https://research.duolingo.com/papers/yancey.kdd20.pdf ; https://doi.org/10.1145/3394486.3403351
[4] Android Developers. Create and manage notification channels. https://developer.android.com/develop/ui/views/notifications/channels
[5] W3C. Understanding SC 2.2.4 Interruptions (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/interruptions.html
