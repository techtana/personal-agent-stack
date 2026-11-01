# Choice architecture, persuasion and ethics (CHO)

This category covers how an interface sets defaults, frames options, shows prices and social signals, and handles consent and cancellation. Load it when auditing sign-up, checkout, subscription, consent and settings flows, or any screen built to change what a person chooses. Most rules here are backed by regulation (FTC, EU, UK, California, Germany) as well as experiments, so a violation is a legal risk as well as a trust risk. Legal status was checked on 2026-10-31 where a source could be opened; laws change, so re-check before advising on a specific market.

Source notes: "(snippet)" means we saw the source only in a search result. "(not opened)" means we could not open the page in this session. "Bibliographic details verified" means the citation was confirmed in Crossref but the paper was not read.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| CHO-01 | Set defaults in the user's interest | Strong | sign-up, checkout, settings, consent, onboarding |
| CHO-02 | Use social proof honestly | Moderate | product, listing and landing pages; ratings, reviews, counters, testimonials |
| CHO-03 | Show urgency and scarcity only when they are real | Strong | e-commerce, booking, ticketing, promotions, pricing pages |
| CHO-04 | Show the full price up front and compare options honestly | Strong | e-commerce, travel, tickets, subscriptions, pricing pages |
| CHO-05 | Make leaving as easy as joining | Strong | subscriptions, account settings, cookie banners, preference centers, data deletion |
| CHO-06 | Never use deceptive patterns | Strong | any conversion, consent, upsell or retention flow |
| CHO-07 | Explain why you need data at the moment you ask | Moderate | forms, permission prompts, onboarding, privacy settings |
| CHO-08 | Frame choices neutrally and comparably | Moderate | pricing tables, plan pickers, accept/decline dialogs, "was/now" prices, savings messages |

---

### CHO-01 Set defaults in the user's interest

**What it is.** Pre-select the option that is best for the person who never changes it: private, safe, reversible and fairly priced. Keep anything that mainly benefits the business (marketing, data sharing, paid add-ons, auto-upgrades) off until the user turns it on.

**Why it works.** Most people keep the default. Changing it takes effort, it reads as the designer's recommendation, and it becomes the status quo. Defaults work best when they signal endorsement or status quo [4].
- Johnson and Goldstein (2003) compared effective organ-donor consent in 11 European countries. Four explicit-consent (opt-in) countries ranged from 4.25% (Denmark) to 27.5% (Netherlands). Seven presumed-consent (opt-out) countries ranged from 85.9% (Sweden) to 99.98% (Austria). In their online experiment 42% consented under opt-in, 82% under opt-out and 79% when forced to choose [1].
- Real donations moved far less than registrations: the authors' regression put the effect at 14.1 to 16.4 donors per million (+16%) [2].
- Madrian and Shea (2001): at one US firm, 85.9% of employees hired under automatic 401(k) enrollment participated, against 37.4% of the cohort hired before the change (cohorts compared a year apart, not randomized) [3].
- A 2019 meta-analysis of 58 studies (n = 73,675) found d = 0.68 (95% CI 0.53 to 0.83) with wide variation. Defaults worked better in consumer than in environmental settings [4].
- GDPR Art. 25(2) requires that, by default, only data necessary for each purpose is processed [5]. On 1 October 2019 the CJEU ruled in Planet49 that a pre-ticked box is not valid consent to cookies, whether or not the data is personal [6].

**Evidence: Strong.** Replicated field and lab studies (2001 to 2019) and a 58-study meta-analysis; the legal parts are formal requirements.
Required: GDPR Art. 25(2) (data protection by default); GDPR Art. 7 with CJEU C-673/17 (no pre-ticked consent).

**Limitations.**
- A default anchors people. In Madrian and Shea's plan about three quarters of auto-enrolled participants stayed at the default 3% contribution, while about three quarters of earlier participants chose 6% or more [3]. A badly set default level can leave people worse off.
- Effects on registrations overstate effects on outcomes (the donation example), and results vary: some studies show null or negative effects [2][4].
- When preferences differ a lot and the stakes are high, forcing an active choice can beat any single default [8].
- The same mechanism serves manipulation. A default that benefits only the business is the "preselection" deceptive pattern (CHO-06). Mathur et al. counted 67 "pressured selling" instances (pre-selecting or pushing pricier variants) on 62 shopping sites [9].
- Inertia is not consent. EU law requires an active act for non-essential cookies and tracking, so "off until the user turns it on" is required there [6].

**How to measure it works.**
- Keep rate (share who never change the default) and revert rate (share who change it back within 30 days), from event logs. A good default has a low revert rate.
- A/B test default on, default off and active choice. Primary metric: the user's outcome (savings rate, setting retained, task success). Guardrails: complaints, refunds, support contacts, unsubscribes in week one.
- Lagging: refund and chargeback rate, regulator or app-store complaints.

**Implemented by.**
- A large US firm's 401(k) plan (1998): automatic enrollment at 3% in a money-market fund; participation 85.9% against 37.4% [3].
- Austria, France, Poland and other presumed-consent countries: 85.9% to 99.98% effective consent (registrations only) [1].
- Apple, iOS 14.5 (26 April 2021): tracking stays off until the user taps Allow. Flurry's early sample showed 4% opt-in in the US (2.5 million daily users) and 12% worldwide (5.3 million users); not a random sample [7].
- EU cookie banners since Planet49 (2019): non-essential cookies must start off [6].

**How to detect it.**
- *Applied:* optional, marketing and data-sharing controls start off or unchecked; the pre-selected plan fits the stated need; each non-obvious default has a one-line reason and a visible way to change it.
- *Violated:* pre-checked newsletter, partner-sharing or add-on boxes; the priciest plan pre-selected; "share my activity" on by default; a trial that converts to a paid plan with the box already ticked.
- *In code:* `<input type="checkbox" checked`, `defaultChecked`, `checked={true}`, `selected` on a premium `<option>`, `defaultValue="annual"`; Android `android:checked="true"`; SwiftUI `@State var optIn = true`; ad or analytics tags that fire before consent, such as `gtag('consent','default',{ad_storage:'granted'})` or tags in `<head>` with no consent gate.
- *Quick test:* open sign-up, checkout and settings in a clean profile and list every control that is on before you touch it. For each, ask who benefits if the user never changes it. Check the network tab for ad or analytics calls before any consent click.

**How to implement.**
1. List every pre-selected control in sign-up, checkout, onboarding and settings.
2. Make the option that protects or saves the user the default. Leave business-only items off, and start consent as denied: `gtag('consent','default',{ad_storage:'denied',analytics_storage:'denied'})`.
3. Where preferences differ and stakes are high (plan size, contribution rate, privacy tier), ask for an active choice between two or three plain options instead of setting a default.
4. Say "Recommended" only when it is true, and give the reason in one line. Make changing a default as easy as keeping it (CHO-05).
5. Test the default level, not just its existence: a 3% default anchored savings low [3]. Judge variants by the user's outcome, not your conversion.
6. Log keep and revert rates and review them each quarter.

**Sources.**
[1] Johnson, E. J., & Goldstein, D. (2003). Do defaults save lives? Science 302(5649), 1338-1339. https://www.dangoldstein.com/papers/DefaultsScience.pdf
[2] Johnson, E. J., & Goldstein, D. G. (2004). Defaults and donation decisions. Transplantation (copy of the paper). https://hods.org/pdf/Defaults%20and%20Donation%20Decisions.pdf
[3] Madrian, B. C., & Shea, D. F. (2001). The power of suggestion: inertia in 401(k) participation and savings behavior. Quarterly Journal of Economics 116(4), 1149-1187 (NBER WP 7682; figures from the working-paper tables). https://www.nber.org/papers/w7682
[4] Jachimowicz, J. M., Duncan, S., Weber, E. U., & Johnson, E. J. (2019). When and why defaults influence decisions: a meta-analysis of default effects. Behavioural Public Policy 3(2), 159-186. https://doi.org/10.1017/bpp.2018.43
[5] GDPR Art. 25, Data protection by design and by default. https://gdpr-info.eu/art-25-gdpr/
[6] Court of Justice of the EU (2019-10-01). Press release 125/19, Judgment in Case C-673/17, Planet49. https://curia.europa.eu/jcms/upload/docs/application/pdf/2019-10/cp190125en.pdf
[7] MacRumors (2021-05-07). Analytics suggest 96% of users leave app tracking disabled in iOS 14.5 (reports Flurry data). https://www.macrumors.com/2021/05/07/most-iphone-users-app-tracking-opt-out/ ; Flurry's method note: https://flurry.com/blog/att-opt-in-rate-monthly-updates (charts only; later-year rates not retrievable)
[8] Carroll, G. D., Choi, J. J., Laibson, D., Madrian, B. C., & Metrick, A. (2009). Optimal defaults and active decisions. Quarterly Journal of Economics 124(4), 1639-1674. https://doi.org/10.1162/qjec.2009.124.4.1639 (bibliographic details verified; argument not re-read)
[9] Mathur, A., et al. (2019). Dark patterns at scale: findings from a crawl of 11K shopping websites. Proc. ACM HCI 3(CSCW), Article 81. https://arxiv.org/abs/1907.07032

---

### CHO-02 Use social proof honestly

**What it is.** Show ratings, review counts, user counts and endorsements only when they are real, current and representative. Give enough detail (count, distribution, dates, verified status) for people to judge them.

**Why it works.** People use other buyers' choices as a shortcut for quality when they cannot judge a product themselves.
- Retailer data analyzed by the Spiegel Research Center (2017): a product with five reviews was 270% more likely to be bought than one with none. The lift was about 380% for higher-priced products and 190% for lower-priced ones [1].
- Purchase likelihood peaked at 4.0 to 4.7 stars and fell toward 5.0, which shoppers read as too good to be true. Verified-buyer badges raised purchase odds by 15%. Returns diminished after the first five reviews [1].
- Faking is regulated. The FTC final rule (announced 14 August 2024, 5-0 vote; effective 21 October 2024 [3]) bans fake or AI-generated reviews, paying for a chosen sentiment, undisclosed insider reviews, "independent" review sites a company controls, review suppression by threats, and buying fake followers or views. Civil penalties apply to knowing violations [2].
- EU: Annex I points 23b and 23c of Directive 2005/29/EC (added by Directive 2019/2161, applied from 28 May 2022) ban claiming reviews come from real buyers without reasonable checks, and posting or commissioning fake reviews [4]. UK: paragraph 13 of Schedule 20 to the DMCC Act 2024 (in force 6 April 2025) also bans hiding that a review was incentivized, or showing only positive reviews [5].
- The UK CMA opened an investigation of hotel booking sites on 27 October 2017. On 6 February 2019 Agoda, Booking.com, Expedia (with ebookers and Hotels.com) and trivago gave undertakings covering pressure-selling claims, discount claims, ranking disclosure and hidden charges. Changes were due by 1 September 2019 [6].

**Evidence: Moderate.** The size of the effect rests on observational retail data (2017) and field and lab studies. The ban on faking is a legal requirement.
Required: FTC rule banning fake reviews and testimonials (16 CFR Part 465, US; part number not checked against the source); Directive 2005/29/EC Annex I points 23b-23c (EU); DMCC Act 2024 Sch. 20 (UK).

**Limitations.**
- The 270% figure compares products with and without reviews in retailer data. It does not show that reviews cause sales: there was no randomized test, and the public page does not describe the retailers [1].
- Popularity cues can distort. In a music-market experiment, social influence made success more unequal and less predictable [7].
- Telling people the norm can backfire. In a household energy study, people already below the average used more once they saw it, until an approval message was added [8].
- Generated "activity" messages are deceptive. Mathur et al. found 313 activity notifications on 264 sites; 29 (on 20 sites) were falsely generated [9]. See CHO-03 and CHO-06.
- A perfect 5.0 average, missing dates and an absence of negative reviews lower trust [1]. Naming real customers in pop-ups raises privacy issues (CHO-07).

**How to measure it works.**
- Conversion and add-to-cart on pages with different review formats (position, distribution chart, verified badge). Never hide genuine reviews from a test group.
- Return and refund rate and post-purchase rating: if displayed ratings overstate quality, returns rise. Also the share of reviews from verified buyers, plus a sampled authenticity audit.
- Trust: a survey item such as "the reviews on this site are honest"; support contacts about fake reviews.

**Implemented by.**
- Agoda, Booking.com, Expedia group, trivago (2019): undertakings to the CMA on scarcity, discount and ranking claims; no conversion outcome published [6].
- Retailers in the Spiegel analysis (unnamed): verified-buyer labels; the result above is correlational [1]. Anecdote.

**How to detect it.**
- *Applied:* average plus count plus star distribution; review dates; a "verified purchase" label with a definition; negative reviews visible and sortable; incentivized reviews labeled; popularity counts state a window ("420 bought in the last 7 days").
- *Violated:* only 5-star quotes; undated testimonials with stock photos; identical praise across products; viewer counts that change at random; a "bestseller" badge on every item; "as seen on" logos with no source; review invitations sent only to happy customers.
- *In code:* `AggregateRating` or `Review` JSON-LD that does not match visible content or hard-codes `ratingValue`; `Math.random()` or `setInterval` driving counters; review text or names hard-coded in templates.
- *Quick test:* reload three times and watch live counters; sort reviews by lowest; compare the average with the visible distribution; look for dates and verified labels.

**How to implement.**
1. Collect reviews only from real customers. Invite every buyer, not only satisfied ones, and label verified purchases.
2. Show average, count and distribution. Keep negative reviews, allow sort by lowest, show dates.
3. Disclose incentives and moderation rules. Never pay for a chosen sentiment. Never suppress honest reviews.
4. Compute popularity counters server-side from real events, with a time window and a minimum threshold. Hide them when numbers are small.
5. Generate `AggregateRating` markup from the same data as the visible reviews.
6. Audit quarterly for duplicate or suspicious reviews.

**Sources.**
[1] Spiegel Research Center (2017). How online reviews influence sales. Northwestern University. https://spiegel.medill.northwestern.edu/How-Online-Reviews-Influence-Sales
[2] FTC (2024-08-14). Federal Trade Commission announces final rule banning fake reviews and testimonials. https://www.ftc.gov/news-events/news/press-releases/2024/08/federal-trade-commission-announces-final-rule-banning-fake-reviews-testimonials
[3] Manatt (2024). FTC issues final rule banning fake reviews and testimonials (effective date 2024-10-21) (snippet). https://manatt.com/insights/newsletters/client-alert/ftc-issues-final-rule-banning-fake-reviews-and-tes
[4] European Parliament and Council (2019). Directive (EU) 2019/2161, Article 3 (Annex I points 23b, 23c) and application date. https://eur-lex.europa.eu/eli/dir/2019/2161/oj
[5] UK Parliament (2024). Digital Markets, Competition and Consumers Act 2024, Schedule 20. https://www.legislation.gov.uk/ukpga/2024/13/schedule/20
[6] CMA. Online hotel booking (case page: investigation opened 2017-10-27, undertakings 2019-02-06). https://www.gov.uk/cma-cases/online-hotel-booking
[7] Salganik, M. J., Dodds, P. S., & Watts, D. J. (2006). Experimental study of inequality and unpredictability in an artificial cultural market. Science 311, 854-856. https://doi.org/10.1126/science.1121066 (bibliographic details verified; findings not checked against the source)
[8] Schultz, P. W., Nolan, J. M., Cialdini, R. B., Goldstein, N. J., & Griskevicius, V. (2007). The constructive, destructive, and reconstructive power of social norms. Psychological Science 18(5), 429-434. https://doi.org/10.1111/j.1467-9280.2007.01917.x (bibliographic details verified; findings not checked against the source)
[9] Mathur, A., et al. (2019). Dark patterns at scale. Proc. ACM HCI 3(CSCW), Article 81. https://arxiv.org/abs/1907.07032

---

### CHO-03 Show urgency and scarcity only when they are real

**What it is.** Show countdown timers, "only N left", "N people viewing" and "ends today" only when they come from a real constraint (a deadline in the pricing system, a stock count, a seat hold), and show the real deadline or number.

**Why it works.** Limited time or supply raises perceived value and speeds decisions.
- A meta-analysis of 131 studies (416 effect sizes) found scarcity cues raise purchase intentions (δ = 0.31; 193 effect sizes, N = 22,655). Demand-based cues worked best for utilitarian products, supply-based cues for experiences and time-based cues for high-involvement products. Most studies measure intention, not sales [1].
- Fake cues are common. Mathur et al. (2019) crawled about 11,000 shopping sites (53,000 product pages) and found 1,818 dark-pattern instances on 1,254 sites (11.1%). Of 393 countdown timers on 361 sites, 157 (on 140 sites) were deceptive: the timer reset, or the offer stayed valid after it ended. Of 632 low-stock messages, 17 (on 17 sites) showed stock numbers that were generated, 16 of them counting down on a fixed schedule. 22 third-party vendors sold such features [2].
- In Luguri and Strahilevitz's second experiment, "must act now" messages did not make people more likely to buy a costly service, while hidden information, trick questions and obstruction did [3]. Fake urgency risks harm for little gain.
- The law treats false limited-time claims as unfair in all circumstances: Annex I point 7 of the EU Unfair Commercial Practices Directive [4] and paragraph 7 of Schedule 20 to the UK DMCC Act 2024 (in force 6 April 2025) [5]. The FTC lists fake countdown timers among misleading dark patterns (September 2022 report) [6].

**Evidence: Strong.** A 131-study meta-analysis (2022), a large crawl (2019) and binding rules.
Required: Directive 2005/29/EC Annex I point 7 (EU); DMCC Act 2024 Sch. 20 para 7 (UK); FTC Act Section 5 (US).

**Limitations.**
- The meta-analysis is mostly lab and hypothetical scenarios. Field lift is unproven and probably smaller [1].
- Suspected manipulation backfires. Aggressive dark patterns raised anger and drop-out in Luguri and Strahilevitz (65 drop-outs against 9 under mild patterns) [3]. The meta-analysis lists reactance as a competing mechanism [1].
- Real constraints are fine: seat or cart holds, real flash-sale end times, true stock. The failure is fake or unexplained timers.
- Countdowns can lock out people who need more time. WCAG 2.2 SC 2.2.1 (Level A) requires a way to turn off, adjust or extend a time limit unless it is essential or part of a real-time event [8]. See A11Y.
- Mathur's counts are a lower bound: text interfaces on sampled pages only [2].
- Overlaps: CHO-06 (fake timers are deceptive patterns), CHO-02 (viewer counts), ERR (timeouts that lose work).

**How to measure it works.**
- Honesty audit: share of timers that reset on reload or in a private window (target 0%), stock numbers matching inventory (target 100%), offers honored after the timer reaches zero (target 0 exceptions).
- Effect: conversion lift of real urgency against none in an A/B test. Guardrails: refund rate, complaints, return-visit cart abandonment, repeat purchase.
- Lagging: chargebacks, consumer-group or regulator complaints.

**Implemented by.**
- Booking.com, Expedia group, Agoda, trivago (6 February 2019): undertakings to the CMA to change practices that may mislead, including claims about rooms left and how many people were viewing a room [7]. The case page does not give each undertaking's terms.
- No company with a published, controlled test of real-only urgency was found.

**How to detect it.**
- *Applied:* deadline shown as date, time and zone; the timer persists across reloads and devices and the price actually changes at zero; low-stock labels use the same count for everyone and match the cart limit; holds are explained ("We hold your seats for 10 minutes").
- *Violated:* timer resets on reload or in a private window; offer still valid at 00:00; the same "sale ends in" for weeks; "Only 2 left" on every product; "limited time" with no date; random "N people are viewing"; urgency on unlimited digital goods.
- *In code:* deadlines computed in the browser at load (`Date.now() + 15*60*1000`, `localStorage.setItem('timerEnd'`); `Math.random()` in counters; hard-coded "Only 3 left" strings; third-party urgency widgets loaded by script tag.
- *Quick test:* note the timer, reload, open a private window, wait for zero, then try to buy at the old price. Add more than "N left" to the cart.

**How to implement.**
1. Store each constraint as server data: an end timestamp in UTC, a stock count, a hold time-to-live.
2. Render from the server timestamp (`<time data-ends-at="2026-11-30T23:59:59Z">`) and enforce it on the server so the price changes at zero.
3. Show scarcity only below a real threshold (for example stock of 5 or fewer) and use the true number.
4. Let users pause or extend timers (WCAG 2.2.1) and state the deadline in text for screen readers.
5. If no real constraint exists, remove the element and state the product's value instead.
6. Log shown values against enforced values and audit them.

**Sources.**
[1] Barton, B. L., Zlatevska, N., & Oppewal, H. (2022). Scarcity tactics in marketing: a meta-analysis of product scarcity effects on consumer purchase intentions. Journal of Retailing 98(4), 741-758. https://pure.bond.edu.au/ws/portalfiles/portal/182976505/Scarcity_tactics_in_marketing.pdf
[2] Mathur, A., Acar, G., Friedman, M., Lucherini, E., Mayer, J., Chetty, M., & Narayanan, A. (2019). Dark patterns at scale: findings from a crawl of 11K shopping websites. Proc. ACM HCI 3(CSCW), Article 81. https://arxiv.org/pdf/1907.07032
[3] Luguri, J., & Strahilevitz, L. J. (2021). Shining a light on dark patterns. Journal of Legal Analysis 13(1), 43-109. https://academic.oup.com/jla/article/13/1/43/6180579
[4] Directive 2005/29/EC, Annex I point 7 (text via legislation.gov.uk) (snippet). https://www.legislation.gov.uk/eudr/2005/29/annex/I/adopted
[5] UK Parliament (2024). Digital Markets, Competition and Consumers Act 2024, Schedule 20, paragraph 7 (commencement 2025-04-06 by S.I. 2025/272). https://www.legislation.gov.uk/ukpga/2024/13/schedule/20
[6] FTC (2022-09-15). FTC report shows rise in sophisticated dark patterns designed to trick and trap consumers. https://www.ftc.gov/news-events/news/press-releases/2022/09/ftc-report-shows-rise-sophisticated-dark-patterns-designed-trick-trap-consumers
[7] CMA. Online hotel booking (case page). https://www.gov.uk/cma-cases/online-hotel-booking
[8] W3C. Understanding SC 2.2.1 Timing Adjustable (WCAG 2.2, Level A). https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html

---

### CHO-04 Show the full price up front and compare options honestly

**What it is.** The first price a person sees includes every mandatory fee (service, cleaning, resort, booking, unavoidable delivery). Optional items appear separately and unchecked. Plans and options are compared on the same basis.

**Why it works.** Drip pricing (revealing fees step by step) exploits commitment: people who have invested effort accept later charges.
- A field experiment on StubHub (Blake, Moshary, Sweeney and Tadelis) found that showing the full price up front reduced both the quantity and the quality of tickets bought. The effect persisted for experienced users, and lower quality explained at least 28% of the revenue drop [1].
- Baymard's list (updated 22 September 2025; about 70.2% average documented abandonment across 50 studies) puts "extra costs too high" first among abandonment reasons at 40%, with "total order cost not visible up front" at 12%. Earlier Baymard surveys reported a higher extra-cost share (47 to 48% in 2023, secondary report) [2].
- US FTC Rule on Unfair or Deceptive Fees (16 CFR Part 464, per a search summary; announced 17 December 2024, 4-1 vote; effective 12 May 2025). For live-event tickets and short-term lodging, the total price including all mandatory fees must be clear and the most prominent price, and no fee may be misrepresented. The FTC estimates up to 53 million hours a year saved [3].
- Airbnb offered an optional total-price toggle from late 2022 and made total price (before taxes in most places) the default for all search results in April 2025, ahead of the FTC rule [4].
- Decoys: adding a clearly worse third option raised the share of the option it resembled in Huber, Payne and Puto (1982) [5]. Frederick, Lee and Baskin (2014) found the effect appears mainly with stylized numeric descriptions, not when people experience products or when one attribute is perceptual, and they question its practical value [6].

**Evidence: Strong.** A field experiment (2018), a binding rule (2025) and practitioner research (Baymard, 2025). The decoy sub-claim is Mixed.
Required: FTC 16 CFR Part 464 (tickets and lodging, from 2025-05-12).

**Limitations.**
- Honest totals can lower short-run sales when competitors hide fees: StubHub buyers bought fewer and cheaper tickets [1]. Platform or regulatory parity matters.
- Some amounts cannot be known up front (tax by address, shipping by destination). The FTC rule lets sellers leave out such charges only if their nature, purpose and amount are disclosed before the buyer agrees to pay [3].
- The FTC rule covers only tickets and lodging. Other sectors fall under general deception law case by case [3]. Other regions have their own price-display rules, which we did not verify.
- A total can still mislead when units differ (per night against per stay, per person against per room). See CHO-08.
- Treat decoys as unreliable [5][6]. Using one to steer people to a costlier tier is manipulation (CHO-06).

**How to measure it works.**
- Price-shock drop: share of users who leave right after the total first appears; compare all-in against drip variants.
- Net revenue after refunds, cancellations and chargebacks; support contacts about fees; a post-purchase question "was the final price what you expected?".
- Comprehension: ask five test users to state the total they will pay after the listing page (target: all correct).

**Implemented by.**
- StubHub (US, field experiment): all-in price display lowered quantity and quality purchased [1].
- Airbnb: optional total-price toggle (late 2022), default total price in search worldwide (April 2025). Earlier regional defaults existed; no conversion outcome published that we found [4] (snippet).
- US ticket and lodging sellers, since 12 May 2025 [3].

**How to detect it.**
- *Applied:* the listing price already includes mandatory fees ("$212 total incl. fees"); a breakdown opens on tap; the number does not change between listing, cart and payment; optional extras unchecked; taxes marked "plus tax" early.
- *Violated:* "from $59" becomes $87 at the last step; "service fee", "cleaning fee", "resort fee" or "processing fee" appear only after card entry; the total is set in smaller type than the base price; comparison tables hide the cheapest option or omit rows for some plans.
- *In code:* fee line items (`serviceFee`, `resortFee`, `convenienceFee`) computed only in checkout components; `Offer.price` in JSON-LD without mandatory fees; price components that read `basePrice` and never `totalPrice`; CSS where the total has a smaller `font-size` than the base price.
- *Quick test:* run the purchase flow to the payment step, screenshot every step, compare the first price with the final total and count the steps where the number changes.

**How to implement.**
1. Compute `total_mandatory = base + all mandatory fees` on the server and show it wherever a price appears (search, listing, ad, cart, email).
2. Show the breakdown on demand, keep the total most prominent, and label optional extras as optional and unchecked.
3. For location-dependent amounts, show a shipping and tax estimate early and state its basis.
4. Build comparison tables from one data model, with the same rows and units for every plan. Include the cheapest viable plan. Do not add dummy options.
5. A/B test all-in against base-only on net revenue after refunds and complaints, not on click-through.
```json
{ "price": { "total": 212.00, "currency": "USD", "includes": ["base", "cleaning_fee", "service_fee"], "excludes": ["tax"] } }
```

**Sources.**
[1] Blake, T., Moshary, S., Sweeney, K., & Tadelis, S. (2018). Price salience and product choice. NBER Working Paper 25186. https://www.nber.org/papers/w25186
[2] Baymard Institute (updated 2025-09-22). Cart abandonment rate statistics. https://baymard.com/lists/cart-abandonment-rate
[3] FTC (2024-12-17). Federal Trade Commission announces bipartisan rule banning junk ticket and hotel fees. https://www.ftc.gov/news-events/news/press-releases/2024/12/federal-trade-commission-announces-bipartisan-rule-banning-junk-ticket-hotel-fees ; effective date: FTC (2025-05). FTC Rule on Unfair or Deceptive Fees to take effect on May 12, 2025 (snippet). https://www.ftc.gov/news-events/news/press-releases/2025/05/ftc-rule-unfair-or-deceptive-fees-take-effect-may-12-2025
[4] AP via Local10 (2025-04-21). Airbnb to display total prices by default (headline only opened; details from search summaries) (snippet). https://www.local10.com/news/national/2025/04/21/airbnb-to-display-total-prices-by-default ; Skift (2022). Airbnb debuts total prices before taxes with plan to make it default view (snippet). https://skift.com/?p=544891
[5] Huber, J., Payne, J. W., & Puto, C. (1982). Adding asymmetrically dominated alternatives. Journal of Consumer Research 9(1), 90-98. https://doi.org/10.1086/208899
[6] Frederick, S., Lee, L., & Baskin, E. (2014). The limits of attraction. Journal of Marketing Research 51(4), 487-507. https://doi.org/10.1509/jmr.12.0061

---

### CHO-05 Make leaving as easy as joining

**What it is.** Let people cancel a subscription, withdraw consent, refuse cookies or delete an account in the channel they used to join, in no more steps than joining took, with no guilt screens. Confirm the result in writing.

**Why it works.** This rule rests less on a persuasion effect than on law, enforcement and friction research.
- GDPR Art. 7(3): withdrawing consent must be as easy as giving it [1].
- ROSCA (US, 2010; 15 U.S.C. 8403): before taking billing details, clearly disclose all material terms of an online negative-option offer, get express informed consent, and provide simple ways to stop recurring charges [2].
- FTC v. Amazon (W.D. Wash.): the June 2023 complaint alleged dark patterns in Prime sign-up and a multi-page cancellation flow Amazon called "Iliad". On 25 September 2025 Amazon settled for USD 2.5 billion: a USD 1 billion civil penalty (the largest in an FTC rule-violation case) and USD 1.5 billion in refunds for an estimated 35 million people. It must add a clear button to decline Prime, disclose material terms, and let people cancel by the method they used to sign up. There was no admission of wrongdoing. In September 2026 a revised order raised the per-person maximum from USD 51 to USD 200; more than USD 845 million had been paid [3].
- FTC "click-to-cancel" amendments to the Negative Option Rule: final rule announced 16 October 2024; the Eighth Circuit vacated it on 8 July 2025 on procedural grounds (snippet). The FTC announced an advance notice of proposed rulemaking on 11 March 2026 (docket FTC-2026-0265); its page lists no proposed rule yet [4]. ROSCA and FTC Act Section 5 remain enforceable.
- California AB 2863 (chaptered 24 September 2024; contracts made, amended or extended from 1 July 2025): separate express consent to auto-renewal; cancellation through the medium used to sign up, so online sign-up needs a prominent online cancel link or button; annual reminders; price-change notices 7 to 30 days ahead [5].
- Germany, §312k BGB (since 1 July 2022): online sellers of continuing consumer contracts must show a button labeled "Verträge hier kündigen" leading to a confirmation page with a "jetzt kündigen" button, and must confirm receipt at once in text form. Without the button, the consumer can cancel at any time without notice [6].
- Cookies: the CNIL fined Google (EUR 150 million) and Facebook (EUR 60 million) on 6 January 2022 because refusing cookies took more steps than accepting them (figures not checked against the source; the CNIL page is no longer available) [7]. Nouwens et al. (2020) scraped consent pop-ups on 680 UK sites: only 11.8% met minimal EU requirements. In a field experiment (n = 40), removing "reject" from the first layer raised consent by 22 to 23 percentage points [8].

**Evidence: Strong.** Binding law in several jurisdictions, a USD 2.5 billion enforcement outcome and a field experiment on consent banners.
Required: GDPR Art. 7(3); ROSCA 15 U.S.C. 8403 (US); California Automatic Renewal Law as amended by AB 2863; §312k BGB (Germany).

**Limitations.**
- A retention offer is acceptable when it is skippable with one clear button. Multi-page save flows are what the FTC attacked. Amazon's order requires cancellation that is not difficult, costly or time-consuming [3].
- Security checks (re-authentication) are legitimate when they take one step. Do not use them as friction.
- US federal rule status is unsettled (vacated 2025, rulemaking restarted 2026). State laws and ROSCA still apply, and rules differ by country, so check the market.
- Nouwens et al. used 40 participants in 2020; the direction matches the CNIL's findings, but the effect size is uncertain [8].
- "Pause" or "downgrade" offers are fine as extras, not as replacements for cancel.
- Overlaps: CHO-01 (defaults), CHO-06 (obstruction, forced continuity).

**How to measure it works.**
- Steps and time to cancel compared with sign-up (target: equal or fewer); self-service cancel completion rate; cancellation-related contacts; complaints, refunds and chargebacks after cancel.
- Cookie banner: click parity (accept and reject in the same number of clicks), share of visitors who reject, time to reject.
- Test: ask five users to cancel the plan and to withdraw a consent from a logged-in state (target: all succeed unaided in under two minutes).

**Implemented by.**
- Amazon (2025 order): decline-Prime button, same-method cancellation, independent supervisor of refunds [3].
- German online sellers (from 1 July 2022): the cancellation button and confirmation page [6].
- Google and Facebook (2022): fined over cookie refusal; the changes they made were not verified [7].

**How to detect it.**
- *Applied:* "Cancel subscription" within two clicks of the account page; one screen stating what happens and the end date; one confirm button labeled with the action; an email confirmation; a cookie banner with equal-weight "Accept all" and "Reject all" on the first layer; a persistent "Cookie settings" link that lets users change or withdraw consent.
- *Violated:* "call us to cancel" for an online sign-up; cancellation behind many screens or chat only; guilt copy on the cancel path; the "Keep my plan" button large and the cancel link grey; cookie refusal behind "Manage options", toggles and "Save"; a cookie wall; withdrawal of consent by email only.
- *In code:* compare route and screen counts of the sign-up and cancel flows; grep for `cancel`, `unsubscribe`, `delete-account`; accept and reject buttons with different classes (`btn-primary` against `btn-link`); CMP config such as `rejectAll: false`; consent stored in `localStorage` with no code path that changes it.
- *Quick test:* sign up, then time how long it takes to cancel from the logged-in state; click reject-all on the banner; try to withdraw consent later and see whether you find the control within 30 seconds.

**How to implement.**
1. Put "Cancel subscription" in Account > Billing and in every receipt email; keep the same channel as sign-up.
2. Flow: the user is already identified; show one screen with the effect and end date; allow one optional, skippable offer or survey; one confirm button labeled "Cancel subscription"; then a confirmation page and email with the date.
3. Honor the cancel at once. Keep access until the period ends and do not charge after confirmation.
4. Cookie banner, first layer: "Accept all", "Reject all" (equal weight), "Manage choices". No pre-ticked boxes. A persistent link to change or withdraw later.
```html
<button class="btn">Accept all</button> <button class="btn">Reject all</button> <button class="btn">Manage choices</button>
```
5. Run a "cancel the plan" usability test every release of the flow.

**Sources.**
[1] GDPR Art. 7, Conditions for consent. https://gdpr-info.eu/art-7-gdpr/
[2] Restore Online Shoppers' Confidence Act, 15 U.S.C. 8403. https://www.law.cornell.edu/uscode/text/15/8403
[3] FTC (2025-09-25). FTC secures historic $2.5 billion settlement against Amazon. https://www.ftc.gov/news-events/news/press-releases/2025/09/ftc-secures-historic-25-billion-settlement-against-amazon ; FTC (2023-06-21). FTC takes action against Amazon for enrolling consumers in Prime without consent and sabotaging their attempts to cancel. https://www.ftc.gov/news-events/news/press-releases/2023/06/ftc-takes-action-against-amazon-enrolling-consumers-amazon-prime-without-consent-sabotaging-their ; FTC (2026-09-17). Additional payments from the Amazon Prime settlement. https://www.ftc.gov/news-events/news/press-releases/2026/09/ftc-announces-additional-payments-consumers-stemming-ftcs-amazon-prime-settlement
[4] FTC. Negative Option Rule (rule page with timeline). https://www.ftc.gov/legal-library/browse/rules/negative-option-rule ; Eighth Circuit vacatur of 2025-07-08: Bass Berry & Sims (2025) (snippet). https://www.bassberry.com/news/eighth-circuit-vacates-ftcs-click-to-cancel-rule/
[5] California Legislature (2024). AB 2863, Automatic renewal and continuous service offers (via CalMatters Digital Democracy). https://calmatters.digitaldemocracy.org/bills/ca_202320240ab2863
[6] Bürgerliches Gesetzbuch §312k. https://www.gesetze-im-internet.de/bgb/__312k.html ; start date 2022-07-01: German Wikipedia, Kündigungsbutton (secondary). https://de.wikipedia.org/wiki/K%C3%BCndigungsbutton
[7] CNIL (2022-01-06). Cookies: the CNIL fines Google and Facebook (page no longer available when tried; not re-verified). https://www.cnil.fr/en/cookies-cnil-fines-google-total-150-million-euros-and-facebook-60-million-euros-non-compliance
[8] Nouwens, M., Liccardi, I., Veale, M., Karger, D., & Kagal, L. (2020). Dark patterns after the GDPR: scraping consent pop-ups and demonstrating their influence. CHI 2020. https://doi.org/10.1145/3313831.3376321

---

### CHO-06 Never use deceptive patterns

**What it is.** A deceptive (dark) pattern is an interface design that tricks, pressures or traps users into choices they would not otherwise make. Do not ship one. Truthful persuasion that is easy to decline is fine (CHO-01 to CHO-04, CHO-08).

**Why it works (for the deceiver) and why it fails.**
- Luguri and Strahilevitz (2021), Study 1 (1,963 US adults; 1,762 in the acceptance analysis): acceptance of a dubious paid service was 11.3% in the control group, 25.8% under mild patterns and 41.9% under aggressive patterns [1].
- Backlash: aggressive patterns produced worse mood (3.94 against 2.96 for control), more anger and 65 drop-outs against 9 under mild patterns. Less-educated people were more susceptible to mild patterns [1].
- Study 2 (3,777 adults): hidden information roughly doubled acceptance (14.8% to 30.1%); a trick question raised it from 19.2% to 33.4%; raising the price from USD 8.99 to USD 38.99 a month made no significant difference [1].
- Prevalence: of about 11,000 shopping sites, 1,254 (11.1%) showed at least one of 1,818 patterns; 183 sites used outright deceptive ones [2].
- Taxonomies: Brignull coined "dark patterns" on 28 July 2010; deceptive.design now lists 18 types [4]. Gray et al. (2018) grouped patterns as nagging, obstruction, sneaking, interface interference and forced action (categories not checked against the source) [3]. The FTC staff report (15 September 2022) names four common types: disguised ads and fake timers, hard-to-cancel subscriptions, buried terms and junk fees, and tricks that capture personal data [5].
- Law: EU DSA Art. 25 (applies from 17 February 2024) bars online platforms from interfaces that deceive or manipulate users or distort free, informed choice; practices already covered by the UCPD or GDPR fall under those laws [6]. FTC v. Epic Games (19 December 2022): USD 245 million in refunds for dark patterns (one-press purchases, confusing buttons, hidden cancel and refund options, lockouts for disputing charges) plus a USD 275 million COPPA penalty [7].

**Evidence: Strong.** Two large controlled experiments (2021), a crawl of 11,000 sites (2019) and repeated enforcement actions.
Required: EU DSA Art. 25 and UCPD Annex I; FTC Act Section 5 and ROSCA (US).

**Limitations.**
- Not every nudge is a dark pattern. Truthful emphasis with an equal-weight decline option is persuasion. Legal definitions differ by jurisdiction.
- Acceptance rate overstates value: backlash, drop-outs, refunds and regulatory cost are missing from the conversion number [1][7].
- The experiments used a made-up offer in an online panel; the crawl saw text patterns on sampled pages only and is a lower bound [2].
- Mild patterns produced no measurable mood backlash, which may be why they persist [1]. Audit for them anyway.
- Overlaps: CHO-01 (preselection), CHO-02 (fake social proof), CHO-03 (fake urgency), CHO-04 (hidden costs), CHO-05 (obstruction, forced continuity).

**How to measure it works.**
- Pattern audit: number of patterns in each conversion, consent and cancellation flow (target 0).
- Comprehension: five users per flow answer "what did you just agree to, and what will it cost?" (target: all correct).
- Regret signals: cancellation or refund within 48 hours of the first charge, chargebacks, complaints per 1,000 users, store reviews that say "can't cancel". Compare variants on regret as well as conversion.

**Implemented by.** Counter-examples from enforcement (allegations unless stated):
- Epic Games (2022): one-press purchases from saved cards; FTC order above [7].
- Amazon Prime (2023 to 2025): settled for USD 2.5 billion; see CHO-05.
- Named in the FTC report: ABCmouse (hard cancellation despite promising easy cancellation), LendingClub ("no hidden fees" claim with hidden fees), Vizio (default sharing of viewing data), Effen Ads (fake news-outlet sender lines) [5].
- No company with a published conversion result for removing patterns was found.

**How to detect it.** Per-pattern list:

| Pattern | What you see | Code or flow cue |
|---|---|---|
| Confirmshaming | Decline text shames the user ("No thanks, I don't like saving money"); decline styled as faint grey text | self-deprecating or guilt strings on the decline control; accept is `btn-primary`, decline `btn-link` |
| Trick questions | Double negatives; checkbox meaning flips between questions in one form | labels with "not" or "don't" beside `checked`; one form mixing "tick to receive" and "tick to opt out" |
| Sneak into basket | Cart count rises, or a donation, insurance or warranty appears, though the user added nothing | add-to-cart called on load or route change with no click handler; pre-filled add-on lines in totals |
| Nagging | The same prompt returns after "Not now" (rate us, notifications, upgrade) | modals reopened by `setTimeout` or on every route; dismissal not stored; no "Don't ask again" |
| Disguised ads | Ads styled as content, navigation or download buttons; a tiny or low-contrast "Sponsored" label | ad containers with content-like class names; no `rel="sponsored"`; label fails WCAG 1.4.3 contrast |
| Hidden costs | Fees first appear at the last step | fee fields computed only in the payment component (CHO-04) |
| Forced continuity | Free trial turns into a paid plan with no reminder; card required for a "free" trial | trial-end job charges with no reminder job; billing page lacks the renewal date (CHO-05) |
| Preselection | Add-ons, premium plans or consent boxes already ticked | `checked`, `defaultChecked`, `selected` on the business-favored option (CHO-01) |
| Obstruction | Cancel, opt-out or delete takes more steps than sign-up, or needs a call or chat | cancel flow with more routes than sign-up; "contact support" as the only path (CHO-05) |

- *Applied:* each pattern above absent; decline, cancel and reject controls as visible as accept; fees and renewal terms shown before commitment.
- *Quick test:* in every flow, decline, cancel and opt out and time each; read the decline label aloud; start a free trial and look for the renewal date and a reminder.

**How to implement.**
1. Run the nine-pattern checklist on every conversion, consent and cancellation flow, and record the result in the design review.
2. Replace shaming copy with neutral labels ("No thanks", "Keep free plan").
3. Give decline, cancel and reject the same visual weight and reachability as accept (CHO-05, CHO-08).
4. Ask once and respect "no": store the dismissal and do not re-prompt for a set period.
5. Show fees and renewal terms before commitment (CHO-04); leave opt-ins unchecked (CHO-01); send a reminder before a trial converts.
6. Add a legal and design-ethics review for any flow where a variant wins mainly by lowering comprehension.

**Sources.**
[1] Luguri, J., & Strahilevitz, L. J. (2021). Shining a light on dark patterns. Journal of Legal Analysis 13(1), 43-109. https://academic.oup.com/jla/article/13/1/43/6180579
[2] Mathur, A., Acar, G., Friedman, M., Lucherini, E., Mayer, J., Chetty, M., & Narayanan, A. (2019). Dark patterns at scale. Proc. ACM HCI 3(CSCW), Article 81. https://arxiv.org/pdf/1907.07032
[3] Gray, C. M., Kou, Y., Battles, B., Hoggatt, J., & Toombs, A. L. (2018). The dark (patterns) side of UX design. CHI 2018. https://doi.org/10.1145/3173574.3174108 (bibliographic details verified; categories not checked against the source)
[4] deceptive.design, Types of deceptive design. https://www.deceptive.design/types ; Wikipedia, Dark pattern (coining date 2010-07-28; secondary). https://en.wikipedia.org/wiki/Dark_pattern
[5] FTC (2022-09-15). FTC report shows rise in sophisticated dark patterns designed to trick and trap consumers (staff report "Bringing Dark Patterns to Light"). https://www.ftc.gov/news-events/news/press-releases/2022/09/ftc-report-shows-rise-sophisticated-dark-patterns-designed-trick-trap-consumers
[6] Regulation (EU) 2022/2065 (Digital Services Act), Art. 25 and Art. 93. https://www.eu-digital-services-act.com/Digital_Services_Act_Article_25.html ; https://www.eu-digital-services-act.com/Digital_Services_Act_Article_93.html
[7] FTC (2022-12-19). Fortnite video game maker Epic Games to pay more than half a billion dollars over FTC allegations. https://www.ftc.gov/news-events/news/press-releases/2022/12/fortnite-video-game-maker-epic-games-pay-more-half-billion-dollars-over-ftc-allegations

---

### CHO-07 Explain why you need data at the moment you ask

**What it is.** Ask for each piece of personal data or device permission when the user reaches the feature that needs it, and give a one-line reason and benefit right there, with a link to details. Ask only for what you need, and let people refuse without losing unrelated features.

**Why it works.** People accept requests that fit the task they are doing and resist ones that do not. Unexpected data use also lowers trust.
- A field study of 36 Android users (27 million logged data points, 2015): at least 80% of participants would have blocked at least one permission request, and they wanted to block more than a third of all requests. The authors suggest prompting only where users would want to decide [1].
- Baymard's list (updated 22 September 2025): 19% of shoppers who abandoned a checkout did not trust the site with their card details [2]. A 2023 Baymard survey also gave 19% (snippet).
- GDPR Art. 13(1) requires the controller to give identity, purposes, legal basis, recipients and transfer information "at the time when personal data are obtained" [3].
- Android guidance: ask in context, when the user starts the feature; show your own rationale before the system dialog; let the user decline; keep the app working after a denial; do not nag [4].
- Apple requires app privacy details in App Store Connect for new apps and updates (data types, purposes, linked to identity, used for tracking) [5]. Google Play requires a Data safety form: opened to developers in October 2021, expected to appear for users from late April 2022, required complete for all apps after 20 July 2022 [6].

**Evidence: Moderate.** One field study (2015), consistent platform guidance and a legal timing duty for the information. We found no controlled test of the explanation text itself.
Required: GDPR Art. 13(1) (information at collection) and Art. 25(2) (only necessary data).

**Limitations.**
- A "why" screen can be used to push consent. Use it to inform, and do not re-ask after a refusal (see ONB on permission priming).
- Too many notices cause fatigue. Use short text at the point of need and layer detail behind a link.
- Vague reasons ("to improve your experience") do not meet Art. 13 and do not build trust.
- Labels in stores (Apple, Google) describe the app at install time. They complement, and do not replace, an in-context explanation. Their accuracy depends on developers [5][6].
- The best fix is often to ask for less. See FRM (fewer fields).

**How to measure it works.**
- Permission grant rate when asked in context against at launch (A/B), and the share of users who uninstall or complain after a prompt.
- Field-level abandonment and error rate on forms with and without "why" text.
- A survey item such as "I understood why the app asked for this" (target: most agree); privacy complaints.
- Audit: share of data fields and permissions with a stated purpose (target 100%).

**Implemented by.**
- Android runtime permissions with rationale API and in-context guidance [4].
- Apple App Privacy Details (the store "nutrition label"; Apple required the labels from December 2020) and Google Play Data safety (2021 to 2022) [5][6]. Neither source we opened gave an outcome measure.

**How to detect it.**
- *Applied:* each sensitive field or permission has a one-line reason beside it ("We use your phone number only to text delivery updates"); the camera, location or notification prompt appears after the user taps the related feature; optional fields marked optional; separate consent per purpose.
- *Violated:* a stack of permission prompts at first launch; "Allow notifications?" before any content; location permission on start for an app that does not need it; a required phone number with no reason; one checkbox bundling several purposes; a generic purpose string.
- *In code:* `requestWhenInUseAuthorization()` or `requestPermissions` called at app start (`didFinishLaunching`, `onCreate`); web `Notification.requestPermission()` or `navigator.geolocation.getCurrentPosition()` called on page load, not from a click handler; iOS `NS…UsageDescription` strings that are generic; `<input type="tel" required>` with no helper text or `aria-describedby`.
- *Quick test:* start from a clean install or profile and count prompts before the first useful action. For every field, check whether you can state the reason from the screen alone.

**How to implement.**
1. Inventory every field and permission. Write purpose, benefit and retention in one line each, and delete what you cannot justify.
2. Put the reason beside the field (helper text linked with `aria-describedby`) and in the permission rationale.
3. Trigger system prompts only from a user gesture tied to the feature.
```js
scanButton.addEventListener('click', () => navigator.mediaDevices.getUserMedia({ video: true }));
```
4. If the user declines, degrade gracefully, do not re-prompt, and offer a path to settings only in the feature's own context.
5. Keep store labels and the privacy policy in step with the app; review them when SDKs change.

**Sources.**
[1] Wijesekera, P., et al. (2015). Android permissions remystified: a field study on contextual integrity. USENIX Security 2015. https://www.usenix.org/conference/usenixsecurity15/technical-sessions/presentation/wijesekera
[2] Baymard Institute (updated 2025-09-22). Cart abandonment rate statistics. https://baymard.com/lists/cart-abandonment-rate
[3] GDPR Art. 13, Information to be provided where personal data are collected from the data subject. https://gdpr-info.eu/art-13-gdpr/
[4] Android Developers. Request runtime permissions. https://developer.android.com/training/permissions/requesting
[5] Apple. App privacy details on the App Store. https://developer.apple.com/app-store/app-privacy-details/
[6] Google Play Console Help. Provide information for Google Play's Data safety section. https://support.google.com/googleplay/android-developer/answer/10787469

---

### CHO-08 Frame choices neutrally and comparably

**What it is.** Show the same facts for every option in the same format (unit, period, order, visual weight) and use neutral wording. Use gain or loss framing and social comparison only where they help the user reach the user's own goal, and use only real reference prices.

**Why it works.** The way a choice is described changes what people choose, even when the facts are identical.
- Tversky and Kahneman (1981): the same disease-outcome problem described as lives saved led 72% to choose the sure option; described as lives lost, 78% chose the gamble [1].
- The gain/loss framing problem was one of 13 effects in the Many Labs 1 replication project (36 samples, 6,344 participants), where 10 effects replicated [2] (per-effect result not re-checked).
- Framing can serve users. Opower's neighbor-comparison home energy reports cut energy use by 2.0% on average across about 600,000 households in randomized field experiments, equal to a short-run electricity price rise of 11 to 20% [3].
- Framing also works against users: in Luguri and Strahilevitz's Study 2 a trick question lifted acceptance of a dubious service from 19.2% to 33.4% [4].
- Comparable reference prices are required in the EU. A price-reduction announcement must show the prior price, the lowest price in at least the previous 30 days (Art. 6a of Directive 98/6/EC, inserted by Directive 2019/2161; applies from 28 May 2022) [5].

**Evidence: Moderate.** The framing effect itself is well replicated, but "neutral and comparable presentation" as a UI rule rests on one regulation, one large field experiment and design consensus.
Required: Art. 6a of Directive 98/6/EC (EU prior-price rule for price reductions).

**Limitations.**
- No frame is neutral. "Neutral" means the same basis for every option, not no framing.
- Framing effect sizes vary by task and population; meta-analyses of risky-choice and health-message framing exist [6] (not opened here, so no effect sizes are given).
- Social comparison can backfire for people already doing better than the norm (CHO-02).
- Opower's effect is small per household and was measured for energy only [3]. Test before transferring it to another goal.
- Overlaps: CHO-06 (confirmshaming and trick questions are framing used against the user), CHO-04 (decoys), CHO-01 (a default is a frame).

**How to measure it works.**
- Comprehension: five users compare the options and name the cheapest per month or the total cost (target: all correct); time to a correct choice.
- Error and regret: wrong-plan purchases, plan changes in the first 30 days, support contacts about "what is included".
- For framing used in the user's interest, the user's own outcome (energy saved, savings rate), plus opt-out and complaint rate for the messages.

**Implemented by.**
- Utilities running neighbor-comparison reports (programs studied in Allcott 2011): 2.0% average reduction [3].
- EU retailers under the prior-price rule since 28 May 2022; no outcome published [5].
- Amazon (2025 order): a plain "decline Prime" button replaces "No, I don't want Free Shipping" (see CHO-05) [7].

**How to detect it.**
- *Applied:* comparison tables with identical rows in the same order and units; prices on the same period with a total; accept and decline buttons of equal weight with plain labels; a "was" price that was really charged, with its date; "most popular" markers that say how popularity is measured.
- *Violated:* /month on one plan and /year on another; the pushed option shown with benefits only; the decline option phrased as a negative self-image; strike-through "was $X" prices never charged; "Recommended" sort that mixes in sponsored items without a label; feature rows that differ by plan.
- *In code:* `text-decoration: line-through` prices with no price-history source; plan cards whose price units differ (`/mo` and `/yr`); `order` or `flex-direction: row-reverse` used to move the preferred plan; decline strings such as "No, I don't want…"; accept `btn-primary` against decline `btn-link text-muted`.
- *Quick test:* convert every option to the same unit and period; recompute each claim ("save 40%") from the numbers on screen; read both buttons aloud for tone.

**How to implement.**
1. Pick one unit and period for all options (for example total per billing period plus the monthly equivalent) and use it everywhere.
2. Build comparison tables from one data model: identical rows, same order, show limits and downsides.
3. Word both choices as plain actions ("Keep Premium", "Cancel Premium") with equal visual weight.
4. Show a reference price only if it was charged for at least 30 days before the cut (EU rule) and show its date.
5. If you use social comparison or a gain frame, run a randomized pilot, measure the user's outcome and complaints, and give an opt-out.
6. Run a comprehension test before launch.

**Sources.**
[1] Tversky, A., & Kahneman, D. (1981). The framing of decisions and the psychology of choice. Science 211(4481), 453-458. https://doi.org/10.1126/science.7455683 (percentages as summarized by Wikipedia, Framing effect (psychology))
[2] Klein, R. A., et al. (2014). Investigating variation in replicability: a "Many Labs" replication project. Social Psychology 45(3), 142-152. https://doi.org/10.1027/1864-9335/a000178
[3] Allcott, H. (2011). Social norms and energy conservation. Journal of Public Economics 95(9-10), 1082-1095. https://doi.org/10.1016/j.jpubeco.2011.03.003
[4] Luguri, J., & Strahilevitz, L. J. (2021). Shining a light on dark patterns. Journal of Legal Analysis 13(1), 43-109. https://academic.oup.com/jla/article/13/1/43/6180579
[5] Directive (EU) 2019/2161 (Omnibus), Art. 2 inserting Art. 6a into Directive 98/6/EC. https://eur-lex.europa.eu/eli/dir/2019/2161/oj
[6] Kühberger, A. (1998). The influence of framing on risky decisions: a meta-analysis. Organizational Behavior and Human Decision Processes 75(1), 23-55. https://doi.org/10.1006/obhd.1998.2781 ; Gallagher, K. M., & Updegraff, J. A. (2012). Health message framing effects on attitudes, intentions, and behavior: a meta-analytic review. Annals of Behavioral Medicine 43(1), 101-116. https://doi.org/10.1007/s12160-011-9308-7 (both: bibliographic details verified; not opened)
[7] FTC (2025-09-25). FTC secures historic $2.5 billion settlement against Amazon. https://www.ftc.gov/news-events/news/press-releases/2025/09/ftc-secures-historic-25-billion-settlement-against-amazon
