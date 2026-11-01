# Visual hierarchy, layout and typography (VIS)

This category covers what users see first and how easily they can read it: the order of importance on a screen, scanning, type, spacing, the fold, carousels, and the tokens that keep layouts consistent. Load it when auditing a page or screen layout, a content or marketing page, or the foundations of a design system. Contrast, zoom and motion live in A11Y (A11Y-01, A11Y-05), touch target size and responsive layout in PLT (PLT-03, PLT-04), and grouping laws (proximity, similarity) in PER.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| VIS-01 | Build a clear visual hierarchy with one primary action per view | Moderate | any screen with actions |
| VIS-02 | Format for scanning; treat the F-pattern as a failure symptom | Moderate | content pages, docs, help, long text |
| VIS-03 | Use readable typography | Mixed | any text-heavy UI |
| VIS-04 | Match whitespace and density to the task | Mixed | data tools, lists, content pages |
| VIS-05 | Don't make important content look like an ad | Moderate | web pages with promos, side rails, banners |
| VIS-06 | Put key content and the main call to action where attention goes; show the page continues | Mixed | landing pages, long pages, mobile web |
| VIS-07 | Avoid auto-advancing carousels for key content | Mixed | home pages, hero areas, promotions |
| VIS-08 | Use a spacing scale, grid and alignment (tokens); use color by role | Moderate | any product with a design system |
| VIS-09 | Use images that carry information; drop decorative filler | Moderate | marketing, e-commerce, staff and about pages |

---

### VIS-01 Build a clear visual hierarchy with one primary action per view

**What it is.** Each view has one dominant action and a visible order of importance. Size, weight, color, spacing and position rank the elements, and secondary actions look quieter than the primary one.

**Why it works.**
- Eyes go to what differs from its surroundings. NN/g names size, value, color, spacing and placement as the tools of hierarchy, and says a layout that leaves people unsure where to look has a weak one [1].
- The platform guides agree. Apple: reserve the prominent style for the most likely action and keep it to one or two per view, because more of them slow decisions [2]. Material 3: filled for the main action, outlined for medium emphasis, text for low [3]. GOV.UK: one default button for the main call to action; a second one weakens both [4].
- Loud is not the same as seen. In a 1998 study, large red banner-style links were found 58% of the time versus 94% for plain control links (6 participants) [5]. Emphasis must use the page's own visual language (VIS-05).
- Competing options also slow choice (PER, Hick's law).

**Evidence: Moderate.** Consensus across Apple, Material and GOV.UK guidance plus NN/g practice (2020). We found no controlled study that isolates one primary button versus several.

**Limitations.**
- Some views have two real choices (for example "Save" and "Save and publish"); Apple allows one or two prominent buttons [2].
- Never make a destructive action the primary style, even when it is the likeliest choice; people press prominent buttons without reading [2].
- Expert tools with dozens of equal commands rank by grouping and position, not one loud button (VIS-04).
- Button color effects are contested; see MYTH (button color).
- Squint, blur and grayscale tests are practitioner techniques. NN/g's visual-design article does not mention them, and we found no primary study validating them [1].

**How to measure it works.**
- Leading: first-click test ("Where would you click to do X?"), five-second test, time to first fixation on the primary action. Expect most first clicks on the primary action.
- Lagging: completion of the primary task; wrong-button errors (clicks on secondary or destructive actions); support contacts asking where to find X.
- A/B-test emphasis changes on task completion, not on clicks alone.

**Implemented by.**
- Apple HIG: one or two prominent buttons per view; destructive actions never primary [2].
- Google Material 3: five button types ranked by emphasis [3].
- GOV.UK Design System: one default button per page; its testing found green Start buttons raised click-through, but no figures are published [4] (anecdote).

**How to detect it.**
- *Applied:* one filled or high-contrast button per region, others outlined or text-only; primary sits in a consistent place; after a blur, one element stands out.
- *Violated:* several equal-weight filled buttons; "Cancel" styled like "Save"; destructive action styled as primary; promo banner louder than the task; several hero CTAs.
- *In code:* count per view of `btn-primary`, `variant="primary"`, `kind="primary"`, `appearance="primary"`, `color="primary"`, `mat-flat-button`, `mat-raised-button`, `<md-filled-button>`, Compose `Button(` beside `OutlinedButton(`/`TextButton(`, `govuk-button` beside `govuk-button--secondary`; more than one `type="submit"` per form.
- *Quick test:* blur and grayscale a screenshot (Chrome DevTools > Rendering > Emulate vision deficiencies > Blurred vision, Achromatopsia). Name the first three things you notice. Count high-emphasis buttons per view (target 1, at most 2).

**How to implement.**
1. Write the one job of the view and name its primary action.
2. Assign levels: one high (filled), a few medium (outlined or tonal), the rest low (text). Rank by style, not size; same-size buttons read as one set [2].
3. Put the primary action where the platform expects it (GOV.UK: left edge of the form [4]; Apple: trailing side of a button row).
4. Don't give a destructive action the primary style, even when it is the likeliest choice [2]; confirm it or offer undo instead (ERR).
5. Check with blur, grayscale and a first-click test; fix the screen if the eye lands on decoration.
6. Encode the levels as tokens (VIS-08) so every team reuses them.

**Sources.**
[1] Gordon, K. (2020). 5 principles of visual design in UX. Nielsen Norman Group. https://www.nngroup.com/articles/principles-visual-design/
[2] Apple (read 2026-10-31). Buttons; Alerts. Human Interface Guidelines. https://developer.apple.com/design/human-interface-guidelines/buttons
[3] Google (read 2026-10-31). Buttons (Material 3 in Compose). Android Developers. https://developer.android.com/develop/ui/compose/components/button
[4] GOV.UK Design System (read 2026-10-31). Button. https://design-system.service.gov.uk/components/button/
[5] Benway, J. P., & Lane, D. M. (1998). Banner blindness: Web searchers often miss "obvious" links. Rice University; listed as Internetworking 1(3), December 1998 (the PDF carries no date). https://www.ruf.rice.edu/~lane/papers/banner_blindness.pdf

---

### VIS-02 Format for scanning; treat the F-pattern as a failure symptom

**What it is.** Break text into descriptive headings, short paragraphs, parallel bullets and a few bold key terms, with the point first. Well-formatted pages draw a layer-cake gaze pattern. The F-shaped pattern is what happens when a page gives readers no cues; it is not a layout to copy.

**Why it works.**
- 2006 eyetracking of 232 users found a common web reading pattern shaped like an F: two horizontal passes, then a vertical scan down the left edge. Advice then: front-load, and put key points in the first two paragraphs [1].
- NN/g's 2017 round (47 participants, desktop and mobile; a mirrored F in Arabic) calls the F a result of poor formatting and says the fix is formatting that directs attention [2]. The 2019 report ranks four scanning patterns: layer-cake (gaze on headings and subheadings, then the relevant body) is by far the most effective short of reading nearly everything; the F ranks lowest [3].
- In a 1997 experiment (51 users), a scannable rewrite scored 47% above promotional text on a composite of task time, errors, memory, sitemap time and satisfaction [4].
- On an average page, visitors can read at most 28% of the words; realistically about 20% [5].
- Headings serve non-visual scanning too: 71.6% of screen reader survey respondents first navigate long pages by headings [6] (A11Y-04).

**Evidence: Moderate.** NN/g eyetracking (2006, 20 years old; 2017; 2019) and one controlled experiment (1997). The 2019 effectiveness ranking gives no sample sizes.

**Limitations.**
- Highly motivated readers read almost everything (the "commitment" pattern); subheadings still help them [3].
- The F varies. Numbers, prices and images change scanning, and E and inverted-L shapes occur [1].
- Chunking can break an argument; bullets for non-parallel ideas hurt; bold everywhere highlights nothing (VIS-01).
- Using the F as a layout template ("put key items along the F") misreads NN/g; see MYTH (F-pattern).
- Headings must carry information (CON-04); decorative headings add noise.

**How to measure it works.**
- Leading: gaze plots or heatmaps (fixations on headings suggest layer-cake; a left-edge stem suggests F); five-second skim test ("what is this page about?").
- Task time and success on find-a-fact tasks on long pages; comprehension quiz after reading.
- Screen reader test: time to reach a section by headings.

**Implemented by.**
- Morkes and Nielsen (1997): scannable +47%, concise +58%, all three +124% over control. NN/g reports a related rewrite of real Sun Microsystems pages at +159% [4].
- GOV.UK writing rules: paragraphs of at most five sentences; split sentences over about 25 words [7].

**How to detect it.**
- *Applied:* a heading every few paragraphs that tells the story when read alone; bullets for 3+ parallel items; key terms bold; each paragraph opens with its point; summary near the top of long pages.
- *Violated:* walls of text (paragraphs over about 5 sentences or 100 words); long pages with no subheads; headings like "Overview" or "Welcome"; whole sentences in bold; long centered text.
- *In code:* long `<p>` blocks; few `<h2>`/`<h3>` per 300 words; no `<ul>`/`<ol>`; `<div class="h2">` instead of real headings; `<br><br>` used as paragraph breaks; `<strong>` around full sentences; skipped heading levels.
- *Quick test:* squint at the page and check that an outline shows. Read the headings alone. Dump the outline: `[...document.querySelectorAll('h1,h2,h3,h4')].map(h => h.tagName + ' ' + h.textContent.trim())`.

**How to implement.**
1. State the main point in the first two sentences (inverted pyramid; CON-04).
2. Add descriptive subheadings every 2-4 paragraphs, as real heading elements in order.
3. Turn 3+ parallel items into bullets and start them with different words (CON-04).
4. Keep paragraphs short and sentences under about 25 words [7].
5. Bold only key terms; write descriptive link text (CON-05).
6. Check the real page with a scanning task or eyetracking; fix pages that show F-scanning.

**Sources.**
[1] Nielsen, J. (2006). F-shaped pattern for reading web content. Nielsen Norman Group. https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content-discovered/
[2] Pernice, K. (2017). F-shaped pattern of reading on the web: misunderstood, but still relevant. Nielsen Norman Group. https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/
[3] Pernice, K. (2019). Text scanning patterns: eyetracking evidence. Nielsen Norman Group. https://www.nngroup.com/articles/text-scanning-patterns-eyetracking/
[4] Morkes, J., & Nielsen, J. (1997). Concise, scannable, and objective: how to write for the web. Nielsen Norman Group. https://www.nngroup.com/articles/concise-scannable-and-objective-how-to-write-for-the-web/
[5] Nielsen, J. (2008). How little do users read? (reports Weinreich et al., 2008, ACM Transactions on the Web). https://www.nngroup.com/articles/how-little-do-users-read/
[6] WebAIM (2024). Screen reader user survey #10 (December 2023 to January 2024, 1,539 responses). https://webaim.org/projects/screenreadersurvey10/
[7] GOV.UK (read 2026-10-31). Use clear language. https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/clear-language/

---

### VIS-03 Use readable typography

**What it is.** Set body text at a comfortable size, 45-75 characters per line, line height near 1.5, left-aligned, in sentence case. Let users resize text and change spacing without breaking the layout.

**Why it works.** The sub-claims have different evidence.
- Size: browsers usually default to 16 px [1]. Apple's default body is 17 pt on iOS (minimum 11 pt) and 13 pt on macOS (minimum 10 pt) [2]. GOV.UK sets body text at 19 px on a 25 px line height [3]. These are platform choices, not experiments.
- Line length: Bringhurst (1992) calls 45-75 characters satisfactory for print and 66 ideal; Tinker and Paterson (1929) found about 57 best for 10-point type [4]. On screen, Dyson and Haselgrove (2001) tested 25, 55 and 100 characters; comprehension was highest at 55, and at fast reading 55 and 100 were read faster than 25 [5]. Other studies favor longer lines for speed while readers often prefer shorter ones [4].
- Spacing: WCAG 1.4.12 requires content to survive user overrides of line height 1.5, paragraph spacing 2, letter spacing 0.12 and word spacing 0.16 times the font size; people with low vision and dyslexia use them [6]. WCAG 1.4.8 (AAA) adds 80 characters maximum and no justified text, because uneven word gaps hurt some readers [7].
- All caps: Tinker's studies (1929-1963) found all-capital text slowed long reading and only about 10% of readers preferred it [8]. Figures of 9.5-19% slower for his 1955 timed tests circulate in secondary sources (snippet only; original not opened). A 2007 test found caps faster at small print sizes and no difference at large sizes, with 7 readers [8].
- Case: Microsoft makes sentence-style the default for UI labels, buttons and headings and says not to use all caps for emphasis [9]. Material's original spec asks for sentence style but exempts button text [10]. Apple uses title-style for buttons [11].

**Evidence: Mixed.** The WCAG-backed parts are firm, line-length studies conflict, the all-caps work is old (1929-1963) plus one small 2007 test, and the justified-text claim rests on guidance. Required: WCAG 2.2 SC 1.4.4 Resize Text (AA) [12]; SC 1.4.12 Text Spacing (AA); see A11Y-05.

**Limitations.**
- Right size depends on the typeface (Apple advises going larger for thin custom fonts) and on viewing distance; secondary labels may be smaller than body (Apple minimum 11 pt) [2].
- Speed and preference pull apart on line length [4][5]. Tables, code and narrow phone columns follow other limits (PLT-04).
- WCAG 1.4.12 does not ask you to use those values; it asks that nothing breaks when users apply them [6].
- All caps is fine for short acronyms and tiny labels, and the legibility effect depends on size [8]. Case conventions differ by platform (Apple title-style, Microsoft sentence-style) [9][11]; follow the platform and stay consistent (CON-06, PLT-01).
- We could not open the British Dyslexia Association style guide (page returned 404), so the dyslexia claim rests on WCAG's rationale [7].

**How to measure it works.**
- Reading speed and comprehension: one passage plus five questions per variant; expect equal or better comprehension at equal speed.
- Pass/fail: 200% zoom plus a text-spacing override shows no clipping or overlap. Lagging: complaints and support contacts about legibility.

**Implemented by.**
- GOV.UK: 19 px body, 25 px line height; small-screen sizes raised in Frontend v6.0.0 [3].
- Apple: Dynamic Type, Body 17 pt on 22 pt leading at the default size [2]. Microsoft: sentence-style capitalization for all UI labels [9]. No published before/after outcome found for any of these.

**How to detect it.**
- *Applied:* body 16 px or more (or the platform body style); prose width 45-80 characters; line height 1.4-1.6; ragged-right text; sentence-case labels; page works at 200% zoom.
- *Violated:* body 12-14 px; full-width paragraphs on desktop (over 100 characters per line); tight line height; long all-caps strings; justified narrow columns; fixed-height boxes that clip text; zoom disabled.
- *In code:* `font-size:\s*(1[0-5]|[0-9])px` on `body`/`p`; no `max-width` in `ch`; `line-height:\s*(1|1\.[0-3])`; `text-transform: uppercase`; `text-align: justify`; fixed `height:` with `overflow:hidden` on text; `user-scalable=no`, `maximum-scale=1`. Native: `UIFont.preferredFont(forTextStyle:)` with `adjustsFontForContentSizeCategory`, SwiftUI `.font(.body)` instead of `.system(size:)`; Android text in `sp`, not `dp`.
- *Quick test:* zoom to 200%; apply a WCAG 1.4.12 text-spacing bookmarklet; count characters in a typical line; read the computed `font-size` and `line-height` of `body`.

**How to implement.**
1. Size text in `rem` with `html { font-size: 100% }` so users' font settings apply [1]; use 1rem or larger for body text (GOV.UK uses 19 px) and never disable zoom (A11Y-05).
2. Cap prose width: `max-width: 65ch` (target 45-75; WCAG 80).
3. Use `line-height: 1.5` for body, paragraph spacing of at least 1em, and test with the 1.4.12 overrides.
4. Use sentence case for headings, labels and buttons unless the platform says otherwise; keep all caps to short labels.
5. Left-align text; avoid justified blocks.
6. On iOS and Android, use system text styles so the user's text-size setting applies.

**Sources.**
[1] MDN (read 2026-10-31). font-size. https://developer.mozilla.org/en-US/docs/Web/CSS/font-size
[2] Apple (read 2026-10-31). Typography. Human Interface Guidelines. https://developer.apple.com/design/human-interface-guidelines/typography
[3] GOV.UK Design System (read 2026-10-31). Type scale. https://design-system.service.gov.uk/styles/type-scale/
[4] Bringhurst, R. (1992). The Elements of Typographic Style, pp. 25-36. Hartley & Marks; with Tinker and Paterson (1929), Dyson and Kipping (1998), Ling and van Schaik (2006), as listed in Wikipedia, Line length (finder; originals not opened). https://en.wikipedia.org/wiki/Line_length
[5] Dyson, M. C., & Haselgrove, M. (2001). The influence of reading speed and line length on the effectiveness of reading from screen. Int. J. Human-Computer Studies, 54(4), 585-612. Abstract read via a blog copy: https://advat.blogspot.com/2012/04/influence-of-reading-speed-and-line.html
[6] W3C (2023). Understanding SC 1.4.12 Text Spacing (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html
[7] W3C (2023). Understanding SC 1.4.8 Visual Presentation (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/visual-presentation.html
[8] Arditi, A., & Cho, J. (2007). Letter case and text legibility in normal and low vision. Vision Research, 47(19), 2499-2505 (summarizes Tinker, 1963, Legibility of Print). https://pmc.ncbi.nlm.nih.gov/articles/PMC2016788/
[9] Microsoft (read 2026-10-31). Capitalization. Microsoft Writing Style Guide. https://learn.microsoft.com/en-us/style-guide/capitalization
[10] Google (read 2026-10-31). Writing. Material Design 1 (no longer maintained). https://m1.material.io/style/writing.html
[11] Apple (read 2026-10-31). Buttons. Human Interface Guidelines. https://developer.apple.com/design/human-interface-guidelines/buttons
[12] W3C (2023). Understanding SC 1.4.4 Resize Text (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html

---

### VIS-04 Match whitespace and density to the task

**What it is.** Choose spacing and density to fit who uses the screen and what they do. Reading and first-time use call for room; frequent scanning and comparing of data calls for compact rows. Offer a density setting when audiences differ.

**Why it works.**
- The popular claim is that white space between paragraphs and in margins raises comprehension by almost 20%. It is widely repeated and we found no primary source. Wikipedia's white-space article has no such figure; it cites a 2010 US health-literacy guide only for the point that very little white space looks cluttered [1]. Grade the 20% as Weak.
- Design systems treat density as a choice. IBM Carbon offers five table row heights, 24 px (xs) to 64 px (xl): xs for information-heavy layouts, taller rows for easier scanning and interaction [2]. Flutter's Material `VisualDensity` changes spacing, not text size, and defaults to compact on desktop and standard on mobile [3].
- Spacing signals structure: closer elements read as related, more surrounding space as more important [4] (PER, proximity).
- WCAG notes that extra space between text blocks can help people with cognitive disabilities tell sections apart; it is not required [5].
- Gmail's Default, Comfortable and Compact density setting is a known example; we did not open a Google page for it, so treat it as unverified.

**Evidence: Mixed.** No controlled study found that supports "more white space is always better". Density options are design-system consensus; the effect depends on task and user.

**Limitations.**
- White space costs screen area and adds scrolling (VIS-06). In tables, fewer visible rows hurts comparison.
- Dense layouts raise misclick risk on touch; keep target size and gaps (PLT-03).
- Density cannot replace grouping; use proximity and alignment (PER, VIS-08).
- Stated preference and measured performance can differ; test both with the real audience.
- An airy marketing style copied into an admin tool (or the reverse) mismatches the task.

**How to measure it works.**
- Task time and error rate in dense versus relaxed variants for the real task (for example triage of 50 rows); rows visible per viewport.
- Mis-tap or mis-click rate; scroll distance per task.
- Share of users who pick the compact setting (leading signal); SUS or preference after tasks.

**Implemented by.**
- IBM Carbon: five row sizes with usage guidance [2].
- Flutter Material: density value with platform defaults [3].
- Gmail: three density levels (unverified here). No published outcome on comprehension or speed for any of these.

**How to detect it.**
- *Applied:* dense tables for expert data views, roomier layouts for reading and onboarding; a density setting or a sensible per-context default; groups separated by space, not only by rules.
- *Violated:* 3 rows visible in a data grid on a laptop; no gap between groups; crowded tap targets; one airy card layout used everywhere; different density on similar screens.
- *In code:* `density`, `dense`, `compact`, `size="small"` (MUI, Ant Design), Carbon `size="xs|sm|md|lg|xl"`, Flutter `visualDensity`, `[data-density]`, `--row-height`; fixed `height: 56px|64px` on rows; `padding: 0` between sibling blocks.
- *Quick test:* count visible rows or items at 1366x768 in the main data view; measure the gap between adjacent tap targets (at least 8 px); switch density if offered and check text size stays constant.

**How to implement.**
1. Classify the screen: reading or learning, occasional task, or expert scanning.
2. Define 2-3 density tiers as tokens (row height, padding); keep font size and touch targets fixed [3].
3. Default to the middle tier; let users switch and save the choice.
4. Group with space first, rules second (VIS-08).
5. Test with real tasks; keep the tier that cuts time and errors.

**Sources.**
[1] Wikipedia (read 2026-10-31). White space (visual arts); cites US HHS (2010), Health Literacy Online. https://en.wikipedia.org/wiki/White_space_(visual_arts)
[2] IBM (read 2026-10-31). Data table usage. Carbon Design System. https://carbondesignsystem.com/components/data-table/usage/
[3] Flutter (read 2026-10-31). VisualDensity class. https://api.flutter.dev/flutter/material/VisualDensity-class.html
[4] IBM (read 2026-10-31). Spacing overview. Carbon Design System. https://carbondesignsystem.com/elements/spacing/overview/
[5] W3C (2023). Understanding SC 1.4.12 Text Spacing (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html

---

### VIS-05 Don't make important content look like an ad

**What it is.** Don't style important content like an advertisement, and don't mix real content into ad slots. Users learn to ignore banner-shaped, bright, image-with-slogan blocks and the page regions where ads usually sit.

**Why it works.**
- Benway and Lane (1998, Rice University): in a pilot with six working professionals, banner-style shortcuts were found 58% of the time versus 94% for plain control links. In a second experiment with 72 students, only 17 of 71 recalled seeing helpful non-ad banners, and 20% recalled any ad. The effect also appeared for plain text that did not look like an ad, so it is wider than ad learning [1].
- NN/g eyetracking (Nielsen, 2007, hundreds of pages): users almost never fixated banner ads; ad-like elements drew little attention even when they were not ads; the right column was largely ignored [2].
- NN/g (Pernice, 2018, desktop and mobile; several examples with 26 participants): users skipped inline promotions that differ from their surroundings and "faux ads" that held useful content. One user made a single fixation in a right rail, 0.8% of content-area fixations and 33 times fewer than its size implies. After glancing at an irrelevant item, people may avoid that area on the page, other pages and other sites [3].
- Banner click-through averaged under 0.1% in Chartbeat's 2014 publisher data [4].

**Evidence: Moderate.** Seen in 1998, 2007 and 2018 with different methods. The 1998 samples are small and the 2007 and 2018 articles do not state full sample sizes.

**Limitations.**
- NN/g does not advise removing ads; it advises not mixing ads and content in one visual section [3].
- Ads that mimic content draw more fixations, but Nielsen calls that unethical, and it conflicts with CHO (deceptive patterns) [2].
- Strongest for goal-directed searching; browsing users notice more. Benway and Lane note that banners can still lift brand awareness [1].
- Text ads on search results pages do get looks [2].
- Not the same as VIS-01: a primary button is salient but looks like interface, not like an ad.

**How to measure it works.**
- Task test: ask users to find an item placed in the suspect area (top banner, right rail, promo block); NN/g advises testing that users see important content there [3].
- Eyetracking areas of interest: fixations on promo versus content blocks; recall and first-click tests.
- Click-through by placement and style (native versus banner-like) in an A/B test.

**Implemented by.**
- No company before/after outcome found. NN/g's 2018 examples show users skipping helpful content near ads (for example on apartmenttherapy.com) [3].
- Chartbeat/Time (2014): banner click-through under 0.1% (context, not a fix) [4].

**How to detect it.**
- *Applied:* key tasks and facts in the main column in the page's own type and colors; promotions labeled and kept apart from content; plain text links for must-find navigation.
- *Violated:* announcements as rectangular banner images with text inside; bright stock-photo promo blocks in the right rail; key tasks only in a top banner; sponsored items styled as content; help content placed beside ads.
- *In code:* class or id containing `banner`, `advert`, `promo`, `sponsor`, `hero-banner`; `<img>` whose `alt` holds full sentences; ad slots (`adsbygoogle`, `div-gpt-ad`) beside content; critical links inside `aside` or `.sidebar`; `position: fixed` promo bars.
- *Quick test:* ask five people to find three key items and watch whether any sits in a banner or rail region. Mark every block that is bright, image-led, slogan-sized and rectangular as ad-like.

**How to implement.**
1. Put key content and primary actions in the main flow, in the same type, color and spacing as the page.
2. Don't rely on the right rail or a top banner for essential items; test any exception.
3. Separate promotions from content, label them ("Promotion", "Sponsored"), and never blend them in one visual section [3].
4. Avoid text inside images, motion and ad-sized rectangles for real content (VIS-07).
5. Attach must-find items to the list or menu people are already scanning, and make them stand out inside it [1].
6. Verify with a task test.

**Sources.**
[1] Benway, J. P., & Lane, D. M. (1998). Banner blindness: Web searchers often miss "obvious" links. Rice University. https://www.ruf.rice.edu/~lane/papers/banner_blindness.pdf
[2] Nielsen, J. (2007). Banner blindness: old and new findings. Nielsen Norman Group. https://www.nngroup.com/articles/banner-blindness-original-eyetracking/
[3] Pernice, K. (2018). Banner blindness revisited: users dodge ads on mobile and desktop. Nielsen Norman Group. https://www.nngroup.com/articles/banner-blindness-old-and-new-findings/
[4] Haile, T. (2014). What you think you know about the web is wrong. Time. https://time.com/12933/what-you-think-you-know-about-the-web-is-wrong/

---

### VIS-06 Put key content and the main call to action where attention goes; show the page continues

**What it is.** Put the key message and main call to action in the first one or two screenfuls, and cue that the page continues so a hero or a blank band does not read as the end.

**Why it works.**
- Nielsen (2010; 21 users, 541 pages, 57,453 fixations, 1,024x768 screens): 80.3% of viewing time fell above the fold; about 5% came after the 2,000 px mark [1].
- NN/g repeated the study in 2018 (Fessenden; 120 participants, over 130,000 fixations, 1,920x1,080 screens, mixed page types): 57% above the fold, 74% in the first two screenfuls (up to 2,160 px) and 81% in three. Attention still drops sharply at the fold [2]. The 2010 report gives no two-screenful figure.
- NN/g (Schade, 2015): the 100 px just above the fold got 102% more viewing than the 100 px just below; in a Google display study, ads above the fold had 73% viewability versus 44% just below [3].
- A "false floor" is a layout with little content at the top that lets users think they have seen the whole page. NN/g says a good design needs no scroll arrow [3].
- Counter-evidence: Chartbeat (Haile, 2014; about 2 billion visits) reported 66% of attention on a normal media page below the fold. That is a time-based measure on media pages, not eyetracking, so the numbers do not compare directly [4].

**Evidence: Mixed.** All sources agree attention falls with depth; they disagree on how much (80% in 2010, 57% in 2018, and about 34% above the fold implied by Chartbeat's 66% below). Method, screen size and page type differ.

**Limitations.**
- The fold moves with device and window; there is no single line (PLT-04).
- Engaged readers of long articles scroll far, and most of their attention lands below the fold [4].
- Cramming everything above the fold hurts clarity (VIS-01, VIS-04); see MYTH (fold).
- NN/g's 2018 report has no mobile-specific results [2]; the 2010 sample was 21 users [1].
- Sticky headers and cookie banners shrink the visible area.

**How to measure it works.**
- Share of sessions in which the primary CTA enters the viewport (IntersectionObserver); scroll-depth distribution; time in view of key blocks.
- CTA click-through by position; A/B test of a moved CTA or an added cue on conversion.
- Eyetracking share of fixations above versus below the fold; scroll maps.

**Implemented by.**
- NN/g's recommended cues: elements that draw the eye down, content that spans the fold, signposts, anchor links [3].
- Publishers using Chartbeat measure attention by depth [4]. No company before/after outcome found.

**How to detect it.**
- *Applied:* at 1366x768 and 390x844 the first viewport shows what the page is, the main action and a slice of the next section; long pages carry anchors or signposts.
- *Violated:* full-screen hero with only an image and a tiny arrow; a big blank band after the hero; main CTA on the second screen; stacked 100vh sections that each look finished.
- *In code:* `min-height: 100vh|100svh|100dvh` or `height: 100vh` on a hero with centered content; `scroll-snap-type`; `.scroll-down`, `.scroll-indicator`; CTA `getBoundingClientRect().top > innerHeight`.
- *Quick test:* screenshot the first viewport at two sizes; answer "what is this, what can I do, is there more?" in five seconds; measure the CTA's top offset.

**How to implement.**
1. List the one to three things every visitor must see; place them in the first two screenfuls (74% of viewing time in NN/g's 2018 data [2]).
2. Let the next section peek above the bottom edge, or let text or images span the fold [3].
3. Replace empty full-screen heroes with a headline, value statement and CTA; if a 100vh hero is needed, leave a visible slice of the next block.
4. Add signposts: headings, a short contents list or anchor links, step counts.
5. Repeat the CTA at natural decision points on long pages (practice; no study cited).
6. Test on real devices and adjust per breakpoint.

**Sources.**
[1] Nielsen, J. (2010). Scrolling and attention (original research). Nielsen Norman Group. https://www.nngroup.com/articles/scrolling-and-attention-original-research/
[2] Fessenden, T. (2018). Scrolling and attention. Nielsen Norman Group. https://www.nngroup.com/articles/scrolling-and-attention/
[3] Schade, A. (2015). The fold manifesto: why the page fold still matters. Nielsen Norman Group. https://www.nngroup.com/articles/page-fold-manifesto/
[4] Haile, T. (2014). What you think you know about the web is wrong. Time. https://time.com/12933/what-you-think-you-know-about-the-web-is-wrong/

---

### VIS-07 Avoid auto-advancing carousels for key content

**What it is.** Don't put key content or navigation in a panel that changes on a timer. If you keep a carousel, let the user control it: no autoplay, or autoplay with a visible pause control, few slides and a position indicator.

**Why it works.**
- Notre Dame (Runyon, 8 July 2013; five university home pages, January to June 2013): on nd.edu 1.07% of visitors clicked any carousel feature, and 89.1% of those clicks hit slide 1; slides 2-5 got 2.4-3.1% each. Across the five sites slide 1 took 54.6-89.1% of clicks [1].
- Counter-evidence in the same data: the one auto-playing site had the highest click rate (9.4% versus 1.1-3.0%) and the flattest spread across slides; Runyon treats it as an exception [1]. The often-quoted "1% click, 84% on slide one" mixes numbers from different sites.
- NN/g (Nielsen, 19 January 2013): in a UK usability test a participant missed the biggest offer on a home page because the box changed every 5 seconds (visible about 20% of the time) and concluded there were no deals (anecdote). Listed harms: slow and non-native readers, motor impairment, loss of control, and ad-like motion that triggers banner blindness [2].
- NN/g (Pernice, 14 September 2013): people scroll past carousels and miss later frames; use five frames or fewer, no auto-forward on mobile, show position, keep large controls inside the carousel [3].
- Baymard (Scott, 2019, updated 3 April 2025): about 46% of desktop and mobile e-commerce sites with a home-page carousel have usability problems; 33% of top US and European desktop sites have one; static content sections are often the better trade [4].
- WCAG 2.2 SC 2.2.2 (A): moving content that starts automatically, lasts over 5 seconds and sits beside other content needs a pause, stop or hide mechanism, unless essential [5].

**Evidence: Mixed.** Click data (one university, 2013), NN/g reports (2013, no sample sizes) and Baymard testing agree later slides get few clicks. The auto-play counter-example and thin methods keep it from Moderate. Required: WCAG 2.2 SC 2.2.2 Pause, Stop, Hide (A); see A11Y-05 and A11Y-06.

**Limitations.**
- Runyon's auto-play site did best; news or event promos in other contexts may differ. No randomized test found.
- NN/g's 2013 evidence is qualitative, and the missed-offer example is a single case.
- User-driven carousels for product images or galleries are a different pattern; the problem is auto-advance for key content.
- A pause button meets WCAG but does not fix hidden content. See MYTH (carousels).

**How to measure it works.**
- Per-slide click-through and the share on slide 1 (Notre Dame range 54-89%); total carousel CTR.
- A/B test static hero versus carousel on conversion and on finding a promoted item.
- Accessibility checks: pause reachable by keyboard; rotation stops on hover and focus; mis-click rate when slides change.

**Implemented by.**
- University of Notre Dame measured five home pages and published the click shares [1].
- Baymard recommends static content sections as the alternative [4]. No company revenue outcome found.

**How to detect it.**
- *Applied:* static hero or manual carousel; visible pause/play button; at most five slides; position indicator ("2 of 4"); no autoplay on mobile; each slide's content also reachable elsewhere.
- *Violated:* slides change every 3-6 seconds with no pause; the only route to an offer or alert is a slide; tiny dots as the only control; rotation continues under hover or focus.
- *In code:* `autoplay`, `autoPlay`, `autoplaySpeed`, `data-ride="carousel"`, `data-bs-ride="carousel"`, `data-bs-interval`, `setInterval(` driving a slide index, Swiper `autoplay: {`, Slick `autoplay: true`, `<marquee>`; `aria-roledescription="carousel"` with no pause control; no `prefers-reduced-motion` handling.
- *Quick test:* time the first slide change; try to pause by keyboard; hover and Tab into it; list content that exists only in slides.

**How to implement.**
1. Prefer a static hero or a short stack of content blocks reached by scrolling [4].
2. If you keep a carousel, start it paused. If it autoplays, add a visible pause or stop button early in the tab order, pause on hover and focus, and stop after any user action [5].
3. Limit to five slides; show position and total; use large, high-contrast controls inside the frame [3].
4. Don't auto-forward on mobile [3]; honor `prefers-reduced-motion`.
5. Make every slide's content available elsewhere on the page.
6. Track per-slide clicks and remove slides that get none.

**Sources.**
[1] Runyon, E. (2013). Carousel interaction stats. https://erikrunyon.com/2013/07/carousel-interaction-stats/
[2] Nielsen, J. (2013). Auto-forwarding carousels and accordions annoy users and reduce visibility. Nielsen Norman Group. https://www.nngroup.com/articles/auto-forwarding/
[3] Pernice, K. (2013). Designing effective carousels. Nielsen Norman Group. https://www.nngroup.com/articles/designing-effective-carousels/
[4] Scott, E. (2019, updated 2025). Homepage carousels. Baymard Institute. https://baymard.com/blog/homepage-carousel
[5] W3C (2023). Understanding SC 2.2.2 Pause, Stop, Hide (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html

---

### VIS-08 Use a spacing scale, grid and alignment (design tokens); use color by role

**What it is.** Define a small set of spacing values and a grid, align elements to them, and name colors by what they do (primary, surface, error) instead of by hue. Store both as tokens and reuse them everywhere.

**Why it works.**
- Spacing carries meaning. Carbon: closer elements read as related, matching patterns signal equal weight, more surrounding space signals importance, and spacing can group content without divider lines [1] (PER, Gestalt proximity).
- Scales and grids already exist in the major systems. Material 1 aligned components to an 8dp grid, type to 4dp, with 48dp touch targets (spec now unmaintained) [2]. Carbon uses 13 tokens from 2 px to 160 px with a 2x grid [1]. GOV.UK sets line heights in multiples of 5 px to match its spacing scale for steady vertical rhythm [3].
- Color roles: Material 3 builds a scheme from roles (primary, secondary, tertiary, containers, surfaces) with matching "on" roles, and says to choose by state, prominence and emphasis rather than hard-coding values. Defining colors once in the theme lets light and dark schemes update together [4].
- Tokens are being standardized: the W3C Design Tokens Community Group published its first stable format version, 2025.10 [5].

**Evidence: Moderate.** Consensus across Material, Carbon and GOV.UK plus Gestalt grouping research (PER). We found no controlled study that isolates a spacing scale or token system, so the benefit is inferred.

**Limitations.**
- Scale adherence is not good layout; optical alignment sometimes needs exceptions (Carbon allows them but discourages them) [1].
- Color roles do not guarantee contrast or independence from color; check both (A11Y-01, A11Y-02). Pair "on" colors only with their base role [4].
- Too many tokens or roles add overhead; keep the set small.
- Material 1 is archived; check the current spec for its numbers [2].
- INT-03 covers design-system consistency and the build-time effect of a shared system.

**How to measure it works.**
- Token coverage: share of margin, padding, gap and color values that come from tokens; count of distinct spacing values and distinct colors in CSS.
- Visual-regression and design-QA defect counts; time to build a new screen (team metric, lagging).
- Usability: can users tell which items belong together (grouping task)?

**Implemented by.**
- Google Material: 8dp grid (original spec) and M3 color roles [2][4].
- IBM Carbon: spacing tokens `$spacing-01` to `$spacing-13`; a Stack component applies gaps from the scale [1].
- GOV.UK: 5 px multiples for line heights and spacing [3]. No published outcome measuring user performance.

**How to detect it.**
- *Applied:* margins and padding come from a short list; CSS custom properties or theme tokens; left edges align; semantic color names (`--color-danger`) used in components.
- *Violated:* arbitrary values (13 px, 17 px, 22 px); hard-coded hex colors in components; many near-duplicate grays; ragged left edges; different padding on identical cards; one color meaning two things.
- *In code:* count distinct values with `grep -ohE '(margin|padding|gap)[a-z-]*:\s*[^;]+' | sort | uniq -c | sort -rn`; `#[0-9a-fA-F]{3,8}` outside token files; Tailwind arbitrary values `\[\d+px\]`, `\[#`; token use such as `var(--space-`, `var(--color-`, `$spacing-0`, `theme.spacing(`, `MaterialTheme.colorScheme.`; Compose `Color(0x` or SwiftUI `Color(red:` in components.
- *Quick test:* overlay a 4 or 8 px grid in devtools and check left edges; open the CSS Overview panel and count unique colors; count unique padding values.

**How to implement.**
1. Pick a base unit (4 or 8) and generate 8-12 steps; document where each step applies (inline, stack, section).
2. Define tokens in one place with layers: primitives, then semantic (`--color-danger`), then component tokens.
3. Define color roles with paired foreground and background, and verify contrast for every pair (A11Y-01).
4. Use layout primitives (stack, grid) that apply token gaps instead of ad-hoc margins [1].
5. Enforce in CI: Stylelint `color-no-hex`, `declaration-property-value-allowed-list`; restrict Tailwind arbitrary values.
6. Allow documented exceptions for optical alignment.

**Sources.**
[1] IBM (read 2026-10-31). Spacing overview. Carbon Design System. https://carbondesignsystem.com/elements/spacing/overview/
[2] Google (read 2026-10-31). Metrics and keylines. Material Design 1 (no longer maintained). https://m1.material.io/layout/metrics-keylines.html
[3] GOV.UK Design System (read 2026-10-31). Type scale. https://design-system.service.gov.uk/styles/type-scale/
[4] Google (read 2026-10-31). Material Design 3 in Compose (color roles). Android Developers. https://developer.android.com/develop/ui/compose/designsystems/material3
[5] Design Tokens Community Group (2025). Design tokens specification, version 2025.10. https://www.designtokens.org/

---

### VIS-09 Use images that carry information; drop decorative filler

**What it is.** Use photos and graphics that show real products, people, data or steps, and remove or shrink images that only decorate. Generic stock photos get ignored and push content down.

**Why it works.**
- Nielsen (2010, NN/g eyetracking): users ignore decorative images and look hard at images with relevant information, especially product photos and photos of real people [1].
- Examples in the same report: on a staff page one participant spent about 10% more time on portraits than on bios that took about 316% more space; on Amazon's category page about 18% of viewing time went to photos and 82% to text; product text drew about 4.4 fixations per item versus about 0.9 for thumbnails; Pottery Barn bookcase thumbnails were studied because they helped compare, while Amazon TV thumbnails were mostly ignored; a product close-up drew 12 fixations [1].
- The 2018 banner-blindness work agrees: users look at images relevant to their task and skip large visual blocks that look like ads [2].
- Attractive visuals still make users more forgiving of small usability problems (aesthetic-usability effect, PER), so decoration is not worthless [3].

**Evidence: Moderate.** NN/g eyetracking from 2010 (16 years old); most examples are individual test users on real sites, and counts of participants are not stated.

**Limitations.**
- Fixations do not measure brand feeling or trust; in travel, fashion and food, the image is the content.
- Examples come from a few pages and single participants.
- Real photography costs more; NN/g notes good photos add value [1].
- Informative images still need alt text; decorative ones need empty alt (A11Y-10).

**How to measure it works.**
- Eyetracking: fixations on image areas of interest; time to first relevant fixation.
- Image zoom and gallery click rates; A/B test of real versus stock imagery on product-page conversion.
- Cost side: page weight and Largest Contentful Paint (FBK-05).

**Implemented by.**
- Product pages where photos differentiate items (Pottery Barn bookcases in NN/g's session) drew close study; pages where thumbnails look alike (Amazon TVs) did not [1]. No company before/after outcome found.

**How to detect it.**
- *Applied:* product photos show differences, angles and use; real staff photos; captions that add facts; an enlarged view at least twice the default size [1].
- *Violated:* stock hero photos (handshakes, headsets); full-width banner images with no information; identical-looking thumbnails; decoration that pushes key content below the fold (VIS-06).
- *In code:* filenames or URLs matching `shutterstock|istock|gettyimages|adobestock|unsplash|pexels|stock`; large `<img alt="">` (decorative but dominant); hero `background-image` with `min-height: 100vh`; no `srcset` or zoom on product images.
- *Quick test:* cover each image and ask whether the page loses information; if not, cut or shrink it.

**How to implement.**
1. Inventory images as informative, functional or decorative.
2. Replace stock photos with real photos of people, products and places.
3. For products, show differentiating details and offer an enlarged view at least twice the default size [1].
4. Remove decoration or move it to CSS backgrounds at low height.
5. Write alt text for informative images and `alt=""` for decorative ones (A11Y-10).
6. Compress images and set width and height to protect load time and layout stability (FBK-05, FBK-06); confirm with a five-second or eyetracking test.

**Sources.**
[1] Nielsen, J. (2010). Photos as web content. Nielsen Norman Group. https://www.nngroup.com/articles/photos-as-web-content/
[2] Pernice, K. (2018). Banner blindness revisited: users dodge ads on mobile and desktop. Nielsen Norman Group. https://www.nngroup.com/articles/banner-blindness-old-and-new-findings/
[3] Moran, K. (2024). The aesthetic-usability effect. Nielsen Norman Group. https://www.nngroup.com/articles/aesthetic-usability-effect/
