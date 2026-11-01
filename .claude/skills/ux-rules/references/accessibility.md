# Accessibility and inclusive design (A11Y)

The baseline for every rule here is WCAG 2.2 at level AA (W3C Recommendation, published 5 October 2023 and updated 12 December 2024), which law or policy
in the EU, the US and the UK references in some version (details below). The category covers whether people with permanent, temporary or situational
limits in vision, hearing, movement, speech and cognition can perceive, operate and understand a UI. Load it for every UI audit: most checks work from
source code or a screenshot, and each rule gives a Quick test for the ones that need a keyboard, a zoom level or a screen reader. Target size is PLT-03;
error message wording is ERR-04 and FRM-09.

**Baseline and legal status** (checked 31 October 2026)
- *Standard.* Content that meets WCAG 2.2 also meets 2.1 and 2.0; 2.2 removed SC 4.1.1 Parsing [B2]. ISO/IEC 40500:2025 is the October 2023 text; the December 2024 text is expected as ISO/IEC 40500:2026 by late 2026 [B1]. WCAG 3.0 is a Working Draft dated 10 September 2026 and does not deprecate WCAG 2 [B3].
- *EU.* The European Accessibility Act (Directive (EU) 2019/882) applies from 28 June 2025 to products and services such as computers, phones, e-books, banking, electronic communications and e-commerce; microenterprises providing services are exempt [B4][B5]. The technical reference is EN 301 549: v3.2.1 (2021, WCAG 2.1 AA) stays the reference until v4.1.1 (WCAG 2.2, published September 2026) is cited in the Official Journal, which would give a presumption of conformity [B6].
- *US federal.* Section 508 (Access Board final rule of 18 January 2017, applying from 18 January 2018) requires WCAG 2.0 A and AA for web content and electronic documents [B7][B8].
- *US state and local government.* The DOJ ADA Title II web rule (Federal Register, 24 April 2024) requires WCAG 2.1 AA [B9]. An interim final rule of 20 April 2026 (91 FR 20902) moved each compliance date back one year: 26 April 2027 for entities of 50,000 people or more (was 24 April 2026) and 26 April 2028 for smaller entities and special district governments [B9][B10]. Existing Title II duties such as effective communication still apply before those dates [B9].
- *UK public sector.* The GOV.UK Service Manual sets WCAG 2.2 AA as the minimum [B11].
- *US private sector.* No federal rule names a web standard; lawsuits and settlements commonly use WCAG (widely reported; not verified in this pass).
- *How often sites fail.* WebAIM Million, automated checks on 1,000,000 home pages in February 2026: 95.9% had detected WCAG 2 failures (94.8% in 2025) and averaged 56.1 detected errors per page (51 in 2025). Six failure types make up 96% of errors: low-contrast text on 83.9% of pages, missing image alt text 53.1%, missing form labels 51.0%, empty links 46.3%, empty buttons 30.6%, missing page language 13.5% [B12]. They map to A11Y-01, A11Y-10 and A11Y-04. The scan is automated, so true failure rates are higher (A11Y-09).

Baseline sources
[B1] W3C WAI (2025). WCAG 2 Overview (WCAG 2.2 published 5 October 2023, updated 12 December 2024; ISO/IEC 40500). https://www.w3.org/WAI/standards-guidelines/wcag/
[B2] W3C (2024-12-12). Web Content Accessibility Guidelines (WCAG) 2.2. https://www.w3.org/TR/WCAG22/
[B3] W3C (2026-09-10). W3C Accessibility Guidelines (WCAG) 3.0, Working Draft. https://www.w3.org/TR/wcag-3.0/
[B4] European Commission (2025-06-27). The EU becomes more accessible for all. https://digital-strategy.ec.europa.eu/en/news/eu-becomes-more-accessible-all
[B5] EUR-Lex. Accessibility of products and services (summary of Directive (EU) 2019/882). https://eur-lex.europa.eu/EN/legal-content/summary/accessibility-of-products-and-services.html (snippet: page body did not load; microenterprise exemption and e-commerce scope taken from the search result)
[B6] AccessibleEU (2026-09-07). The European accessibility standard EN 301 549 has been updated. https://accessible-eu-centre.ec.europa.eu/content-corner/news/european-accessibility-standard-en-301-549-has-been-updated-2026-09-07_en
[B7] U.S. Access Board. Information and communication technology standards and guidelines. https://www.access-board.gov/ict/
[B8] Section508.gov. Laws and policies. https://www.section508.gov/manage/laws-and-policies/
[B9] ADA.gov (2026). First steps toward complying with the Title II web and mobile application accessibility rule; Small entity compliance guide. https://www.ada.gov/resources/web-rule-first-steps/ and https://www.ada.gov/resources/small-entity-compliance-guide/
[B10] Federal Register (2026-04-20). Extension of Compliance Dates for ... Accessibility of Web Information and Services of State and Local Government Entities. https://www.federalregister.gov/documents/2026/04/20/2026-07663/extension-of-compliance-dates-for-nondiscrimination-on-the-basis-of-disability-accessibility-of-web (snippet: the page redirected; the original dates and the 91 FR 20902 citation come from the search result). Original rule: https://www.federalregister.gov/documents/2024/04/24/2024-07758/nondiscrimination-on-the-basis-of-disability-accessibility-of-web-information-and-services-of-state (snippet)
[B11] GOV.UK Service Manual. Testing for accessibility. https://www.gov.uk/service-manual/helping-people-to-use-your-service/testing-for-accessibility
[B12] WebAIM (2026). The WebAIM Million, 2026 edition (data collected February 2026, page updated 30 March 2026). https://webaim.org/projects/million/

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| A11Y-01 | Meet contrast minimums for text and UI parts | Strong | any visual UI |
| A11Y-02 | Never use color alone to convey meaning | Strong | status, links, charts, forms |
| A11Y-03 | Make everything work by keyboard, with visible, unobscured focus | Strong | web and desktop; mobile with keyboard or switch |
| A11Y-04 | Use semantic structure and give every control an accessible name | Strong | web and native apps |
| A11Y-05 | Respect user settings: zoom, text size, reflow, text spacing, reduced motion, forced colors | Strong | web and native apps |
| A11Y-06 | Caption and transcribe media; never autoplay sound | Strong | video, audio, live events |
| A11Y-07 | Support cognitive accessibility and accessible authentication | Strong | sign-in, multi-step flows, help |
| A11Y-08 | Design inclusively for permanent, temporary and situational limits | Moderate | product process and research |
| A11Y-09 | Test with automated tools and with people | Moderate | build pipeline and release process |
| A11Y-10 | Give images and icons text alternatives that match their purpose | Strong | any UI with images, icons or charts |

---

### A11Y-01 Meet contrast minimums for text and UI parts

**What it is.** Text needs a contrast ratio of at least 4.5:1 against its background, or 3:1 for large text (18 pt, about 24 px; or 14 pt bold, about 18.5 px).
Boundaries of controls, icons, focus rings and chart marks that carry meaning need 3:1 against adjacent colors (SC 1.4.11, AA). AAA raises text to 7:1, or 4.5:1 for large text (SC 1.4.6) [7].

**Why it works.** WCAG takes the 3:1 minimum for normal vision from ANSI/HFES 100-1988 and ISO 9241-3 and multiplies it by 1.5 to cover the contrast-sensitivity loss
of people with about 20/40 acuity, which is typical at around age 80 [1]. Large text gets 3:1 because its strokes are wider [1]. The ratio uses luminance, not hue, so it
also helps people with color vision deficiency [1]. It is the most common failure measured: low-contrast text was detected on 83.9% of home pages in 2026, up from 79.1% in 2025 [2].

**Evidence: Strong.** Formal standard (SC 1.4.3 since WCAG 2.0 in 2008; 1.4.11 since WCAG 2.1 in 2018) drawing on acuity and contrast-sensitivity studies from 1986 and 2004 (Gittings and Fozard; Arditi and Faye) [1].
Required: WCAG 2.2 SC 1.4.3 (AA) and 1.4.11 (AA, 3:1 for UI parts) [7]; EU Accessibility Act via EN 301 549; ADA Title II (WCAG 2.1 AA); Section 508 for 1.4.3 only (it uses WCAG 2.0, which has no 1.4.11).

**Limitations.**
- The WCAG 2 ratio ignores font weight and size beyond the large-text cutoff. APCA, a proposed alternative, is not part of WCAG 2.x, and the 10 September 2026 WCAG 3.0 draft does not name it: its contrast measure is a placeholder with the algorithm still to be determined [3]. Pass the WCAG 2 ratio for compliance.
- Ratios are not rounded: 4.499:1 fails. Inactive controls, pure decoration and logotypes are exempt; text over photos or gradients must still pass against the image behind it (failure F83) [1].
- A passing ratio does not make text legible; size, weight, spacing and line length still matter (VIS category).
- Brand colors often fail as text or button fills. Darken the text shade instead of asking for an exemption.

**How to measure it works.**
- Leading: `color-contrast` violations from axe-core or Lighthouse per template and per state (hover, focus, error, dark mode); expect 0.
- Lagging: task success and reading speed in sessions with low-vision or older participants; contrast-related support complaints. Benchmark: 83.9% of home pages fail [2].

**Implemented by.**
- GOV.UK Design System: text and interactive elements must meet SC 1.4.3 (AA); the main text color #0b0c0c is 19.6:1 on white (our calculation, not published by GOV.UK) [4]. No outcome published.
- Material Design 3 (Google): tonal palettes built on HCT; the library source states that a tone difference of 40 guarantees at least 3:1 and 50 guarantees at least 4.5:1 [5]. A comment in code, not a formal proof.
- Trello (September 2022): the 20 new label colors had to meet WCAG AA contrast, which the post says took extra design and development work [6]. No outcome published.

**How to detect it.**
- *Applied:* near-black text on white (or the reverse); placeholder, helper and footer text still readable; input borders and icons visible; text on photos sits on a scrim.
- *Violated:* light gray text (#999 on white is 2.85:1, #aaa 2.32:1, Tailwind v3 gray-400 2.54:1); white text on mid-tone fills (Material 2 blue 500 is 3.12:1, green 500 2.78:1, orange #ff9800 2.16:1); light-gray input borders that are the only boundary (Tailwind gray-300 is 1.47:1). Ratios computed with the WCAG formula.
- *In code:* `color: #999`, `#aaa`, `#bbb`, `#ccc`; `opacity: .5` or lower on text; `text-gray-300`, `text-gray-400`; `::placeholder` lighter than #757575; `border: 1px solid #ddd` on inputs. Native: color pairs in theme files and asset catalogs.
- *Quick test:* run axe DevTools or Lighthouse, then check hover, focus, error and dark-mode states and text over images by hand. On white, #767676 is the lightest gray that passes 4.5:1 (4.54:1; #777777 gives 4.48:1).

**How to implement.**
1. Put text, border, icon and focus colors in design tokens and record the ratio of each allowed foreground and background pair: 4.5:1 for text; 3:1 for large text, UI parts and focus rings.
2. Build palettes by lightness steps (Material's 40 and 50 tone rule) so pairs pass by construction [5].
3. Darken brand colors used for text or fills until they pass; keep the brand shade for large decoration.
4. Check every state: hover, active, focus, selected, error, placeholder, dark theme, text on images (add a scrim), chart marks (3:1; see A11Y-02).
5. Run `color-contrast` in CI and fail on new violations; check gradients and images by hand, because tools cannot judge them.

**Sources.**
[1] W3C (2024). Understanding SC 1.4.3 Contrast (Minimum). https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
[2] WebAIM (2026). The WebAIM Million, 2026 edition. https://webaim.org/projects/million/
[3] W3C (2026-09-10). W3C Accessibility Guidelines (WCAG) 3.0, Working Draft. https://www.w3.org/TR/wcag-3.0/
[4] GOV.UK Design System. Colour. https://design-system.service.gov.uk/styles/colour/
[5] Material Foundation. material-color-utilities, typescript/hct/hct.ts (comment on tone difference and contrast). https://github.com/material-foundation/material-color-utilities/blob/main/typescript/hct/hct.ts
[6] Atlassian (2022-09-13). 20 new Trello label colors. https://www.atlassian.com/blog/trello/20-new-trello-label-colors
[7] W3C (2024). WCAG 2.2, SC 1.4.6 (AAA, 7:1) and 1.4.11. https://www.w3.org/TR/WCAG22/

### A11Y-02 Never use color alone to convey meaning

**What it is.** Anything shown by color (status, errors, required fields, links, chart series, selected state) must also be available through text, an icon, a shape,
a pattern or position (SC 1.4.1, A).

**Why it works.** About 1 in 12 men (8%) and 1 in 200 women (0.5%) have color vision deficiency, most often red-green [1][2]; Colour Blind Awareness puts it at about 300 million people worldwide [2].
People with partial sight, older adults and people on monochrome or limited-color displays also lose color cues, and a color that is not written down does not reach a screen reader [3].
Scanners were weak here: in the UK Government Digital Service's 2017 test, links distinguished only by color were missed by all ten automated tools [4]; current axe versions include a `link-in-text-block` rule [8].

**Evidence: Strong.** WCAG 2.2 SC 1.4.1 Use of Color (A), present since WCAG 2.0 (2008). Required: every regime in the baseline (Level A).

**Limitations.**
- Color may stay as one cue among several; the rule bans it as the only cue. Browser-controlled visited-link colors are exempt [3].
- A link in running text passes without an underline only if it has at least 3:1 contrast against the surrounding text; an underline is the simpler fix [3].
- Emulating one deficiency is not enough: GitHub ships separate themes for red-green and for blue-yellow deficiency [5]. For many series or tags, use direct labels, not a longer legend.
- Error message wording is covered by ERR-04 and FRM-09; this rule only requires that a red border or red text is not the sole error signal.

**How to measure it works.**
- Leading: axe `link-in-text-block` violations (0) [8], plus a grayscale pass in which every status, link, chart and error is still understood.
- Lagging: error rate and task success with participants who have color vision deficiency; support tickets such as "which one is the red one".

**Implemented by.**
- GitHub (19 April 2022): public beta of a Protanopia & Deuteranopia theme and a new Tritanopia theme; the earlier single Colorblind theme was split based on customer feedback [5]. No outcome published.
- Trello: a colorblind-friendly mode pairs each label color with a pattern; it was kept when label colors grew from 10 to 30 in September 2022 [6]. The post does not say when the mode began (a third-party site says 2014; unverified). No outcome published.

**How to detect it.**
- *Applied:* inline links underlined; status chips contain words or icons; required fields say "(required)"; errors carry an icon and text; chart lines have markers or direct labels.
- *Violated:* red and green dots with no label; "fields in red are required"; links that differ from body text only by hue; chart legends that map colors only; invalid inputs marked by a red border alone; availability calendars or heatmaps coded by color only.
- *In code:* `text-decoration: none` on `a` inside paragraphs or prose; `.error` or `.status-red` classes that set only `color` or `border-color`; `aria-invalid="true"` with no visible message; SVG or canvas series that differ only in `stroke` or `fill`. Native: states that differ only by tint.
- *Quick test:* in Chrome DevTools, Rendering, Emulate vision deficiencies, choose Achromatopsia, then Protanopia, Deuteranopia and Tritanopia; check every state, link, chart and error [7].

**How to implement.**
1. Add a second cue to each color: a word, icon, shape, pattern, underline, weight or position.
2. Underline links in body text. If the design drops the underline, keep 3:1 against the surrounding text and add a non-color cue on hover and focus [3].
3. Charts: label series directly, vary marker shapes or line styles, print values where space allows; keep a legend as a backup, not the only key.
4. Forms: mark required fields in words; show errors with icon, message and color together (ERR-04, FRM-09).
5. For user-assigned colors (labels, tags), offer patterns or a colorblind-safe palette, as Trello and GitHub do.
6. Check designs in grayscale and in the three deficiency emulations before handoff.

**Sources.**
[1] National Eye Institute (page updated 2025-11-05). Color blindness. https://www.nei.nih.gov/learn-about-eye-health/eye-conditions-and-diseases/color-blindness
[2] Colour Blind Awareness. Colour blindness (8% of men, 0.5% of women, about 300 million people). https://www.colourblindawareness.org/colour-blindness/
[3] W3C (2024). Understanding SC 1.4.1 Use of Color. https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html
[4] Duran, M. (2017-02-24). What we found when we tested tools on the world's least accessible webpage. GDS Accessibility blog. https://accessibility.blog.gov.uk/2017/02/24/what-we-found-when-we-tested-tools-on-the-worlds-least-accessible-webpage/
[5] GitHub (2022-04-19). Protanopia & Deuteranopia Colorblind Themes Beta. https://github.blog/changelog/2022-04-19-protanopia-deuteranopia-colorblind-themes-beta/
[6] Atlassian (2022-09-13). 20 new Trello label colors. https://www.atlassian.com/blog/trello/20-new-trello-label-colors
[7] Chrome for Developers. Apply effects (Emulate vision deficiencies). https://developer.chrome.com/docs/devtools/rendering/apply-effects
[8] Deque University. axe-core 4.10 rule descriptions. https://dequeuniversity.com/rules/axe/4.10

### A11Y-03 Make everything work by keyboard, with visible, unobscured focus

**What it is.** Every function works from the keyboard (SC 2.1.1, A) and focus never gets stuck (2.1.2, A). Users can skip repeated blocks (2.4.1, A), focus moves in a meaningful order (2.4.3, A),
and the focused control is visible (2.4.7, AA) and not entirely hidden by sticky headers, banners or chat widgets (2.4.11, AA, new in WCAG 2.2). At AAA the indicator must be at least 2 CSS px thick around the
control with a 3:1 change (2.4.13) and never partly hidden (2.4.12).

**Why it works.** Many assistive technologies, such as screen readers and switch devices, operate pages through keyboard events, and so do people who cannot use a pointer. Sighted keyboard users need to see where focus is; without it they may think the page has stopped responding [2].
Sites often break this: in 2025 67% of sites explicitly removed the default focus outline (up 14% from 2024) and only about 24% of pages had a skip link [3].

**Evidence: Strong.** WCAG 2.2 SC 2.1.1, 2.1.2, 2.4.1, 2.4.3 (A) and 2.4.7, 2.4.11 (AA) [1][5]; all but 2.4.11 date from WCAG 2.0 (2008), and 2.4.11 from WCAG 2.2 (2023). Required: 2.1.1 to 2.4.7 under every regime in the baseline; 2.4.11 only where WCAG 2.2 is the benchmark (GOV.UK now, EN 301 549 v4.1.1 once cited). 2.4.12 and 2.4.13 are AAA.

**Limitations.**
- 2.4.11 fails only when the focused item is entirely hidden; partly covered passes at AA, though less is better [2].
- The 67% figure counts sites that remove the default outline, not sites with no visible indicator; removal is acceptable only when a visible replacement exists (SC 2.4.7) [3].
- Custom widgets (tabs, menus, grids, comboboxes) follow arrow-key conventions in the ARIA Authoring Practices Guide; Tab alone is not enough. Single-character shortcuts must be switchable off, remappable or active only on focus (SC 2.1.4, A).
- Pointer target size is PLT-03. Mobile screen reader users navigate by gesture, but external keyboards and switch control still need this rule.

**How to measure it works.**
- Leading: keyboard-only completion of the top three tasks (pass or fail; expect 100%); axe `tabindex`, `bypass`, `skip-link`, `scrollable-region-focusable` and `aria-hidden-focus` violations (0) [6].
- Lagging: task time and success for keyboard, switch and screen reader users; support tickets about unreachable controls.

**Implemented by.**
- GOV.UK Design System: focus is a yellow background with a thick black bottom border on links, and a yellow outline with a thick black border on inputs; it is designed to meet SC 1.4.11 on any GOV.UK background, yellow against dark ones and the black border against light ones [4]. Our calculation: yellow on white is 1.35:1, black on yellow 14.5:1.
- Adoption at scale: about 24% of pages have a skip link (HTTP Archive, 2025) [3]. No company-level outcome data found.

**How to detect it.**
- *Applied:* the first Tab reveals a "Skip to main content" link; every stop in the tab order shows a clear ring; dialogs take focus and return it on close; Esc closes popups; a sticky header does not cover the focused field.
- *Violated:* no visible focus; menus and tooltips that open on hover only; click handlers on `div` or `span`; custom selects that need a mouse; focus lost after a route change or dialog close; keyboard traps in embedded widgets; focus hidden behind a cookie bar.
- *In code:* `outline: none`, `outline: 0` or `:focus { outline` with no `:focus-visible` replacement; `onClick` on non-interactive tags; `role="button"` without `tabindex="0"` and key handlers; `tabindex="1"` or higher; no `href="#main"` skip link; `position: sticky` or `fixed` headers without `scroll-padding-top`. Native: custom views that are not focusable or lack accessibility traits.
- *Quick test:* put the mouse aside. Tab and Shift+Tab through the page and the main flow: is focus visible at every stop; can you operate everything with Enter, Space, arrows and Esc; can you leave every widget? Repeat at 400% zoom with sticky bars showing.

**How to implement.**
1. Use native `<button>`, `<a href>`, `<input>`, `<select>` and `<dialog>`; they bring focus and key handling for free (A11Y-04).
2. Never remove the outline without a replacement. Style `:focus-visible` with at least 3:1 contrast against adjacent colors and a 2 px or thicker line: `:focus-visible { outline: 3px solid var(--focus-color); outline-offset: 2px; }`.
3. Make the first focusable element a skip link: `<a class="skip-link" href="#main">Skip to main content</a>` and `<main id="main" tabindex="-1">`.
4. Keep DOM order equal to visual order and avoid positive `tabindex`.
5. Dialogs: open with `dialog.showModal()` (the rest of the page becomes inert), put focus inside, return it to the trigger on close, close on Esc.
6. Sticky UI: set `scroll-padding-top` to the header height so focused items scroll clear of it (technique C43), and make banners dismissible [2].
7. After single-page-app navigation, move focus to the new page heading or main region.

**Sources.**
[1] W3C (2024). Web Content Accessibility Guidelines (WCAG) 2.2, SC 2.1.1, 2.1.2, 2.4.1, 2.4.3, 2.4.7, 2.4.11-2.4.13. https://www.w3.org/TR/WCAG22/
[2] W3C (2024). Understanding SC 2.4.11 Focus Not Obscured (Minimum). https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html
[3] HTTP Archive (2025). Web Almanac 2025, Accessibility chapter. https://almanac.httparchive.org/en/2025/accessibility
[4] GOV.UK Design System. Focus states. https://design-system.service.gov.uk/get-started/focus-states/
[5] W3C WAI. What's new in WCAG 2.2. https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
[6] Deque University. axe-core 4.10 rule descriptions. https://dequeuniversity.com/rules/axe/4.10

### A11Y-04 Use semantic structure and give every control an accessible name

**What it is.** Build with elements that carry meaning (headings, landmarks, lists, tables, buttons, links, labeled form controls) so every part has a role, name, state and value
(SC 1.3.1 and 4.1.2, A). Headings and labels describe their topic (2.4.6, AA); the visible label is part of the accessible name (2.5.3, A); the page language is set (3.1.1, A);
status messages are exposed without moving focus (4.1.3, AA). Image alternatives are A11Y-10.

**Why it works.** Assistive technology reads the accessibility tree, not pixels. Screen reader users move by structure: in WebAIM's July to August 2026 survey (1,780 respondents), 67.8% first navigate a long page by headings,
12.5% use Find and 3.4% start with landmarks, though 28.3% use landmarks often or whenever available [1]. Missing names are common: 51.0% of home pages had unlabeled form inputs, 46.3% empty links, 30.6% empty buttons
and 13.5% no page language [2]. ARIA is not a cure. 82.7% of home pages used ARIA (over 133 attributes per page, up 27% in a year) and those pages averaged 59.1 detected errors against 42 without ARIA; WebAIM cautions that complex pages use more ARIA, so this is correlation [2].
W3C's first rule of ARIA use says to use a native element when one has the semantics and behavior you need [3]; the APG adds that no ARIA is better than bad ARIA [4].

**Evidence: Strong.** WCAG 2.2 SC 1.3.1, 2.5.3, 3.1.1, 4.1.2 (A) and 2.4.6, 4.1.3 (AA) [6]. Required: 1.3.1, 2.4.6, 3.1.1 and 4.1.2 (WCAG 2.0, 2008) under every regime in the baseline; 2.5.3 and 4.1.3 come from WCAG 2.1 (2018), so EN 301 549 v3.2.1 and ADA Title II require them and Section 508 (WCAG 2.0) does not.

**Limitations.**
- ARIA is needed where HTML has no element (tabs, comboboxes, trees, live regions). Follow APG patterns and keep keyboard support. W3C's "Using ARIA", the source of the first rule, is now a Discontinued Draft (24 February 2026) that points to the APG [3][4].
- A name that differs from the visible text breaks voice control ("click Search"); the accessible name must contain the visible label (SC 2.5.3).
- Placeholders and `title` are weak name sources; label guidance is in the FRM category. Link-text wording is in the CON category.
- Landmarks and headings help only if the outline is sound: one `h1`, no skipped levels, few landmarks, a label on each extra `nav`.
- In the same WebAIM data, most pages on common CMS platforms had fewer errors than average and nearly all popular JavaScript libraries were linked to more errors (correlation) [2].

**How to measure it works.**
- Leading: axe violations for `button-name`, `link-name`, `label`, `html-has-lang`, `aria-valid-attr`, `aria-required-attr`, `nested-interactive`, `aria-hidden-focus` (all 0) [7]; the screen reader headings list reads like a table of contents.
- Lagging: screen reader task success and time; detected errors per page over releases (benchmark: 56.1 per page in 2026) [2].

**Implemented by.**
- GOV.UK Design System password input: a native input with a Show button; two password fields on one page need distinct button labels, and a known issue is that a button label can mismatch the field state when a browser or screen reader adds its own toggle [5]. No outcome published.
- W3C ARIA Authoring Practices Guide: reference patterns and the principle that a role is a promise to implement the behavior [4]. No company outcome data found.

**How to detect it.**
- *Applied:* one `h1` and ordered subheadings; `header`, `nav`, `main`, `footer`; real `<button>` and `<a href>`; every input has a visible `<label for>`; icon buttons announce a name; `<html lang>` is set; toasts use `role="status"`.
- *Violated:* `div` or `span` with click handlers; headings chosen for size; `<a>` without `href` used as a button; icon-only buttons with no name; placeholder-only inputs; repeated "Read more" links; `aria-label` that differs from the visible text; `aria-hidden="true"` on focusable elements; tables used for layout.
- *In code:* `<div onClick`, `<span onClick`, `role="button"`, `<a ` without `href`, `<button>` containing only `<svg` or `<i` with no `aria-label`, `<input` with no `id` plus matching `<label for>` or `aria-label`, `<html>` with no `lang`, `aria-hidden="true"` on a control. Native: `accessibilityLabel` and traits (iOS), `contentDescription` (Android), `AutomationProperties.Name` (WinUI).
- *Quick test:* open the DevTools Accessibility pane or a screen reader's headings and landmarks list, then Tab through and listen: each control should announce a name and role; run axe.

**How to implement.**
1. Start from native elements: `<button>` for actions, `<a href>` for navigation, `<label for>` with `<input>`, `<nav>`, `<main>`, `<h1>` to `<h6>` in order, `<ul>`, `<table>` with `<th scope>`.
2. Name every control from visible text. For icon-only controls: `<button aria-label="Search"><svg aria-hidden="true">...</svg></button>`. If the control shows text, the name must include it.
3. Set `<html lang="en">` (and `lang` on phrases in another language).
4. Use ARIA only to fill gaps: do not override native roles, keep keyboard support, never put `aria-hidden` on a focusable element [3].
5. Announce changes without moving focus: `role="status"` for confirmations, `role="alert"` for errors; keep the container in the DOM before you update its text (SC 4.1.3).
6. Lint and test: `eslint-plugin-jsx-a11y` in the editor, axe in CI, a screen reader pass on key flows (A11Y-09).

**Sources.**
[1] WebAIM (2026). Screen Reader User Survey #11 (July to August 2026, n = 1,780). https://webaim.org/projects/screenreadersurvey11/
[2] WebAIM (2026). The WebAIM Million, 2026 edition. https://webaim.org/projects/million/
[3] W3C (2026-02-24, Discontinued Draft). Using ARIA. https://www.w3.org/TR/using-aria/
[4] W3C WAI. ARIA Authoring Practices Guide, Read Me First. https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/
[5] GOV.UK Design System. Password input. https://design-system.service.gov.uk/components/password-input/
[6] W3C (2024). Web Content Accessibility Guidelines (WCAG) 2.2. https://www.w3.org/TR/WCAG22/
[7] Deque University. axe-core 4.10 rule descriptions. https://dequeuniversity.com/rules/axe/4.10

### A11Y-05 Respect user settings: zoom, text size, reflow, text spacing, reduced motion, forced colors

**What it is.** Pages keep working when people change how content is shown: text resized to 200% (SC 1.4.4, AA), reflow in a 320 CSS px wide viewport with no sideways scrolling (1.4.10, AA), user-set text spacing
(1.4.12, AA: line height 1.5, paragraph spacing 2, letter spacing 0.12 and word spacing 0.16 times the font size), and OS settings for reduced motion and forced colors. Motion over 5 seconds needs pause, stop or hide (2.2.2, A);
no more than three flashes a second (2.3.1, A); at AAA, interaction-triggered animation can be turned off (2.3.3).

**Why it works.** People with low vision rely on screen magnifiers and larger browser fonts, and a zoom lock removes that [1]. 320 CSS px equals a 1280 px window at 400% zoom, the case reflow protects [2].
Large-scale motion (zooms, parallax, spinning) can trigger vestibular symptoms such as loss of balance and nausea [3]. Forced colors modes such as Windows contrast themes replace page colors, remove shadows and gradient backgrounds,
so meaning kept there disappears [4]. Platforms now ship the switches: Apple's Reduce Motion dates from iOS 7 (2013), and iOS 7.0.3 (22 October 2013) extended it from parallax to the new zoom animations [3][5];
Safari 10 (2016) always allows pinch zoom and ignores the viewport `user-scalable` setting [6].

**Evidence: Strong.** WCAG 2.2 SC 1.4.4, 1.4.10, 1.4.12 (AA), 2.2.2, 2.3.1 (A), 2.3.3 (AAA) [9], dating from 2008 (1.4.4, 2.2.2, 2.3.1) and 2018 (the rest); `prefers-reduced-motion` has been in all major browsers since January 2020 and `forced-colors` since September 2022 [4][7].
Required: 1.4.4, 2.2.2 and 2.3.1 under every regime in the baseline; 1.4.10 and 1.4.12 come from WCAG 2.1 (EN 301 549 v3.2.1, ADA Title II); 2.3.3 is not required anywhere.

**Limitations.**
- Reflow exempts content that needs two-dimensional layout (maps, data tables, video, games, toolbars); only that section may scroll sideways [2].
- Reduce motion does not mean remove all motion: keep motion that carries meaning and swap vestibular triggers (scale, spin, parallax) for fades [3][7].
- `prefers-reduced-motion` does not satisfy 2.2.2: motion that starts by itself and lasts over 5 seconds still needs an on-page pause control.
- Safari ignoring `user-scalable=no` does not excuse it: axe still flags `user-scalable=no` and `maximum-scale` below 2 as critical [1].
- Common belief vs finding: Reduce Motion was not added after iOS 7 shipped. It was in iOS 7.0 but turned off only parallax; iOS 7.0.3 widened it to the zoom animations that still bothered some users [5].

**How to measure it works.**
- Leading: axe `meta-viewport` violations (0); manual pass at 200% text, at 400% zoom in a 1280 px window, with the text-spacing values applied, with OS reduce motion on, and in a Windows contrast theme.
- Lagging: share of sessions with `prefers-reduced-motion: reduce` or large text (`matchMedia` counts) to size the need; complaints about clipped text or motion.

**Implemented by.**
- Apple: Reduce Motion in iOS 7 (2013); iOS 7.0.3 (22 October 2013) replaced app-switch, unlock and folder zooms with a faster cross-fade; a public API followed in 2014 and macOS got the setting in 2016 [3][5]. No usage data published.
- WebKit (15 May 2017): wrote up the `prefers-reduced-motion` media feature and adopted it on Apple's own sites [3]; it is now in every major browser [7].
- Adoption (HTTP Archive, 2025): 19% of mobile sites restrict scaling and about half of pages contain a `prefers-reduced-motion` rule [8]; Safari 10 (2016) already ignores zoom locks [6].

**How to detect it.**
- *Applied:* single column at 320 px with no page-level horizontal scroll; text grows at 200% without clipping; a `prefers-reduced-motion: reduce` block swaps motion for fades; borders and focus survive a contrast theme; carousels pause.
- *Violated:* `user-scalable=no` or `maximum-scale=1`; fixed heights or `overflow: hidden` that clip text; `px` root font size; parallax, zoom-on-scroll or spinners that ignore the OS setting; shadow-only borders and icons that vanish in forced colors.
- *In code:* `user-scalable=no`, `maximum-scale=1`; `html { font-size: 14px }`; `height:` in px on text containers; `animation:`, `transition:` or `scroll-behavior: smooth` with no `prefers-reduced-motion` override; `forced-color-adjust: none`; `box-shadow` as the only edge. Native: Dynamic Type (iOS), `sp` units (Android), `UIAccessibility.isReduceMotionEnabled`.
- *Quick test:* zoom to 400% in a 1280 px window; set OS reduce motion; apply a text-spacing stylesheet; look for clipped text, sideways scroll and leftover motion.

**How to implement.**
1. Viewport: `<meta name="viewport" content="width=device-width, initial-scale=1">`; never `user-scalable=no` or a `maximum-scale` below 2 [1].
2. Use rem, em and % with `max-width: 100%`; let flex and grid wrap; add `overflow-wrap: anywhere`; do not fix heights on text containers; let tables and maps scroll inside their own container [2].
3. Test text spacing: apply `line-height: 1.5; letter-spacing: .12em; word-spacing: .16em` and `p { margin-bottom: 2em }` and confirm nothing is cut off.
4. Motion: write the default animation, then override it: `@media (prefers-reduced-motion: reduce) { .hero { animation: fade 1s; } }`. For script-driven motion read `matchMedia('(prefers-reduced-motion: reduce)')` and listen for changes [3][7]. Pause carousels and autoplay motion.
5. Forced colors: use real borders instead of shadows (MDN swaps a shadow for `border: 2px ButtonText solid` inside `@media (forced-colors: active)`), let icons take `currentColor`, and keep `forced-color-adjust: none` for small fixes only [4].
6. Native apps: support Dynamic Type or font scale and read the system reduce-motion flag.

**Sources.**
[1] Deque University. axe rule meta-viewport (axe-core 4.10). https://dequeuniversity.com/rules/axe/4.10/meta-viewport
[2] W3C (2024). Understanding SC 1.4.10 Reflow. https://www.w3.org/WAI/WCAG22/Understanding/reflow.html
[3] Craig, J. (2017-05-15). Responsive Design for Motion. WebKit blog. https://webkit.org/blog/7551/responsive-design-for-motion/
[4] MDN. forced-colors media feature. https://developer.mozilla.org/en-US/docs/Web/CSS/@media/forced-colors
[5] Daring Fireball (2013-10-22). Apple Releases iOS 7.0.3 With Updated Reduce Motion Setting (links MacStories). https://daringfireball.net/linked/2013/10/22/ios-7
[6] Apple. What's New in Safari 10.0 (pinch-to-zoom always on; `user-scalable` ignored). https://developer.apple.com/library/archive/releasenotes/General/WhatsNewInSafari/Articles/Safari_10_0.html
[7] MDN. prefers-reduced-motion media feature. https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion
[8] HTTP Archive (2025). Web Almanac 2025, Accessibility chapter. https://almanac.httparchive.org/en/2025/accessibility
[9] W3C (2024). Web Content Accessibility Guidelines (WCAG) 2.2. https://www.w3.org/TR/WCAG22/

### A11Y-06 Caption and transcribe media; never autoplay sound

**What it is.** Prerecorded video with sound needs captions (SC 1.2.2, A); live video needs live captions (1.2.4, AA); prerecorded video needs audio description (1.2.5, AA); audio-only content needs a transcript (1.2.1, A).
Audio that starts by itself and plays over 3 seconds must be stoppable or have its own volume control (1.4.2, A). Moving or auto-updating content that starts by itself and lasts over 5 seconds needs pause, stop or hide (2.2.2, A).

**Why it works.** Captions serve deaf and hard-of-hearing viewers first and help everyone else too. A 2015 peer-reviewed review of more than 100 studies found captions improve comprehension, attention and memory for children, students and adults, hearing or not [1].
In a 2016 survey of 2,124 US students at 15 universities, caption users most often cited focus, retention and poor audio quality, and 98.6% of them called captions helpful [2]. Autoplaying sound takes control from the user. Chrome 66 (April 2018) blocks it unless the user has interacted with the site, has a high media engagement score or installed
the site; Chrome gives its reasons as a better experience, fewer ad-blocker installs and less data use [3].

**Evidence: Strong.** WCAG 2.2 SC 1.2.1, 1.2.2, 1.4.2, 2.2.2 (A) and 1.2.4, 1.2.5 (AA) [7], all from WCAG 2.0 (2008), plus a peer-reviewed review from 2015 [1]. Required: these WCAG 2.0 criteria under Section 508, EN 301 549 and ADA Title II, each with its own exceptions.
The subtitle-use and sound-off statistics often quoted with this rule are Weak (see Limitations).

**Limitations.**
- Machine captions are drafts. YouTube says automatic captions can misrepresent speech (accents, noise) and creators should review and edit them; live auto-captions are English only [4].
- Widely repeated statistics we could not trace: "7.5 million UK TV subtitle users, 6 million of them with no hearing impairment" is attributed to Ofcom's television access services work (the year is not given in the Wikipedia article that repeats it; the Ofcom page returned HTTP 403) [8]. Verizon Media and Publicis Media (2019) sound-off figures: no primary source found. Treat both as Weak.
- Muted autoplay is allowed by browsers [3], but SC 2.2.2 still needs a pause control for motion over 5 seconds.
- Audio description (1.2.5) applies when the visuals carry information the audio lacks. A transcript does not replace captions on video.

**How to measure it works.**
- Leading: share of videos with human-checked captions (expect 100%); caption word error rate; audio-only items with transcripts; media that starts with sound (expect 0).
- Lagging: caption-on rate and completion rate by caption setting (analytics or A/B); complaints. Vendor claims of completion lifts were not verified here.

**Implemented by.**
- YouTube (19 November 2009): automatic captions launched, announced on the Official Google Blog [5]; creators are told to review them [4]. No outcome published in these sources.
- Google Live Caption (Android): on-device captions for any audio the phone plays (video, podcasts, calls), processed locally [6]. The 2019 launch date and Apple's Live Captions (iOS 16) were not verified in this pass.
- Chrome (April 2018, Chrome 66): muted autoplay always allowed; sound only after user interaction or a high media engagement score; Chrome says the policy blocks about half of unwanted autoplays (its own claim) [3].

**How to detect it.**
- *Applied:* a captions control; captions on for muted autoplay; a transcript link; a described version where visuals carry information; media starts paused or muted with a visible pause button.
- *Violated:* sound on page load; `<video>` with no captions track; "captions on request"; looping background video longer than 5 seconds with no pause; auto-advancing carousels; information shown only in the visuals of a video.
- *In code:* `<video` with `autoplay` and without `muted`; `<audio autoplay`; `new Audio(` followed by `.play()` on load; no `<track kind="captions"`; `autoplay=1` in embed URLs; axe `video-caption` and `no-autoplay-audio` [9].
- *Quick test:* load the page with sound on and do not click: does anything play? Play each video: are captions available and accurate, with speakers and sound cues? Mute and watch: is the meaning kept? Is there a transcript?

**How to implement.**
1. Add synced captions in WebVTT: `<track kind="captions" srclang="en" src="talk.en.vtt" default>`; name speakers, include meaningful sounds, and edit machine drafts.
2. Provide a transcript for audio-only content and a text alternative for video; add audio description or a described version where visuals carry information (1.2.5).
3. Use real-time captions (human or reviewed speech recognition) for live events (1.2.4).
4. Do not start sound on load. If media autoplays, mute it and show a visible pause and play control; any audio over 3 seconds needs stop or independent volume (1.4.2).
5. Use a keyboard-operable, labeled player (A11Y-03, A11Y-04) and turn captions on by default for muted playback.

**Sources.**
[1] Gernsbacher, M. A. (2015). Video Captions Benefit Everyone. Policy Insights from the Behavioral and Brain Sciences 2(1), 195-202. https://pmc.ncbi.nlm.nih.gov/articles/PMC5214590/
[2] Oregon State University Ecampus (2016-10-31). Students say closed captions, transcripts aid learning (Linder, K., Student Uses and Perceptions of Closed Captions and Transcripts). https://ecampus.oregonstate.edu/news/2016/closed-captions/
[3] Chrome for Developers. Autoplay policy in Chrome. https://developer.chrome.com/blog/autoplay
[4] YouTube Help. Use automatic captioning. https://support.google.com/youtube/answer/6373554
[5] Google (2009-11-19). Automatic captions in YouTube. Official Google Blog. https://googleblog.blogspot.com/2009/11/automatic-captions-in-youtube.html
[6] Google. Use Live Caption on Android. https://support.google.com/accessibility/android/answer/9350862
[7] W3C (2024). Web Content Accessibility Guidelines (WCAG) 2.2. https://www.w3.org/TR/WCAG22/
[8] Wikipedia. Closed captioning (secondary; cites Ofcom, "Television access services", http://www.ofcom.org.uk/consult/condocs/accessservs/summary/, which we could not open). https://en.wikipedia.org/wiki/Closed_captioning
[9] Deque University. axe-core 4.10 rule descriptions. https://dequeuniversity.com/rules/axe/4.10

### A11Y-07 Support cognitive accessibility and accessible authentication

**What it is.** Do not make people remember, retype or puzzle out what the system can supply. WCAG 2.2 adds three criteria: Redundant Entry (SC 3.3.7, A), Consistent Help (3.2.6, A)
and Accessible Authentication (Minimum) (3.3.8, AA). W3C's COGA note adds eight objectives for people with cognitive and learning disabilities.

**Why it works.** Limits in memory, attention, reading and number processing make recall and transcription costly. Memorizing usernames and passwords can be very hard or impossible for some people with cognitive disabilities,
and retyping codes or solving puzzles adds burden; people with memory limits, dyslexia, dyscalculia or perception-processing limits benefit [1]. Re-entering earlier answers is hard for people who struggle to recall them, and mental fatigue raises
errors and abandonment [2]. COGA's eight objectives include helping users avoid mistakes, ensuring processes do not depend on memory, and providing help and support [3].

**Evidence: Strong.** Normative text of WCAG 2.2 SC 3.3.7, 3.2.6 (A) and 3.3.8 (AA) [5][6]. The criteria date from October 2023, so published outcome data are thin. COGA is a W3C Working Group Note (29 April 2021): supplemental guidance, not needed for conformance [3].
Required: only where WCAG 2.2 is the benchmark (GOV.UK now; EN 301 549 v4.1.1 once cited); not under Section 508, ADA Title II or EN 301 549 v3.2.1.

**Limitations.**
- 3.3.8 still allows object recognition and personal-content tests at AA; AAA 3.3.9 forbids them. It covers logging in, not creating an account, though the same techniques help sign-up [1].
- Redundant Entry has exceptions: essential re-entry, security (confirming a new password) and information that is no longer valid. Browser autofill alone does not count; the site must supply the data [2].
- A code the user must retype fails; pasting or autofill must work. Email-link login passes (G218); text and puzzle CAPTCHAs need a non-cognitive alternative, and an audio CAPTCHA that needs transcribing does not count. Device methods such as fingerprint or WebAuthn are not cognitive tests [1].
- Security policies that block paste conflict with this rule; GOV.UK says to always allow paste [4].
- COGA patterns come from user needs and have little quantitative outcome evidence. Error message wording is ERR-04 and FRM-09.

**How to measure it works.**
- Leading: fields a user must retype in the main flows (expect 0 outside the exceptions); login works with paste, autofill and a password manager; help link in the same place on five sampled pages.
- Lagging: login success, password-reset and lockout rates; drop-off at sign-in and between form steps; task success with participants who have cognitive or learning disabilities.

**Implemented by.**
- GOV.UK Design System password input: always allow paste, optional Show password button, `new-password` and `current-password` autocomplete values, no `maxlength`, no confirm-password field [4]. The page does not cite SC 3.3.8 and publishes no outcome.
- W3C's own Redundant Entry examples: a "billing address same as delivery" checkbox, a card number kept after a payment error, a search term kept on the results page [2]. These are patterns, not company results.
- No company outcome data found for 3.3.7, 3.2.6 or 3.3.8.

**How to detect it.**
- *Applied:* login accepts paste and password-manager autofill; a passkey, email-link or single sign-on path exists; "Show password"; checkout offers "same as shipping"; review steps are pre-filled; the help or contact link sits in the same place on every page.
- *Violated:* paste blocked; "type the characters" or image-puzzle CAPTCHA with no alternative; the same email or address asked twice; "enter the 3rd and 5th character of your passphrase"; one-time codes that cannot be pasted or autofilled; a help link that moves between pages.
- *In code:* `onpaste` handlers or `preventDefault()` on paste; `autocomplete="off"` on login fields; missing `autocomplete="username"`, `current-password`, `new-password` or `one-time-code`; `type="text"` for passwords; `maxlength` on password inputs; duplicate `name="email"` inputs in one flow; reCAPTCHA v2 image challenges.
- *Quick test:* sign in with a password manager and paste a code; walk the longest form and count retyped items; open five pages and compare the help link's place.

**How to implement.**
1. Login: allow paste and autofill, set correct `autocomplete` values, and offer a passkey, email link or single sign-on as an alternative path; never require transcribing a code.
2. Replace puzzle or transcription CAPTCHAs with a non-cognitive check or an alternative route.
3. Multi-step flows: keep entered data in the session and pre-fill later steps; offer "same as" checkboxes; keep search terms and failed-payment inputs; ask again only for security or expired data [2].
4. Put help (contact, chat, FAQ link) in the same relative order on every page of the set, sign-in pages included (3.2.6).
5. Apply COGA basics: plain wording (CON category), one clear next step, undo and confirmation for risky actions (ERR category), warning and extension for time limits.
6. Test with participants who have cognitive or learning disabilities (A11Y-08).

**Sources.**
[1] W3C (2024). Understanding SC 3.3.8 Accessible Authentication (Minimum). https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html
[2] W3C (2024). Understanding SC 3.3.7 Redundant Entry. https://www.w3.org/WAI/WCAG22/Understanding/redundant-entry.html
[3] W3C (2021-04-29). Making Content Usable for People with Cognitive and Learning Disabilities (Working Group Note). https://www.w3.org/TR/coga-usable/
[4] GOV.UK Design System. Password input. https://design-system.service.gov.uk/components/password-input/
[5] W3C (2024). Web Content Accessibility Guidelines (WCAG) 2.2. https://www.w3.org/TR/WCAG22/
[6] W3C WAI. What's new in WCAG 2.2. https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/

### A11Y-08 Design inclusively for permanent, temporary and situational limits

**What it is.** Treat a limit as a mismatch between a person and an interaction, not as a trait of the person. The same barrier hits someone with a permanent condition (one arm), a temporary one (an arm injury)
and a situation (holding a baby). Start from the permanent case, involve people who have it, and extend the solution to many.

**Why it works.** Disability is common and rising: WHO estimates 1.3 billion people, 16% or about 1 in 6, live with significant disability (2023) [1]. Microsoft's inclusive design principles are to recognize exclusion,
learn from diversity, and solve for one and extend to many [2]. The "extend to many" step has direct support in one case: captions built for deaf viewers improve comprehension for hearing viewers too (A11Y-06) [6].
The curb-cut effect names the same pattern from city planning: Angela Glover Blackwell argues that measures for excluded groups often benefit everyone [3]. The persona spectrum (permanent, temporary, situational; for example one arm, an arm injury, holding a baby)
comes from Microsoft's inclusive design toolkit (the research lead dates it 2016). We could not open the toolkit PDF (over the fetch size limit) and Microsoft's main site pages do not describe it, so the spectrum, its examples and the date are unverified.

**Evidence: Moderate.** The prevalence data (WHO) and one peer-reviewed review (captions, 2015) are solid. The persona spectrum and the curb-cut effect are frameworks and case studies with no controlled tests, so read "benefits everyone" as plausible, not proven.
Required: nothing directly; it motivates the WCAG-based rules above.

**Limitations.**
- The curb-cut effect is an advocacy essay (Stanford Social Innovation Review, Winter 2017; the page's own citation shows 2016). Blackwell offers it as a framing, and the essay does not discuss captions or voice features [3].
- The persona spectrum can mislead if used instead of people: a situational limit is brief and can be left; a permanent one cannot. Include people with disabilities; do not stand in for them.
- Accommodations can conflict (for example less motion against richer feedback), so keep user-controlled settings (A11Y-05).
- A purpose-built device such as the Xbox Adaptive Controller needed partners and new hardware; most products only need the process.

**How to measure it works.**
- Leading: participants with disabilities per research round; share of specs with a "who could this exclude" check; settings coverage (captions, text size, reduce motion, input alternatives).
- Lagging: task success and time by cohort (with and without assistive technology); adoption of accessibility settings; accessibility complaints.

**Implemented by.**
- Microsoft, Xbox Adaptive Controller: announced 16 May 2018, on sale 4 September 2018 at US$99.99; built with AbleGamers, The Cerebral Palsy Foundation, Craig Hospital, SpecialEffect and Warfighter Engaged, with gamers who have limited mobility; works with common adaptive switches [4][5]. No sales or usage data in these sources.
- Microsoft Inclusive Design: the three principles, the Inclusive 101 Guidebook and activity cards [2].
- Curb cuts (anecdote): the first appeared in Kalamazoo, Michigan, in 1945; Berkeley installed its first official one in 1972 after advocates pushed; the ADA (26 July 1990) required them; strollers and luggage users also benefit [3].

**How to detect it.**
- *Applied:* research plans and usability sessions include people with disabilities; tasks offer more than one input route (touch, keyboard, voice); settings for text size, captions and reduced motion; situational cases (one hand, glare, noise, muted, slow network) in design reviews; an accessibility statement with a feedback route.
- *Violated:* one input mode only (gesture-only, hover-only, voice-only); "edge case" language about assistive technology users; accessibility reviewed only at the end; no way to report a barrier; drag-only or tiny-target interactions with no alternative (see PLT-03).
- *In code:* swipe, drag or `pointermove` handlers with no button or keyboard equivalent; no `prefers-*` media queries; no `@media (hover: none)` fallback; no accessibility statement or feedback `mailto:` link.
- *Quick test:* use the product one-handed, in bright light, with sound off, and with the keyboard only; list what breaks. Check the footer for an accessibility statement.

**How to implement.**
1. Add "who could this exclude, permanently, temporarily or in a situation?" to design reviews; use the persona spectrum to find cases.
2. Offer at least two ways to do each task: pointer and keyboard, gestures with button alternatives, drag with a click alternative (SC 2.5.1 Pointer Gestures, A; 2.5.7 Dragging Movements, AA, new in 2.2 [7]). Target size is PLT-03.
3. Recruit and pay participants with disabilities from prototype stage; observe task success with their own tools.
4. Respect OS settings and surface in-app ones (A11Y-05); prefer defaults that help everyone, such as captions on for muted video.
5. Publish an accessibility statement with a contact route; log, fix and date reported barriers.

**Sources.**
[1] World Health Organization (2023-03-07). Disability. https://www.who.int/news-room/fact-sheets/detail/disability-and-health
[2] Microsoft. Inclusive Design (principles, tools). https://inclusive.microsoft.design/
[3] Blackwell, A. G. (2017). The Curb-Cut Effect. Stanford Social Innovation Review, Winter 2017. https://ssir.org/articles/entry/the_curb_cut_effect
[4] Xbox Wire (2018-05-16). Xbox Adaptive Controller. https://news.xbox.com/en-us/2018/05/16/xbox-adaptive-controller/
[5] Wikipedia. Xbox Adaptive Controller (release date 2018-09-04 and price, citing IGN and The Verge). https://en.wikipedia.org/wiki/Xbox_Adaptive_Controller
[6] Gernsbacher, M. A. (2015). Video Captions Benefit Everyone. Policy Insights from the Behavioral and Brain Sciences 2(1). https://pmc.ncbi.nlm.nih.gov/articles/PMC5214590/
[7] W3C WAI. What's new in WCAG 2.2. https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/

### A11Y-09 Test with automated tools and with people

**What it is.** Run automated checkers (axe-core, Lighthouse, WAVE) on every build for what tools can detect, and add manual checks (keyboard, zoom, screen reader) and sessions with disabled users for the rest.
Do not use an overlay widget in place of either.

**Why it works.** Tools see code, not meaning: they cannot judge whether alt text is accurate or focus order is logical. Two independent studies show the gap. Deque (2021) analyzed more than 2,000 audits, 13,000 pages and nearly 300,000 issues
and found its axe tools fully covered about 57% of issues by volume; it is a vendor study and counts issues, not criteria [1]. The UK GDS (2017) ran 10 free tools against a page with 143 deliberate failures: the best found 37% (41% counting prompts for manual checks),
the worst 17%, all tools together about 71%, and 42 failures were found by no tool, including links distinguished only by color [2]. The WebAIM Million is itself an automated count [3]. People matter: in WebAIM's 2026 survey of 1,780 screen reader users, JAWS (55.0%), NVDA (32.9%) and VoiceOver (6.5%)
are the primary desktop screen readers, and 44.9% say web accessibility did not change in the past year (32.2% more accessible, 22.9% less) [4].

**Evidence: Moderate.** Two studies with stated methods (2017 and 2021) agree that automation alone is not enough; one is by a vendor, the other used an engineered page. Required: no law prescribes the method, but GOV.UK requires a formal audit before public beta [5].

**Limitations.**
- The numbers are not comparable: Deque counts real-audit issues by volume (57%); GDS counts engineered barriers (best single tool 37% to 41%). Tools have changed since 2017.
- A clean scan is not conformance; about 29% of the GDS failures were found by no tool [2].
- Overlays and "accessibility widgets" are neither testing nor fixing. The FTC announced a consent order on 3 January 2025 requiring accessiBe to pay $1 million over claims that its AI tool could make any website WCAG-compliant [6]. About 2% of sites used an overlay in 2025 (2.1% desktop, 1.8% mobile) [7].
- Screen reader survey samples are self-selected [4], so shares are indicative, not population estimates.
- Sessions with disabled participants need skilled moderators and pay; scanners do not replace them.

**How to measure it works.**
- Leading: new axe violations per pull request (expect 0); share of key templates with scripted checks; audit findings closed; assistive-technology coverage (screens by screen reader by browser).
- Lagging: detected errors per page over releases (WebAIM-style); user-reported barriers; task success of assistive-technology users.

**Implemented by.**
- GOV.UK Service Manual: combine automated tools (Axe, WAVE, ARC Toolkit, Siteimprove) with manual checks and assistive-technology testing; test with disabled users; get a formal audit before public beta; WCAG 2.2 AA minimum [5].
- GDS (2017): measured tool coverage before choosing tools and published the result [2].
- HTTP Archive's monthly crawl runs Lighthouse with axe-core, so the engine is widely shared [7].

**How to detect it.**
- *Applied:* axe or pa11y in CI; `eslint-plugin-jsx-a11y`; a written manual checklist (keyboard, 400% zoom, NVDA or JAWS on Windows, VoiceOver on Apple devices); an accessibility statement with the last audit date and known issues; an `a11y` bug label; research that includes assistive-technology users.
- *Violated:* an overlay or widget script; "Lighthouse 100" as the only evidence; no accessibility statement or contact route; accessibility only as a pre-launch audit; accessibility bugs closed as "won't fix".
- *In code:* `axe-core`, `@axe-core/playwright`, `jest-axe`, `cypress-axe`, `pa11y`, `lighthouse` in `package.json` or CI files; overlay scripts whose URL contains `accessibe`, `userway`, `audioeye` or `equalweb`; `eslint-plugin-jsx-a11y` in the lint config.
- *Quick test:* look for an accessibility step in CI; run axe DevTools on one page, then do a five-minute keyboard pass and list what the manual pass found that axe did not.

**How to implement.**
1. Lint with `eslint-plugin-jsx-a11y`, add component tests (`jest-axe`) and page tests (`@axe-core/playwright`) in CI, and fail on new serious or critical violations.
2. Manual checks per release: keyboard pass, 400% zoom, reduced motion, forced colors, and a screen reader smoke test of the main flows. Cover JAWS and NVDA on Windows and VoiceOver on Apple devices [4].
3. Commission an expert audit before launch and after major redesigns; fix, retest and publish an accessibility statement.
4. Run sessions with disabled participants on real tasks (A11Y-08).
5. Fix defects in source code and the design system; do not buy an overlay as a fix.
6. Track errors per page and open barriers per release.

**Sources.**
[1] Deque (2021-03-10). Automated testing study identifies 57 percent of digital accessibility issues. https://www.deque.com/blog/automated-testing-study-identifies-57-percent-of-digital-accessibility-issues/
[2] Duran, M. (2017-02-24). What we found when we tested tools on the world's least accessible webpage. GDS Accessibility blog. https://accessibility.blog.gov.uk/2017/02/24/what-we-found-when-we-tested-tools-on-the-worlds-least-accessible-webpage/
[3] WebAIM (2026). The WebAIM Million, 2026 edition. https://webaim.org/projects/million/
[4] WebAIM (2026). Screen Reader User Survey #11. https://webaim.org/projects/screenreadersurvey11/
[5] GOV.UK Service Manual. Testing for accessibility. https://www.gov.uk/service-manual/helping-people-to-use-your-service/testing-for-accessibility
[6] Federal Trade Commission (2025-01-03). Press release on the accessiBe consent order ($1 million). https://www.ftc.gov/news-events/news/press-releases/2025/01/ftc-order-requires-online-marketer-pay-1-million-deceptive-claims-its-ai-product-could-make-websites
[7] HTTP Archive (2025). Web Almanac 2025, Accessibility chapter. https://almanac.httparchive.org/en/2025/accessibility

### A11Y-10 Give images and icons text alternatives that match their purpose

**What it is.** Every non-text element needs a text alternative that serves the same purpose (SC 1.1.1, A). Informative images get a short description in context; images inside links or buttons say where they go or what they do;
decorative or duplicate images get an empty `alt=""`; charts get a takeaway plus the data in text; images of text repeat the text. (Added rule: SC 1.1.1 moved here from A11Y-04 because alt text is a separate check with its own failure rate and decision tree.)

**Why it works.** Screen readers and braille displays present the alternative, and so do image-off modes; without it the user hears a file name, "image" or nothing. Context decides: the same photo can be informative on one page and decorative on another,
which is why W3C gives a decision tree rather than a per-file rule [1]. Missing alt text was found on 53.1% of home pages in 2026 (55.5% in 2025), next to empty links (46.3%) and empty buttons (30.6%), which are often icon-only controls with no name [2].
In HTTP Archive's 2025 data about 13 to 14% of images have no `alt` attribute and 30% have an empty one [3]. Screen reader users compensate: 60.1% of 2026 survey respondents use AI to generate image descriptions or alt text [4].

**Evidence: Strong.** WCAG 2.2 SC 1.1.1 Non-text Content (A), present since WCAG 2.0 [5]. Required: every regime in the baseline.

**Limitations.**
- Tools check that alt exists, not that it is right. Review quality by hand, in context.
- Over-description hurts: "image of ...", repeating adjacent text and keyword stuffing add noise; use empty alt for duplicates [1].
- Complex images (charts, diagrams) need the information elsewhere on the page, not only in alt [1].
- AI-written alt text is a draft; review it for key images. Users' own use of AI describers is a fallback, not a substitute [4].
- CSS background images that carry meaning have no alt mechanism; use `<img>`, or `role="img"` with a name.

**How to measure it works.**
- Leading: axe `image-alt`, `input-image-alt`, `svg-img-alt`, `role-img-alt`, `button-name` and `link-name` violations (all 0); a person reviews 20 images per template for purpose match.
- Lagging: screen reader task success on image-led pages; share of pages with missing alt over time (benchmark: 53.1% of home pages in 2026) [2].

**Implemented by.**
- W3C WAI Images Tutorial: the decision tree that most guidance follows [1].
- No company outcome found. The evidence is prevalence: alt-related failures persist on over half of home pages [2].

**How to detect it.**
- *Applied:* informative images have specific alt; decorative images have `alt=""`; icon buttons have names; charts have a summary and a data table; the logo link names the site.
- *Violated:* `<img>` with no `alt`; alt that is a file name, "image", "photo" or "graphic"; alt that repeats the caption; text baked into images; icon fonts or CSS background icons that carry meaning; SVG icons in buttons with no name.
- *In code:* `<img` without `alt=`; `alt="image"`; `alt=` ending in `.jpg`, `.png` or `.webp`; `<svg` inside `<button>` or `<a>` without `aria-label` or `<title>`; `<input type="image"` without `alt`; `background-image` on elements that carry meaning. Native: `contentDescription` (Android), `accessibilityLabel` and `isAccessibilityElement = false` (iOS), `Image(decorative:)` (SwiftUI).
- *Quick test:* run `document.querySelectorAll('img:not([alt])').length` in the console, then read ten alt texts out of context: does each tell you what a sighted user gets from the image in that spot?

**How to implement.**
1. Decide per image with the W3C tree: text in the image, so alt is that text; link or button, so describe the destination or action; adds meaning, so a short description; complex, so a short alt plus full data nearby; decorative or duplicate, so `alt=""` [1].
2. Write as you would describe it on the phone; leave out "image of"; avoid keywords.
3. Icons: if the control shows text, mark the icon `aria-hidden="true"`; otherwise name the control (`aria-label` or visually hidden text).
4. Charts: put the takeaway in alt or a caption and the numbers in a table (A11Y-02 for color).
5. CMS: make alt a required field with a "decorative" checkbox; review AI drafts.
6. Add axe `image-alt` and `jsx-a11y/alt-text` to CI.

**Sources.**
[1] W3C WAI. Images Tutorial: Decision tree. https://www.w3.org/WAI/tutorials/images/decision-tree/
[2] WebAIM (2026). The WebAIM Million, 2026 edition. https://webaim.org/projects/million/
[3] HTTP Archive (2025). Web Almanac 2025, Accessibility chapter. https://almanac.httparchive.org/en/2025/accessibility
[4] WebAIM (2026). Screen Reader User Survey #11. https://webaim.org/projects/screenreadersurvey11/
[5] W3C (2024). Web Content Accessibility Guidelines (WCAG) 2.2. https://www.w3.org/TR/WCAG22/
