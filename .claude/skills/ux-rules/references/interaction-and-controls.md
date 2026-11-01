# Interaction design and controls (INT)

How controls look, behave and relate to the things they control: visible cues, icon labels, internal consistency and design systems, mapping and direct manipulation, accelerators, moving complexity into the system, and modes and modal dialogs. Load this file when auditing buttons, toolbars, settings, editors, dialogs or any screen where people act on objects. Touch size and gestures are in PLT; feedback timing is in FBK; undo and confirmation are in ERR.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| INT-01 | Make interactive elements look interactive | Moderate | any UI with clickable or tappable elements |
| INT-02 | Pair icons with text labels | Moderate | toolbars, tab bars, navigation, icon buttons |
| INT-03 | Keep the product internally consistent; use a design system | Moderate | multi-screen products and any team of two or more |
| INT-04 | Map controls to what they control; let people act on objects directly | Strong | control panels, settings, editors, lists, canvases |
| INT-05 | Provide accelerators for frequent and expert use | Moderate | tools people use repeatedly (editors, inboxes, consoles) |
| INT-06 | Absorb complexity in the system, not in the user | Weak | forms, setup, settings, anything the system could derive |
| INT-07 | Avoid needless modes and modal dialogs | Moderate | dialogs, overlays, state-dependent controls |

---

### INT-01 Make interactive elements look interactive

**What it is.** Give every control a visible cue (fill, border, underline, color plus a second cue, icon, cursor, pressed state) that says it can be used. Norman calls these cues signifiers: perceivable signs that show where an action can happen.

**Why it works.**
- People scan for things to act on. When a link or button looks like plain text, they spend extra fixations deciding whether to try it.
- NN/g ran an eyetracking experiment (2017): 71 participants, 9 live pages, each rebuilt with strong and with weak signifiers, assigned between subjects. Weak versions took 22% longer and drew 25% more fixations (both p < 0.05). Six of nine page pairs showed different gaze patterns; the reverse never occurred [1].
- On one page, 86% (25 of 29) of people on the strong version moved from a heading to the target link; on the weak version only 50% (12 of 24) did [1].
- Norman (2013) separates what an object allows (affordance) from the cue that reveals it (signifier); designers control the signifier [2].
- Hover is not a cue on touch screens, and hover-only labels add interaction cost [3].
- Platforms build the cue in: Material orders buttons by emphasis (filled, tonal or elevated, outlined, text) [4]; iOS offers Button Shapes, which underlines tappable text [5].

**Evidence: Moderate.** One published eyetracking experiment with a stated method (2017) plus agreement across platform guidelines; Norman's concept dates from 1988 and was revised in 2013.

**Limitations.**
- The NN/g tasks were short, single-page findability tasks; wrong clicks were not measured, and NN/g expects the 22% gap to shrink on full tasks [1].
- NN/g says flat styles can work when pages are sparse, layouts are conventional and elements are high-contrast and well spaced; in-line links may skip underlines if their color contrasts [1].
- Too many strong cues compete for attention; keep one primary action per view (VIS) and use the emphasis ladder.
- A button look on something that is not a button, or a fake close control, is a deceptive pattern (CHO).
- Color alone is not a cue for people with color-vision deficiency (A11Y).

**How to measure it works.**
- First-click or "what can I click?" test on a screenshot: share of participants who pick the right element, and time to first click; expect higher and faster.
- Eyetracking or click maps: fixations before the first correct action; expect fewer.
- Analytics: dead clicks (clicks on non-interactive elements) and missed taps; expect fewer. Lagging: adoption of features that sit behind weakly marked controls.

**Implemented by.**
- Google, Material Design: five button types ordered by emphasis, filled for primary actions and outlined or text for secondary ones [4]. No outcome data published.
- Apple, iOS: Button Shapes accessibility setting (the iOS 13 guide says it underlines tappable text) [5]. No outcome data published.
- NN/g test pages (2017): strong-signifier versions won on time and fixations [1].

**How to detect it.**
- *Applied:* buttons have a fill or border; inline links are underlined or differ in color plus one more cue; icon controls show hover, focus and pressed states; disabled differs from enabled.
- *Violated:* "buttons" that are plain body-colored text; clickable cards with no cue; headings that are links; controls that appear only on hover; disabled and enabled look alike.
- *In code:* `<div onClick`, `<span onclick`, `role="button"` on a non-`<button>`, missing `cursor: pointer`, `text-decoration: none` on `a` with no other cue, `outline: none` with no replacement, `opacity: 0` that becomes `1` on `:hover`; SwiftUI `.buttonStyle(.plain)` with no other cue; Compose `Text(modifier = Modifier.clickable {})` styled as body text.
- *Quick test:* convert the screenshot to grayscale and blur it; can you still tell buttons from labels? Or ask a colleague to circle everything clickable in 10 seconds and compare with the real list.

**How to implement.**
1. Define three or four button styles by emphasis (primary filled, secondary outlined, tertiary text); allow one primary per view.
2. Keep inline links underlined, or use contrasting color plus a second cue; reserve plain text for non-interactive content.
3. Style every state from tokens: default, hover, `:focus-visible`, pressed, disabled.
4. Put nothing essential behind hover; touch has no hover.
5. Use native `<button>` and `<a href>` so the browser supplies focus, cursor and keyboard behavior; in native apps use the standard button styles.
6. Re-check in grayscale and with Button Shapes switched on.

**Sources.**
[1] Moran, K. (2017). Flat UI Elements Attract Less Attention and Cause Uncertainty. Nielsen Norman Group, Sept 3, 2017. https://www.nngroup.com/articles/flat-ui-less-attention-cause-uncertainty/
[2] Norman, D. A. (2013). The Design of Everyday Things (revised and expanded edition). Basic Books. Book; not opened in this pass.
[3] Harley, A. (2014). Icon Usability. Nielsen Norman Group, July 27, 2014. https://www.nngroup.com/articles/icon-usability/
[4] Google. Buttons, Jetpack Compose (Material 3 button types and emphasis). https://developer.android.com/develop/ui/compose/components/button
[5] Apple. iPod touch User Guide, iOS 13: Display & Text Size (Button Shapes, On/Off Labels). https://support.apple.com/bn-in/guide/ipod-touch/iph3e2e1fb0/13.0/ios/13.0

---

### INT-02 Pair icons with text labels

**What it is.** Show a visible text label next to or under each icon that starts an action or opens a destination. Skip the label only when the icon is close to universal in that context. A tooltip is not a label.

**Why it works.**
- Few icons have a settled meaning. NN/g (2014) names only three as nearly universal: home, print and the magnifier for search. Its advice is a visible label on every icon, even standard ones, never revealed by hover [1].
- In an NN/g test, a clock icon that opened browsing history was recognized as a clock, but no participant clicked it [1].
- Wiedenbeck (1999) compared buttons with text only, icons only and both, for novices. First-session performance was best with label-only and icon-plus-label; a secondary description says the label benefit fades with practice but labels still speed learning and raise perceived ease of use [2] (snippet).
- Platform guidance leans the same way, with exceptions. Apple recommends a label for each tab and requires one on visionOS [3]. Microsoft notes that labels beside the icon stay visible, while labels below are hidden until the bar opens [4]. Material's navigation bar can be labeled, selected-only or unlabeled; its default shows all labels at three items or fewer and only the selected label at four or more [5].
- Hidden entry points get used less. NN/g (2016; 179 participants, 6 sites) saw hidden navigation used in 27% of desktop cases versus 48% for visible navigation, and 57% versus 86% (combined navigation) on mobile. It did not compare icon-only with labeled buttons [6].

**Evidence: Moderate.** NN/g qualitative findings (2014), one 1999 experiment known from its abstract, and platform guidance that is itself split.
Related standard: WCAG 2.2 SC 2.5.3 Label in Name (A) requires the accessible name to contain the visible label text [7].

**Limitations.**
- Space: five labeled tabs on a 360 px phone are tight, and Material's default drops labels on unselected items at four or more [5]. Cut the number of destinations (three to five) before cutting labels.
- Near-universal icons in context (close ×, magnifier inside a search field, play) carry lower risk.
- The label benefit shrinks with practice [2], so dense expert toolbars (bold, italic) can be icon-only with tooltips and shortcuts (INT-05).
- Labels grow in translation; keep them to one short word where possible [3][4].
- Tooltips supplement labels but fail on touch and for keyboard-only users [1].

**How to measure it works.**
- Icon-recognition test: show icons without labels and record what people think each does; icons with frequent wrong answers need labels.
- First-click test on navigation, and A/B of tap rate per item with and without labels; expect more correct first taps and higher use of items whose meaning was unclear.
- Lagging: adoption of features reached only through icons; support questions asking where a feature is.

**Implemented by.**
- Apple, iOS tab bars: a label per tab, single words preferred [3].
- Google, Material navigation bar: labeled, selected-only, unlabeled and auto modes; three to five destinations [5].
- Microsoft, WinUI CommandBar: compact mode shows icons only; the docs advise labels to the right on larger windows [4]. No outcome data published for these three.

**How to detect it.**
- *Applied:* each nav item and toolbar action shows an icon plus a one- or two-word label; the menu icon carries the word "Menu" where space allows; the accessible name equals or contains the visible text.
- *Violated:* rows of glyphs with no text; icon-only primary actions; labels shown only on hover or long-press; a `title` or `aria-label` as the only name.
- *In code:* `<button>` holding only an `<svg>`, `<i class="fa-…">` or `<span class="material-icons">`; `aria-label` with no visible text node; Android `IconButton`, `ImageButton` or `FloatingActionButton` with only `contentDescription`; `labelVisibilityMode="unlabeled"`; SwiftUI `tabItem { Image(systemName:) }` with no `Text`; WinUI `AppBarButton` with an empty `Label`.
- *Quick test:* cover the labels and ask five people what each icon does; any icon more than one person misreads needs a label.

**How to implement.**
1. Default to icon plus a short visible label for navigation and primary actions. Put the label beside the icon when width allows, under it in tab bars.
2. Go icon-only only for near-universal icons or repeated expert toolbar actions; add a tooltip, an accessible name and a keyboard shortcut.
3. When width runs short, reduce the number of items instead of removing labels.
4. Make the accessible name contain the visible label text (SC 2.5.3).
5. Never let hover be the only way to learn what an icon does.
6. Test with five users before and after.

**Sources.**
[1] Harley, A. (2014). Icon Usability. Nielsen Norman Group, July 27, 2014. https://www.nngroup.com/articles/icon-usability/
[2] Wiedenbeck, S. (1999). The use of icons and labels in an end user application program: an empirical study of learning and retention. Behaviour & Information Technology 18(2):68-82. https://scilit.com/publications/69a8ee4f1d6cf726a650945daf8a929a (snippet; page returned 403)
[3] Apple. Human Interface Guidelines, Tab bars. https://developer.apple.com/design/human-interface-guidelines/tab-bars
[4] Microsoft. Command bar (Windows apps). https://learn.microsoft.com/en-us/windows/apps/design/controls/command-bar
[5] Material Components for Android. Navigation bar (BottomNavigation) documentation. https://raw.githubusercontent.com/material-components/material-components-android/master/docs/components/BottomNavigation.md
[6] Pernice, K., Budiu, R. (2016). Hamburger Menus and Hidden Navigation Hurt UX Metrics. Nielsen Norman Group, June 26, 2016. https://www.nngroup.com/articles/hamburger-menus/
[7] W3C. Understanding SC 2.5.3 Label in Name. https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html

---

### INT-03 Keep the product internally consistent; use a design system

**What it is.** The same thing looks and behaves the same everywhere in the product: colors, type, spacing, components, wording and placement. A design system (tokens, shared components, usage rules) is how a team keeps it that way.

**Why it works.**
- Consistency lets people carry what they learned on one screen to the next, which cuts learning and errors. Nielsen's heuristic 4 (1994, last reviewed 2024) asks for internal consistency within a product and adherence to outside conventions [1].
- Sparkbox ran an experiment (published about late October 2021, not 2019): eight developers coded the same Figma contact form from scratch and with IBM Carbon. Median 4.2 hours from scratch versus 2 hours with Carbon, learning time included. Sparkbox reports 47% faster; the medians imply about 52%, so the headline figure was computed another way [2].
- Reviewers ranked each form against the design file; only one of the eight from-scratch forms ranked more visually consistent than that developer's Carbon form [2].
- On web pages, Ozok and Salvendy (2000) found more comprehension errors on physically inconsistent pages, and satisfaction tracked overall consistency level (secondary summary) [3].

**Evidence: Moderate.** Heuristic consensus (1994), one small developer-speed experiment, and one older user-performance experiment known only from a summary. Evidence on user outcomes is thinner than on developer speed.

**Limitations.**
- Grudin (1989) argued that consistency is an unreliable guide: its senses (internal, external, analogic) can conflict, and users' tasks should drive design. Rejecting it as the primary goal does not mean randomness [4].
- A consistent wrong convention spreads the problem. Where your system conflicts with the platform or with products users already know, see PLT-01 and PER (Jakob's law).
- Sparkbox's study had eight people, free-time work, subjective ranking and developers with accessibility training; the authors say results may differ for other teams [2].
- A design system costs people, versioning and adoption effort; a very small product may not repay it.
- Uniform is not consistent: different actions should look different (INT-01).

**How to measure it works.**
- Developer side: time to build a standard screen with and without the system; share of UI built from system components; count of one-off components; style-related review comments.
- Drift: distinct colors, font sizes, spacing values and radii in shipped CSS (expect the count to fall toward the token set size); visual-regression diffs.
- User side: errors on tasks that cross screens; ease ratings; support questions of the form "where did X go".

**Implemented by.**
- IBM, Carbon: the system under test in Sparkbox's experiment [2].
- Google, Material Design: shared component set and emphasis rules (see INT-01); no outcome published in the sources checked.
- Atlassian, Shopify Polaris, Airbnb DLS (introduced 2016) and GitHub Primer are widely cited systems; we found no verified outcome numbers for them.

**How to detect it.**
- *Applied:* one token file (color roles, spacing scale, type scale, radii); components imported from a shared library; one style per action type; the same label for the same action; primary action and navigation in the same place on every screen.
- *Violated:* many near-duplicate colors (`#3B82F6` and `#3A81F5`); raw hex and `px` values inside components; several button, modal or table implementations; "Save", "Submit" and "Apply" for one action; spacing off the scale (13px, 17px).
- *In code:* count distinct `#[0-9a-fA-F]{3,8}` and `rgb(` values outside token files; inline `style={{`; Tailwind arbitrary values (`p-[13px]`, `bg-[#…]`); few `var(--` or `theme.` references; duplicate component names (`Button2`, `NewButton`); stylelint `color-no-hex`.
- *Quick test:* screenshot five main screens and list every button style, link style, heading size and corner radius. More than one primary-button style, or more than about six text sizes, suggests drift (a rule of thumb, not a published threshold).

**How to implement.**
1. Audit first: inventory colors, type sizes, spacing values and component variants in the product.
2. Define tokens by role (`color-text-primary`, `space-4`) on a 4 or 8 unit scale, as CSS custom properties or a token file (for example Style Dictionary).
3. Build the 10 to 15 most reused components first: button, input, select, checkbox, modal, table, tabs, toast, navigation.
4. Enforce with lint rules against raw hex and px values, and with visual-regression tests on a component catalog (such as Storybook).
5. Write do and don't usage notes; version the system; retire old components on a schedule.
6. Use one verb per action across screens (CON).
7. If you lack capacity, adopt and theme an existing system (Material, Carbon, Fluent, Polaris, Primer).

**Sources.**
[1] Nielsen, J. (1994; reviewed Jan 30, 2024). 10 Usability Heuristics for User Interface Design. Nielsen Norman Group. https://www.nngroup.com/articles/ten-usability-heuristics/
[2] Sparkbox (about Oct 2021). Yes, Design Systems Do Improve Developer Efficiency and Design Consistency. The page shows no date; copies appeared Oct 28 to Nov 5, 2021 (CSS-Tricks, Nov 5, 2021). https://sparkbox.com/foundry/design_system_roi_impact_of_design_systems_business_value_carbon_design_system and https://css-tricks.com/yes-design-systems-do-improve-developer-efficiency-and-design-consistency/
[3] Ozok, A. A., Salvendy, G. (2000). Measuring consistency of web page design and its effects on performance and satisfaction. Ergonomics 43(4):443-460. https://www.econbiz.de/Record/measuring-consistency-of-web-page-design-and-its-effects-on-performance-and-satisfaction/10006289598 (snippet)
[4] Grudin, J. (1989). The case against user interface consistency. Communications of the ACM 32(10):1164-1173. https://www.microsoft.com/en-us/research/publication/case-user-interface-consistency/ (snippet)

---

### INT-04 Map controls to what they control; let people act on objects directly

**What it is.** Natural mapping: arrange and move controls the way the things they control are arranged and move. Direct manipulation: let people act on the visible object (drag, resize, edit in place) with immediate, reversible feedback, instead of through a separate command or form.

**Why it works.**
- Chapanis and Lindenbaum (1959) timed people choosing the control for a given stove burner across four control layouts. Slightly displacing the burners so each control sat in line with its burner gave a strong, consistent mapping [1][2]. Secondary descriptions give 15 subjects per layout and 80 trials (snippet).
- Later studies agree that spatial congruence drives the expectation: Shinar and Acton (1978), Ray and Ray (1979), and Tlauka (2004), where 88% and 92% of participants chose the expected mapping on a congruent layout [2]. In Osborne and Ellingstad (1987), displaced hotplates beat painted sensor lines, which beat a standard layout, on reaction time and errors [2].
- Shneiderman (1983) named direct manipulation: the object stays visible, physical actions replace command syntax, and actions are rapid, incremental and reversible with visible results [3]. Hutchins, Hollan and Norman (1985) explained it as shrinking the distance between goals and actions [4].
- Margono and Shneiderman (1987): after short training, novices doing file tasks on a Macintosh (direct manipulation) were faster, made fewer errors and were more satisfied than on MS-DOS commands [5].

**Evidence: Strong.** For mapping: stimulus-response experiments replicated from 1959 to 2011. Direct manipulation is weaker (theory plus one platform-level comparison from 1987), so treat that half as Moderate.

**Limitations.**
- Mapping stereotypes depend on the population: the best stove arrangement in US studies differed from Chinese and South African hardware and paper tests [2].
- Extra cues cannot rescue a bad mapping: painted lines helped compatible panels and hurt incompatible ones (Chapanis and Yoblick 2001) [2].
- Margono and Shneiderman compared two whole systems, so the result is confounded [5]. Direct manipulation trades away flexibility and repeatability and is weak on precision, accessibility and bulk work; add non-drag alternatives (PLT-05) and accelerators (INT-05) [4].
- Toggles are a frequent mapping failure. NN/g: use them only for binary settings that take effect immediately; its example is Windows 10, where the word "Off" sat opposite the knob so the state read as on [6]. Apple adds: never use color alone to show state [7].

**How to measure it works.**
- Mapping test: wrong-control selections and time to the first correct control for each target; expect fewer errors and faster selection.
- Direct manipulation: time and errors against a form or dialog baseline; undo rate; first-try success; accidental drops.
- Toggle test: show a screenshot and ask for the state of each switch; expect near-100% correct reading.

**Implemented by.**
- Apple Macintosh: the direct-manipulation system in the 1987 comparison [5].
- Apple, iOS: the On/Off Labels accessibility setting marks switches so state does not depend on color or knob position [8].
- Trello boards (drag cards between lists) and inline rename or edit in editors such as Google Docs are everyday examples; anecdotes, no published outcome.

**How to detect it.**
- *Applied:* controls sit on or beside the object they change; control order matches visual order; right or up means more; click-to-edit titles; drag handles with live drop targets; live preview while a value changes; switches show state with text or position plus a non-color cue.
- *Violated:* a row of four controls for a 2×2 set of objects; an Edit button that opens another page to change one field; settings applied only after Save with no preview; a toggle inside a form with a Submit button; a label like "Dark mode?" that does not say what ON does; reversed direction.
- *In code:* `contenteditable`, `draggable="true"`, dnd-kit, SortableJS, `react-beautiful-dnd`; `<input type="range">` with `oninput` (live) versus `onchange` plus Save; `role="switch"` with `aria-checked`; native `Toggle`, WinUI `ToggleSwitch` (`OnContent`/`OffContent`), `SwitchMaterial`, `ItemTouchHelper`.
- *Quick test:* hide the labels and ask a new user which control changes which object; read each toggle's state from a screenshot.

**How to implement.**
1. Put each control next to or on the object it changes. Keep control order identical to on-screen order; for a grid of objects, lay out the controls in the same grid.
2. Use conventional directions (right or up is more) and check right-to-left locales.
3. Let people edit in place, drag to reorder or resize, and see a live preview with undo (ERR).
4. Always offer a non-drag alternative: buttons or a menu ("Move up", "Move to…") and typed input (PLT-05).
5. Use a toggle only for an on/off setting that applies at once; otherwise use a checkbox with Save. Write the label as what happens when ON; NN/g's test is to read the label aloud with "on" or "off" appended [6].
6. Show state with shape, text or position, not color alone.
7. Test the mapping with five people who have not seen the product.

**Sources.**
[1] Chapanis, A., Lindenbaum, L. E. (1959). A reaction time study of four control-display linkages. Human Factors 1:1-7. Original not opened; cited as listed in [2].
[2] Hoffmann, E. R., Chan, A. H. S. (2011). Alternative approaches to the design of four-burner stoves. Ergonomics 54(9):777-791. https://doi.org/10.1080/00140139.2011.597879 (PDF read: https://www.ergo.human.cornell.edu/DEA3510HWs/HoffmanandChan2011.pdf)
[3] Shneiderman, B. (1983). Direct manipulation: a step beyond programming languages. IEEE Computer 16(8):57-69. https://doi.org/10.1109/MC.1983.1654471 (citation from search results; principles from a secondary summary)
[4] Hutchins, E. L., Hollan, J. D., Norman, D. A. (1985). Direct manipulation interfaces. Human-Computer Interaction 1:311-338. https://vis.csail.mit.edu/classes/6.859/readings/pdfs/Hutchins-DirectManipulationInterfaces.pdf (snippet)
[5] Margono, S., Shneiderman, B. (1987). A study of file manipulation by novices using commands vs. direct manipulation. University of Maryland report CAR-TR-264. https://drum.lib.umd.edu/items/2b159044-927d-4eb3-aeb3-8fce5ea1fe41/full
[6] Kendrick, A. (2018). Toggle Switch Guidelines. Nielsen Norman Group, July 29, 2018. https://www.nngroup.com/articles/toggle-switch-guidelines/
[7] Apple. Human Interface Guidelines, Toggles. https://developer.apple.com/design/human-interface-guidelines/toggles
[8] Apple. iPod touch User Guide, iOS 13: Display & Text Size (On/Off Labels). https://support.apple.com/bn-in/guide/ipod-touch/iph3e2e1fb0/13.0/ios/13.0

---

### INT-05 Provide accelerators for frequent and expert use

**What it is.** Shortcuts that speed up repeated work without hiding the visible path from novices: keyboard shortcuts, command palettes, multi-select and bulk actions, saved views and filters, templates, gestures and customization.

**Why it works.**
- Nielsen's heuristic 7 (1994, reviewed 2024): accelerators that novices never see let experts work faster, so one design serves both. Examples given are keyboard shortcuts, touch gestures and personalization [1].
- People do not find shortcuts on their own. Lane and colleagues (2005, IJHCI 18(2)): experienced users of several applications rarely used keyboard shortcuts and preferred icon toolbars, though shortcuts were more efficient (summary of the abstract) [2].
- Adoption can be nudged. Grossman, Dragicevic and Balakrishnan (CHI 2007): hotkey use was 28.9% with an unchanged menu, 66.6% with audio feedback and 72.8% when menu items were disabled; in the baseline group 7 of 14 people made no effort to learn hotkeys [3].
- Command palettes collect every command behind one search box. VS Code documents Ctrl/Cmd+Shift+P as access to all its functionality [4]; GitHub's palette opens with Ctrl/Cmd+K [5].

**Evidence: Moderate.** Heuristic consensus plus peer-reviewed lab studies on adoption; we found no controlled field study of palettes. Tognazzini's 1989 claim that users feel faster on the keyboard while the mouse is faster rests on an Apple study with no published method or data (Weak) [6].

**Limitations.**
- Accelerators serve repeated use; a one-time flow such as checkout should not depend on them.
- Single-character shortcuts clash with typing and assistive technology: WCAG 2.1.4 (A) needs a way to turn them off, remap them or limit them to focus [7]. Apple says menu items revealed by a modifier key must never be the only way to do a task [8].
- Hidden shortcuts go unused unless shown in menus, tooltips or a `?` cheat sheet; Grossman's gains came from imposed costs (disabled menu items), which may frustrate people outside a training setting [3].
- GitHub's palette is a public preview and off by default [5]; a reported deprecation was delayed after pushback, with low measured usage as the stated reason (snippet) [9]. Default-off makes usage a poor popularity measure.

**How to measure it works.**
- Share of weekly active users who use a shortcut, palette or bulk action; accelerator share of repeat tasks; expect up.
- Time and steps for a repeated task (archive 20 messages); expect lower.
- Hint funnel: share who see a shortcut hint and then use it within a week. Guard metrics: accidental triggers and support tickets.

**Implemented by.**
- Microsoft, VS Code: command palette on Ctrl/Cmd+Shift+P [4]. Slack, Linear and Figma ship similar quick switchers; we found no published adoption figures for any of them.
- GitHub: command palette on Ctrl/Cmd+K, public preview, off by default [5].
- Google, Gmail: keyboard shortcuts with custom shortcuts via Labs (2008 post title and date verified; body not opened) [10].

**How to detect it.**
- *Applied:* shortcut hints in menus and tooltips; a Cmd/Ctrl+K palette; a `?` cheat sheet; checkboxes with select-all and a bulk action bar; saved filters or views; recent items; templates; j/k or arrow-key navigation in lists.
- *Violated:* a daily-use tool where every task is a four-click path; lists with no multi-select; no duplicate or repeat-last; mouse-only paths; shortcuts that exist but are shown nowhere.
- *In code:* `addEventListener('keydown'`, `useHotkeys`, `hotkeys-js`, `mousetrap`, `aria-keyshortcuts`, `accesskey`; palette libraries `cmdk`, `kbar`; native `.keyboardShortcut`, Electron `accelerator`, WinUI `KeyboardAccelerators`; row `<input type="checkbox">` plus "select all".
- *Quick test:* do the top task ten times in a row and count clicks and screens; try it keyboard-only; try acting on 20 items at once.

**How to implement.**
1. Find the five to ten most frequent tasks (analytics, interviews).
2. Add modifier-key shortcuts for them, using the standard ones for standard actions, and show them in menus and tooltips.
3. Add a palette (Cmd/Ctrl+K or Shift+Cmd+P) with fuzzy search, shortcut display and a visible button to open it.
4. Add multi-select with bulk actions, repeat-last, saved views and templates.
5. Teach at the moment of need: after someone does a task the slow way a few times, show the shortcut once (ONB).
6. Let users remap or disable single-key shortcuts (WCAG 2.1.4); never make an accelerator the only path.

**Sources.**
[1] Nielsen, J. (1994; reviewed Jan 30, 2024). 10 Usability Heuristics for User Interface Design. Nielsen Norman Group. https://www.nngroup.com/articles/ten-usability-heuristics/
[2] Lane, D. M., Napier, H. A., Peres, S. C., Sandor, A. (2005). Hidden costs of graphical user interfaces: failure to make the transition from menus and icon toolbars to keyboard shortcuts. International Journal of Human-Computer Interaction 18(2):133-144. https://dblp.dagstuhl.de/rec/journals/ijhci/LaneNPS05.html (snippet; abstract via a secondary summary, page returned access denied)
[3] Grossman, T., Dragicevic, P., Balakrishnan, R. (2007). Strategies for accelerating on-line learning of hotkeys. CHI 2007, pp. 1591-1600. https://www.dgp.toronto.edu/~ravin/papers/chi2007_learninghotkeys.pdf
[4] Microsoft. Visual Studio Code user interface (Command Palette). https://code.visualstudio.com/docs/getstarted/userinterface
[5] GitHub Docs. GitHub Command Palette. https://docs.github.com/en/get-started/accessibility/github-command-palette
[6] Tognazzini, B. (1989). Keyboard vs. the mouse, part 1. AppleDirect, Aug 1989; Tog on Interface, ch. 6. https://asktog.com/TOI/toi06KeyboardVMouse1.html
[7] W3C. Understanding SC 2.1.4 Character Key Shortcuts. https://www.w3.org/WAI/WCAG22/Understanding/character-key-shortcuts.html
[8] Apple. Human Interface Guidelines, The menu bar. https://developer.apple.com/design/human-interface-guidelines/the-menu-bar
[9] Neowin. GitHub customers rejoice as command palette deprecation is delayed. https://www.neowin.net/news/github-customers-rejoice-as-command-palette-deprecation-is-delayed/ (snippet; page returned 403)
[10] Google. Tip: Read your mail without touching your mouse. Official Gmail Blog, Oct 2, 2008. https://gmail.googleblog.com/2008/10/tip-read-your-mail-without-touching.html (title and date only)

---

### INT-06 Absorb complexity in the system, not in the user

**What it is.** Tesler's law of conservation of complexity: a task has an irreducible core of complexity, and the design decides who handles it. Where the system can detect, infer, derive or default a value, it should, and it should show what it did so the user can change it.

**Why it works.**
- Larry Tesler formulated the idea in the mid-1980s at Xerox PARC; his interview in Dan Saffer's Designing for Interaction (2010) is the usual source [1][2].
- His argument is economic: if an engineer can remove a problem that costs a million users a minute a day, a week of added code is the better trade, and making users absorb avoidable complexity penalizes the user for the engineer's convenience [1].
- Concrete cases: the first digits of a card number identify the network (Visa starts with 4), which lets a form pick the brand, format the number (4-4-4-4 versus 4-6-5 for American Express) and adjust helper text, as Baymard documents [3]; the browser reports the user's IANA time zone through `Intl.DateTimeFormat().resolvedOptions().timeZone` [4].

**Evidence: Weak.** A design adage from the 1980s with no experiment testing the law itself; Baymard's guidance covers specific features (card-type detection, auto-formatting) from its own checkout research, which is not a test of the law. Better-evidenced instances live in FRM.

**Limitations.**
- Hidden automation takes away control and fails silently on wrong guesses (VPN, shared device). Show the result and make it editable; see ERR and the human-control rules in AI.
- Tognazzini's counterpoint: when an application is simplified, people attempt more complex tasks, so complexity comes back elsewhere [1][2].
- Engineering cost and upkeep: card ranges and time-zone data change, and heuristics fail at edges.
- Do not automate consequential choices (consent, payment amounts) without confirmation (CHO, ERR).
- Detecting location or identity-linked values has privacy cost (CHO).

**How to measure it works.**
- Fewer fields, steps and seconds to complete; error rate on derived fields; completion rate.
- Override rate: share of users who change the automatic value; a high rate means a bad guess.
- Lagging: support tickets about the derived value.

**Implemented by.**
- Baymard-benchmarked checkouts: card-type auto-detection and auto-formatting are among the features Baymard recommends for card fields [3]. No outcome numbers in the page we read.
- Phone and desktop operating systems offer a "set time zone automatically" option (observed in OS settings; no published outcome).
- Browsers expose time zone and language to pages, so forms can default them [4] (capability, not an outcome).

**How to detect it.**
- *Applied:* values pre-filled from known data; time zone detected with a "change" link; the card brand logo appears while typing; phone and card numbers format as typed; fields the system can derive are hidden or shown read-only with an edit control.
- *Violated:* asking for card type before the number; a 400-item time-zone dropdown with no default; asking for city and state after the ZIP code; asking again for data the system already holds; users converting units or formats by hand.
- *In code:* `autocomplete="cc-number"`, `inputmode="numeric"`; `Intl.DateTimeFormat().resolvedOptions().timeZone`; a BIN-prefix regex; a card-type `<select>` next to a card-number input; `navigator.language`.
- *Quick test:* walk through sign-up or checkout and list every field; for each, ask whether the system already knows it or can derive it, and count the "yes" answers.

**How to implement.**
1. List every field and decision; mark those the system already knows or can infer.
2. Infer with a visible result and a one-step override ("Time zone: Bangkok (UTC+7), change").
3. Use platform capabilities (browser autofill, `autocomplete` tokens, `Intl` APIs) instead of hand-rolled detection.
4. Detect on input, not after submit; format as the user types.
5. Keep a manual fallback and log override rates to tune the guess.
6. Ask for confirmation before any irreversible or financial default.

**Sources.**
[1] Wikipedia. Law of conservation of complexity (cites the Saffer interview as the primary source). https://en.wikipedia.org/wiki/Law_of_conservation_of_complexity
[2] Yablonski, J. Tesler's Law. Laws of UX. https://lawsofux.com/teslers-law/ (primary source, Saffer 2010, Designing for Interaction, New Riders; Tesler's own site and the Saffer interview page could not be opened)
[3] Baymard Institute. Credit card IIN ranges and spacing patterns. https://baymard.com/checkout-usability/credit-card-patterns
[4] MDN. Intl.DateTimeFormat.prototype.resolvedOptions(). https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/DateTimeFormat/resolvedOptions

---

### INT-07 Avoid needless modes and modal dialogs

**What it is.** A mode is a state in which the same action does different things; a modal dialog blocks the rest of the interface until answered. Both interrupt and invite error. Prefer inline, non-modal alternatives, and keep modals for critical, required or irreversible decisions.

**Why it works.**
- Raskin (The Humane Interface, 2000, ch. 3): mode errors happen when people misjudge the current state, act on that belief and get a surprise. Where a mode cannot be removed, make it a quasimode held by continuous action, such as holding Shift [1][2].
- Mode confusion is documented in safety-critical work: Sarter and Woods (1995, Human Factors 37(1):5-19) studied mode error and awareness in flight-deck automation [3] (snippet).
- NN/g (2017): modals break workflow, raise cognitive load, lose context and add a dismissal step; use them only when the interruption is worth it. Fit: critical warnings, required information, steps of a complex workflow, short time-saving questions. Poor fit: unrelated content such as newsletter sign-ups, checkout, repeated prompts. Its only cited study was a qualitative one where participants strongly disliked newsletter modals; no sample size is given [4].
- Apple HIG: use modality only when it clearly helps, keep modal tasks short, avoid nested modals, always give an obvious dismissal, never show more than one alert at a time, and do not show an alert at app launch [5][6].
- Search engines act on it: Google announced a mobile ranking signal against intrusive interstitials, effective Jan 10, 2017, with exemptions for legal notices, login dialogs and small banners (snippet) [7]. Its current page says intrusive dialogs can drive users away and make content harder for search engines to understand [8].

**Evidence: Moderate.** Practitioner guidance with a stated rationale (2017), platform agreement, and the human-factors literature on mode error; no controlled test of modals versus inline alternatives found.

**Limitations.**
- Modals are right for irreversible or high-risk choices (ERR), information required to continue (login), and focused short tasks [4].
- Modes are fine when visible and short (a drawing tool selection, a Caps Lock indicator); Raskin's concern is invisible modes [1][2].
- Non-modal can fail: pop-ins can cover content, or become full-screen modals on small screens [4].
- Too many confirmation dialogs teach click-through; offer undo for reversible actions (ERR).
- Legal gates (age checks, cookie consent) are exempt in Google's guidance; keep them small and overlaid, not redirects [8].
- Marketing teams often report higher sign-ups from pop-ups; we found no independent study that also measures harm to task completion or return visits.

**How to measure it works.**
- Modals per session; share opened without a user action (on load, timer, exit intent); dismiss rate and time to dismiss; bounce after a modal; expect lower for unprompted modals.
- A/B: completion of the underlying task with the modal versus an inline alternative.
- Mode errors in tests: actions taken in the wrong state; immediate-undo rate.

**Implemented by.**
- Apple, HIG: modality and alert rules for iOS, iPadOS and macOS [5][6].
- Google Search (2017): ranking signal against intrusive mobile interstitials (snippet) [7]. No outcome numbers found for either.

**How to detect it.**
- *Applied:* inline errors and banners; toasts with Undo; popovers anchored to the control; modals opened only by a user action; one at a time; Esc, close button and scrim click all dismiss; visible mode indicators.
- *Violated:* a modal on page load or after a timer; newsletter or app-install overlays covering content; modal stacks; confirm dialogs for reversible actions; dialogs with no close; edit and view states that look identical.
- *In code:* `window.alert(`, `confirm(`, `prompt(`; `<dialog` with `.showModal()`; `role="dialog" aria-modal="true"`; open state set in `useEffect(() => setOpen(true), [])`, `DOMContentLoaded`, `setTimeout` or `mouseleave` handlers; `position: fixed; inset: 0; z-index: 9999`; `body { overflow: hidden }`; native `UIAlertController` in `viewDidLoad`, `NSAlert.runModal()`, `MessageBox.Show`, Android `AlertDialog` in `onCreate`.
- *Quick test:* load each key page cold in a private window and count overlays before any action; open a flow and count nested dialogs; press Esc on each.

**How to implement.**
1. Default to inline: errors beside fields, status banners, toasts with Undo for reversible actions.
2. Use a modal only for critical or irreversible choices, information required to proceed, or a short focused task; one at a time.
3. Trigger modals from user actions only, never on load, timer or exit intent.
4. Give a visible close control, Esc and scrim click; return focus to the trigger; make the background inert (A11Y).
5. Make unavoidable modes visible and short: an indicator, a cursor change, a quasimode (hold a key) for temporary tools.
6. Remove confirmations for reversible actions and offer undo instead.
7. Test with five users: any "what just happened?" points to a hidden mode.

**Sources.**
[1] Raskin, J. (2000). The Humane Interface: New Directions for Designing Interactive Systems. Addison-Wesley. Book; not opened. Chapter 3 covers modes and quasimodes.
[2] Raskin Center for Humane Interfaces. Core principles of humane interface design. https://www.raskincenter.org/rchi/core-principles
[3] Sarter, N. B., Woods, D. D. (1995). How in the world did we ever get into that mode? Mode error and awareness in supervisory control. Human Factors 37(1):5-19. https://doi.org/10.1518/001872095779049516 (snippet; DOI from a search result)
[4] Fessenden, T. (2017). Modal and Nonmodal Dialogs: When (and When Not) to Use Them. Nielsen Norman Group, Apr 23, 2017. https://www.nngroup.com/articles/modal-nonmodal-dialog/
[5] Apple. Human Interface Guidelines, Modality. https://developer.apple.com/design/human-interface-guidelines/modality
[6] Apple. Human Interface Guidelines, Alerts. https://developer.apple.com/design/human-interface-guidelines/alerts
[7] Google. Helping users easily access content on mobile. Google Search Central Blog, Aug 2016 (effective Jan 10, 2017). https://developers.google.com/search/blog/2016/08/helping-users-easily-access-content-on (snippet; the fetch returned the blog index, not the post)
[8] Google. Interstitials and dialogs. Google Search Central. https://developers.google.com/search/docs/appearance/avoid-intrusive-interstitials
