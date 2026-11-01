# Contested and debunked rules (MYTH)

Rules of thumb that circulate widely in UX but fail, are narrower than stated, or cannot be traced to a primary source. Load this file when a design, a design rationale or a review comment cites one of these claims. Do not flag a UI for breaking a myth and do not credit it for following one; judge the design with the rules named under "What to do instead". Rule references use a category prefix and topic (for example "NAV, information scent") except where the catalog ID is fixed (FBK-03, VIS-07, MEA-01).

Verdicts: **Debunked** (evidence contradicts the claim as stated), **Misapplied** (a real finding stretched beyond what it showed), **Contested** (studies disagree), **Context-dependent** (true in some conditions, false in others).
Source notes: "(snippet)" means we saw the source only in a search result. "(not opened)" means we could not open the page in this session. "Bibliographic details verified" means the citation was confirmed in Crossref but the paper was not read.

| ID | Claim | Verdict |
|---|---|---|
| MYTH-01 | Every page should be reachable within three clicks | Debunked |
| MYTH-02 | Keep menus to 7 ± 2 items | Misapplied |
| MYTH-03 | Users don't scroll, so everything important must sit above the fold | Debunked |
| MYTH-04 | The human attention span is 8 seconds, shorter than a goldfish's | Debunked |
| MYTH-05 | More choice always reduces sales | Contested |
| MYTH-06 | The Zeigarnik effect makes unfinished tasks sticky, so use it as a design lever | Contested |
| MYTH-07 | Design layouts for the F-pattern | Misapplied |
| MYTH-08 | Skeleton screens always beat spinners | Context-dependent |
| MYTH-09 | Carousels engage users | Debunked |
| MYTH-10 | Red (or green) buttons convert better | Misapplied |
| MYTH-11 | Infinite scroll is always better than pagination | Context-dependent |
| MYTH-12 | NPS is the one number you need | Contested |
| MYTH-13 | Dark mode is easier on the eyes | Context-dependent |
| MYTH-14 | The golden ratio makes layouts beautiful | Contested |
| MYTH-15 | Five test users are always enough (or, the reverse, you always need large samples) | Context-dependent |

---

### MYTH-01 "Every page should be reachable within three clicks"

**Verdict: Debunked.**

**Where it comes from.** Web-design advice from the early 2000s. We found no study behind it. Joshua Porter tested it at User Interface Engineering in 2003 [1].

**What the evidence says.** In the UIE test, 44 users attempted 620 tasks (over 8,000 clicks). Click count did not predict success: successful and failed tasks had the same length distribution, and the share of dissatisfied users stayed between 46% and 61% at every path length. Porter reports that "hardly anybody gave up after three clicks", and concludes that complaints about clicking are really complaints about not finding things [1]. It is a single 2003 test; we did not look for later replications.

**What to do instead.** Raise certainty at each step: clear labels, strong information scent, a visible sense of location, easy ways back. Count task success, not clicks. See NAV (information scent, wayfinding), CON (link and action labels), PER (Hick's law, for the breadth against depth trade-off).

**How to spot it in a review.** A requirement such as "all content within three clicks" that leads to crowded menus or giant footers; an IA audit that scores click depth instead of task success; a path rejected because it takes four clear steps.

**Sources.**
[1] Porter, J. (2003). Testing the three-click rule. User Interface Engineering. https://articles.centercentre.com/three_click_rule/

---

### MYTH-02 "Keep menus to 7 ± 2 items"

**Verdict: Misapplied.**

**Where it comes from.** Miller's 1956 paper "The magical number seven, plus or minus two" (Psychological Review 63, 81-97), quoted for decades as a limit on menu and navigation size [1].

**What the evidence says.** Miller's paper covers absolute judgments of one-dimensional stimuli (such as tones) and the span of immediate memory for chunks. It does not mention menus or navigation, and Miller himself called the recurrence of seven possibly a "pernicious, Pythagorean coincidence" [1]. Cowan (2001) calls Miller's number a rough estimate and argues the real short-term limit is about four chunks [2]. Neither limit governs a visible menu, where people recognize items instead of recalling them. Menu studies point the other way: Kiger (1984) found broad, shallow hierarchies faster and less error-prone than deep ones, and Larson and Czerwinski (1998) found a three-level web hierarchy (8 × 8 × 8) slower to search than two-level ones with 16 or 32 links per page [3][4] (both not opened; findings as widely reported).

**What to do instead.** Size a menu for scanning: group related items under clear headings, keep labels distinct, prefer broad and shallow to deep, and add search or filters for long lists. See PER (Hick's law, memory limits), NAV (visible navigation, filters), INT (menus).

**How to spot it in a review.** "Max 7 nav items" stated as a rule; a "More" catch-all added to hit the limit; four or five levels of nesting built to keep each level short.

**Sources.**
[1] Miller, G. A. (1956). The magical number seven, plus or minus two: some limits on our capacity for processing information. Psychological Review 63, 81-97. http://psychclassics.yorku.ca/Miller/
[2] Cowan, N. (2001). The magical number 4 in short-term memory: a reconsideration of mental storage capacity. Behavioral and Brain Sciences 24(1), 87-114. https://doi.org/10.1017/S0140525X01003922
[3] Kiger, J. I. (1984). The depth/breadth trade-off in the design of menu-driven user interfaces. International Journal of Man-Machine Studies 20(2), 201-213 (not opened).
[4] Larson, K., & Czerwinski, M. (1998). Web page design: implications of memory, structure and scent for information retrieval. CHI '98, 25-32 (not opened).

---

### MYTH-03 "Users don't scroll, so everything important must sit above the fold"

**Verdict: Debunked.** The weaker claim, that the first screen gets the most attention, holds.

**Where it comes from.** Print's "above the fold" idea carried into web design. We traced no single originating study.

**What the evidence says.** NN/g eyetracking found that the share of viewing time spent above the fold fell from 80% in 2010 (1024 × 768 screens) to 57% in 2018 (1920 × 1080 screens), and that 74% of viewing time in 2018 fell within the first two screenfuls (up to 2,160 px) [1]. Chartbeat (9 March 2014, about 2 billion visits) reported that 66% of attention on a typical media page was spent below the fold, yet 55% of visitors spent under 15 seconds actively on a page [2]. People do scroll, but the first screen still decides whether they continue.

**What to do instead.** Put the main message and the primary action in the first view. Signal that more content follows (for example a cut-off element), avoid "false floors" (bands that look like the end of the page), and test page length with real users. See VIS (primary action, fold), CON (front-loading).

**How to spot it in a review.** A rationale such as "keep everything above the fold, users won't scroll" that crams content into one screen; or the opposite, a full-viewport hero with no cue that content continues below it.

**Sources.**
[1] Nielsen Norman Group (2018). Scrolling and attention. https://www.nngroup.com/articles/scrolling-and-attention/
[2] Haile, T. (2014-03-09). What you think you know about the web is wrong. Time (Chartbeat data). https://time.com/12933/what-you-think-you-know-about-the-web-is-wrong/

---

### MYTH-04 "The human attention span is 8 seconds, shorter than a goldfish's"

**Verdict: Debunked.**

**Where it comes from.** A 2015 Microsoft Canada consumer-insights report said average attention fell from 12 seconds in 2000 to 8 seconds in 2013, below a goldfish's 9 seconds. The report credited third-party web statistics, and the BBC program More or Less (2017) reported that no research stood behind the figure. We could not open the report or the BBC piece in this session (the BBC domain was blocked and the report PDF did not load), so this is the widely repeated account, not one we confirmed here. Grade of the claim: Weak.

**What the evidence says.** We found no primary study that measured an 8-second attention span or compared people with goldfish. A general reference summary says attention varies with task, motivation, fatigue and environment [1] (secondary source). What can be measured is behavior, not capacity: Chartbeat found that 55% of visitors spent under 15 seconds actively on a page [2]. That describes how people choose among pages, not how long they can attend. Gloria Mark's logging studies report shorter stretches on a single screen over the years; they measure task switching at work, and we did not open her 2023 book (not opened).

**What to do instead.** Design for relevance and low effort, not a time limit: put the point first, chunk and label content, and show value in the first screen. See CON (front-loading, scannable text), VIS (hierarchy), PER. Measure task completion and time on task (MEA).

**How to spot it in a review.** Slides or rationales that cite "8 seconds" or "goldfish" to justify cutting content, forcing autoplay or shortening onboarding; a statistic with no source.

**Sources.**
[1] Wikipedia. Attention span (secondary; lists the research it relies on). https://en.wikipedia.org/wiki/Attention_span
[2] Haile, T. (2014-03-09). What you think you know about the web is wrong. Time (Chartbeat data). https://time.com/12933/what-you-think-you-know-about-the-web-is-wrong/

---

### MYTH-05 "More choice always reduces sales"

**Verdict: Contested.**

**Where it comes from.** Iyengar and Lepper (2000): a jam tasting booth with 24 flavors against 6, plus chocolate and essay studies [1].

**What the evidence says.** At the booth, 60% (145 of 242) of passers-by stopped at the 24-jam display against 40% (104 of 260) at the 6-jam display, but about 30% (31) of stoppers at the small display bought, against 3% (4) at the large one. In the essay study, 74% completed the optional assignment with 6 topics against 60% with 30 [1]. A meta-analysis of 50 experiments (63 conditions, 5,036 participants) found a mean effect of virtually zero with large variance, and no sufficient conditions for choice overload [2]. A later meta-analysis of 99 observations (N = 7,202) found four moderators (choice-set complexity, decision difficulty, preference uncertainty, decision goal) and a significant overall effect once they are accounted for [3].

**What to do instead.** Do not cut options by reflex. Reduce difficulty: filters, sorting, comparison and good defaults or recommendations when people lack firm preferences; keep a wide range when they know what they want. Test it. See PER (Hick's law), NAV (search, filters), FRM (smart defaults), MEA (A/B tests).

**How to spot it in a review.** "Limit to 3 plans because of the jam study" with no data from the product; or "more options is always better"; 30 or more similar items with no way to filter or sort.

**Sources.**
[1] Iyengar, S. S., & Lepper, M. R. (2000). When choice is demotivating: can one desire too much of a good thing? Journal of Personality and Social Psychology 79(6), 995-1006. https://doi.org/10.1037/0022-3514.79.6.995 (figures from the paper text)
[2] Scheibehenne, B., Greifeneder, R., & Todd, P. M. (2010). Can there ever be too many options? A meta-analytic review of choice overload. Journal of Consumer Research 37(3), 409-425. https://doi.org/10.1086/651235
[3] Chernev, A., Böckenholt, U., & Goodman, J. (2015). Choice overload: a conceptual review and meta-analysis. Journal of Consumer Psychology 25(2), 333-358. https://doi.org/10.1016/j.jcps.2014.08.002

---

### MYTH-06 "The Zeigarnik effect makes unfinished tasks sticky, so use it as a design lever"

**Verdict: Contested.** The memory effect is not supported; a tendency to resume interrupted tasks is.

**Where it comes from.** Bluma Zeigarnik (1927): people recalled interrupted tasks better than completed ones, a result popularized in UX and marketing to justify progress bars ("profile 64% complete"), checklists and cliffhangers.

**What the evidence says.** A 2025 meta-analysis of the Zeigarnik and Ovsiankina effects found no memory advantage for unfinished tasks but a general tendency to resume them. The authors say the Zeigarnik effect "lacks universal validity" and may depend on situational demands, such as an experimenter's authority, that were more common historically [1]. Earlier attempts also failed: Van Bergen (1968) found no recall difference between finished and interrupted tasks (via a secondary summary) [2].

**What to do instead.** Do not justify an unfinished-state UI with Zeigarnik. Use better-supported levers and measure them: goal gradient and endowed progress (PER), clear next steps and checklists (ONB), and "resume where you left off" with saved state (ERR, never losing work), which fits the resumption tendency. Do not create artificial incompleteness to nag users (CHO-06).

**How to spot it in a review.** A rationale that says "the Zeigarnik effect keeps users coming back"; permanent "incomplete" badges or "complete your profile" nudges with no stated user benefit.

**Sources.**
[1] Ghibellini, R., & Meier, B. (2025). Interruption, recall and resumption: a meta-analysis of the Zeigarnik and Ovsiankina effects. Humanities and Social Sciences Communications 12(1). https://doi.org/10.1057/s41599-025-05000-w (abstract via Crossref; full text not opened)
[2] Wikipedia. Zeigarnik effect (secondary; cites Van Bergen 1968). https://en.wikipedia.org/wiki/Zeigarnik_effect

---

### MYTH-07 "Design layouts for the F-pattern"

**Verdict: Misapplied.**

**Where it comes from.** An NN/g eyetracking study of 232 users (2006) found a dominant F-shaped scanning pattern on text-heavy pages; it spread as a layout recipe ("put key content at the top left") [1].

**What the evidence says.** NN/g's 2017 follow-up (12 November 2017) says the F-pattern is the default when nothing on the page attracts the eyes to meaningful information. It is bad for users and businesses because people skip content on the right, and it also appears on mobile. Other patterns exist (layer-cake, spotted, commitment, marking), and good formatting changes them [2]. The F describes failure to guide the eye, not a target.

**What to do instead.** Design to break the F: put key points in the first two paragraphs, use headings that start with information-carrying words, group related chunks visually, bold key terms, use lists and descriptive link text [2]. See CON (front-loading, scannable text) and VIS (scanning patterns).

**How to spot it in a review.** A rationale such as "users read in an F, so the CTA goes top left and the rest is a long text block"; unformatted walls of text defended as fine.

**Sources.**
[1] Nielsen, J. (2006). F-shaped pattern for reading web content. Nielsen Norman Group. https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content-discovered/
[2] Pernice, K. (2017-11-12). F-shaped pattern of reading on the web: misunderstood, but still relevant (even on mobile). Nielsen Norman Group. https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/

---

### MYTH-08 "Skeleton screens always beat spinners"

**Verdict: Context-dependent.** See FBK-03.

**Where it comes from.** Wide adoption of skeleton screens in app UIs as a way to make waits feel shorter; we traced no primary study behind "always".

**What the evidence says.** Viget (19 October 2017) compared a skeleton screen, a spinner and a blank screen of equal length with 136 participants on mobile mock-ups (animated GIFs). The skeleton did worst: 59% agreed the page loaded quickly against 74% for the spinner and 66% for blank, and the mean perceived wait was 2.82 s against 2.41 s and 2.29 s. The test was small and simulated, and Viget suggests novelty or very short waits as causes [1]. NN/g (4 June 2023) gives duration-based guidance: nothing under 1 second; skeleton or spinner under 10 seconds; skeletons for full-page loads, spinners for a single module; progress bars over 10 seconds. It cites one study, Mejtoft et al. (2018), without reporting its findings [2].

**What to do instead.** Choose the loading state by expected duration and scope (FBK-03). Make the skeleton match the final layout so nothing shifts (FBK, layout stability). Measure perceived speed, not assumed speed.

**How to spot it in a review.** Skeletons on every request, including sub-300 ms fetches that flash; a skeleton layout that differs from the loaded page; skeletons for uploads or long jobs; no progress indication after 10 seconds.

**Sources.**
[1] Faulkner, K., & Olvera, K. (2017-10-19). A bone to pick with skeleton screens. Viget. https://www.viget.com/articles/a-bone-to-pick-with-skeleton-screens/
[2] Tankala, S. (2023-06-04). Skeleton screens vs. progress bars vs. spinners. Nielsen Norman Group. https://www.nngroup.com/articles/skeleton-screens/

---

### MYTH-09 "Carousels engage users"

**Verdict: Debunked.** This applies to auto-rotating homepage carousels; user-controlled galleries are a different case. See VIS-07.

**Where it comes from.** Stakeholders who want every message on the home page; vendor demos.

**What the evidence says.** In Erik Runyon's analysis of a university homepage carousel (the University of Notre Dame, per my recollection of the post), about 1% of visitors clicked a feature and 84% of those clicks hit the first slide (28,928 feature clicks, mid-October 2012 to 22 January 2013) [1]. In an NN/g usability test (19 January 2013) a user missed a discount in an auto-rotating box that was visible about 20% of the time; moving elements lose user control, cut how often any item is seen, look like ads and can be hard for people with motor or reading difficulties [2]. We found no controlled study showing that carousels beat a static hero for engagement.

**What to do instead.** Put the most important content in the first view without motion. If you need several items, use visible, user-controlled tabs or a list. If you keep a carousel, make it user-initiated with visible controls and a pause control (WCAG 2.2 SC 2.2.2 Pause, Stop, Hide, Level A, applies to auto-advancing content [3]). Track clicks per slide. See VIS-07, A11Y (motion).

**How to spot it in a review.** An auto-advancing hero with four or more slides; analytics showing nearly all clicks on slide one; critical offers or tasks only inside a slide; no pause control.

**Sources.**
[1] Runyon, E. (2013). Carousel interaction stats. https://erikrunyon.com/2013/01/carousel-interaction-stats/
[2] Nielsen, J. (2013-01-19). Auto-forwarding carousels and accordions annoy users and reduce visibility. Nielsen Norman Group. https://www.nngroup.com/articles/auto-forwarding/
[3] W3C. Understanding SC 2.2.2 Pause, Stop, Hide (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html

---

### MYTH-10 "Red (or green) buttons convert better"

**Verdict: Misapplied.**

**Where it comes from.** A 2011 HubSpot/Performable A/B test reported that a red button beat a green one on a landing page (the commonly quoted lift is 21%, on roughly 2,000 visitors). The original post was not retrievable at the URL we tried, so we could not confirm the figures; treat the test as an anecdote. Grade of the claim: Weak.

**What the evidence says.** One test on one page, with no published replication across sites, cannot establish that a hue wins in general. The mechanism that generalizes is contrast with the surroundings: an item that differs from its neighbors is noticed and remembered more (the isolation or von Restorff effect, 1933), and the effect varies across people and contexts [1]. A button whose hue differs from the page around it stands out; on a page with a different palette the result could reverse. Standards ask for contrast, not a hue: interface components need at least 3:1 contrast against adjacent colors (WCAG 2.2 SC 1.4.11, Level AA) [2].

**What to do instead.** Pick a primary-action color that contrasts with the page and the brand palette, passes contrast checks, and is used for the same role across the product. Test your own pages with a properly sized A/B test. See VIS (primary action), INT (consistency), A11Y (contrast), MEA (A/B tests).

**How to spot it in a review.** "Red converts better" or "green means go" as the sole reason for a color; every button the same color so no action is primary; a color change shipped without a test.

**Sources.**
[1] Wikipedia. Von Restorff effect (secondary; cites von Restorff 1933, Psychologische Forschung). https://en.wikipedia.org/wiki/Von_Restorff_effect
[2] W3C. Understanding SC 1.4.11 Non-text Contrast (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html

---

### MYTH-11 "Infinite scroll is always better than pagination"

**Verdict: Context-dependent.**

**Where it comes from.** Social feeds made it familiar, and "less friction means more engagement" seemed obvious.

**What the evidence says.** Etsy tested infinite scroll on search results. In Dan McKinley's talk (December 2012) users saw fewer items (median 40 against 80), clicked fewer, saved fewer favorites and bought fewer items from search. A month of bug-hunting found no cause, follow-up tests showed the premises were wrong, and Etsy removed the feature [1]. NN/g (4 September 2022) says infinite scrolling works best for homogeneous items browsed with no particular goal (news, social, entertainment). It works poorly when people look for something specific, compare items, or need the footer, and Back often returns users to the top of the list [2].

**What to do instead.** Use pagination or a "Load more" button for search, listings and comparison; keep the footer reachable and the position restorable after Back (NAV, URLs and Back). Reserve infinite scroll for feeds. Validate with an A/B test on task success, not on pageviews.

**How to spot it in a review.** Infinite scroll on product search or listing pages; footer links unreachable; Back returns to the top; no page numbers or URL state; the design justified by engagement alone.

**Sources.**
[1] McKinley, D. (2012-12). Design for continuous experimentation (talk and slides; infinite scroll example). https://www.slideshare.net/danmckinley/design-for-continuous-experimentation ; post: https://mcfunley.com/design-for-continuous-experimentation
[2] Neusesser, T. (2022-09-04). Infinite scrolling: when to use it, when to avoid it. Nielsen Norman Group. https://www.nngroup.com/articles/infinite-scrolling-tips/

---

### MYTH-12 "NPS is the one number you need"

**Verdict: Contested.**

**Where it comes from.** Reichheld's 2003 Harvard Business Review article "The one number you need to grow" (81(12), 46-54) argued that the "would you recommend" question predicts growth better than other loyalty measures.

**What the evidence says.** Keiningham, Cooil, Andreassen and Aksoy (2007) used longitudinal data from 21 firms and more than 15,500 interviews in the Norwegian Customer Satisfaction Barometer, and compared Reichheld's findings with the American Customer Satisfaction Index. In the industries Reichheld cited as exemplars, they could not replicate his claim of Net Promoter's clear superiority over other measures [1]. Other critics (Hayes 2008) report no evidence that the recommend question beats other loyalty questions (via a secondary summary) [2]. NPS can still serve as a simple relationship signal; the contested part is "the one number".

**What to do instead.** Pair NPS with task-based UX measures (success, time, errors, a standard usability scale), behavior (retention, repeat use) and open-text reasons. See MEA (satisfaction metrics, HEART).

**How to spot it in a review.** A dashboard with NPS as the sole KPI; NPS tied to bonuses; "NPS rose, so the UX improved" with no task data.

**Sources.**
[1] Keiningham, T. L., Cooil, B., Andreassen, T. W., & Aksoy, L. (2007). A longitudinal examination of Net Promoter and firm revenue growth. Journal of Marketing 71(3), 39-51. https://doi.org/10.1509/jmkg.71.3.039 (abstract via Crossref)
[2] Wikipedia. Net promoter score (secondary; lists Reichheld 2003 and Hayes 2008). https://en.wikipedia.org/wiki/Net_promoter_score

---

### MYTH-13 "Dark mode is easier on the eyes"

**Verdict: Context-dependent.**

**Where it comes from.** Preference, glare from bright screens at night, and real battery savings on OLED displays.

**What the evidence says.** NN/g's 2020 review (2 February 2020) found that, for people with normal vision, light mode gave better performance in the cited tasks (visual acuity, proofreading, nighttime glanceable reading). The gap narrows with larger fonts and bright ambient light, fatigue ratings did not differ significantly, and readers did not perceive the performance difference. Some low-vision users, such as those with cataracts or cloudy ocular media, read faster in dark mode (seven participants in Legge's study), and dark mode may save battery on emissive screens [1]. Piepenbrock et al. (2014) found dark text on a light background beat light on dark in proofreading, with the advantage growing as characters shrank from 14 to 8 pt [2]. A 2013 study by the same group found the positive-polarity advantage for both younger and older adults [3] (abstract not opened).

**What to do instead.** Offer both themes and honor the OS setting (A11Y, user settings). Meet contrast requirements in both (A11Y, contrast), avoid small light-on-dark text, and do not claim an eye-health benefit. NN/g suggests prioritizing dark mode in long-form reading apps and keeping the option consistent across screens [1].

**How to spot it in a review.** A dark-only UI; release notes saying dark mode "reduces eye strain"; small grey text on black; no `prefers-color-scheme` support or manual toggle.

**Sources.**
[1] Budiu, R. (2020-02-02). Dark mode vs. light mode: which is better? Nielsen Norman Group. https://www.nngroup.com/articles/dark-mode/
[2] Piepenbrock, C., Mayr, S., & Buchner, A. (2014). Positive display polarity is particularly advantageous for small character sizes: implications for display design. Human Factors 56(5), 942-951. https://doi.org/10.1177/0018720813515509 (abstract via Crossref)
[3] Piepenbrock, C., Mayr, S., Mund, I., & Buchner, A. (2013). Positive display polarity is advantageous for both younger and older adults. Ergonomics 56(7), 1116-1124. https://doi.org/10.1080/00140139.2013.790485 (bibliographic details verified)

---

### MYTH-14 "The golden ratio makes layouts beautiful"

**Verdict: Contested.** No study shows that golden-ratio layouts improve usability.

**Where it comes from.** Claims that the Parthenon, the Mona Lisa, Mondrian's paintings and the Gutenberg Bible follow the ratio, plus Fechner's preference experiments with rectangles, begun in the 1860s.

**What the evidence says.** A review of the psychology of the golden section (Green 1995, Perception 24(8), 937-968) concluded that there seem to be real effects, but that they are sensitive to careless methodology [1]. A summary source says Fechner found a preference for rectangles near the golden ratio and that later careful tests were at best inconclusive; many famous examples (Parthenon, Mona Lisa, Mondrian) are not supported by the artists' own records [2]. The studies test taste for isolated shapes, not task success in layouts.

**What to do instead.** Use a spacing scale and a consistent grid, set type by readability tests, and check preferences with users. See VIS (spacing systems, typography) and INT (consistency). A golden-ratio proportion is fine as a taste choice, not as a justification.

**How to spot it in a review.** "The layout follows the golden ratio" given as the reason for column widths or type sizes; a 1.618 type scale chosen without a readability check; a logo said to be "proven" beautiful by its geometry.

**Sources.**
[1] Green, C. D. (1995). All that glitters: a review of psychological research on the aesthetics of the golden section. Perception 24(8), 937-968. https://doi.org/10.1068/p240937 (abstract via Crossref)
[2] Wikipedia. Golden ratio (secondary; relies on Livio 2002, The Golden Ratio). https://en.wikipedia.org/wiki/Golden_ratio

---

### MYTH-15 "Five test users are always enough" (and its reverse, "you always need large samples")

**Verdict: Context-dependent.** Both extremes are misreadings. See MEA-01.

**Where it comes from.** Nielsen and Landauer's 1993 model: problems found = N × (1 − (1 − L)^n), with L about 31% on average, so five users find about 85% of problems; Nielsen's 2000 article made "test with five" a slogan [1].

**What the evidence says.** Nielsen's actual advice is to run several small tests (for example three rounds of five), redesigning between them, and to test 3 to 4 users per segment when audiences differ [1]. His 2012 guidance asks for about 20 users for quantitative studies, 15 per group for card sorting and 39 for stable eyetracking heatmaps [2]. Faulkner (2003) drew random groups from 60 test users: groups of five found 85% of problems on average but as few as 55%, and no group of twenty found fewer than 95% (figures via a secondary summary; abstract not opened) [3]. So five is a floor for one round of qualitative testing, not a guarantee of coverage and not a sample for measurement.

**What to do instead.** Test about five people per segment per round and iterate. Add users for distinct audiences and for high-severity risks. For metrics such as task time or success rate, use larger samples and report confidence intervals. Do not quote percentages from a sample of five. See MEA-01 (usability testing), MEA (task metrics).

**How to spot it in a review.** "We tested with 5 users, so the design is validated" after a single round; percentages reported from n = 5; or a demand for a 100-person panel before any first-round discovery test.

**Sources.**
[1] Nielsen, J. (2000-03-18). Why you only need to test with 5 users. Nielsen Norman Group (describes Nielsen & Landauer 1993). https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/
[2] Nielsen, J. (2012-06-03). How many test users in a usability study? Nielsen Norman Group. https://www.nngroup.com/articles/how-many-test-users/
[3] Faulkner, L. (2003). Beyond the five-user assumption: benefits of increased sample sizes in usability testing. Behavior Research Methods, Instruments, & Computers 35(3), 379-383. https://doi.org/10.3758/BF03195514 (figures via Wikipedia, Usability testing: https://en.wikipedia.org/wiki/Usability_testing)
