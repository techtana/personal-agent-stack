# Content and microcopy (CON)

This category covers the words in an interface: how much text there is, how plain it is, what buttons and links say, how headings start, how consistent terms and voice are, and where help appears. Load it when auditing UI copy, labels, dialogs, links, headings or help text. Empty states belong to ONB; error messages belong to ERR and FRM; accessible names for links and controls are also covered in A11Y-04.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| CON-01 | Write concise, scannable, objective text | Moderate | any page, help text, onboarding, UI copy |
| CON-02 | Use plain language and the user's words, not internal or technical terms | Strong | all user-facing text |
| CON-03 | Label buttons with specific verbs; avoid Yes/No/OK in dialogs | Moderate | dialogs, alerts, confirmations, buttons |
| CON-04 | Front-load headings, links and labels | Moderate | headings, navigation, links, lists |
| CON-05 | Write link and button text that makes sense on its own | Strong | links, buttons, icon controls |
| CON-06 | Keep terminology, capitalization, voice and tone consistent | Moderate | products with many screens or writers |
| CON-07 | Offer contextual help where the question arises | Moderate | forms, settings, complex features |

---

### CON-01 Write concise, scannable, objective text

**What it is.** Cut words, structure the text for scanning, and replace hype with facts. Web readers skim, so every sentence has to earn its place.

**Why it works.**
- Morkes and Nielsen (1997; 51 users in the measurement study; five versions of a seven-page travel site): against a promotional control, the concise version (about half the words) scored 58% higher on an overall usability score, scannable 47%, objective 27%, and all three together 124%. The score is the geometric mean of task time, errors, memory, sitemap time and satisfaction [1].
- Weinreich et al. (2008; 25 users, 45,237 page views analyzed, data from 2005): on an average 593-word page visitors can read at most 28% of the words, realistically about 20%. Each extra 100 words adds about 4.4 seconds, enough for roughly 18 words [2].
- Working rules: GOV.UK splits sentences over about 25 words and keeps paragraphs to five sentences [3]; Material asks for short, scannable segments [4].

**Evidence: Moderate.** One controlled experiment (1997, 29 years old, one site) plus a naturalistic study (2008). Several advantages of the objective version were not statistically significant [1].

**Limitations.**
- One small site in 1997. The authors tested each trait as present or absent, not the best amount [1].
- Shorter is not always better: legal, medical, safety and expert tasks need complete information, and long-form still reaches dedicated readers [2].
- The experiment measured information tasks, not sales conversion; we found no study showing hype-free copy converts better.
- Cutting words can remove needed detail; pair with CON-07 (help on demand) and VIS-02 (structure).

**How to measure it works.**
- Success and time on fact-finding tasks; comprehension quiz; recall after reading (the 1997 measures).
- Scroll depth and read-through; word-count budgets met; "Was this page useful?" ratings; support contacts per page.
- A/B test original versus edited copy on task completion.

**Implemented by.**
- Morkes and Nielsen's related rewrite of real Sun Microsystems pages: 159% improvement, as reported by NN/g [1].
- GOV.UK: short words, 25-word sentence limit, five-sentence paragraphs [3].
- Shopify: plain language at about US grade 7, short sentences, bullets, no repeated page titles [5].

**How to detect it.**
- *Applied:* short sentences, one idea per paragraph, concrete facts and numbers, headings and bullets, no hype adjectives.
- *Violated:* promotional adjectives ("world-class", "revolutionary"), exclamation marks, welcome paragraphs, paragraphs over 100 words, repeated page titles, dialogs or tooltips with paragraphs.
- *In code:* UI strings (i18n JSON, `strings.xml`, `.strings`, JSX text) over 150 characters; `\b(amazing|awesome|world-class|best-in-class|revolutionary|cutting-edge|next-generation|unparalleled)\b`; `!{1,}` in labels and headings; filler such as `in order to|please note|utilize`; Flesch-Kincaid grade above 10 on body copy.
- *Quick test:* cut the key paragraph to half its words without losing a fact; cover the hero text and see if the page still works.

**How to implement.**
1. Write the point in one sentence and start with it (CON-04).
2. Cut intros, filler and repeated titles; aim for fewer than half the words of print copy [6].
3. Swap claims for facts: price, time, number, name.
4. Add structure: headings, bullets, short paragraphs (VIS-02).
5. Set a word budget per component (title, hint, dialog message) in the style guide (CON-06).
6. Test the edit with a fact-finding task before shipping.

**Sources.**
[1] Morkes, J., & Nielsen, J. (1997). Concise, scannable, and objective: how to write for the web. Nielsen Norman Group. https://www.nngroup.com/articles/concise-scannable-and-objective-how-to-write-for-the-web/
[2] Nielsen, J. (2008). How little do users read? (reports Weinreich et al., 2008, ACM Transactions on the Web). Nielsen Norman Group. https://www.nngroup.com/articles/how-little-do-users-read/
[3] GOV.UK (read 2026-10-31). Use clear language. https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/clear-language/
[4] Google (read 2026-10-31). Writing. Material Design 1 (no longer maintained). https://m1.material.io/style/writing.html
[5] Shopify (read 2026-10-31). Content. App design guidelines. https://shopify.dev/docs/apps/design/content
[6] Loranger, H. (2017). Plain language is for everyone, even experts. Nielsen Norman Group. https://www.nngroup.com/articles/plain-language-experts/

---

### CON-02 Use plain language and the user's words, not internal or technical terms

**What it is.** Use words the audience already uses. Prefer short, common words and active voice, explain terms you cannot avoid, and keep internal names, error codes and system jargon out of the interface.

**Why it works.**
- GOV.UK cites a study of legal-document sentences: 80% preferred the clear-English version, the preference grew with the complexity of the issue, and more educated or specialist readers preferred plain English more strongly. The study is an SSRN paper that we could not open (HTTP 403) [1].
- NN/g (Loranger, 2017; domain experts in science, technology and medicine; sample size not stated): highly educated readers wanted concise, scannable, plain text. Suggested targets: 15-20 words per sentence, grades 6-8 for the general public, grades 10-12 for experts [2].
- Heuristic 2: speak the audience's language, not insider jargon, and use research to learn their terms [3].
- Literacy: about 1 in 6 adults in England have very poor literacy; GOV.UK makes plain English mandatory [1].
- Rules: the US Plain Writing Act (signed 13 October 2010, Pub. L. 111-274) requires plain writing in covered federal documents [4]. ISO 24495-1:2023 sets international plain-language principles [5]. WCAG 3.1.5 (AAA) asks for a simpler version or supplement when text needs more than lower secondary reading ability [6].

**Evidence: Strong.** Law, a standard and consistent preference research. The experiments we verified are thin (one preference study via GOV.UK, NN/g's qualitative work); we did not open peer-reviewed comprehension studies. Required: US Plain Writing Act of 2010 (federal agencies' covered documents). Standards: WCAG 2.2 SC 3.1.5 (AAA); ISO 24495-1:2023.

**Limitations.**
- Shared expert jargon is fine if you confirm the audience knows it; otherwise define it on first use [2].
- Plain is not the same as short: jargon-heavy text is too long at any length [1].
- Readability formulas are crude; WCAG describes no formula and leaves the judgment to qualified educators [6].
- Users' words vary by segment and locale; use search logs and interviews, not guesses (NAV).
- Over-simplified legal or safety text can lose precision; add a plain summary instead.

**How to measure it works.**
- Reading grade of UI strings and help (about grades 7-9 for the public; Shopify uses about grade 7 [7]).
- Comprehension: paraphrase test ("say it in your own words"), cloze test, first-click success on labels.
- Match rate between labels and top site-search queries; support tickets that ask what a term means.

**Implemented by.**
- GOV.UK: plain English mandatory; short word swaps such as "buy" for "purchase" [1].
- Shopify: about US grade 7, no idioms or jargon [7].
- US federal agencies: annual plain-writing compliance reports under the Act [4].

**How to detect it.**
- *Applied:* labels match user research or search terms; abbreviations expanded on first use; short active sentences; necessary terms explained inline.
- *Violated:* internal product or team names as labels; database terms ("payload", "entity", "null", "instance"); bare error codes; "Authenticate", "Terminate", "Utilize" where "Sign in", "Stop", "Use" fit; undefined acronyms.
- *In code:* UI strings (i18n files, JSX text, `strings.xml`) matching `\b(null|undefined|exception|payload|invalid argument|stack trace|ERR_[A-Z_]+|0x[0-9A-Fa-f]+)\b`; raw keys such as `user_id` shown in the UI; `\b(utilize|terminate|authenticate|initiate|facilitate)\b`; a readability tool (for example textstat) run over the strings.
- *Quick test:* read every label aloud to someone outside the team; list the five most-searched site terms and check whether labels use them; run a grade-level check.

**How to implement.**
1. Collect users' vocabulary: interviews, support tickets, site-search logs, card sorts (NAV).
2. Keep a glossary: user term, internal term, definition.
3. Write 15-20 word sentences in active voice with common words; define unavoidable terms where they appear (CON-07).
4. Replace system messages and codes with plain statements, and keep the code as secondary detail (ERR).
5. Test with the audience; for experts, confirm the shared jargon before keeping it.
6. Set a reading-grade budget for the audience and check it in review.

**Sources.**
[1] GOV.UK (read 2026-10-31). Use clear language (links the SSRN study, abstract_id 1843415, not opened). https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/clear-language/
[2] Loranger, H. (2017). Plain language is for everyone, even experts. Nielsen Norman Group. https://www.nngroup.com/articles/plain-language-experts/
[3] Nielsen, J. (1994, wording updated 2020). 10 usability heuristics for user interface design. Nielsen Norman Group. https://www.nngroup.com/articles/ten-usability-heuristics/
[4] US Congress (2010). Plain Writing Act of 2010, Pub. L. 111-274. https://www.govinfo.gov/content/pkg/PLAW-111publ274/html/PLAW-111publ274.htm
[5] ISO 24495-1:2023, Plain language, Part 1: governing principles and guidelines (existence and year read via Wikipedia; ISO page returned 403). https://en.wikipedia.org/wiki/Plain_language
[6] W3C (2023). Understanding SC 3.1.5 Reading Level (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/reading-level.html
[7] Shopify (read 2026-10-31). Content. App design guidelines. https://shopify.dev/docs/apps/design/content

---

### CON-03 Label buttons with specific verbs; avoid Yes/No/OK in dialogs

**What it is.** Name the outcome on each action button ("Delete file", "Save changes", "Keep editing") instead of "Yes", "No", "OK" or "Submit". The label should make sense even if the user skips the message.

**Why it works.**
- Apple: alert buttons should be one or two words, ideally verbs tied to the alert text (View All, Reply, Ignore; Erase, Convert, Delete). "OK" suits only purely informational alerts; avoid "Yes" and "No" [1]. Buttons in general start with a verb [2].
- Microsoft (WinUI dialogs): use specific responses to the dialog's main instruction as button text, such as Allow and Block for a location request; specific responses are understood faster and speed decisions [3].
- Material 1: use verbs that name the outcome, such as Discard or Delete, not a bare Yes or No; full-screen dialogs confirm with save, send, share, update or create rather than Done, OK or Close [4].
- GOV.UK: start button labels with a verb in sentence case ("Save and continue") and add words where clarity needs them [5].
- Mechanism (inference, no study found): dialogs interrupt, people often glance only at the buttons, so the buttons must carry the meaning.

**Evidence: Moderate.** Consensus across Apple, Microsoft, Material and GOV.UK guidance. We found no controlled experiment on label specificity.

**Limitations.**
- Specific is not always better for conversion. In the Obama campaign's December 2007 splash-page test (310,382 visitors; 4 button labels x 6 media), the winning button was the generic "Learn More"; the best button-and-image pair lifted sign-ups from 8.26% to 11.6% (+40.6%) [6]. The write-up does not isolate the button effect or list all four labels, so read it as a caution: commitment level matters as well as clarity.
- "OK" is acceptable for pure acknowledgments (Apple, Material) [1][4].
- Long labels hurt scanning; keep to 1-3 words [3].
- Capitalization differs by platform: Apple title-style, Microsoft and GOV.UK sentence case [1][5]; see VIS-03 and CON-06.
- The best dialog is often none: Apple says not to alert for common, undoable destructive actions [1]. Use undo, and confirm only rare, irreversible actions (ERR).

**How to measure it works.**
- Wrong-choice signals: undo or reversal right after a dialog; accidental destructive confirmations; dialog decision time.
- Comprehension test: "What happens if you press this?" with the message covered.
- A/B test labels on completion of the whole task, not on button clicks alone.

**Implemented by.**
- Apple HIG alerts: Cancel is always labeled "Cancel" and never the default; destructive alerts always include it [1].
- Microsoft WinUI: "Delete file permanently?" with Delete and Cancel; "Allow AppName to access your location?" with Allow and Block [3].
- Material 1: no third "Learn more" action in dialogs [4]. Counter-example: Obama 2007, where "Learn More" won [6]. No published error-rate outcome found.

**How to detect it.**
- *Applied:* title phrased as the decision; buttons are verbs that match it (Delete / Keep); safe action labeled Cancel or Close; destructive style only where the user did not choose the action on purpose [1].
- *Violated:* Yes/No answering a question not phrased as yes/no; "OK" confirming a destructive action; "Submit", "Confirm" or "Done" with no object; a "Cancel" that is ambiguous in a dialog about canceling.
- *In code:* `>\s*(OK|Ok|Yes|No|Submit|Confirm|Done)\s*<`; `window.confirm(` and `alert(` (they show generic OK/Cancel); `setPositiveButton("OK"`, `android.R.string.ok`, `android.R.string.yes`; `UIAlertAction(title: "OK"`; WinForms or WPF `MessageBoxButtons.YesNo`, `MessageBoxButton.OKCancel`; Flutter `TextButton(child: Text('OK')`.
- *Quick test:* hide the dialog message; can you tell what each button does? Grep for the patterns and trigger every confirmation once.

**How to implement.**
1. Write the title as the decision or question.
2. Label each button with a verb (plus object if needed) that answers it: "Delete", "Keep", "Save changes".
3. Keep labels to 1-3 words.
4. Always offer a safe, non-destructive exit (Cancel, Close) [3]; never make Cancel the default [1].
5. Use "OK" or "Got it" only for informational alerts.
6. Confirm only when needed and offer undo for the rest (ERR).

**Sources.**
[1] Apple (read 2026-10-31). Alerts. Human Interface Guidelines. https://developer.apple.com/design/human-interface-guidelines/alerts
[2] Apple (read 2026-10-31). Buttons. Human Interface Guidelines. https://developer.apple.com/design/human-interface-guidelines/buttons
[3] Microsoft (2026). Dialog controls. Windows apps, Microsoft Learn. https://learn.microsoft.com/en-us/windows/apps/design/controls/dialogs-and-flyouts/dialogs
[4] Google (read 2026-10-31). Dialogs. Material Design 1 (no longer maintained). https://m1.material.io/components/dialogs.html
[5] GOV.UK Design System (read 2026-10-31). Button. https://design-system.service.gov.uk/components/button/
[6] Siroker, D. (2010). How Obama raised $60 million by running a simple experiment. Optimizely. https://www.optimizely.com/insights/blog/how-obama-raised-60-million-by-running-a-simple-experiment/

---

### CON-04 Front-load headings, links and labels

**What it is.** Start headings, links, labels, list items and paragraphs with the words that carry the meaning. Lead with the conclusion (inverted pyramid) so a reader who stops early still gets the point.

**Why it works.**
- Nielsen (2009): users often take in only about the first two words of a list item. His study had 80 participants and 20 links from 20 sites; people predicted a link's destination from its truncated text, and picked the right link from a list of 10 [1].
- Results: Ann Taylor's "Gift Cards" was predicted by 85% and chosen by 100%; Chase's "Introducing" was chosen by 15%; 35% of the links left users with no idea where they led [1].
- The 2006 eyetracking study found the same left-edge scanning: people rarely read past the first two words of a line [2].
- NN/g (Schade, 2018) argues the inverted pyramid aids comprehension and cuts interaction cost, but cites no study or numbers [3].

**Evidence: Moderate.** One NN/g study with a stated method (2009, 17 years old) plus the 2006 eyetracking (232 users). The sample skewed young and college-educated, which NN/g says likely understates the problem [1].

**Limitations.**
- The two-word effect concerns scanning lists, menus and headings; running prose needs flow.
- Front-loading can clash with natural grammar or brand voice, and word order differs across languages (my inference; check with localization).
- UI truncation (ellipsis in tabs, menus, mobile titles) shows only the first words.
- Do not stuff keywords; labels must stay natural (CON-02).
- Related: VIS-02 (scanning), CON-05 (link text), NAV (information scent).

**How to measure it works.**
- NN/g's method: show the truncated link and ask where it leads (prediction); show 10 links and a scenario and ask which to pick (selection). Expect higher pass rates after rewriting.
- First-click tests and time-to-find on menus; heading-only comprehension ("read only the headings; what is this page about?").
- Click-through on rewritten navigation items (lagging).

**Implemented by.**
- Strong in NN/g's test: Ann Taylor "Gift Cards" and Barclays' "New customers" (95% chose it, 75% predicted its destination). Weak: Chase "Introducing", Directgov "Working whi" (25% chose it) and Xerox "Profit Acce" (5%) [1].
- No before/after rewrite outcome published.

**How to detect it.**
- *Applied:* headings open with the topic or action ("Delete your account", "Shipping costs"); navigation labels begin with the noun; list items start with distinct words; link text starts with the destination.
- *Violated:* headings that open with "Introducing", "Welcome to" or "How to"; sibling items sharing first words ("Our products", "Our services"); links that begin "Click here to" or "Learn more about"; filler lead-ins.
- *In code:* headings matching `<h[1-6][^>]*>\s*(Introducing|Welcome|About|How to|Learn more|Click)`; link text matching `>\s*(Learn more about|Click here to|Read our|Find out)`; sibling `<li>` or `<a>` elements in a `nav` that share the same first word.
- *Quick test:* cut every nav label, heading and link to its first 11 characters (about two words); can you still guess the destination? Read only the first two words of each bullet.

**How to implement.**
1. Put the topic or action first and remove filler prefixes.
2. For sets of similar items, move the shared prefix into a group heading and vary the first words.
3. Write the first sentence of a section as its summary (inverted pyramid) [3].
4. Keep the first 11 characters meaningful; they act as a filter [1].
5. Test with prediction and selection tasks.

**Sources.**
[1] Nielsen, J. (2009). First 2 words: a signal for scanning. Nielsen Norman Group. https://www.nngroup.com/articles/first-2-words-a-signal-for-scanning/
[2] Nielsen, J. (2006). F-shaped pattern for reading web content. Nielsen Norman Group. https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content-discovered/
[3] Schade, A. (2018). Inverted pyramid: writing for comprehension. Nielsen Norman Group. https://www.nngroup.com/articles/inverted-pyramid/

---

### CON-05 Write link and button text that makes sense on its own

**What it is.** A link or button name states its destination or action without needing the sentence around it: "Download the 2026 tax guide (PDF, 2 MB)", not "Click here" or "More".

**Why it works.**
- WCAG 2.2 SC 2.4.4 Link Purpose (In Context), level A: purpose must be clear from the link text, or from the text plus context that software can read (same sentence, paragraph, list item, table cell, or an ARIA label). It helps screen reader users who list links or tab from link to link, people with motor impairments who skip unwanted links, and people with cognitive limits who get disoriented by unwanted pages [1]. SC 2.4.9 (AAA) asks that purpose be clear from the link text alone [2].
- WebAIM's screen reader survey (December 2023 to January 2024, 1,539 responses): "links or buttons that do not make sense" ranked third among the most problematic items. In the same survey 71.6% first navigate long pages by headings and 4.8% by links, so both headings (VIS-02) and link names matter [3].
- WebAIM advises link text that is meaningful out of context and avoiding "click here" and "more", because screen reader users must listen to each link [4].
- NN/g: "Introducing" as a link was chosen by only 15% of participants (CON-04) [5]; a home-page button labeled "Rewarding.Life.Style" gave no clue where it led [6].

**Evidence: Strong.** A formal standard (WCAG 2.2) plus survey data (2024). Required: WCAG 2.2 SC 2.4.4 (A); SC 2.4.9 (AAA).

**Limitations.**
- SC 2.4.4 allows "Read more" when software-readable context names the topic (for example inside a news summary); it passes but is weaker [1].
- Long links (whole sentences) are noisy; make names as long as needed and no longer [4].
- Hidden-text fixes can break voice control if the accessible name drops the visible words; keep the visible text inside the name (WCAG 2.5.3 Label in Name, A; not opened).
- As a button label, generic "Learn More" won the Obama 2007 test (CON-03); clarity for assistive technology and conversion are separate questions.
- Link text also depends on CON-04 (front-loading) and NAV (information scent); accessible names are covered in A11Y-04.

**How to measure it works.**
- Automated: axe `link-name` and `identical-links-same-purpose`; the Lighthouse `link-text` audit (flags generic text). Expect zero findings.
- Manual: open the screen reader links list (NVDA Insert+F7; VoiceOver rotor) and read it out of context.
- Task test: link prediction as in CON-04; click-through of descriptive versus generic labels (lagging).

**Implemented by.**
- Google's developer documentation style guide: link text describes its destination [7].
- WebAIM publishes the same advice for developers [4]. No measured outcome found.

**How to detect it.**
- *Applied:* link text names the destination ("View invoice 1042"); icon-only links have accessible names; repeated "Read more" links are tied to their headings; different destinations have different text.
- *Violated:* "Click here", "here", "more", "read more", "learn more", "link", bare URLs; the same text for different destinations; icon-only links with no name; "Download" with no object.
- *In code:* `<a[^>]*>\s*(click here|here|more|read more|learn more|link|this)\s*</a>` (case-insensitive); `<a>` or `<button>` holding only `<img>` or `<svg>` with no `alt`, `aria-label` or `aria-labelledby`; many links with the same `aria-label`; `title` as the only name. Native: Android `ImageButton` without `contentDescription`; iOS controls without `accessibilityLabel`.
- *Quick test:* list all link texts out of context with `[...document.links].map(a => a.textContent.trim())` and check each is self-explanatory and unique per destination.

**How to implement.**
1. Name the destination or action: verb plus object, front-loaded (CON-04).
2. Add file type and size where relevant: "Annual report (PDF, 2 MB)".
3. For repeated "Read more" cards, name the link after the card title with `aria-labelledby="link-id title-id"` or visually hidden text, and keep the visible words inside the accessible name.
4. Use the same text for the same destination and different text for different ones.
5. Avoid raw URLs as link text.
6. Add `link-name` checks to CI (axe, Lighthouse CI).

**Sources.**
[1] W3C (2023). Understanding SC 2.4.4 Link Purpose (In Context) (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html
[2] W3C (2023). Understanding SC 2.4.9 Link Purpose (Link Only) (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-link-only.html
[3] WebAIM (2024). Screen reader user survey #10. https://webaim.org/projects/screenreadersurvey10/
[4] WebAIM (read 2026-10-31). Link text and appearance. https://webaim.org/techniques/hypertext/link_text
[5] Nielsen, J. (2009). First 2 words: a signal for scanning. Nielsen Norman Group. https://www.nngroup.com/articles/first-2-words-a-signal-for-scanning/
[6] Nielsen, J. (2013). Auto-forwarding carousels and accordions annoy users and reduce visibility. Nielsen Norman Group. https://www.nngroup.com/articles/auto-forwarding/
[7] Google (read 2026-10-31). Highlights. Google developer documentation style guide. https://developers.google.com/style/highlights

---

### CON-06 Keep terminology, capitalization, voice and tone consistent (style guide)

**What it is.** One word per concept, one capitalization rule, one voice, and a tone that adapts to the moment. A short, searchable style guide holds the rules, and a linter or review enforces them.

**Why it works.**
- Nielsen's heuristic 4: users should not have to wonder whether different words, situations or actions mean the same thing [1].
- Shopify Polaris: use one noun, verb or phrase per concept and remove synonyms (its example to avoid is "Upload images" in one place and "Add photos" in another); voice stays constant while tone adapts to the situation [2].
- Microsoft: sentence-style capitalization by default for UI labels, buttons and headings; no all caps for emphasis [3]. Google: conversational, friendly, second person, active voice, sentence-case headings, a shared word list [4]. Mailchimp's guide covers voice and tone and a word list, and is licensed CC BY-NC 4.0 [5].
- Tone has measurable effects. NN/g (Moran, 2016) tested four pairs of insurance, hospital, bank and home-security copy that differed only in tone (survey of 100 US adults): tone changed perceived friendliness, trustworthiness and desirability; trustworthiness explained about half the variation in desirability; a playful tone cut trust for car insurance, while a casual tone worked for a bank [6].

**Evidence: Moderate.** Consensus across four major style guides plus one NN/g tone experiment (2016, survey raters). We found no study that measures terminology consistency alone.

**Limitations.**
- Tone must adapt: errors need directness, onboarding can be warmer [2].
- Humor can alienate users and hide key information [6].
- Long style guides go unused; keep rules short and findable.
- Platform conventions can override house style (Apple uses title-style); stay consistent within the product (INT-03, PLT-01).
- Localization needs a glossary per language, or one term becomes three.
- The tone study used fictional sites and ratings, not behavior.

**How to measure it works.**
- Term audit: distinct labels per concept (target 1); style-linter violations per 1,000 words.
- Heuristic evaluation findings tagged "consistency and standards".
- Tone survey: ask 20-100 users to rate samples for friendliness, trustworthiness and desirability (NN/g's method) [6]; support tickets citing confusing terms.

**Implemented by.**
- Mailchimp Content Style Guide (copyright 2023) [5]; Shopify Polaris content guidelines [2]; Microsoft Writing Style Guide [3]; Google developer documentation style guide [4]. None publishes outcome data.

**How to detect it.**
- *Applied:* same action, same label everywhere ("Sign in" on every screen); one capitalization style; a glossary; shared i18n keys for common actions.
- *Violated:* "Sign in", "Log in" and "Login" mixed; "Remove", "Delete" and "Trash" for one action; "Settings", "Preferences" and "Options"; title case and sentence case mixed; "we" and "I" mixed.
- *In code:* collect strings (i18n JSON, `strings.xml`, `Localizable.strings`, `.po`, JSX text) and count variants: `Sign in|Log in|Login|Log on`, `Delete|Remove|Trash|Discard`, `Settings|Preferences|Options`; near-duplicate strings under different keys; a `.vale.ini` or other prose-lint config present or absent.
- *Quick test:* list the top 10 verbs on buttons and count variants per concept; screenshot five screens and compare capitalization and tone.

**How to implement.**
1. Write a one-page glossary: preferred term, banned synonyms, definition.
2. Fix the mechanics: sentence case, "you", contractions, numerals.
3. Define tone by situation (success, error, destructive, empty) and keep the voice constant [2].
4. Keep the guide in the repo and lint prose in CI (for example Vale with the Microsoft or Google style packages).
5. Centralize strings with shared keys for common actions.
6. Review copy in design review; test tone with 3-5 users.

**Sources.**
[1] Nielsen, J. (1994, wording updated 2020). 10 usability heuristics for user interface design. Nielsen Norman Group. https://www.nngroup.com/articles/ten-usability-heuristics/
[2] Shopify (read 2026-10-31). Content. App design guidelines. https://shopify.dev/docs/apps/design/content
[3] Microsoft (read 2026-10-31). Capitalization. Microsoft Writing Style Guide. https://learn.microsoft.com/en-us/style-guide/capitalization
[4] Google (read 2026-10-31). Highlights. Google developer documentation style guide. https://developers.google.com/style/highlights
[5] Mailchimp (2023). Content Style Guide. https://styleguide.mailchimp.com/
[6] Moran, K. (2016). The four dimensions of tone of voice. Nielsen Norman Group. https://www.nngroup.com/articles/tone-voice-users/

---

### CON-07 Offer contextual help where the question arises

**What it is.** Put help at the point of need: helper text under a field, a short inline explanation, a link to the exact docs section, a tooltip for optional detail. Keep anything required to finish the task visible.

**Why it works.**
- Nielsen's heuristic 10 (1994, wording refined 2020): documentation should be easy to find, task-focused and brief, and works best in context at the moment of need [1].
- Carroll and Rosson's "paradox of the active user" (1987): people skip manuals and start using the system at once, so help has to reach them inside the task (book chapter in Interfacing Thought, MIT Press; not opened) [2].
- NN/g (Kendrick, 2019): tooltips disappear, so essential information such as field requirements should stay on screen; keep tooltips brief, keyboard-accessible and consistent. The article cites no studies [3].
- WCAG 2.2: SC 1.4.13 (AA) says hover or focus content must be dismissible, hoverable and persistent [4]; SC 3.2.6 (A) says help mechanisms repeated across pages keep the same relative order [5].
- GOV.UK: collapsible "details" help suits information only some users need; do not hide what most users need, because many will never open it [6].

**Evidence: Moderate.** Heuristic consensus since 1994 plus standards for how hover and focus help must behave. We found no controlled study of the effect size.

**Limitations.**
- Tooltips fail on touch and for keyboard-only users, and they hide information [3].
- If a field needs a paragraph of help, redesign the field (Tesler's law, INT-06).
- Too much inline help adds clutter (VIS-04).
- Collapsed help often goes unopened; some users avoid it because they fear it leaves the page [6].
- Material's original dialog spec says not to add a "Learn more" action to a dialog because it navigates away mid-task; put help inline or before the dialog [7].
- Product examples such as Google Workspace or Stripe could not be verified here.

**How to measure it works.**
- Help usage: tooltip and details open rates; click-through to docs from context; support tickets per topic (deflection).
- Task success and error rate with and without helper text (A/B); time on field.
- Help-center search queries and "was this helpful" ratings; abandonment at help-heavy steps.

**Implemented by.**
- GOV.UK Design System: details component for optional help, with a short descriptive summary such as "Help with nationality" [6].
- NN/g's tooltip review cites tooltips on Amtrak, FedEx, Sprint, Alibaba, McDonald's and Wikipedia (observations, not outcomes) [3]. No measured outcome found.

**How to detect it.**
- *Applied:* hint text under labels; "Why we ask" links beside sensitive fields; deep links to the relevant docs section; tooltips that add optional detail; the help entry in the same place on every page.
- *Violated:* help only in a separate help center; `title` attribute as the only explanation; instructions in placeholders that vanish; essential requirements only on hover; "Learn more" links that leave a task with no way back.
- *In code:* `aria-describedby` pointing to hint elements; `<details>`/`<summary>`; `role="tooltip"`; `title=` as sole help; `placeholder=` carrying instructions; `data-tooltip`; MUI `helperText`, Compose `supportingText`, Android `TextInputLayout` `helperText`; iOS `UIToolTipInteraction`.
- *Quick test:* keyboard pass: can you reach every tooltip, read it and dismiss it with Esc? Move the pointer onto the tooltip; does it stay? Complete a task using only on-screen help and note where you hesitate.

**How to implement.**
1. Find where users hesitate: usability tests, support tickets, session replays.
2. Write helper text in one sentence that starts with what the user needs; link to detail. For field hints, keep them visible and tie them to the input (FRM-02).
3. Show essential information always; use tooltips or details only for optional extras [3][6].
4. Make hover and focus help dismissible, hoverable and persistent [4].
5. Keep help entry points in the same place across pages [5].
6. Track use; if everyone reads a hint, fold it into the label or redesign the step.

**Sources.**
[1] Nielsen, J. (1994, wording updated 2020). 10 usability heuristics for user interface design. Nielsen Norman Group. https://www.nngroup.com/articles/ten-usability-heuristics/
[2] Carroll, J. M., & Rosson, M. B. (1987). Paradox of the active user. In J. M. Carroll (Ed.), Interfacing Thought, pp. 80-111. MIT Press. (Citation not verified in this session; not opened; no URL.)
[3] Kendrick, A. (2019). Tooltip guidelines. Nielsen Norman Group. https://www.nngroup.com/articles/tooltip-guidelines/
[4] W3C (2023). Understanding SC 1.4.13 Content on Hover or Focus (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html
[5] W3C (2023). Understanding SC 3.2.6 Consistent Help (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/consistent-help.html
[6] GOV.UK Design System (read 2026-10-31). Details. https://design-system.service.gov.uk/components/details/
[7] Google (read 2026-10-31). Dialogs. Material Design 1 (no longer maintained). https://m1.material.io/components/dialogs.html
