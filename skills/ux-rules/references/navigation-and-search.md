# Navigation, information architecture and search (NAV)

This category covers how people find things: link and menu labels, always-visible navigation, location cues, consistent navigation, search, filters and sorting, URLs and the Back button, and how content is grouped. Load it when auditing a header, menu, tab bar, site map, search box, listing page or single-page-app routing. Label wording as copy is in CON, touch-target size and thumb reach are in PLT, and how to run card sorts, tree tests and first-click tests is in MEA.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| NAV-01 | Give links and menus strong information scent | Moderate | any UI with links, menus, cards or tabs |
| NAV-02 | Keep primary navigation visible; use a tab bar for 3 to 5 phone destinations | Moderate | websites, mobile web, mobile apps |
| NAV-03 | Show users where they are | Moderate | multi-page sites, single-page apps, multi-section apps |
| NAV-04 | Keep navigation consistent across screens | Strong | any site or app with repeated navigation or help links |
| NAV-05 | Make search forgiving and helpful | Moderate | catalogs, content sites, apps with more than a few dozen items |
| NAV-06 | Offer filters and sorting for large collections | Moderate | product lists, listings, search results, data tables |
| NAV-07 | Keep URLs and the Back button working | Moderate | websites, single-page apps, apps with deep links |
| NAV-08 | Organize by users' tasks and mental models, not the org chart | Moderate | site and app structure, intranets, public services |

---

### NAV-01 Give links and menus strong information scent

**What it is.** Label every link, menu item and card with the words users expect to find at the destination, so they can predict what a click returns. Add a summary line or a representative image where a label alone is ambiguous.

**Why it works.**
- Information foraging theory treats "scent" as an imperfect estimate of a source's value and cost, built from cues such as link labels; people choose paths on that estimate [1]. NN/g: scent is relative to a need, and vague labels ("More", "Learn more"), jargon and branded terms weaken it [2]. Menus should use clear, familiar words, not made-up terms or abstract top-level categories [3].
- The first click carries much of the outcome. Bailey and Wolfson's live-site studies (2006 to 2009, about a dozen tests, as summarised by MeasuringU) found 87% task success after a first click on an optimal path and 46% after any other [4]. We could not find the primary paper.
- MeasuringU's 2023 replication (five websites, 21 tasks, 750 participants) found a smaller gap: success about 13% higher in relative terms after a correct first click, listed as 70% versus 78% [4].

**Evidence: Moderate.** Peer-reviewed theory (1999) plus NN/g guidance; the often-quoted first-click numbers are contested. Required for link text and labels: WCAG 2.2 SC 2.4.4 Link Purpose (In Context) (A) and SC 2.4.6 Headings and Labels (AA) [5].

**Limitations.**
- A clear label cannot repair a wrong grouping (NAV-08). Specific is not long: long labels slow scanning (CON). Icon-only items weaken scent (INT).
- Do not quote 87% versus 46% as a forecast: the only replication found a much smaller effect, and neither study tested a design change.
- Scent depends on the audience; familiar brand or domain terms can still work [2].

**How to measure it works.**
- First-click success and time in a first-click test; success and directness in a tree test (MEA). Expect fewer wrong first clicks on top tasks after relabelling.
- Lagging: fewer immediate Back clicks after a menu click, fewer searches for terms already in the menu, higher task success in moderated tests.

**Implemented by.**
- Apple HIG: label every tab, one word where possible [6]. Material navigation bar: icon plus text label on each item [7]. We found no published before/after metric for a label rewrite alone.

**How to detect it.**
- *Applied:* labels are concrete nouns or verbs for content or tasks ("Pricing", "Docs", "Pay a bill"); mega-menu items carry a one-line description; link text makes sense out of context.
- *Violated:* "Solutions", "Resources", "Explore", "More", "Learn more", "Click here"; internal product code names; the same link text pointing to different places.
- *In code:* `<a>` or `<button>` text matching `click here|read more|learn more|^more$|solutions|resources`; icon-only `<a>` with no `aria-label`; duplicate link text with different `href` values.
- *Quick test:* show only the menu labels (no page) to three people and ask what they expect under each; or run a five-task first-click test and count wrong first clicks.

**How to implement.**
1. List the top 5 to 10 user tasks (analytics, search logs, support tickets) and write labels in the users' own words; name the thing the user gets, not the department that owns it (NAV-08).
2. Add one line of summary text under ambiguous menu items; put the distinctive words first in link text.
3. Make link text stand alone (SC 2.4.4); give icon-only links an accessible name.
4. Test with a first-click or tree test (MEA) and rewrite the labels that draw the most wrong first clicks.

**Sources.**
[1] Pirolli, P., & Card, S. (1999). Information foraging. Psychological Review 106(4), 643-675. https://doi.org/10.1037/0033-295X.106.4.643 (definition of scent from secondary summaries (snippet); paper not opened)
[2] Budiu, R. (2020-02-02). Information scent: how users decide where to go next. NN/g. https://www.nngroup.com/articles/information-scent/
[3] Laubheimer, P. (2024-06-07). NN/g article on menu design (17 guidelines). https://www.nngroup.com/articles/menu-design/
[4] Sauro, J., Schiavone, W., Du, D., & Lewis, J. (2023-03-21). Do click tests predict live site clicks? MeasuringU. https://measuringu.com/do-click-tests-predict-live-site-clicks/
[5] W3C (2023). Understanding SC 2.4.4 Link Purpose (In Context) and SC 2.4.6 Headings and Labels, WCAG 2.2. https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html and https://www.w3.org/WAI/WCAG22/Understanding/headings-and-labels.html
[6] Apple. Human Interface Guidelines: Tab bars. https://developer.apple.com/design/human-interface-guidelines/tab-bars
[7] Material Components for Android. Bottom navigation docs. https://github.com/material-components/material-components-android/blob/master/docs/components/BottomNavigation.md

---

### NAV-02 Keep primary navigation visible; use a tab bar for 3 to 5 phone destinations

**What it is.** Show the top-level destinations on screen instead of behind a menu icon. On desktop, list the main links in the header. On phones with three to five top-level destinations, use a persistent bottom tab bar with an icon and a visible label.

**Why it works.**
- Hidden items must be remembered and opened; visible ones prompt use. NN/g's 2016 study (179 participants, six live sites, two simple tasks each) found navigation was used 27% of the time when hidden, versus 48% visible and 50% combined (some links visible, some hidden) on desktop, and 57% hidden versus 86% combined on phones [1].
- Hidden navigation also cut content discoverability by more than 20%, raised difficulty ratings (2.6 hidden versus 2.1 visible, on a 1 to 7 scale), and made desktop tasks at least 39% slower and phone tasks 15% slower than combined. Time to first use differed only at p < 0.1 [1].
- Spotify (2016) replaced its iPhone hamburger with a bottom tab bar. The company told TechCrunch that users clicked about 9% more overall and about 30% more on menu items, with no harm to retention, engagement or listening time [2]. Company-reported; no method published.
- Guidelines agree: Material navigation bars hold three to five destinations and become a rail on large screens [3][4]; Apple says to keep the tab bar visible, avoid overflow "More" tabs and use tabs for sections, not actions [5]; NN/g says tab bars suit few options and recommends labelled icons [6].

**Evidence: Moderate.** One NN/g study with a stated method (2016, now ten years old) plus consensus across Apple and Google guidance. The company results are anecdotes.

**Limitations.**
- The phone arm compared hidden with combined navigation only (no visible-only condition), on six sites with simple tasks [1].
- More than five equal destinations do not fit a tab bar; use a "More" tab, drawer or rail and expect lower discovery for hidden items [3][6] (PER, Hick's law). NN/g still calls the hamburger a "necessary evil" on small screens [7].
- Full-screen content (video, camera, maps) can justify hiding the bar inside a flow; Apple warns people then lose their place [5].
- The Android Views default (`labelVisibilityMode=auto`) shows only the selected label once there are four items [4]; NN/g and Apple prefer a label on every tab (NAV-01).
- Facebook and Redbooth reported gains after moving to a tab bar and Zeebox a drop after moving to a drawer, with no figures in the source [8]. Larger percentages quoted online were not traced.

**How to measure it works.**
- Share of sessions using primary navigation; per-user views of sections that were hidden before; first-session navigation use (leading); retention as a guard metric (lagging).
- A/B test hamburger versus tab bar; moderated test: reach a secondary section and record success, time and taps.

**Implemented by.**
- Spotify (2016): +9% clicks, +30% menu-item clicks, retention unchanged [2] (anecdote). Facebook (iOS) and Redbooth: reported more engagement or sessions after moving to a tab bar [8] (anecdote).
- Apple (tab bars) and Google (Material navigation bar, rail, drawer) specify visible, persistent navigation [3][5].

**How to detect it.**
- *Applied:* main links visible in the header at desktop widths; phone shows three to five labelled bottom tabs; the bar persists across sub-screens; the active tab is marked.
- *Violated:* desktop with only a hamburger icon; icon-only tabs; more than five tabs squeezed together; a tab bar that disappears inside flows; primary sections reachable only from a drawer.
- *In code:* `.hamburger`, `.menu-toggle`, `.navbar-toggler` still shown at 1024 px or wider (Bootstrap collapses by `navbar-expand-*`); a `<button aria-expanded>` wrapping all `<nav>` links; native tab bars (`BottomNavigationView`, Compose `NavigationBar`, `UITabBarController`, SwiftUI `TabView`) with label-hiding flags (`labelVisibilityMode="unlabeled"`, `alwaysShowLabel = false`).
- *Quick test:* load the page at 1280 px and 390 px wide; count destinations reachable without a tap; ask someone to reach a secondary section and count taps.

**How to implement.**
1. List top-level destinations, rank them by usage and keep the five that matter most.
2. Desktop: show those links in the header and put the long tail under "More" (combined navigation) [1].
3. Phone with five or fewer: bottom tab bar, icon plus visible label, active state marked (sizes and thumb reach: PLT). With more: top four plus a "More" tab, or a drawer; never hide what users need weekly.
4. Keep the bar on every sub-screen; switch to a rail or drawer on wide windows [3].
5. A/B test against the old pattern with retention as the guard metric.

**Sources.**
[1] Pernice, K., & Budiu, R. (2016-06-26). Hamburger menus and hidden navigation hurt UX metrics. NN/g. https://www.nngroup.com/articles/hamburger-menus/
[2] Perez, S. (2016-05-03). Spotify ditches the controversial "hamburger" menu in iOS app redesign. TechCrunch. https://techcrunch.com/?p=1316422
[3] Android Developers. Layout and navigation patterns. https://developer.android.com/design/ui/mobile/guides/layout-and-content/layout-and-nav-patterns
[4] Material Components for Android. Bottom navigation docs. https://github.com/material-components/material-components-android/blob/master/docs/components/BottomNavigation.md
[5] Apple. Human Interface Guidelines: Tab bars. https://developer.apple.com/design/human-interface-guidelines/tab-bars
[6] Budiu, R. (2015-11-15). Basic patterns for mobile navigation: a primer. NN/g. https://www.nngroup.com/articles/mobile-navigation-patterns/
[7] Laubheimer, P. (2024-06-07). NN/g article on menu design (17 guidelines). https://www.nngroup.com/articles/menu-design/
[8] Wroblewski, L. (2015-04-27). Obvious always wins. https://www.lukew.com/ff/entry.asp?1945

---

### NAV-03 Show users where they are

**What it is.** Tell people where they are at three levels: a unique page title, the current item marked in the navigation, and, for deep hierarchies, a breadcrumb trail that shows the page's location.

**Why it works.**
- People land on deep pages from search and shared links with no context. WCAG: descriptive titles help users find content and orient themselves, and single-page apps should change the title with the view [1].
- NN/g: a missing current-location indicator is probably the single most common mistake in website menus [2]. Breadcrumbs should show location, not session history; the last item is the current page and not a link; show the full trail on desktop and the last level or two on mobile; they add to main navigation and do not replace it [3].
- Apple: hiding the tab bar makes it easy to lose track of where you are [4].

**Evidence: Moderate.** A standard requires page titles; the rest is NN/g guidance that publishes no study. Required: WCAG 2.2 SC 2.4.2 Page Titled (A) [1]. SC 2.4.8 Location (AAA) is optional [5].

**Limitations.**
- Breadcrumbs add little on flat sites (one or two levels) or linear flows such as checkout; for items in several categories show one canonical path, not a personalised one [3].
- On phones breadcrumbs are small and wrap; show only the parent level [3].
- A colour change alone must not carry the active state (A11Y); titles that all start with the brand name make browser tabs look identical (CON).
- Breadcrumbs do not replace working navigation (NAV-02) or the Back button (NAV-07).

**How to measure it works.**
- Moderated test: "Where are you in this site?" and "Go to the parent section"; success rate. Audit: share of routes with a unique `<title>` and of nav items that expose a current state.
- Behavioural: Home/logo clicks and back-and-forth after landing on a deep page from search (disorientation signs). A low breadcrumb click share is normal on flat sites.

**Implemented by.**
- Material 3 navigation bar: the active destination gets a filled indicator pill (56 x 32 dp by default) [6]. Apple tab bars: a persistent bar keeps the current tab visible [4].
- NN/g says it has recommended breadcrumbs since 1995 [3]. We found no company outcome data for titles or breadcrumbs.

**How to detect it.**
- *Applied:* distinct `<title>` on each page; the current nav item styled and exposed with `aria-current="page"`; breadcrumb in `<nav aria-label="Breadcrumb">` with the last crumb as plain text.
- *Violated:* every route titled "App", "Document" or just the site name; no active state; a breadcrumb of visited pages; a last crumb that links to itself; active state shown by colour only.
- *In code:* duplicate `<title>` values across templates; single-page routes with no `document.title =`, `<Helmet>`, Next.js `metadata` or Angular `Title.setTitle`; `.active` classes with no `aria-current`. JSON-LD `BreadcrumbList` alone is not a visible breadcrumb.
- *Quick test:* open five deep pages in separate tabs and read the tab titles; crop the logo out of a screenshot and try to say where you are.

**How to implement.**
1. Write titles as "Page name - Section - Site" (specific part first) and set them on every route change, including in single-page apps.
2. Mark the active nav item with `aria-current="page"` plus a non-colour cue (weight, bar, filled icon).
3. Add breadcrumbs when the hierarchy is deeper than two levels: `<nav aria-label="Breadcrumb"><ol>` with links for each ancestor and `<li aria-current="page">Current page</li>` last. On phones show only the parent link.
4. After a client-side route change, move focus to the page heading (A11Y).

**Sources.**
[1] W3C (2023). Understanding SC 2.4.2 Page Titled (Level A), WCAG 2.2. https://www.w3.org/WAI/WCAG22/Understanding/page-titled.html
[2] Laubheimer, P. (2024-06-07). NN/g article on menu design (17 guidelines). https://www.nngroup.com/articles/menu-design/
[3] Laubheimer, P. (2018-12-23, last reviewed 2026-09-01). NN/g article on breadcrumb design guidelines. https://www.nngroup.com/articles/breadcrumbs/
[4] Apple. Human Interface Guidelines: Tab bars. https://developer.apple.com/design/human-interface-guidelines/tab-bars
[5] W3C (2023). Understanding SC 2.4.8 Location (Level AAA), WCAG 2.2. https://www.w3.org/WAI/WCAG22/Understanding/location.html
[6] Material Components for Android. Bottom navigation docs. https://github.com/material-components/material-components-android/blob/master/docs/components/BottomNavigation.md

---

### NAV-04 Keep navigation consistent across screens

**What it is.** Repeat navigation, labels, icons and help links in the same place and order on every screen of the same kind, and call the same function by the same name everywhere.

**Why it works.**
- Predictable placement lets people find repeated controls faster; keyboard, screen-reader and magnifier users depend on a stable order [1].
- WCAG 3.2.3 Consistent Navigation: repeated navigation keeps the same relative order across a set of pages unless the user changes it [1]. SC 3.2.4 Consistent Identification: components with the same function are identified the same way [2]. SC 3.2.6 Consistent Help (new in 2.2): help links keep the same relative order [3].
- W3C's failure examples: "Search" on one page and "Find" on another, and a floppy-disk icon for Save on one page but a checkmark on another [2].
- Same logic as Jakob's law (users expect your site to work like others; PER) and design-system consistency (INT).

**Evidence: Strong.** Formal standard; no controlled study that quantifies the benefit turned up in the pages we opened. Required: WCAG 2.2 SC 3.2.3 (AA), SC 3.2.4 (AA), SC 3.2.6 (A). Legal mapping is in A11Y.

**Limitations.**
- A "set of pages" shares a purpose and author; a checkout that drops the global header can be its own set if it does so consistently [1].
- Allowed: user-initiated reordering, sub-menus that insert items without reordering the rest, and labels that adapt to context such as "Previous page" [1][2]. The page does not address collapsing directly; keep the remaining items in the same relative order.
- Consistent is not uniform; GOV.UK's design principle is "Be consistent, not uniform" [4]. Consistency can freeze a bad pattern; fix it everywhere in one release (NAV-01, NAV-08).

**How to measure it works.**
- Audit: compare header, footer and nav order across a sample of templates; list every label used for the same action. Automated: snapshot nav text and order per route in CI.
- Usability: time to find a repeated control (search, cart, help) on the fifth page of a session; errors; a screen-reader pass for landmark order.

**Implemented by.**
- Apple HIG: keep the tab bar visible when switching sections and do not hide or disable tabs, because inconsistent availability makes the interface seem unstable [5]. Android Navigation: one fixed start destination and one Up/Back model [6].
- GOV.UK design principles (published 2012-04-03) [4]. No measured outcomes found for any of these.

**How to detect it.**
- *Applied:* one shared header/footer component; Home, Search, Account and Cart in the same order on every template; the same icon and label for the same action; help link in the same place.
- *Violated:* nav order changes between sections; "Basket", "Cart" and "Bag" mixed; two icons for Save; the help link moves; the logo goes to different places.
- *In code:* several header implementations (`header-v2`, `NavLegacy`); per-page arrays of links; the same action with different `aria-label` values; synonym pairs in templates (`Search|Find`, `Cart|Basket|Bag`, `Sign in|Log in|Login`).
- *Quick test:* screenshot the header of five pages from different sections and overlay them; note every difference in order or wording.

**How to implement.**
1. Build navigation from one component and one data source that every template uses.
2. Keep a glossary of action names and icons (CON, INT) and lint templates for synonyms.
3. Where a flow needs a reduced header (checkout, onboarding), make it identical across that flow.
4. Put help and contact links in the same relative position on every page (SC 3.2.6); ship navigation changes to all templates in one release.

**Sources.**
[1] W3C (2023). Understanding SC 3.2.3 Consistent Navigation (AA), WCAG 2.2. https://www.w3.org/WAI/WCAG22/Understanding/consistent-navigation.html
[2] W3C (2023). Understanding SC 3.2.4 Consistent Identification (AA), WCAG 2.2. https://www.w3.org/WAI/WCAG22/Understanding/consistent-identification.html
[3] W3C (2023). Understanding SC 3.2.6 Consistent Help (A), WCAG 2.2. https://www.w3.org/WAI/WCAG22/Understanding/consistent-help.html
[4] GOV.UK. Government design principles (first published 2012-04-03, updated 2025-04-02). https://www.gov.uk/guidance/government-design-principles
[5] Apple. Human Interface Guidelines: Tab bars. https://developer.apple.com/design/human-interface-guidelines/tab-bars
[6] Android Developers. Principles of navigation. https://developer.android.com/guide/navigation/principles

---

### NAV-05 Make search forgiving and helpful

**What it is.** Make search tolerate typos, synonyms and natural phrases, suggest queries as people type, and never end on a dead-end "no results" page.

**Why it works.**
- Baymard's 2026 benchmark (10,000+ usability ratings across 170+ sites and apps) rates 56% of e-commerce search "mediocre or worse". Sites with issues by query type: exact 12%, product type 20%, feature 39%, use case 43%, abbreviation and symbol 54%, compatibility 44%, symptom 37%, non-product 66% [1].
- Autocomplete is on 80% of sites (72% in 2014) but only 19% get the details right (2022); problems start above about 10 suggestions on desktop and 8 on mobile [2]. 69% give no relevant suggestions for slightly misspelled queries such as "furnture"; users then fix the typo, spend 30 seconds or more on it, switch to category navigation or leave (2021) [3].
- Nearly 50% of sites fail to help users recover from a no-results search (2019, updated 2025) [4].
- Visibility: swapping a search link for a search box raised search use by 91% on Nielsen's own homepage (2001, uncontrolled); first-query success was 51% in NN/g's e-commerce study [5].

**Evidence: Moderate.** Baymard usability tests and benchmarks with a stated method (e-commerce, 2014 to 2026); the NN/g figures are old. Related requirement: WCAG 2.2 SC 2.4.5 Multiple Ways (AA) asks for at least two ways to find a page, and search is an accepted way [6].

**Limitations.**
- Baymard's data is e-commerce. Benchmark definitions change between editions (the non-product share was 15% in a 2019 headline and 66% in 2026), so do not compare years.
- Very small sites may not need search [7]. Too many suggestions backfire [2]. Fuzzy matching can bury exact matches; keep exact hits first (my inference).
- Query logs are personal data (CHO). A magnifier-only button is workable [7], but a visible field works better on desktop [5] (conflicts with hiding it, NAV-02).

**How to measure it works.**
- Zero-result rate (queries with no results divided by all queries) and the top zero-result terms weekly; search success (a result click or add-to-cart after the search); reformulation and exit rates; suggestion acceptance.
- Searchers convert better than non-searchers because of intent, so test changes with A/B tests. Test queries: a typo, a synonym, a use-case phrase, an abbreviation.

**Implemented by.**
- U.S. Web Design System: full search box (not a link) on the home page, at least 27 characters wide, label for screen readers, submit button [7]. The "27 characters fits 90% of queries" rationale is repeated online; we found it only in secondary sources.
- We found no company before/after search metrics we could verify.

**How to detect it.**
- *Applied:* visible input at least 27 characters wide with label and submit button; suggestions capped near 10 (8 on mobile), active one highlighted and copied into the field; "furnture" returns results or a "Did you mean"; a no-results page with related categories, simplified queries, popular items and contact options.
- *Violated:* icon-only search on desktop; "0 results" with tips only; autocomplete that vanishes on a typo; exact-name matching only; the query is not echoed on the results page.
- *In code:* `<input type="search">` inside `role="search"`; combobox ARIA (`role="combobox"`, `aria-autocomplete="list"`, `aria-controls`, `aria-activedescendant`); engine settings (`fuzziness` in Elasticsearch, `typoTolerance` in Algolia, synonym lists); no template for empty results.
- *Quick test:* search a deliberate typo, a synonym, a phrase describing a use ("jacket for rain") and gibberish; judge each results page in under a minute.

**How to implement.**
1. Put a visible search field on every page: `<form role="search">` with a label, `<input type="search" size="30" enterkeyhint="search">` and a submit button [7].
2. Add spelling tolerance and a synonym list built from query logs; map frequent misspellings by hand [3].
3. Autocomplete: at most 10 suggestions (8 on mobile), highlight the active one, copy it into the field, style category-scoped suggestions differently [2].
4. Support product-type, feature, use-case, abbreviation and symbol queries, plus non-product queries such as policies and order status [1].
5. No-results page: related categories, simplified queries with 3 to 5 product previews, popular items, support contact [4].

**Sources.**
[1] Baymard Institute (first published 2024-09-12, updated 2026-04-29). Ecommerce search UX: 8 search query types. https://baymard.com/blog/ecommerce-search-query-types
[2] Scott, E. (2022-08-02). Baymard article on autocomplete design. https://baymard.com/blog/autocomplete-design
[3] Scott, E. (2021-08-31). Offer autocomplete suggestions for misspellings. Baymard. https://baymard.com/research-articles/offer-autocomplete-suggestions-for-misspellings
[4] Baymard Institute (2019-02-04, updated 2025-02-18). Designing the no-results page. https://baymard.com/research-articles/no-results-page
[5] Nielsen, J. (2001-05-12). Search: visible and simple. NN/g. https://www.nngroup.com/articles/search-visible-and-simple/
[6] W3C (2023). Understanding SC 2.4.5 Multiple Ways (AA), WCAG 2.2. https://www.w3.org/WAI/WCAG22/Understanding/multiple-ways.html
[7] U.S. Web Design System. Search component. https://designsystem.digital.gov/components/search/

---

### NAV-06 Offer filters and sorting for large collections

**What it is.** For lists too long to scan, give filters on the attributes people care about (price, size, brand, rating, category-specific attributes), show which are applied, and offer sorting. Combined with keyword search this is faceted search.

**Why it works.**
- Filters let users state constraints instead of paging. Facets combine several category hierarchies with keyword search, and users narrow or widen by adding or removing labels [1].
- Yee et al. (CHI 2003): 32 art-history students compared the Flamenco faceted interface with a standard image-search baseline on about 35,000 images. 90% preferred the faceted interface; 97% said it helped them learn about the collection; 75% found it more flexible; 72% found it easier to use [2].
- Baymard's 2015 study (19 sites tested, 700+ usability problems; 50 US sites benchmarked): 16% of sites had good filtering, 50% passable, 34% poor; 42% lacked category-specific filters; 40% of test subjects at some point could not find the filters [3].
- Baymard's 2025 benchmark (170+ sites): 51% lack at least one of five essential filters (price, rating, color, size, brand); 14% do not let users pick several values in one filter; 20% show no applied-filters overview; 58% of desktop and 78% of mobile product lists rate poor to mediocre overall [4].

**Evidence: Moderate.** Baymard tests and benchmarks (2015, 2025) plus one controlled preference study (2003).

**Limitations.**
- Preference is not speed: in the Flamenco study the faceted interface was about an order of magnitude slower than the baseline, and for a one-facet task about half the participants preferred the baseline [1].
- Facets that do not match users' mental models, or too many long facets, bring back the problems of directories [1] (NAV-08). Small collections do not need filters; each filter adds visual weight (VIS).
- Mobile is the weak spot (78% of lists poor to mediocre); horizontal filter bars suit about eight filter types or fewer [4].
- Each filter combination can create a crawlable near-duplicate URL; manage canonical URLs while keeping state in the URL (NAV-07). General practice, not from these sources.

**How to measure it works.**
- Filter usage rate; time to first product click or add-to-cart; zero-result combinations; "Clear all" clicks; abandonment after filtering. Filter users self-select for intent, so use A/B tests, not user-versus-non-user comparisons.
- Usability tasks with compound criteria ("waterproof, black, size 10, under $100"); in Baymard's 2015 tests compatibility tasks had a 35% completion rate [3].

**Implemented by.**
- Hearst's chapter cites eBay Express (since discontinued), Dell, WebMD and the Michigan State University library catalogue as faceted designs in use [1]. Baymard's 2025 example: HP's mice and keyboards list pairs the essential filters with many category-specific ones [4].
- Amazon, Booking and Airbnb ship facet filters (observed pattern); we found no published outcome data for them.

**How to detect it.**
- *Applied:* grouped filters (checkbox lists, counts), several values per filter, applied-filter chips with "Clear all", a result count, a sort control, category-specific filters, filters promoted above the list.
- *Violated:* sort only; single-select filters; filters behind a tiny icon; no applied state; zero-result combinations with no way back; filters reset by Back.
- *In code:* `<fieldset><legend>` groups with `<input type="checkbox">`; `aria-live="polite"` on the result count; query params such as `?color=black&size=10&sort=price`; `history.pushState` on filter change; Elasticsearch `aggregations`, Algolia `facets`/`disjunctiveFacets`.
- *Quick test:* in a category with 100+ items, find "black, size 10, under $100" and count taps; pick two values in one filter; press Back.

**How to implement.**
1. Derive facets from item attributes and search logs. For retail start with price, rating, brand, size and color, then add category-specific filters [3][4].
2. Show counts; disable or hide values that would return nothing. Allow several values within a filter (OR) and combine filters (AND).
3. Show applied filters in an overview with one-tap removal and "Clear all" [4]. On phones use a full-screen filter sheet with a live "Show N results" button.
4. Keep filter and sort state in the URL so Back undoes steps (NAV-07). Default sort to relevance (search) or popularity (browse) and label sort options plainly.

**Sources.**
[1] Hearst, M. (2009). Search user interfaces, chapter 8, section on faceted navigation. http://searchuserinterfaces.com/book/sui_ch8_navigation_and_search.html
[2] Yee, K.-P., Swearingen, K., Li, K., & Hearst, M. (2003). Faceted metadata for image search and browsing. CHI 2003, 401-408. https://doi.org/10.1145/642611.642681 (abstract read at https://sciweavers.org/node/46167)
[3] Holst, C. (2015-04-20). The current state of e-commerce filtering. Smashing Magazine (Baymard Institute research). https://www.smashingmagazine.com/2015/04/the-current-state-of-e-commerce-filtering
[4] Baymard Institute (2025, updated September 2025). The current state of product list and filtering. https://baymard.com/research-articles/current-state-product-list-and-filtering

---

### NAV-07 Keep URLs and the Back button working

**What it is.** Give every meaningful view its own URL (or deep link), make Back undo the last navigation step, and restore position and state when users return.

**Why it works.**
- People backtrack and revisit constantly. Tauscher and Greenberg logged 23 people for six weeks (1997); summaries report 58% of visits as revisits and about 30% of navigation actions as Back (snippet) [1]. Cockburn and McKenzie's four months of logs (2001) put previously visited pages at about 81% (snippet) [2]. Chrome data: one in ten desktop and one in five mobile navigations are Back or Forward [3].
- Nielsen ranked breaking Back first in his 1999 list of web design mistakes and called it the second most used navigation action; the article cites no data. It names new windows, immediate redirects and uncached pages as ways to break it [4].
- Baymard (2020): 59% of e-commerce sites get at least one of four Back expectations wrong: overlays and lightboxes (37%), filtering and sorting (27%), accordion checkout steps, and returning to the product list [5].
- Android keeps a back stack and builds a synthetic one for deep links, so Up and Back behave as if the user navigated manually [6].

**Evidence: Moderate.** Old log studies, Chrome telemetry, Baymard tests (2020) and platform guidance; no controlled study of conversion effects.

**Limitations.**
- One history entry per micro-change floods Back. Use `replaceState` for transient states and do not use `pushState` for expanding or truncated content [5].
- Keep tokens, personal data and secrets out of URLs (CHO). After a payment or other irreversible step Back must not resubmit; redirect after POST (ERR).
- Single-page apps need extra work: update the title on each route [7], move focus, restore scroll, serve the app shell for deep URLs. Pages with `unload` handlers miss the back/forward cache in Firefox desktop; use `pagehide` [3].
- Native apps: Up and Back differ, and Up never leaves the app [6].

**How to measure it works.**
- Back followed by an exit within seconds (pogo-sticking); state-loss events (filters or scroll reset after Back) found with session replay; support tickets that say "lost my place"; funnel drop-off at checkout steps after Back.
- Deep-link success: share of shared or bookmarked URLs that open the intended view (synthetic test).

**Implemented by.**
- Skechers: "Load more" rewrites the URL on each click so Back returns to the right list state [5]. Android Navigation component: synthetic back stack on deep link [6].
- Browser back/forward cache: near-instant Back for eligible pages [3].

**How to detect it.**
- *Applied:* the URL changes with view, filter, sort, page and tab; reload and copy-paste give the same view; Back closes overlays and undoes steps; scroll position returns on the list.
- *Violated:* one URL for every screen; Back leaves the site from a modal; `href="#"` links driven by JS; redirect loops; history traps; `target="_blank"` on ordinary links; `beforeunload` prompts.
- *In code:* `history.pushState(`/`replaceState(` and `popstate` listeners; router setup (`createBrowserRouter`, hash-only `HashRouter`); `<a onClick>` without `href`; `javascript:`; `unload` listeners; Android `<deepLink>`, `intent-filter` with `autoVerify`, `OnBackPressedCallback`; iOS `apple-app-site-association`.
- *Quick test:* apply a filter, open an item, press Back (filter and scroll kept?); open a modal, press Back (does it close, staying on the page?); copy the URL into a private window; refresh a deep view.

**How to implement.**
1. Give resources path URLs and filter, sort, page and search state query parameters. Use real `<a href>` links; intercept clicks for client routing only for same-origin links.
2. `pushState` for navigation-like changes (a page-like view, an overlay that acts as a page); `replaceState` for refinements such as typing [5]. Handle `popstate`; for async lists set `history.scrollRestoration = 'manual'` and restore scroll after the data loads.
3. On route change update `document.title` and move focus to the new heading (NAV-03). Make the server return the app shell for deep URLs and keep real 404s.
4. Remove `unload` handlers and check back/forward-cache eligibility. Android: Navigation component with deep links; iOS: universal links.
```js
form.addEventListener('change', () => { const u = new URL(location);
  u.search = new URLSearchParams(new FormData(form)); history.pushState({}, '', u); render(); });
addEventListener('popstate', render);
```

**Sources.**
[1] Tauscher, L., & Greenberg, S. (1997). How people revisit web pages: empirical findings and implications for the design of history systems. Int. J. Human-Computer Studies 47(1), 97-137. Study design confirmed at https://grouplab.cpsc.ucalgary.ca/Projects/ProjectHowPeopleUsetheWeb ; the 58% and 30% figures are from secondary summaries (snippet).
[2] Cockburn, A., & McKenzie, B. (2001). What do web users do? An empirical analysis of web use. Int. J. Human-Computer Studies 54(6), 903-922. https://ir.canterbury.ac.nz/handle/10092/514 (abstract seen in search results (snippet); the page returned 403 to my fetch)
[3] web.dev. Back/forward cache. https://web.dev/articles/bfcache
[4] Nielsen, J. (1999-05-30). The top ten web design mistakes of 1999. NN/g. https://www.nngroup.com/articles/the-top-ten-web-design-mistakes-of-1999/
[5] Baymard Institute (2020-07-20). Back button expectations. https://baymard.com/research-articles/back-button-expectations
[6] Android Developers. Principles of navigation. https://developer.android.com/guide/navigation/principles
[7] W3C (2023). Understanding SC 2.4.2 Page Titled, WCAG 2.2. https://www.w3.org/WAI/WCAG22/Understanding/page-titled.html ; MDN, History API (pushState and popstate): https://developer.mozilla.org/en-US/docs/Web/API/History_API

---

### NAV-08 Organize by users' tasks and mental models, not the org chart

**What it is.** Group and label content the way users think about their tasks, not the way the organization is structured, and validate the structure with users before building it.

**Why it works.**
- Users arrive with a task and do not know the org chart. GOV.UK launched on 2012-10-17, replacing Directgov and Business Link. The launch release says it was planned around user needs rather than government's preferred processes and was "built and tested in public" [1]. Design principle 1 is "Start with user needs" (published 2012-04-03) [2].
- Open card sorting shows the groupings and names users produce (NN/g: at least 15 participants for qualitative work, 30 to 50 for quantitative) [3]. Tree testing then checks a proposed hierarchy, with no visual design, by success, time and directness [4]. NN/g warns that a card sort does not give a finished structure [3][4].
- The launch release claimed GOV.UK would cost taxpayers up to 70 million pounds a year less than the services it replaced [1]. Other sources give different estimates (for example 64 million potential savings in the earlier Alphagov project, per a Wikipedia summary citing The Independent) [5]. We found no audited result.

**Evidence: Moderate.** Practitioner consensus (NN/g methods) and one well-documented case (GOV.UK). No controlled comparison of org-chart and task-based structures turned up in the pages we opened.

**Limitations.**
- When the user's task is about the organization (find a person, department or policy owner), an org view is right; GOV.UK still hosts a page for each department and agency [5].
- Different audiences hold different mental models; sort by segment before merging. Card-sort category names are not final labels; test labels separately (NAV-01). Closed and hybrid sorts bias results [3].
- Consolidation is costly: GOV.UK moved departments and agencies in stages through March 2014 [1]. The savings and satisfaction claims come from the site's owner.

**How to measure it works.**
- Tree test on top tasks: success, directness, time (MEA) [4]; first-click test on the new menu (NAV-01).
- Search logs: share of searches for items that already exist in the menu; "I couldn't find..." feedback; contact volume by topic (lagging: support contacts per task).

**Implemented by.**
- GOV.UK (2012): one domain organized by user needs, iterated in public [1][2]. Claimed outcomes: up to 70 million pounds a year lower cost (government figure) and the Design of the Year 2013 award (Wikipedia citing The Guardian) [1][5]. No other outcome-bearing example verified.

**How to detect it.**
- *Applied:* top-level menu items are tasks or topics in users' words ("Pay a bill", "Driving", "Benefits"); one task has one home; organization information sits in an "About" area; tree-test or card-sort results exist.
- *Violated:* top level equals divisions, business units or product code names; one task spread across silos; URLs mirror the org chart; labels only insiders know.
- *In code:* nav labels equal to department names; paths like `/divisions/emea/marketing/`; CMS taxonomies named after teams; redirects between silos for a single task.
- *Quick test:* write the five most common user tasks; for each count the clicks and the org units involved; ask five people which section holds each task before showing the menu.

**How to implement.**
1. Collect top tasks from analytics, search logs, support tickets and interviews; run an open card sort (15+ participants qualitative, 30 to 50 quantitative) [3].
2. Draft the structure by task or topic; keep org information in a separate "About" area.
3. Tree-test the draft on the top tasks, fix the lowest-scoring branches, retest [4]. Label in users' words (NAV-01) and add cross-links where one task spans topics.
4. After launch, watch search logs and feedback and iterate (GOV.UK principle: "Iterate. Then iterate again" [2]).

**Sources.**
[1] GOV.UK (2012-10-17). Launch of GOV.UK: a key milestone in making public service delivery digital by default (press release). https://www.gov.uk/government/news/launch-of-gov-uk-a-key-milestone-in-making-public-service-delivery-digital-by-default
[2] GOV.UK. Government design principles (first published 2012-04-03, updated 2025-04-02). https://www.gov.uk/guidance/government-design-principles
[3] Tankala, S., & Sherwin, K. (2024-02-02). NN/g article on card sorting. https://www.nngroup.com/articles/card-sorting-definition/
[4] Laubheimer, P. (2023-08-06). NN/g article on tree testing. https://www.nngroup.com/articles/tree-testing/
[5] Wikipedia. GOV.UK (secondary; cites The Independent and The Guardian). https://en.wikipedia.org/wiki/Gov.uk
