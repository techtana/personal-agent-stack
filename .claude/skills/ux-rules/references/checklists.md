# Detection checklists

Fast scan for an audit. Each line is something you can see, measure or try, followed by the rule it tests. Work
through the sections that match the surface, mark each line pass, fail or can't tell, then open the full entry only
for the fails and can't-tells: `Grep "^### FRM-04" -A 60` in `references/` returns the entry with its evidence,
limitations, fix and measure. The cues are condensed from each entry's "How to detect it" section.

Contents: [Every screen](#every-screen) · [Forms and sign-in](#forms-and-sign-in) ·
[Checkout, pricing, subscriptions, consent](#checkout-pricing-subscriptions-consent) ·
[Navigation, search, lists](#navigation-search-lists) · [Layout and copy](#layout-and-copy) ·
[Feedback, loading, performance](#feedback-loading-performance) · [Errors and destructive actions](#errors-and-destructive-actions) ·
[Mobile and touch](#mobile-and-touch) · [Desktop apps](#desktop-apps) · [Accessibility pass](#accessibility-pass-10-minutes) ·
[First run and engagement](#first-run-and-engagement) · [AI features](#ai-features) · [Code grep sheet](#code-grep-sheet) ·
[Myths in design rationales](#myths-in-design-rationales)

## Every screen

- One element wins a blur or squint test; at most one filled primary button per region; destructive actions are not styled primary. VIS-01, PER-08
- Every click, tap or key press changes something visible within about 0.1 s (pressed state, label change, spinner); submit buttons lock while pending. FBK-01
- Clickable things look clickable in a grayscale screenshot: buttons have fill or border, links are underlined or otherwise cued, nothing important appears only on hover. INT-01
- Icon buttons carry a text label, or at least an accessible name and tooltip for universal icons only. INT-02, A11Y-10
- Labels, states and errors use the user's words: no IDs, enum constants, config keys, HTTP codes or stack traces on screen. PER-11, CON-02
- Buttons name the action ("Delete project", "Save changes"), not Yes/No/OK/Submit. CON-03
- Text contrast is at least 4.5:1 (3:1 for 24 px, or 18.66 px bold); input borders and icons at least 3:1. A11Y-01
- Status, errors and links are not told apart by color alone. A11Y-02
- Everything works with the keyboard, focus is visible at every stop and never hidden under sticky bars. A11Y-03
- Targets are at least 24×24 CSS px (or spaced), 44–48 for touch. PLT-03
- Reversible actions offer undo; only irreversible, costly actions ask for confirmation, and the dialog names what is lost. ERR-02, ERR-03
- Every dialog, overlay and flow has a visible exit and responds to Esc and Back. ERR-06, INT-07
- Nothing deceives: no pre-checked consent, fake urgency, hidden fees, shaming decline links or hard-to-find cancel. CHO-06
- The same thing has the same name, style and place on every screen. INT-03, CON-06, NAV-04

## Forms and sign-in

- Every field earns its place; ask "what breaks if this is deleted?" Optional extras sit behind links. FRM-01
- A visible label stays above each field while typing; placeholders hold examples only. FRM-02
- One column, labels above fields; only short related fields (city, state, ZIP) share a row. FRM-03
- Errors appear after leaving a field, not on the first keystroke, and clear as soon as the value is valid. FRM-04
- Inputs use the right `type`, `inputmode` and `autocomplete` token, so phones show the right keyboard and autofill offers saved data. FRM-05
- Card numbers, phones and dates accept spaces, dashes and common formats; input is trimmed. FRM-06
- One field per value: no phone split into three boxes, no card number in four. FRM-13
- Nothing has to be remembered across steps: long numbers display in groups, earlier choices stay visible in a summary, codes can be pasted. PER-03
- Required and optional fields are marked with one convention, and the marks match server validation. FRM-08
- Each error sits beside its field, names it and says how to fix it; a summary links to fields on long forms; values survive the error. FRM-09, ERR-05
- Sign-in allows paste and password managers, offers show-password, imposes no composition rules or short maximums, and offers passkeys where possible. FRM-10, A11Y-07
- Known data is pre-filled (billing same as shipping, country from locale, city from postal code); nothing is asked twice. FRM-11, INT-06, A11Y-07
- Long forms are split into steps with "Step n of m", a Back that keeps answers, and a review page. FRM-12, PER-10
- Sensitive fields say why they are needed. CHO-07

## Checkout, pricing, subscriptions, consent

- Purchase works without creating an account, or account creation comes after payment. FRM-07, ONB-01
- The first price shown includes mandatory fees and never changes on the way to payment. CHO-04
- Countdown timers survive reloads and private windows; "only N left" comes from real inventory. CHO-03
- Optional add-ons, marketing and data-sharing boxes start unchecked; plan defaults fit the user's stated need. CHO-01
- Ratings show count, distribution and dates; counters do not change at random. CHO-02
- Decline buttons are plain and neutral ("No thanks"); accept and decline have equal weight where consent is asked. CHO-06, CHO-08
- Plans are compared in the same units, periods and rows; "was" prices were really charged. CHO-08
- Auto-renewal terms, renewal date and price sit next to the buy button, not in fine print. CHO-04, CHO-06
- Cancelling takes no more steps than signing up, through the same channel (online sign-up, online cancel). CHO-05
- The cookie banner has "Reject all" on the first layer with the same weight as "Accept all"; consent can be changed later from a persistent link. CHO-05

## Navigation, search, lists

- Menu labels predict their content ("Pricing", "Pay a bill"), not "Solutions" or "Resources". NAV-01
- Primary navigation is visible on desktop; phones use a labelled tab bar for 3–5 destinations. NAV-02
- Each page has a unique title, the current nav item is marked (`aria-current`), deep pages have breadcrumbs. NAV-03
- Navigation order, labels and icons are identical across screens. NAV-04
- Search tolerates typos and synonyms, suggests as you type, and a zero-results page offers a way forward. NAV-05
- Large collections have multi-select filters with counts, applied-filter chips, "Clear all" and sorting. NAV-06
- Views, filters and tabs are in the URL; reload, share and Back reproduce them; Back closes overlays. NAV-07
- The structure follows user tasks, not departments or product code names. NAV-08
- Frequent targets are large and near where the pointer already is; edge controls reach the screen edge. PER-01
- Decision screens offer few equal-weight choices; advanced options are behind a labelled toggle. PER-02
- Lists people work through daily support multi-select, bulk actions, saved views and keyboard shortcuts shown in menus or tooltips. INT-05
- Options, recents and suggestions are shown instead of asking users to remember exact names. PER-04

## Layout and copy

- Long text has headings every few paragraphs, bullets for lists, key point first in each paragraph. VIS-02, CON-01, CON-04
- Body text is 16 px or more (platform body style on native), lines about 45–80 characters, line height about 1.5, no long all-caps. VIS-03
- Density fits the task: data tools show enough rows; reading and onboarding screens breathe. VIS-04
- Important information does not sit in banner-like boxes or side rails. VIS-05
- The first viewport says what the page is, shows the main action and hints that more follows. VIS-06
- No auto-advancing carousel; any carousel has a pause control and its content exists elsewhere. VIS-07
- Spacing and color come from a small set of tokens; color has one meaning per role. VIS-08, INT-03
- Images carry information; stock filler doesn't push content down. VIS-09
- Polish is consistent (one type scale, icon set and corner radius), but a polished screen still needs task evidence: attractive designs get rated easier than they are. PER-07
- Controls sit on or next to what they change, toggles state what ON means, and changes preview live instead of waiting for Save. INT-04
- Related items are grouped by proximity or a shared container; a label is closer to its field than to the next one. PER-05
- Conventions users know are kept (logo top left links home, search in the header, cart top right). PER-06
- Copy is plain, short, consistent in terminology and capitalization; link text makes sense out of context. CON-01, CON-02, CON-05, CON-06
- Help sits where the question arises (hint text, "why we ask", a deep link), not only in a help center. CON-07

## Feedback, loading, performance

- Waits over about 2 s show progress; over about 10 s show a measure (percent, "3 of 12") and a working Cancel. FBK-02
- Page and list loads show a placeholder that matches the final layout, or a spinner for small modules; no blank screen. FBK-03
- Low-risk toggles (like, star, check) update at once and roll back with a message on failure; payments never show success early. FBK-04
- Field data (CrUX or RUM, 75th percentile) meets LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1. FBK-05, MEA-08
- Images have dimensions, embeds reserve space, banners don't push content down. FBK-06
- Save, send and delete confirm with a non-blocking message that stays 4–10 s, offers Undo when it can, and is announced (`role="status"`). FBK-07
- Notifications and prompts are rare, relevant, and switchable by type; no permission prompt on first load. FBK-08, ONB-08

## Errors and destructive actions

- Invalid input is prevented where possible (date pickers with min/max, selects for finite sets, double-submit protection). ERR-01
- Delete, archive and move offer Undo or a trash with a stated retention period. ERR-02
- Confirmation dialogs are rare, name the object and the loss, use verb buttons, and don't focus the destructive button by default. ERR-03, CON-03
- Error messages say what happened and what to do, sit next to the problem, and never blame; no bare codes or "Something went wrong". ERR-04, FRM-09
- No path loses typed work: failed submits keep values, sessions expire without data loss, editors autosave or warn before leaving. ERR-05, PLT-06
- Offline or failed requests show a message with Retry, not an endless spinner. PLT-06, AI-09

## Mobile and touch

- Primary actions and navigation sit in thumb reach on tall phones (bottom bars, bottom sheets). PLT-02
- Touch targets are 44–48 px with at least 8 px between them. PLT-03
- No horizontal scroll at 320 px; text reflows at 200–400% zoom; zoom is not blocked. PLT-04, A11Y-05
- Every swipe, drag, pinch or long-press has a visible button or menu alternative. PLT-05
- The app follows platform navigation and Back conventions (Android back, iOS swipe-back). PLT-01
- The app survives interruption: state kept after switching apps, forms kept after a lost connection. PLT-06

## Desktop apps

- Platform conventions: system window controls, standard shortcuts (close, quit, preferences), menus, dark mode and text-size settings honored. PLT-01
- Tray or menu-bar apps: a tooltip, a left-click action, a right-click menu with Open and Quit, and a way to reach the app without the tray icon. PLT-01
- Keyboard: Tab reaches every control, focus is visible (check custom themes; Tk needs `highlightthickness` or a themed focus ring), Enter triggers the default button, Esc closes dialogs. A11Y-03, ERR-06
- The UI thread never blocks: slow work runs in the background with a busy state and disabled duplicate actions. FBK-01, FBK-02
- Start-up and background failures are visible: a missing config file, an import error or a blocked executable produces a message or a dialog (and the launcher reports whether the app came up), never only a log line. Windowless apps (`pythonw`, services) need this most. ERR-04, FBK-07
- Status shown is true: "starting" is not shown as "stopped", errors are not shown as empty data, and figures use the platform's own units so they match its tools (CPU as a share of the whole machine, as Task Manager shows it; idle pseudo-processes left out). PER-06, PER-11
- Fonts are at least 9 pt for body text and scale with system DPI. VIS-03, A11Y-05
- Theme color pairs meet contrast in both light and dark themes (check token tables with `scripts/contrast.py`). A11Y-01
- Icon-only buttons have tooltips and accessible names. INT-02, A11Y-10
- Frequent tasks have keyboard shortcuts (shown in menus and tooltips) and, for lists, multi-select and bulk actions. INT-05
- Stock message boxes with Yes/No/OK are used only where the platform convention requires them; otherwise buttons name the action. CON-03

## Accessibility pass (10 minutes)

- Run `scripts/ui_lint.py` on the code and `scripts/measure_page.js` (or axe) on the page; automated checks find well under half of real barriers, so continue by hand. A11Y-09
- Contrast of text, placeholders, borders and focus rings, including hover, error and dark-mode states. A11Y-01
- Grayscale and color-blindness emulation: nothing becomes ambiguous. A11Y-02
- Keyboard only: reach, operate and leave everything; focus visible and not obscured; skip link present. A11Y-03
- Screen reader or accessibility tree: headings in order, landmarks present, every control has a name and role, `lang` set, status messages announced. A11Y-04, FBK-07
- Zoom to 200% and 400%, 320 px width, text-spacing override, reduced motion: no clipping, sideways scroll or leftover motion. A11Y-05
- Media: captions, transcripts, no autoplaying sound, pause for anything that moves over 5 s. A11Y-06, VIS-07
- Sign-in and long flows: paste allowed, no puzzle CAPTCHA without alternative, no retyping, help in the same place. A11Y-07
- Images: informative ones have specific alt, decorative ones `alt=""`, charts have a text summary. A11Y-10
- Process: research includes people with disabilities, tasks have more than one input route (touch, keyboard, voice), and an accessibility statement offers a way to report barriers. A11Y-08

## First run and engagement

- A first-time visitor gets value (content, a sample, a working core action) before an account is demanded. ONB-01
- The post-sign-up screen points to one core action, and an analytics event marks it. ONB-02
- No mandatory intro carousel or tour; tips appear at the point of need, one at a time, dismissible. ONB-03
- Every empty screen says what goes there and offers the first action; loading looks different from empty. ONB-04
- Multi-step setup has a short, dismissible checklist whose progress starts from real completed steps. ONB-05, PER-10
- Creation tools offer templates or sample content next to an equally visible Blank option. ONB-06
- Streaks and reminders serve the user's own goal, can be turned off in a couple of taps, and avoid guilt copy. ONB-07
- Permission prompts follow a user action and give a reason; the feature works after a refusal. ONB-08, CHO-07
- Endings are designed: key flows finish on a clear confirmation with next steps, and the worst moment (errors, waiting, payment) is handled with care. PER-09

## AI features

- The first screen says what the AI can and can't do and how reliable it is; example prompts are offered. AI-01
- Output arrives as a proposal with Accept, Edit, Dismiss, Retry, Stop and Undo. AI-02
- Claims link to the sources that support them; reasons are given for recommendations. AI-03
- Sending, paying, deleting or changing things needs a preview and an explicit approval; vague requests get a question, not a guess; actions are logged. AI-04
- Slow responses stream, show the current step and can be stopped, keeping partial output. AI-05
- Feedback controls sit on each output and have a visible effect; model or behavior changes are announced. AI-06
- Memory and personalization can be viewed, deleted and turned off from settings; a temporary mode saves nothing. AI-07
- The product says it is AI, labels synthetic media, and never poses as a person. AI-08
- Failures, refusals and timeouts say what happened and offer a next step; truncated answers are marked. AI-09

## Code grep sheet

Patterns that point at a rule. `scripts/ui_lint.py` runs many of them; the rest are worth a manual grep.

| Pattern | Look for | Rule |
|---|---|---|
| `placeholder=` with no `<label for>` / `aria-labelledby` | placeholder as label | FRM-02 |
| `outline: none` / `outline: 0` with no `:focus-visible` style | removed focus ring | A11Y-03 |
| `<div onClick` / `<span onclick` without `role` and `tabindex` | keyboard-inaccessible control | A11Y-03, A11Y-04 |
| `<img` without `alt=`; `<button>` holding only `<svg>` or `<i>` | missing text alternative or name | A11Y-10, A11Y-04 |
| `user-scalable=no`, `maximum-scale=1` | zoom blocked | A11Y-05 |
| `type="text"` on email or phone; missing `autocomplete` on personal fields | wrong keyboard, no autofill | FRM-05 |
| `onpaste="return false"`, paste `preventDefault`, `maxlength` < 64 on passwords, `(?=.*[A-Z])` | sign-in friction | FRM-10 |
| `checked` / `defaultChecked` on marketing or sharing checkboxes | preselected consent | CHO-01 |
| `Date.now() +` used as an offer deadline; `Math.random()` in counters | fake urgency or social proof | CHO-03, CHO-02 |
| `confirm(` in delete handlers; `alert(` for errors or success | confirmation instead of undo; blocking feedback | ERR-02, ERR-04, FBK-07 |
| `form.reset()` or cleared state in an error path | lost work | ERR-05 |
| "Something went wrong", "Invalid input", raw `error.message` in UI | unhelpful errors | ERR-04 |
| `>(click here\|here\|read more\|learn more)<` | vague links | CON-05 |
| `>(OK\|Yes\|No\|Submit)<` on buttons; `MessageBoxButtons.YesNo`, `askyesno` | generic action labels | CON-03 |
| `setInterval` advancing slides; `autoplay: true` in carousel config | auto-advancing carousel | VIS-07 |
| `<img`/`<iframe` without `width` and `height` or `aspect-ratio` | layout shift | FBK-06 |
| `loading="lazy"` on the first, largest image; `<script>` without `async`/`defer` in `<head>` | slow LCP | FBK-05 |
| `Notification.requestPermission()` or geolocation on page load | permission without context | ONB-08, CHO-07 |
| auth guard on `/` or `/checkout`; "account is required" | value gated behind sign-up | ONB-01, FRM-07 |
| "to cancel, call" / cancel path longer than sign-up | obstruction | CHO-05 |
| hamburger toggle visible at ≥ 1024 px | hidden navigation | NAV-02 |
| one `<title>` for every route; no `aria-current` | no wayfinding | NAV-03 |
| `items.length === 0` branch rendering nothing or "No data" | empty state without guidance | ONB-04 |
| AI output written straight to the document; no `AbortController` on a Stop button | AI output not controllable | AI-02, AI-05 |
| `auto_approve`, `bypassPermissions`, no audit log around agent actions | no human control | AI-04 |

## Myths in design rationales

Flag these when a design decision rests on them, and point to the better rule instead (`contested-and-debunked.md`):
"three clicks" (MYTH-01) · "7±2 menu items" (MYTH-02) · "users don't scroll" (MYTH-03) · "8-second attention span"
(MYTH-04) · "fewer choices always sell more" (MYTH-05) · "Zeigarnik keeps them coming back" (MYTH-06) · "design for
the F-pattern" (MYTH-07) · "skeletons always beat spinners" (MYTH-08) · "carousels engage" (MYTH-09) · "red buttons
convert" (MYTH-10) · "infinite scroll is always better" (MYTH-11) · "NPS is the one number" (MYTH-12) · "dark mode is
easier on the eyes" (MYTH-13) · "golden ratio" (MYTH-14) · "five users are always enough" (MYTH-15).
