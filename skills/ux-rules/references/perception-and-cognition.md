# Perception, cognition and decision laws (PER)

These are the psychology and human-performance results that many other rules rest on: how fast people point, how many options they weigh, what they hold in mind, how they group what they see, and how they remember and judge an experience. Load this file when an audit needs the reason behind a layout, form or flow decision, or when another category (field grouping in FRM, menu length in NAV, touch size in PLT) needs its underlying evidence. Several popular readings of these laws are weaker than their reputation: Hick's law as proof that fewer options always win, the "seven items" limit, and peak-end as a proven software design rule. The entries say where.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| PER-01 | Make frequent and important targets large and close | Strong | any pointer or touch UI; toolbars, menus, window chrome |
| PER-02 | Limit equal-weight choices at each decision point | Mixed | menus, settings, pricing, navigation, onboarding choices |
| PER-03 | Don't make users hold information across steps; chunk long strings | Strong | multi-step flows, forms, long codes and numbers |
| PER-04 | Show options, recents and suggestions instead of making users remember | Strong | search, inputs, menus, command lists, login |
| PER-05 | Group related elements with proximity, similarity, common region and connectedness | Strong | forms, cards, settings, lists, steppers |
| PER-06 | Follow the conventions users know from other products | Moderate | headers, navigation, e-commerce, controls, icons |
| PER-07 | Invest in visual polish, but do not read polish as proof of usability | Mixed | any visual UI; usability tests and surveys |
| PER-08 | Put key items first or last, and make the one thing that matters distinct | Moderate | lists, navigation, pricing tables, recommendations |
| PER-09 | Design the worst moment and the ending of a flow | Moderate | end-to-end journeys, completion and cancel flows |
| PER-10 | Show progress toward a goal and credit genuine head starts | Mixed | multi-step flows, onboarding, profile and loyalty meters |
| PER-11 | Use the user's model and words, not the system's | Moderate | labels, states, errors, IDs, settings, information architecture |

---

### PER-01 Make frequent and important targets large and close

**What it is.** Time to reach a target grows with its distance and shrinks with its size (Fitts's law). Put frequent and critical controls near the pointer or finger and make them large. With a mouse, a screen edge or corner acts as a target of unlimited depth, because the pointer stops there.

**Why it works.**
- Aimed movement trades speed for accuracy. Fitts (1954) modelled movement time on an index of difficulty, log2(2A/W), with A the distance and W the target width [1]. MacKenzie (1992) proposed the Shannon form, log2(A/W + 1), which cannot go negative and became the standard [2]. ISO 9241-9 and its successor ISO 9241-411 build pointing-device evaluation on this model [3].
- At an edge the pointer cannot overshoot, so the target is effectively unbounded along that axis; a corner is unbounded on two axes [4].
- Pie menus put every item at the same distance and make targets larger. Callahan et al. (1988) tied their advantage to those two factors, and a text archive of the study reports them 15% faster than linear menus, with fewer errors [5].

**Evidence: Strong.** Replicated since 1954 across devices (MacKenzie's 1992 review covers six device studies) and standardised in ISO. The edge and corner corollary rests on geometry and design-team practice, not on a controlled study we could open. Size floor required: WCAG 2.2 SC 2.5.8 Target Size (Minimum), AA, 24 by 24 CSS px with exceptions [6].

**Limitations.**
- It predicts only the movement. Finding the target and deciding what to click usually cost more (PER-02, PER-04).
- Edges are unbounded only where the pointer stops. Touch and pen input have no clamped pointer, multi-monitor setups pass through edges, and a windowed app has no screen edge. Finger input also needs an extra error term for finger width [7]. See PLT (touch targets).
- A dead zone cancels the gain: before Windows 2000 the Start button ignored clicks on its outermost pixel along the left and bottom sides [4].
- Bigger is not always better. A large destructive control beside a frequent one invites slips (ERR), and moving tools to the cursor can break consistency (INT-03).

**How to measure it works.**
- Time to acquire the target and miss-click rate in a timed task test (MEA-03), and throughput in bits per second when comparing input devices [3]; expect lower time and fewer misses as distance falls or size rises.
- Analytics: clusters of near-miss clicks and rage clicks around small controls (MEA-07), then task completion time.

**Implemented by.**
- Microsoft, Office 2007 (design post, 22 August 2006): Quick Access Toolbar in the title bar so its buttons reach the top edge; Office button hit area stretched to the upper-left corner; labelled Ribbon controls made larger; Mini Toolbar shown beside the cursor. The post reports no timing result [4].
- Apple, macOS menu bar: one menu bar at the top edge for every app. Tognazzini says Fitts's law predicts menu access about five times faster than Windows menus; his page gives no data for the figure [8].

**How to detect it.**
- *Applied:* frequent actions are large and sit next to the content they change; persistent bars reach the screen edge when maximised; context menus and mini toolbars open at the pointer.
- *Violated:* small icon buttons for frequent actions; a gap between an edge control and the screen edge; the primary action far from the content it affects; dialogs that open away from the pointer.
- *In code:* `min-height`, `min-width`, `padding` on `button` and `.icon-btn`; hit-area expansion such as `::after { inset: -8px }`; `position: fixed` or `sticky` with `top: 0`; `@media (pointer: coarse)`; `contextmenu` handlers using `clientX`/`clientY`; Electron `Menu.setApplicationMenu`; native main menus (macOS `NSMenu`).
- *Quick test:* measure the three most frequent controls and their distance from where the pointer rests after the previous step. Slam the pointer into each edge control in a maximised window and check that it responds.

**How to implement.**
1. Rank actions by frequency and criticality from analytics or task analysis. Give the top three the largest, nearest positions.
2. Enlarge hit areas without changing visuals (padding or a pseudo-element). Keep pointer targets at least 24 by 24 CSS px, and larger for touch (PLT).
3. Anchor persistent controls to an edge or corner and extend the clickable area to it; leave no margin dead zone.
4. Show contextual controls beside the selection or pointer (mini toolbar, popover), not in a distant toolbar.
5. Keep destructive actions away from the most frequent targets (ERR).

**Sources.**
[1] Fitts, P. M. (1954). The information capacity of the human motor system in controlling the amplitude of movement. Journal of Experimental Psychology, 47(6), 381-391. https://doi.org/10.1037/h0055392
[2] MacKenzie, I. S. (1992). Fitts' law as a research and design tool in human-computer interaction. Human-Computer Interaction, 7(1), 91-139. https://www.yorku.ca/mack/hci1992.html
[3] Soukoreff, R. W., & MacKenzie, I. S. (2004). Towards a standard for pointing device evaluation, perspectives on 27 years of Fitts' law research in HCI. International Journal of Human-Computer Studies, 61(6), 751-789. https://doi.org/10.1016/j.ijhcs.2004.09.001 (summary text only). ISO 9241-411:2012 (Evaluation methods for the design of physical input devices): catalogue page returned HTTP 403, not opened.
[4] Harris, J. (2006). Giving you Fitts. Microsoft MSDN blog (archive), 22 August 2006. https://learn.microsoft.com/en-us/archive/blogs/jensenh/giving-you-fitts
[5] Callahan, J., Hopkins, D., Weiser, M., & Shneiderman, B. (1988). An empirical comparison of pie vs. linear menus. CHI '88, 95-100. https://doi.org/10.1145/57167.57182 . The 15% figure is from a text archive of the findings, not the paper: https://nic.funet.fi/pub/graphics/misc/news+mails/Comp.graphics/piemenues.txt
[6] W3C (2023). Understanding SC 2.5.8: Target Size (Minimum), WCAG 2.2. https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
[7] Bi, X., Li, Y., & Zhai, S. (2013). FFitts law: modeling finger touch with Fitts' law. CHI '13, 1363-1372. https://doi.org/10.1145/2470654.2466180
[8] Tognazzini, B. (2014). First principles of interaction design (revised). Ask Tog. https://asktog.com/atc/principles-of-interaction-design/

---

### PER-02 Limit equal-weight choices at each decision point

**What it is.** In choice-reaction tasks, decision time rises with the logarithm of the number of equally likely alternatives (the Hick-Hyman law). Teams cite it to justify fewer equal-weight options per screen and progressive disclosure.

**Why it works.**
- Hick (1952) timed choices among up to ten alternatives and found a roughly constant rate of information gain, of the order of five bits per second, so more alternatives take longer [1]. Hyman (1953) tied reaction time to the information in the stimulus set, which covers unequal probabilities [2].
- A memory model explains the set-size effect as retrieval interference that changes with practice [3].
- For menus, Cockburn, Gutwin and Greenberg (2007) model novices as visual searchers and experts as Hick-Hyman decision makers; predictions matched measured times for four menu designs [4].
- Nielsen (2006) argues that progressive disclosure improves learnability, efficiency of use and error rate [5].

**Evidence: Mixed.** Solid in lab choice-reaction tasks since 1952, contested for interfaces. Liu et al. (2020) argue the law does not support "less is better", that log-shaped data do not prove the law, and that most HCI tasks do not match the stimulus-response set-up [6]. A 2018 review lists practice, stimulus-response compatibility, very large sets and sequential dependencies as challenges [7]. None of the sources we could open reports a product study that isolates option count.

**Limitations.**
- Practice and highly compatible mappings reduce the set-size effect, so experts show less growth than novices [3][7].
- For lists users must scan, time is dominated by visual search, not decision time [4]. Sorted or familiar lists change that.
- Hiding options costs steps and discoverability. NN/g finds that designs with more than two disclosure levels usually have low usability [5].
- The law gives no item cap. See MYTH (7 plus or minus 2 menus) and PER-03.

**How to measure it works.**
- Time to first click and success on the main task in first-click or tree tests (MEA-10), reduced screen against original; lagging: completion or conversion on the decision screen.
- Use of the deferred ("Advanced") features and support questions about missing features, to catch the cost of hiding.

**Implemented by.**
- Progressive disclosure is documented as a pattern more than 30 years old; NN/g's staged-disclosure example comes from testing 46 web applications and gives no figures [5].
- Research: the Cockburn model predicted times for traditional, recency/frequency split and morphing menus [4]. No company outcome that isolates option count was found in the sources we could open.

**How to detect it.**
- *Applied:* one clear primary action; a short visible set with a labelled "More" or "Advanced" control; long lists grouped under headings; a sensible default preselected.
- *Violated:* many same-weight buttons or links on one decision screen; settings pages with every option expanded; pricing tables with many same-weight plans; long unsorted `<select>` lists.
- *In code:* `<details>`/`<summary>`, `aria-expanded`, "Advanced" or "More options" toggles; count same-class `<button>`/`<a>` siblings in one container; count `<option>` per `<select>`; `role="menu"` nested deeper than two levels.
- *Quick test:* count the options a user must weigh on the screen and which are equal in visual weight. Run a five-person first-click test on the main task and time it.

**How to implement.**
1. Rank options by frequency and importance from analytics and task analysis.
2. Show the top few. Group the rest under labelled categories or one "More" control, with at most two disclosure levels.
3. Preselect a sensible default or recommendation (PER-08; CHO for default ethics).
4. Keep list order predictable (alphabetical, numeric, or fixed by frequency) so users learn positions.
5. Decide by timing and first-click results, not by an option-count rule.

**Sources.**
[1] Hick, W. E. (1952). On the rate of gain of information. Quarterly Journal of Experimental Psychology, 4(1), 11-26. https://doi.org/10.1080/17470215208416600
[2] Hyman, R. (1953). Stimulus information as a determinant of reaction time. Journal of Experimental Psychology, 45(3), 188-196. https://doi.org/10.1037/h0056940 (not opened)
[3] Schneider, D. W., & Anderson, J. R. (2011). A memory-based model of Hick's law. Cognitive Psychology, 62(3), 193-222. https://doi.org/10.1016/j.cogpsych.2010.11.001 (abstract via Semantic Scholar)
[4] Cockburn, A., Gutwin, C., & Greenberg, S. (2007). A predictive model of menu performance. CHI '07, 627-636. https://doi.org/10.1145/1240624.1240723 (abstract via OpenAlex)
[5] Nielsen, J. (2006). Progressive disclosure. Nielsen Norman Group, 3 December 2006. https://www.nngroup.com/articles/progressive-disclosure/
[6] Liu, W., Gori, J., Rioul, O., Beaudouin-Lafon, M., & Guiard, Y. (2020). How relevant is Hick's law for HCI? CHI 2020. https://researchportal.ip-paris.fr/en/publications/how-relevant-is-hicks-law-for-hci/ (abstract page; DOI 10.1145/3313831.3376878)
[7] Proctor, R. W., & Schneider, D. W. (2018). Hick's law for choice reaction time: A review. Quarterly Journal of Experimental Psychology, 71(6), 1281-1299. https://pubmed.ncbi.nlm.nih.gov/28434379/

---

### PER-03 Don't make users hold information across steps; chunk long strings

**What it is.** Working memory is small and short-lived. Show the facts a step needs on that step, carry entered data forward, and break long strings into chunks.

**Why it works.**
- Miller (1956) described the limits of immediate memory and how recoding into chunks stretches them. He called the recurring sevens "a pernicious, Pythagorean coincidence" [1].
- Cowan (2001) reviewed the evidence and concluded that, with chunking and rehearsal controlled, capacity is about four chunks; other estimates run from three to five [2].
- Sweller (1988) argued, with a computational model and experiments, that means-ends problem solving uses capacity that schema learning needs; this is the base of cognitive load theory [3].
- Baymard's checkout testing found users struggle to type and check 15 to 16 digit card numbers, and that grouping them as printed on the card helps [4].

**Evidence: Strong.** Capacity limits and chunking are core, replicated findings (1956, 2001); cognitive load theory dates from 1988. The payment-form application rests on Baymard's observational testing, which is Moderate. Required: WCAG 2.2 SC 3.3.7 Redundant Entry (A): information entered earlier in the same process must be auto-populated or selectable, with exceptions [5].

**Limitations.**
- Do not turn "7 plus or minus 2" or "4" into a menu or list length rule. Span limits what people hold, not what they recognise from a visible list; NN/g itself says menus can run past seven items [6]. See MYTH (7 plus or minus 2 menus).
- Chunk size depends on familiarity. Group digits as users see them on the source: 4-4-4-4 for most cards, 4-6-5 for American Express [4].
- NN/g's 2009 article says held items fade in about 20 seconds and still uses the seven-chunk figure; Cowan's four is the better-supported estimate [6][2].

**How to measure it works.**
- Entry error rate, validation failures and time on long numeric fields (card, phone, IBAN) in an A/B test of grouped, auto-formatted input against raw input (MEA-06).
- Back-navigation or abandonment at steps that need facts from earlier steps (MEA-07); reported load with NASA-TLX or a single ease question (MEA-04).

**Implemented by.**
- Stripe, Card Element and Payment Element (docs): both format card numbers, and Stripe lists "improved UX" card formatting for the Payment Element. No outcome published [7].
- Google, libphonenumber: `AsYouTypeFormatter` formats a phone number as each digit is typed [8].
- Baymard benchmark (2017, updated 2025): about 15% of benchmarked sites still do not auto-format card spacing, down from 50% in 2019 [4].

**How to detect it.**
- *Applied:* card and phone numbers appear in groups; confirmation steps redisplay earlier choices; a running summary sits beside the current step; labels stay visible; one-time codes can be pasted or autofilled.
- *Violated:* "enter the code from step 2" with no reminder; a decision that depends on an unseen earlier choice; long unbroken digit or ID strings; fields that reject spaces; a placeholder used as the only label.
- *In code:* `autocomplete="cc-number"`, `inputmode="numeric"`, `autocomplete="one-time-code"`; masking libraries (`cleave.js`, `imask`, `react-number-format`, `libphonenumber-js` `AsYouType`); `maxlength="16"` or `pattern="\d{16}"` with no formatting (violated); `placeholder` with no `<label>`.
- *Quick test:* run the longest flow and list every fact you had to remember or look up again. Enter a card number with and without spaces; both should be accepted and shown grouped.

**How to implement.**
1. List what each step needs from earlier steps and show it on that step (summary or inline).
2. Keep entered data after errors, Back and refresh (ERR; WCAG 3.3.7).
3. Format long strings in the pattern users see on the source. Accept pasted or spaced input and strip separators in code instead of rejecting them. Use proven components (Stripe Payment Element, libphonenumber).
4. Split long forms into labelled groups of related fields (PER-05; FRM, multi-step forms).

**Sources.**
[1] Miller, G. A. (1956). The magical number seven, plus or minus two: Some limits on our capacity for processing information. Psychological Review, 63(2), 81-97. https://doi.org/10.1037/h0043158 (abstract via OpenAlex)
[2] Cowan, N. (2001). The magical number 4 in short-term memory: A reconsideration of mental storage capacity. Behavioral and Brain Sciences, 24(1), 87-114. https://doi.org/10.1017/S0140525X01003922
[3] Sweller, J. (1988). Cognitive load during problem solving: Effects on learning. Cognitive Science, 12(2), 257-285. https://doi.org/10.1207/s15516709cog1202_4
[4] Baymard Institute (2017, updated 2025). The "credit card number" field must allow and auto-format spaces. https://baymard.com/blog/credit-card-field-auto-format-spaces . Card digit patterns: Baymard Institute (2020). Credit card IIN ranges and spacing patterns. https://baymard.com/checkout-usability/credit-card-patterns
[5] W3C (2023). Understanding SC 3.3.7: Redundant Entry, WCAG 2.2. https://www.w3.org/WAI/WCAG22/Understanding/redundant-entry.html
[6] Nielsen, J. (2009). Short-term memory and web usability. Nielsen Norman Group, 6 December 2009. https://www.nngroup.com/articles/short-term-memory-and-web-usability/
[7] Stripe. Compare the Payment Element and Card Element. https://docs.stripe.com/payments/payment-card-element-comparison
[8] Google. libphonenumber (README). https://github.com/google/libphonenumber

---

### PER-04 Show options, recents and suggestions instead of making users remember

**What it is.** Recognition (spotting something you have seen among options) is easier than recall (producing it from memory). Make options, recent items and suggestions visible so users do not have to remember names, commands or values. This is Nielsen's usability heuristic 6.

**Why it works.**
- Memory research shows recognition outperforms recall. Standing (1973) found recognition memory for pictures "almost limitless" under suitable conditions; a later modelling paper cites 83% correct after 10,000 pictures seen once [3].
- Budiu (2024): recognition supplies more cues, which spread activation to the answer. Search suggestions turn query writing from recall into recognition [2].
- Nielsen's heuristic (1994, reviewed 2024) states the design consequence: minimise memory load by making elements, actions and options visible [1].

**Evidence: Strong.** The memory effect is over 50 years old and replicated; the interface form is a long-standing heuristic with no single decisive trial. Required: WCAG 2.2 SC 3.3.8 Accessible Authentication (Minimum), AA: a login step may not rely on remembering a password unless an alternative or help exists, such as paste and password managers [7].

**Limitations.**
- Visible options cost space and attention (PER-02, VIS-01). Experts want accelerators (INT-05); good designs offer both.
- The gain is often surfacing information, not saving keystrokes: a 2024 study of IDE autocomplete found no significant drop in keystrokes [6].
- Recents and suggestions go stale, can expose private items, and can steer choices. Let users clear them and do not show sensitive history by default.
- Recognition needs recognisable labels and icons; icon-only toolbars fail it (INT-02).

**How to measure it works.**
- Unaided task success and time to first successful use of a feature (MEA-03); the share of users who find the feature without help.
- Search and command inputs: query-formulation time, suggestion click rate, zero-result and reformulation rates (NAV; MEA-07); for command palettes, the share of commands run through the palette and shortcut use after users see the hint.

**Implemented by.**
- Google, Search autocomplete (2018): Google says it cuts typing by about 25% on average and saves over 200 years of typing time per day. These are Google's own estimates; we found no independent check [4].
- Microsoft, VS Code Command Palette: shows each command's default keyboard shortcut next to the command, so searching also teaches shortcuts [5]. No outcome published.
- Amazon recently viewed items, cited by NN/g as recognition support; no outcome published [2].

**How to detect it.**
- *Applied:* pickers or comboboxes where the valid values are known; autocomplete with suggestions; recents and favourites; labelled toolbar buttons; a command palette that shows shortcuts; format examples beside fields; earlier values prefilled.
- *Violated:* a blank field that needs an exact name, ID or command; icon-only navigation; features reachable only by hidden gestures; "Invalid code" with no sign of the valid format; a setting that refers to an item not shown.
- *In code:* `<datalist>`, `list=`, `role="combobox"`, `aria-autocomplete="list"`; palette libraries `cmdk`, `kbar` or `metaKey && key === 'k'` handlers; storage keys such as `recent`; `<input type="text">` for finite sets such as country; a `<button>` holding only an `<svg>` with no label.
- *Quick test:* give a new user a task that needs a rarely used feature and say nothing. Note each time they must type an exact string or hunt for a hidden control. Focus each search or entry field and see whether recents or suggestions appear.

**How to implement.**
1. Replace free text with pickers or comboboxes wherever the valid values are known; let typing filter the list.
2. Show recents and popular items when a search or command field gains focus, before any typing.
3. In apps with many actions, add a command palette that lists each command with its shortcut (INT-05).
4. Put format examples and expected values beside the field, not only in the error (FRM).
5. Label icons (INT-02) and keep suggestions fast (FBK). Never block paste or password managers at login.

**Sources.**
[1] Nielsen, J. (1994, reviewed 2024). 10 usability heuristics for user interface design. Nielsen Norman Group. https://www.nngroup.com/articles/ten-usability-heuristics/
[2] Budiu, R. (2024). Memory recognition and recall in user interfaces. Nielsen Norman Group, 15 January 2024. https://www.nngroup.com/articles/recognition-and-recall/
[3] Standing, L. (1973). Learning 10,000 pictures. Quarterly Journal of Experimental Psychology, 25(2), 207-222. https://doi.org/10.1080/14640747308400340 (abstract via OpenAlex). The 83% figure is from a later modelling paper, seen only as a snippet: https://www.mrcbndu.ox.ac.uk/papers/computational-models-can-replicate-capacity-human-recognition-memory (snippet)
[4] Sullivan, D. (2018). How Google autocomplete works in Search. Google, 20 April 2018. https://blog.google/products/search/how-google-autocomplete-works-search/
[5] Microsoft. Visual Studio Code: Tips and tricks (Command Palette). https://code.visualstudio.com/docs/getstarted/tips-and-tricks
[6] An analysis of the costs and benefits of autocomplete in IDEs. ESEC/FSE 2024. https://2024.esec-fse.org/details/fse-2024-research-papers/4/An-Analysis-of-the-Costs-and-Benefits-of-Autocomplete-in-IDEs (snippet)
[7] W3C (2023). Understanding SC 3.3.8: Accessible Authentication (Minimum), WCAG 2.2. https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html

---

### PER-05 Group related elements with proximity, similarity, common region and connectedness

**What it is.** People see items as a group when they sit close together, look alike, share an enclosed area, or are joined by a line. Use these cues so the visual grouping matches the meaning, for example a label closer to its own field than to the next field.

**Why it works.**
- Wertheimer (1923) described proximity, similarity, common fate, good continuation and closure as factors that organise what we see [1].
- Palmer (1992) added common region and reported that it can overcome proximity and similarity [2]. Palmer and Rock (1994) proposed uniform connectedness: connected, homogeneous regions form the first units of perception, and the effect holds even when proximity and similarity oppose it [3].
- In forms, Penzo's eye-tracking study (2006) measured label-to-field eye movements of about 50 ms for labels above fields and about 500 ms for left-aligned labels beside fields; the article does not state the sample size [4]. NN/g advises a top-aligned label close to its field, with a larger gap before the next label-field pair [5].

**Evidence: Strong.** Perceptual grouping is replicated lab science (1923 to 1994). The form-specific numbers come from one eye-tracking study with an unstated sample, which is weak on its own. Required: WCAG 2.2 SC 1.3.1 Info and Relationships (A): structure conveyed visually must also be available in markup, for example with `fieldset` and `legend` [6].

**Limitations.**
- Cues compete. If spacing says one group and borders say another, users misgroup; common region and connectedness can beat proximity [2][3].
- Boxing everything adds clutter and weakens hierarchy (VIS-04). Use spacing first and add borders where grouping must be strong.
- Grouping shows relatedness, not meaning. Groups still need headings (CON) and programmatic structure (A11Y).
- Penzo's test pages had no other visual design, so the timings may not carry over to real pages [4]. Top versus left labels is a form-layout question (FRM).

**How to measure it works.**
- Wrong-field entries and form completion time in a task test (MEA-03); expect fewer errors and less time with clearer grouping.
- Eye tracking or first fixation (eye-movement length between label and field, time to find a section), and a grouping test: ask users to mark which items belong together and compare with the intended groups.

**Implemented by.**
- GOV.UK Design System, fieldset component: groups related inputs such as an address, with a legend that names the group (undated page) [7].
- NN/g (2020) says 12 fields in one group look more daunting than the same fields in three groups; a claim without data [5]. No company outcome with numbers was found in the sources we could open.

**How to detect it.**
- *Applied:* the gap between a label and its field is clearly smaller than the gap to the next label; sections framed by cards, panels or dividers; related controls in a `fieldset`; items with the same role share one style; steppers and timelines joined by lines.
- *Violated:* equal spacing between label, field and next label; a label midway between two fields; unrelated items inside one box; a checkbox far from its text; one style on items with different roles.
- *In code:* `<fieldset>`/`<legend>`, `role="group"` with `aria-labelledby`; `label` margin smaller than the gap before the next `.field`; `gap`/`row-gap` tokens; `.card` with `border`, `box-shadow` or `background`; `<hr>`.
- *Quick test:* blur the screen (squint, or `filter: blur(4px)`) and check the intended groups still show. Then check that the gap between groups is clearly larger than the gap inside a group; about twice as large is a common practitioner starting point, not a research result.

**How to implement.**
1. List the groups from the task (for example billing and shipping) and name each one.
2. Set spacing tokens so gaps inside a group are smaller than gaps between groups, and each label sits nearest its own field (VIS-08). Re-check at narrow widths, where stacked layouts often lose group gaps.
3. Use common region (card, panel, fieldset) where groups need strong separation; use dividers sparingly.
4. Use one style per role (similarity), and different styles for different roles.
5. Add headings or legends, and group in markup with `fieldset`/`legend` or `role="group"`.

**Sources.**
[1] Wertheimer, M. (1923). Untersuchungen zur Lehre von der Gestalt II. Psychologische Forschung, 4, 301-350. https://doi.org/10.1007/BF00410640 . English translation (1938): Laws of organization in perceptual forms. https://psychclassics.yorku.ca/Wertheimer/Forms/forms.htm
[2] Palmer, S. E. (1992). Common region: A new principle of perceptual grouping. Cognitive Psychology, 24(3), 436-447. https://doi.org/10.1016/0010-0285(92)90014-S (summary text via Semantic Scholar; full abstract not opened)
[3] Palmer, S., & Rock, I. (1994). Rethinking perceptual organization: The role of uniform connectedness. Psychonomic Bulletin & Review, 1(1), 29-55. https://link.springer.com/article/10.3758/BF03200760
[4] Penzo, M. (2006). Label placement in forms. UXmatters, 12 July 2006. https://www.uxmatters.com/mt/archives/2006/07/label-placement-in-forms.php
[5] Harley, A. (2020). Proximity principle in visual design. Nielsen Norman Group, 2 August 2020. https://www.nngroup.com/articles/gestalt-proximity/
[6] W3C (2023). Understanding SC 1.3.1: Info and Relationships, WCAG 2.2. https://www.w3.org/WAI/WCAG22/Understanding/info-and-relationships.html
[7] GOV.UK Design System. Fieldset. https://design-system.service.gov.uk/components/fieldset/

---

### PER-06 Follow the conventions users know from other products

**What it is.** Jakob's law: users spend most of their time on other products, so they expect yours to work like those. Use the usual places for common elements and the usual behaviour for common controls. Break a convention only when you have evidence the new way is better.

**Why it works.**
- Nielsen (2000) stated the law as "Users spend most of their time on other sites". He cites Yahoo and Amazon as standardised sites that did more business; we found no measured result behind that claim on the page [1]. NN/g's 2017 video restates the law as: use the patterns users already know [2].
- Inconsistency with what users already know forces them to learn something new, which raises cognitive load [3].
- NN/g test (Whitenton, 2016): 50 users each used one of 14 fashion-retail sites (8 centred logo, 6 left logo). Users were about 6 times as likely to fail to reach the homepage in one click when the logo was centred (p < 0.05) [4].
- Bernard's studies (2001, 2003) found that people hold definable expectations for where web objects belong, including the cart, login, search and home link on e-commerce pages [5][6].

**Evidence: Moderate.** NN/g studies with a stated method plus two expectation studies from 2001 and 2003 (23 to 25 years old). A 2004 paper (Di Nocera et al.) says the 2001 study had serious methodological problems (snippet) [8]. We could not verify the commonly quoted "cart at top right" result: the 2003 abstract reports that expectations exist but gives no positions.

**Limitations.**
- A convention can be wrong or dated. The logo result is one study on fashion retail, and the same article found no significant brand-recall loss from centred logos (4 hotel sites, 128 participants) [4]. Copying competitors can also copy their mistakes or deceptive patterns (CHO).
- Platforms differ (iOS, Android, web); follow the target platform (PLT). The 2001 and 2003 studies predate mobile.
- Innovation needs room. Test a deviation before shipping it, and teach it (ONB).
- It can conflict with internal consistency (INT-03); choose deliberately which one wins for each pattern.

**How to measure it works.**
- First-click success and time on convention-dependent tasks (go home, open the cart, find search, sign in) using first-click or tree tests (MEA-10).
- A/B test any deviation against the conventional version and watch errors, time and abandonment (MEA-06); support questions and in-product searches of the form "where is X" (NAV).

**Implemented by.**
- NN/g recommends a left-aligned logo that links home plus an explicit Home link [4].
- GOV.UK design principles (updated 2 April 2025) tell teams to use the same language and patterns across services where possible so people become familiar with them, without forcing uniformity. This applies across government services, not the whole web [7].

**How to detect it.**
- *Applied:* logo at top left that links home; search as a magnifier icon or labelled field in the header; cart or bag and account at top right; links that look like links; native form controls; platform shortcuts left alone.
- *Violated:* a centred or right-hand logo that is not a link; unfamiliar icons for common actions; links styled as plain text; custom scrollbars or checkboxes with unfamiliar states; shortcuts that override the browser (Ctrl+F, Ctrl+S).
- *In code:* `header a[href="/"]` wrapping the logo; `<input type="search">` or `role="search"`; `aria-label="Cart"`; `<a>` versus `<div onclick>`; `::-webkit-scrollbar`; `keydown` handlers that call `preventDefault()` on common shortcuts.
- *Quick test:* ask five people unfamiliar with the product to find home, search, the cart and sign-in without hints. Compare placements with three leading products in the same category.

**How to implement.**
1. Pick a comparison set (3 to 5 leading products in the category) and list where each puts logo, search, cart, account and help.
2. Use the most common placement and standard icons for these objects. Make the logo a home link and add a text Home link.
3. Use native or platform-standard controls and keep platform shortcuts.
4. Deviate only for a measured gain: run first-click tests on the new pattern before shipping.
5. When you do change a convention, add onboarding and keep the familiar path visible for a transition period (ONB).

**Sources.**
[1] Nielsen, J. (2000). End of web design. Nielsen Norman Group, 22 July 2000. https://www.nngroup.com/articles/end-of-web-design/
[2] Nielsen, J. (2017). Jakob's law of internet user experience (video). Nielsen Norman Group, 18 August 2017. https://www.nngroup.com/videos/jakobs-law-internet-ux/
[3] Nielsen, J. (1994, reviewed 2024). 10 usability heuristics for user interface design (heuristic 4). Nielsen Norman Group. https://www.nngroup.com/articles/ten-usability-heuristics/
[4] Whitenton, K. (2016). Centered logos hurt website navigation. Nielsen Norman Group, 10 July 2016. https://www.nngroup.com/articles/centered-logos/
[5] Bernard, M. L. (2001). Developing schemas for the location of common web objects. Proceedings of the Human Factors and Ergonomics Society 45th Annual Meeting, 1161-1165. https://doi.org/10.1177/154193120104501502 (not opened; its finding is summarised in a 2006 blog post: https://disambiguity.com/?p=121 )
[6] Bernard, M. L. (2003). Examining user expectations for the location of common e-commerce web objects. Proceedings of the Human Factors and Ergonomics Society 47th Annual Meeting, 1356-1360. https://doi.org/10.1177/154193120304701108 (abstract via Crossref)
[7] GOV.UK. Government design principles (updated 2 April 2025). https://www.gov.uk/guidance/government-design-principles
[8] Di Nocera, F., et al. (2004). PsychNology Journal (volume 2, issue 1, per the file name; title not seen). https://www.psychnology.org/File/PSYCHNOLOGY_JOURNAL_2_1_DINOCERA.pdf (snippet; the PDF would not load)

---

### PER-07 Invest in visual polish, but do not read polish as proof of usability

**What it is.** People rate attractive interfaces as easier to use and forgive their minor flaws (the aesthetic-usability effect). Polish improves first impressions, trust and tolerance. It does not remove usability problems, and it can hide them in tests.

**Why it works.**
- Kurosu and Kashimura (1995, Hitachi Design Center) had people rate 26 ATM interface layouts; 252 participants, per NN/g. Apparent usability followed beauty more than inherent usability [1][2].
- Tractinsky (1997) ran three experiments to validate and replicate that result, with attention to cultural and methodological issues [3].
- Tractinsky, Katz and Ikar (2000) used an ATM simulation: perceived aesthetics and perceived usability correlated before and after use; the system's aesthetics changed post-use perceptions of usability, while actual usability did not [4].
- First impressions form fast: visual appeal ratings held at 50 ms exposure (Lindgaard et al., 2006) [5]. "Design look" appeared in 46.1% of credibility comments from 2,684 people (Fogg et al., 2003) [6].

**Evidence: Mixed.** The perception link has replicated since 1995. The effect on performance is inconsistent: Sonderegger and Sauer (2010; 60 adolescents, phone simulation) found the attractive version was rated more usable and also gave shorter task times [7], while Tractinsky et al. found actual usability did not shift post-use perceptions [4]. Hassenzahl (2004) found perceived usability moved with experience while beauty stayed stable [8].

**Limitations.**
- It can mask problems in testing. Participants may struggle, then praise the look; watch behaviour, not only ratings. Tolerance covers minor problems, not major ones, and a good-looking design can lead a team to skip testing [2].
- Most studies use ATM layouts, a phone simulation or web-page screenshots from 1995 to 2010. Modern apps are untested here.
- Beauty is partly cultural and follows fashion. Heavy decoration adds load (PER-03, VIS-09).

**How to measure it works.**
- Measure perceived and actual usability separately: SUS or a single ease question against success rate, time and errors (MEA-03, MEA-04). A gap where ratings exceed behaviour signals masking.
- A/B test visual-only changes against task completion and trust measures (MEA-06); five-second tests for first impressions; lagging: conversion, retention and credibility ratings.

**Implemented by.**
- Research settings only: Hitachi Design Center's ATM study (1995) [1]; the Stanford web-credibility survey (2003) [6]. No company report of a controlled, visual-only A/B outcome was found in the sources we could open.

**How to detect it.**
- *Applied:* a consistent spacing and type scale; an aligned grid; a limited palette; one icon set and one radius scale; sharp images.
- *Violated:* misalignment; mixed fonts and icon styles; low-resolution images; unstyled default controls; layouts that break at common widths.
- *In code:* design tokens (`--space-*`, `--font-size-*`, `--radius-*`, `--color-*`); many one-off literals (count distinct `font-size`, `border-radius` and hex colours); frequent `!important`; unstyled `<button>` and `<input>`.
- *Quick test:* count distinct font sizes, colours and radii. Show the screen for five seconds and ask what the product is for and whether they would trust it. Then run one task test and compare ratings with the success rate.

**How to implement.**
1. Define tokens for spacing, type, colour, radius and elevation, and use them everywhere (VIS-08).
2. Polish first-impression surfaces first: the first screen, sign-up, checkout and error pages.
3. Align to a grid and fix inconsistencies before adding decoration.
4. In usability tests, ask neutral questions and record task outcomes; compare ratings with behaviour (MEA-01).
5. Do not ship a redesign on looks alone; check task success and trust together.

**Sources.**
[1] Kurosu, M., & Kashimura, K. (1995). Apparent usability vs. inherent usability: Experimental analysis on the determinants of the apparent usability. CHI '95 Conference Companion, 292-293. https://doi.org/10.1145/223355.223680 (abstract via OpenAlex)
[2] Moran, K. (2024). The aesthetic-usability effect. Nielsen Norman Group, 3 February 2024. https://www.nngroup.com/articles/aesthetic-usability-effect/
[3] Tractinsky, N. (1997). Aesthetics and apparent usability: Empirically assessing cultural and methodological issues. CHI '97, 115-122. https://doi.org/10.1145/258549.258626 (summary text via Semantic Scholar; abstract not opened)
[4] Tractinsky, N., Katz, A. S., & Ikar, D. (2000). What is beautiful is usable. Interacting with Computers, 13(2), 127-145. https://academic.oup.com/iwc/article-lookup/doi/10.1016/S0953-5438(00)00031-X
[5] Lindgaard, G., Fernandes, G., Dudek, C., & Brown, J. (2006). Attention web designers: You have 50 milliseconds to make a good first impression! Behaviour & Information Technology, 25(2), 115-126. https://doi.org/10.1080/01449290500330448 (abstract via OpenAlex)
[6] Fogg, B. J., Soohoo, C., Danielson, D. R., Marable, L., Stanford, J., & Tauber, E. R. (2003). How do users evaluate the credibility of Web sites? A study with over 2,500 participants. DUX '03. https://doi.org/10.1145/997078.997097 (abstract via OpenAlex)
[7] Sonderegger, A., & Sauer, J. (2010). The influence of design aesthetics in usability testing: Effects on user performance and perceived usability. Applied Ergonomics, 41(3), 403-410. https://pubmed.ncbi.nlm.nih.gov/19892317/ (abstract via Europe PMC)
[8] Hassenzahl, M. (2004). The interplay of beauty, goodness, and usability in interactive products. Human-Computer Interaction, 19(4), 319-349. https://doi.org/10.1207/s15327051hci1904_2 (abstract via OpenAlex)

---

### PER-08 Put key items first or last, and make the one thing that matters distinct

**What it is.** In a list, people remember the first items (primacy) and the last items (recency) best. They also remember an item that differs from its surroundings (the isolation or von Restorff effect). Put key items at the ends of lists and give only one item a distinct treatment.

**Why it works.**
- Murdock (1962) found a U-shaped recall curve: a primacy effect over the first 3 to 4 words and a recency effect over the last 8 [1].
- Recency depends on recall coming right after the list. Glanzer and Cunitz (1966) are credited with showing that filling the delay with a distractor task removes it while primacy stays [2]; a secondary summary puts the cut-off for a distractor at roughly 15 to 30 seconds [6].
- Von Restorff (1933) showed an isolated item is remembered better [3]. Hunt and Lamb (2001) trace the isolation effect to how people process similarities and differences among items [4].
- For choices, Milosavljevic et al. (2012) found that visually salient products biased food choices more than preferences did at rapid decision speeds, more under cognitive load, and most when preferences were weak [5].

**Evidence: Moderate.** The memory effects are among the most replicated in psychology (1933 to 2001). Evidence that they drive UI outcomes is indirect: one lab study on salience and choice [5]. We found no controlled test of navigation position or of "recommended" plan badges.

**Limitations.**
- Recency fades with delay or interference, so list ends help recall right after a list, not later [2][6].
- The isolation effect needs one item unlike a uniform background. Highlight several items and none stands out; the effect depends on difference from context [4].
- Emphasis steers choice. When preferences are weak, salience can push users to an option that does not suit them [5]. Recommend honestly (CHO).
- Position in a visible list also reflects scanning and attention (VIS-02), and fixed first and last slots can clash with consistent navigation (NAV).

**How to measure it works.**
- Choice share of the emphasised option in an A/B test (MEA-06), with downstream satisfaction, refunds or plan changes as a guard against regret.
- Click distribution by list position (MEA-07); a recall test after a task (which menu labels can users name?); a five-second test (what stood out?).

**Implemented by.**
- Slack, pricing page (observed 31 October 2026, page text only): a "Best value" label on the Business+ plan. Styling was not captured and no outcome is published [7]. No other company example with a published outcome was found in the sources we could open.

**How to detect it.**
- *Applied:* exactly one pricing card carries a "Recommended" or "Most popular" badge and a distinct colour; the most important navigation items sit first and last; one filled primary button per view.
- *Violated:* two or more badges, or every card highlighted; the key action buried mid-list; the primary button styled like the rest.
- *In code:* `.recommended`, `.popular`, `.featured`, `.badge`, `.ribbon`, `aria-current`; count emphasis classes among siblings in one container (more than one is a violation); count `btn-primary` per view; position of the call to action in `<nav>` `<li>` order.
- *Quick test:* squint at the screen and ask which one item stands out. If none or several do, fix it. After a short task, ask users to name what they remember from the menu.

**How to implement.**
1. Decide the single item to emphasise, and the evidence for it (most chosen, best fit for most users).
2. Use one strong cue (colour fill, badge or size), not three. Keep every other item in a uniform style.
3. Place the most important items first and last in navigation, toolbars and lists; keep rarely used or risky items in the middle or behind a menu.
4. A/B test choice share with a satisfaction guard (MEA-06).
5. Keep labels honest and verifiable (CHO).

**Sources.**
[1] Murdock, B. B. (1962). The serial position effect of free recall. Journal of Experimental Psychology, 64(5), 482-488. https://doi.org/10.1037/h0045106 (abstract via OpenAlex)
[2] Glanzer, M., & Cunitz, A. R. (1966). Two storage mechanisms in free recall. Journal of Verbal Learning and Verbal Behavior, 5(4), 351-360. https://doi.org/10.1016/S0022-5371(66)80044-0 (not opened)
[3] von Restorff, H. (1933). Über die Wirkung von Bereichsbildungen im Spurenfeld. Psychologische Forschung, 18, 299-342. https://doi.org/10.1007/BF02409636 (not opened)
[4] Hunt, R. R., & Lamb, C. A. (2001). What causes the isolation effect? Journal of Experimental Psychology: Learning, Memory, and Cognition, 27(6), 1359-1366. https://doi.org/10.1037/0278-7393.27.6.1359 (abstract via OpenAlex)
[5] Milosavljevic, M., Navalpakkam, V., Koch, C., & Rangel, A. (2012). Relative visual saliency differences induce sizable bias in consumer choice. Journal of Consumer Psychology, 22(1), 67-74. https://doi.org/10.1016/j.jcps.2011.10.002 (abstract via OpenAlex)
[6] Serial-position effect. Wikipedia (secondary; cites Bjork & Whitten, 1974, for the distractor cut-off). https://en.wikipedia.org/wiki/Serial-position_effect
[7] Slack. Pricing. https://slack.com/pricing (observed 31 October 2026)

---

### PER-09 Design the worst moment and the ending of a flow

**What it is.** People judge an experience mostly by its most intense moment and its end, and give little weight to how long it lasted (the peak-end rule). For a product flow: fix the worst moment, end clearly and positively, and place a proportionate high point where users have achieved something.

**Why it works.**
- Kahneman et al. (1993): people held a hand in 14 °C water for 60 seconds, and in a second trial for 60 seconds plus 30 more seconds in slightly warmer water. A significant majority chose to repeat the longer trial [1].
- Redelmeier and Kahneman (1996): for colonoscopy (n = 154) and lithotripsy (n = 133), retrospective pain tracked the peak and the last 3 minutes, not the duration [2].
- Redelmeier, Katz and Kahneman (2003): in a randomised trial of 682 colonoscopy patients, a short extra interval at the end lowered the rating of the final moments (1.7 against 2.5) and the whole experience (4.4 against 4.9), and raised return for a repeat colonoscopy (odds ratio 1.41, P = 0.038) [3].
- A 2022 meta-analysis of 174 effect sizes found a large peak-end effect (r = 0.581) and essentially no duration effect [4].

**Evidence: Moderate.** Strong for pain and affect episodes (1993 to 2022, including a meta-analysis). But the average of all moments predicted about as well as peak-end [4], and applying the rule to software is an extrapolation: we found no controlled software trial.

**Limitations.**
- The evidence covers physical and affective episodes. Treat product examples as design intent, not proof.
- The simple average predicts about as well as peak-end [4], so the middle of a flow still matters. Duration neglect does not excuse slow flows; people still dislike waiting during a task (FBK).
- A pleasant ending cannot rescue repeated failure. Repeated or blocking celebration animations can irritate and add motion problems (A11Y).
- Using the rule to hide costs or steer retention drifts into manipulation (CHO).

**How to measure it works.**
- Compare a post-task rating (CSAT, single ease question) with moment-by-moment ratings in a test (MEA-03, MEA-04); check whether the rating follows the worst moment and the ending.
- A/B test end-screen variants on return or repeat use, as the colonoscopy trial used return as its outcome [3] (MEA-06); drop-offs and errors at the final step (MEA-07); lagging: retention.

**Implemented by.**
- Asana, celebrations (blog post of 21 March 2016): an occasional animated creature appears when tasks are completed; off by default; no outcome published [5].
- Mailchimp, "high five" after sending a campaign: widely cited, but we could not open a primary Mailchimp source. Aarron Walter, who founded Mailchimp's UX practice, wrote Designing for Emotion (2011; second edition 2020) [6]. Treat as an anecdote.

**How to detect it.**
- *Applied:* a clear confirmation state at the end of key flows, with what happens next; the hardest moments (errors, waiting, payment) handled with reassurance and recovery; a modest high point at real achievements.
- *Violated:* flows that end on an error, dead end, upsell wall or surprise fee; submit then redirect with no confirmation; cancel flows that end in guilt messaging.
- *In code:* routes such as `/success`, `/thank-you`, `/done`; `role="status"` or `aria-live` confirmation text; `canvas-confetti`, `lottie`; `@media (prefers-reduced-motion: reduce)`; `window.location = '/'` straight after submit (violated).
- *Quick test:* walk the flow twice, marking the worst moment and the last screen. Ask three users right afterwards what they remember most.

**How to implement.**
1. Map the journey with an effort and emotion curve. Mark the single worst moment and the final screen.
2. Fix or soften the worst moment first: clearer errors, saved progress, reassurance (ERR, FBK).
3. End with a confirmation that states the result and the next step.
4. Add a high point only for real achievements (first publish, first send), not routine actions. Make it skippable and respect `prefers-reduced-motion`.
5. Check post-task against in-task ratings, and guard against manipulation (CHO).

**Sources.**
[1] Kahneman, D., Fredrickson, B. L., Schreiber, C. A., & Redelmeier, D. A. (1993). When more pain is preferred to less: Adding a better end. Psychological Science, 4(6), 401-405. https://doi.org/10.1111/j.1467-9280.1993.tb00589.x (abstract via Crossref)
[2] Redelmeier, D. A., & Kahneman, D. (1996). Patients' memories of painful medical treatments: Real-time and retrospective evaluations of two minimally invasive procedures. Pain, 66(1), 3-8. https://doi.org/10.1016/0304-3959(96)02994-6 (abstract via OpenAlex)
[3] Redelmeier, D. A., Katz, J., & Kahneman, D. (2003). Memories of colonoscopy: A randomized trial. Pain, 104(1-2), 187-194. https://pubmed.ncbi.nlm.nih.gov/12855328/
[4] Alaybek, B., Dalal, R. S., Fyffe, S., Aitken, J. A., Zhou, Y., Qu, X., Roman, A., & Baines, J. I. (2022). All's well that ends (and peaks) well? A meta-analysis of the peak-end rule and duration neglect. Organizational Behavior and Human Decision Processes, 170, 104149. https://ideas.repec.org/a/eee/jobhdp/v170y2022ics0749597822000334.html
[5] Asana Design Team (2016). Celebrations revamped: Meet the unicorn's new team. Asana blog, 21 March 2016. https://asana.com/inside-asana/new-celebrations
[6] Walter, A. (2020). Designing for Emotion, second edition. A Book Apart (first edition 2011). https://abookapart.com/products/designing-for-emotion (page confirms the author's Mailchimp role; does not mention the high five)

---

### PER-10 Show progress toward a goal and credit genuine head starts

**What it is.** People work faster as a goal gets closer (the goal-gradient effect) and finish more often when they start with credited progress (endowed progress). In interfaces: progress meters, checklists with an item already done, and loyalty cards with a head start.

**Why it works.**
- Kivetz, Urminsky and Zheng (2006) found that café customers bought coffee more often the closer they were to a free one, and that customers with a 12-stamp card holding 2 bonus stamps finished the 10 required purchases faster than customers with a plain 10-stamp card [1].
- A summary of that paper reports purchase gaps about 20% shorter by the last stamp, and 12.7 days to finish a bonus-stamp card against 15.6 days for a plain card [2].
- Nunes and Drèze (2006) gave 300 car-wash customers either an 8-stamp card or a 10-stamp card with 2 stamps already filled. The abstract says completion became more likely and faster, and the effect depended on perceived progress, the reason given for the head start and the currency of progress [3]. A secondary report gives completion rates of 34% against 19% (nine-month follow-up) [4].

**Evidence: Mixed.** Two top-journal field experiments (2006), but we found no direct replication of the car-wash study, and the exact rates come from a secondary report. A meta-analysis of 32 randomised experiments found constant progress bars did not reduce drop-off in web surveys [5], and a 2011 study found motivation can dip midway [6]. No published outcome was found for LinkedIn's meter.

**Limitations.**
- Progress bars are not a general fix. In 32 survey experiments a constant bar did not help, fast-to-slow bars reduced drop-off, slow-to-fast bars increased it, and with a small incentive a constant bar raised drop-off [5].
- Acceleration needs a reward and visible progress: cards that tracked purchases without a reward did not speed up, and purchases slowed right after the first reward before rising again [2].
- Motivation can be U-shaped, lowest near the middle [6]. Plan quick early wins and a visible midpoint.
- Credit that is not real is a deceptive pattern (CHO). Credit only genuine prior work and say why. For "unfinished task" explanations of meters, see MYTH (Zeigarnik effect).

**How to measure it works.**
- Completion rate and time to complete in an A/B test with and without a head start or progress indicator (MEA-06); step-level drop-off (MEA-07).
- Time between actions near thresholds (is there acceleration?), retention after the goal is reached (is there a post-reward slump?), and trust or complaint signals if progress is credited artificially.

**Implemented by.**
- LinkedIn, profile level meter: Beginner, Intermediate and All-star levels, seven recommended sections, visible only to the member, and hidden once All-star is reached (help page, undated). LinkedIn gives no outcome data; web claims of a specific lift had no source [7].
- Academic field settings: café reward cards [1] and car-wash cards [3].

**How to detect it.**
- *Applied:* steppers ("Step 2 of 5"); progress bars with honest values; checklists that show completed items; completeness meters that name the next action; prior work credited ("Account created").
- *Violated:* long multi-step flows with no position cue; meters that start at zero when work is done; bars that move backward or add steps late; fake bars driven by timers; progress that is slow early and fast late.
- *In code:* `<progress value max>`; `role="progressbar"` with `aria-valuenow` and `aria-valuemax`; "Step {n} of {m}"; `stepper`, `checklist`, `completeness`; a `setInterval` that raises a bar with no real events (violated).
- *Quick test:* start the longest flow. Can you see where you are and how much remains? Is the head start real and explained? Do the numbers match what you actually complete?

**How to implement.**
1. Break the goal into real milestones; show the position and the next action.
2. Credit genuine prior progress (account created, data imported) and say why it counts.
3. Make early steps quick and visible (fast-to-slow, per the survey meta-analysis [5]).
4. Keep the meter honest: no inflated values, no moving backward.
5. A/B test against drop-off and satisfaction; shorten the flow before adding a meter (FBK for progress indicators, ONB for checklists).

**Sources.**
[1] Kivetz, R., Urminsky, O., & Zheng, Y. (2006). The goal-gradient hypothesis resurrected: Purchase acceleration, illusionary goal progress, and customer retention. Journal of Marketing Research, 43(1), 39-58. https://doi.org/10.1509/jmkr.43.1.39 (abstract via Crossref)
[2] Chicago Booth Review. Summary of Kivetz, Urminsky & Zheng (2006) (author and date not shown on the fetched page). https://www.chicagobooth.edu/review/going-goal
[3] Nunes, J. C., & Drèze, X. (2006). The endowed progress effect: How artificial advancement increases effort. Journal of Consumer Research, 32(4), 504-512. https://doi.org/10.1086/500480 (abstract only; sample size from Wharton: https://knowledge.wharton.upenn.edu/?p=5630 )
[4] Silicon Canals. Car wash loyalty cards and the endowed progress effect (secondary report of 34% against 19%; undated). https://siliconcanals.com/t-car-wash-loyalty-cards-endowed-progress/
[5] Villar, A., Callegaro, M., & Yang, Y. (2013). Where am I? A meta-analysis of experiments on the effects of progress indicators for web surveys. Social Science Computer Review, 31(6), 744-762. https://doi.org/10.1177/0894439313497468 (abstract via OpenAlex)
[6] Bonezzi, A., Brendl, C. M., & De Angelis, M. (2011). Stuck in the middle: The psychophysics of goal pursuit. Psychological Science, 22(5), 607-612. https://pubmed.ncbi.nlm.nih.gov/21474842/ (snippet)
[7] LinkedIn Help. Use the profile level meter to update your profile. https://www.linkedin.com/help/learning/answer/391

---

### PER-11 Use the user's model and words, not the system's

**What it is.** Users form beliefs about how a product works. The interface should present the concepts, terms and states of those beliefs, not database tables, IDs, internal states or architecture.

**Why it works.**
- Norman (2013) separates the designer's conceptual model, the user's mental model and the system image, the only channel through which the first reaches the second. A mismatch produces errors [1].
- NN/g (Chan, 2024, updating Nielsen's 2010 article) defines a mental model as what users believe about a system, notes that designers hold richer models than users, and recommends card sorting and think-aloud testing to find them [2].
- Kempton (1986) interviewed people about home thermostats and found two folk theories, "feedback" and "valve". The valve theory contradicts engineering, was estimated to be held by 25 to 50% of Americans, and may work well in daily use [3].
- Nielsen's heuristic 2: use words, phrases and concepts users already know, not internal jargon [4].

**Evidence: Moderate.** A long-taught conceptual framework (Norman) plus qualitative studies (Kempton 1986; NN/g cases). We found no controlled trial that isolates "implementation wording" against "user wording".

**Limitations.**
- Mental models vary by user and change with experience [2]. Research your audience; do not assume.
- For technical audiences (developer and admin tools) the system's own terms may be the right ones. Keep real states available behind progressive disclosure (PER-02).
- A "wrong" model can work well in daily use (the valve theory) [3]. Do not correct beliefs that do not hurt the task.
- Hiding the implementation fails when something breaks. Error states need a route to detail (ERR).

**How to measure it works.**
- Think-aloud tests (MEA-01): count misreadings of labels and states; ask "what do you think this does?". Terminology checks with card sorts, tree tests and first-click tests (MEA-10).
- Support tickets and search queries that use user wording unlike the UI wording (leading); error rate and churn (lagging).

**Implemented by.**
- GOV.UK design principles (updated 2 April 2025) start from user needs and tell teams to do the hard work to make services simple. No mental-model outcome data published [5].
- NN/g cases of mismatch: Nomad Lane added shipping insurance to carts by default, against the expectation that shoppers control cart contents; a university library page had two search boxes and users assumed each searched everything [2]. No outcome numbers.

**How to detect it.**
- *Applied:* labels in task words; states described as outcomes ("Payment pending"); objects behave like their real-world counterparts; technical detail behind a "Details" control; errors say what the user can do.
- *Violated:* raw IDs and UUIDs; database column or property names as labels (`user_id`, `created_at`); enum constants on screen (`STATUS_PENDING_REVIEW`); HTTP codes or stack traces in messages; words like payload, schema, instance, entity, provision; visible i18n keys (`errors.generic`).
- *In code:* grep user-facing strings for `\b(uuid|guid|null|undefined|NaN|exception|stack ?trace|payload|schema|entity|ECONN\w+)\b`; labels built from variable names; `alert(err.message)` or `toast(String(err))`; enum values rendered without a lookup table.
- *Quick test:* read every label, state and error message aloud to someone outside the team. Note each term they cannot explain in their own words.

**How to implement.**
1. Collect the audience's vocabulary from interviews, support tickets, search logs and card sorts (MEA-10).
2. Keep a glossary that maps each system term to the user's term, and use the user's term in the UI (CON for terminology and voice).
3. Rewrite states and errors around outcomes and next steps. Move IDs and technical state behind a "Details" disclosure.
4. Make the system image carry the model: structure, names and feedback that agree with each other.
5. Test with think-aloud sessions and revise terms that cause misreadings (MEA-01).

**Sources.**
[1] Norman, D. A. (2013). The Design of Everyday Things, revised and expanded edition. Basic Books. https://www.hachettebookgroup.com/titles/don-norman/the-design-of-everyday-things/9780465050659/ (book; the publisher page confirms edition and date only; the three-model framing is from the book, not opened)
[2] Chan, M. (2024). Mental models (updated from Nielsen's 2010 article). Nielsen Norman Group, 26 January 2024. https://www.nngroup.com/articles/mental-models/
[3] Kempton, W. (1986). Two theories of home heat control. Cognitive Science, 10(1), 75-90. https://doi.org/10.1207/s15516709cog1001_3 (abstract via OpenAlex)
[4] Nielsen, J. (1994, reviewed 2024). 10 usability heuristics for user interface design (heuristic 2). Nielsen Norman Group. https://www.nngroup.com/articles/ten-usability-heuristics/
[5] GOV.UK. Government design principles (updated 2 April 2025). https://www.gov.uk/guidance/government-design-principles
