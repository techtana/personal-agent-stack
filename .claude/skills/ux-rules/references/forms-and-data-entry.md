# Forms and data entry (FRM)

How to ask people for information: how many fields, how they are labelled and laid out, when input is checked, what the browser and keyboard can do for the user, and the account and sign-in steps that sit in front of a form. An auditor should load this category for any UI that contains typed input: checkout, sign-up, sign-in, contact, settings, applications. Error-message wording is in ERR-04, ethical defaults in CHO-01, contrast and keyboard access in A11Y-01 and A11Y-03, touch targets in PLT-03.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| FRM-01 | Ask only for what you need | Moderate | Any form; checkout, sign-up, lead-gen |
| FRM-02 | Use visible labels; never use the placeholder as the label | Strong | Any text field (web, mobile, desktop) |
| FRM-03 | Use a single column with labels above fields | Moderate | Web forms on desktop and tablet |
| FRM-04 | Validate inline, at the right moment | Mixed | Fields with format rules or availability checks |
| FRM-05 | Use the right input type, keyboard and autocomplete token | Strong | Web and native forms that collect user data |
| FRM-06 | Accept input in the formats people type | Moderate | Phone, card, date, ID and postal-code fields |
| FRM-07 | Don't force account creation before purchase or value | Moderate | Checkout, quotes, gated content, lead-gen |
| FRM-08 | Mark required and optional fields clearly | Mixed | Forms longer than a login |
| FRM-09 | Put error messages next to the field and say how to fix it | Strong | Any form that validates input |
| FRM-10 | Remove needless friction from passwords and sign-in | Strong | Sign-up, sign-in, reset, recovery |
| FRM-11 | Use smart defaults and pre-fill what you already know | Moderate | Multi-step flows, checkout, returning users |
| FRM-12 | Split long forms into steps with visible progress | Mixed | Long or complex forms, applications |
| FRM-13 | Use one field for one value | Moderate | Name, phone, card number, date fields |

---

### FRM-01 Ask only for what you need

**What it is.** Collect only the fields the task cannot work without. Delete, derive, defer or hide the rest, and explain any question that looks unnecessary.

**Why it works.** Each field adds typing, recall and privacy cost, and a long-looking form puts people off.
- Baymard's checkout benchmark found 11.3 form fields on average in 2024 (12.7 in 2019, 11.8 in 2021), while most sites need about 8. In Baymard's survey of US online shoppers, 17% of those who abandoned a cart (excluding people just browsing) blamed a checkout that was too long or complicated [1][2].
- Baymard testers were intimidated by 10 to 15 or more fields. Simplifying typically removed 20 to 60% of default visible fields and elements [3].
- NN/g cut one of its own forms from 6 fields to 2 and advises at most one or two optional fields [7].

**Evidence: Moderate.** Benchmark and usability-test research with a stated method (Baymard, 2024). The famous case numbers are weaker than their reputation (see Limitations). Required in part: GDPR Art. 5(1)(c) limits personal data to what is necessary [10].

**Limitations.**
- Imagescape (June 2008, 18 years old) is a before/after comparison on one contact page, not a randomized test. Cutting 11 fields to 4 moved conversion from 5.4% to 11.9% (+120%). That is 10 versus 26 submissions (+160%) in two-month windows five months apart. The write-up reports unchanged lead quality and notes that required fields barely changed (4 to 3) [4]. The source is Imaginary Landscape's own case study, not a third-party test.
- Expedia's "$12 million a year" for deleting an optional "Company" field traces to a 2010 Silicon.com/ZDNet report of a talk by Expedia's Joe Megibow. We could not open the original. The reported mechanism was not length: some customers typed their bank's name there, then the bank's address as billing address, so address verification failed [5][6]. Treat the dollar figure as an unaudited claim (Weak). The lesson is "remove ambiguous fields".
- Fewer is not always better. Baymard found unexplained required fields hurt because people assume the worst, and that a short reason or making the field optional fixed it without removal [8]. A Baymard summary updated 29 Jul 2025 puts 14% of users abandoning when a phone number is required with no explanation (summary text only; we could not open the article). We found no public, method-documented test where a longer form beat a shorter one. Qualification fields for sales leads are a business trade-off, not a UX finding.
- Conflicts: FRM-12 (split a form you cannot cut), FRM-11 (prefill shrinks the effective form), FRM-07 (account fields).

**How to measure it works.**
- Form completion rate (starts to submits), per-field drop-off and time-in-field from form analytics or event funnels; expect completion up.
- Guardrails: lead-to-opportunity rate, invalid or duplicate entries, payment or address-verification failures, chargebacks; expect no drop. Run an A/B test, not before/after.
- Audit count: visible inputs on the first screen; Baymard's checkout average is 11.3, its practical floor about 8 [1].

**Implemented by.**
- Baymard benchmark sites (2019 to 2024): the average fell from 12.7 to 11.3 fields, yet 75% still show Address Line 2 and 35% show a coupon field by default [1].
- Imagescape (2008): small-number anecdote [4]. Expedia (2010): second-hand anecdote [5][6].
- NN/g (2016): its own form from 6 fields to 2, no conversion figure published [7].
- GOV.UK Design System: teams must know why they ask each question; a "question protocol" helps decide [9].

**How to detect it.**
- *Applied:* only task-critical fields visible; Address Line 2, coupon, company and billing address behind links; one name field; city and state derived from the postal code; a one-line reason beside any surprising field.
- *Violated:* fax, company, job title, birthday, gender or "How did you hear about us?" on a transaction form; phone required with no reason; "confirm email" duplicates; more than about 10 visible inputs in a checkout.
- *In code:* count `<input>`, `<select>`, `<textarea>` per `<form>` excluding `type="hidden|submit|button"`; `name="(company|fax|title|dob|gender|phone)"` with `required`; `name="(email|password)_?confirm"`; `autocomplete="organization"`.
- *Quick test:* count the visible inputs, then ask of each "what breaks if this is deleted?" Anything with no answer goes.

**How to implement.**
1. List every field with its owner and downstream use; delete fields no one consumes.
2. Derive what you can: city and state from postal code or address lookup, country from locale, card brand from the number, one name field (FRM-13).
3. Defer what is not needed now: account creation and profile data come after the first success (FRM-07).
4. Hide rarely used fields behind a link (Address Line 2, coupon, company, billing address equal to shipping).
5. Put a one-line reason beside any kept field that looks odd (for phone: used only if delivery has a problem); make it optional if the reason is weak (FRM-08).
6. A/B test the shorter form with a downstream-quality guardrail.

**Sources.**
[1] Baymard Institute (2024). Checkout form-field benchmark: average 11.3 fields, most sites need 8 (page title not captured). https://baymard.com/blog/checkout-flow-average-form-fields
[2] Baymard Institute (page updated 2025-09-22). Cart abandonment rate statistics. https://baymard.com/lists/cart-abandonment-rate
[3] Baymard Institute (undated page). Form Design: 6 Best Practices for Better Ecommerce UI. https://baymard.com/blog/form-design
[4] Moloney, B. (2008, June). Fewer fields in a contact form sharply increases conversions. Imaginary Landscape case study (PDF). https://imagescape.com/filer/canonical/1455648270/152
[5] Silicon.com/ZDNet (2010). Expedia on how one extra data field can cost $12m. http://www.zdnet.com/expedia-on-how-one-extra-data-field-can-cost-12m-3040153863/ (snippet; page not opened)
[6] Empoprise BI blog (2010, Nov). When simplification makes money (confirms the mechanism; does not state the figure). https://empoprise-bi.blogspot.com/2010/11/when-simplification-makes-money.html
[7] Whitenton, K. (2016, 1 May). Website Forms Usability: Top 10 Recommendations. Nielsen Norman Group. https://www.nngroup.com/articles/web-form-design/
[8] Holst, C. (2012, 31 Jul). Baymard Institute article on seemingly unnecessary checkout information. https://baymard.com/blog/checkout-experience-seemingly-unnecessary-information
[9] GOV.UK Design System. Question pages. https://design-system.service.gov.uk/patterns/question-pages/
[10] European Union (2016). General Data Protection Regulation, Art. 5(1)(c), data minimisation. EUR-Lex. https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679 (page text did not load in my fetch)

---

### FRM-02 Use visible labels; never use the placeholder as the label

**What it is.** Give every input a text label that stays visible when the field is empty, focused and filled, and tie it to the control in code. Use a placeholder, if at all, only for a short format example.

**Why it works.** Placeholder text vanishes when typing starts, so people must remember the question, cannot review their answers, and cannot tell which field an error refers to.
- NN/g (2014, reviewed 2018) lists seven problems seen in repeated testing: memory strain, hard to check work, hard to fix errors, skipped by keyboard users, filled fields look finished, mistaken for pre-filled values, and extra clearing. It adds low-contrast default styling and uneven screen-reader support [1].
- W3C's forms tutorial says placeholder text does not replace a label [4]. GOV.UK says the same and puts visible labels above inputs [5].
- Baymard advises putting descriptions above the field because inline labels disappear once users type [6].

**Evidence: Strong.** Required: WCAG 2.2 SC 3.3.2 Labels or Instructions (A) [2] and SC 1.3.1 Info and Relationships (A) [3]. WCAG does not name placeholders. The placeholder ban rests on NN/g testing (practitioner research) and design-system guidance.

**Limitations.**
- A placeholder may still supply an accessible name in some browsers, so a placeholder-only field is a risk against 3.3.2 (labels must reach all users, not only assistive technology), not an automatic failure [2].
- Floating labels (a label that starts inside the field and shrinks above it) are, per NN/g, an acceptable compromise with noticeability and accessibility issues; external labels stay best when space allows [1]. We could not load Material Design 3's text-field page to check its current wording.
- An icon can serve as the visible label when its meaning is plain, such as a magnifier on a search field; it still needs an accessible name [2].
- A format example in a placeholder helps, but GOV.UK keeps examples and hints out of placeholders and uses persistent hint text [5].

**How to measure it works.**
- Usability test (five users): count wrong-field entries and "what was this field?" pauses; per-field error rate in analytics.
- Automated: axe-core `label` rule and the Lighthouse form-label audit; expect zero unlabeled controls.
- Lagging: first-submit error rate and form abandonment.

**Implemented by.**
- GOV.UK Design System: labels above inputs, short and in sentence case; no placeholders as labels, hints or examples [5].
- Baymard recommends label descriptions above fields in e-commerce checkout [6].
- No published conversion outcome for removing placeholder-only labels was found.

**How to detect it.**
- *Applied:* a text label stays above each field while typing; a screenshot of a filled form still shows every question; hint text sits outside the field.
- *Violated:* grey text inside empty fields is the only cue; a filled form with no visible questions; labels hidden with `.sr-only` on every field.
- *In code:* `<input placeholder="...">` with no `<label for>` or `aria-labelledby`; `aria-label` as the only name on a text field; MUI `<TextField placeholder>` without `label`; SwiftUI `TextField("Email", text:)` with no separate label; Android `EditText android:hint` with no `TextInputLayout`.
- *Quick test:* fill every field and screenshot it: can you tell what each one asked? Tab through with a screen reader and listen for names.

**How to implement.**
1. Add `<label for="id">` to every text input; use `<fieldset>` and `<legend>` for radio and checkbox groups.
2. Put the label above the field, short and in sentence case (FRM-03); keep hints visible and link them with `aria-describedby`.
3. Reserve `placeholder` for a rare format example and check its colour passes contrast (A11Y-01); every control also needs an accessible name (A11Y-04).
4. If the brand needs floating labels, keep the label visible in every state, test long labels and autofill, and fall back to a label above when it wraps or truncates.
5. On native, use a visible text label or `TextInputLayout` rather than the hint or prompt string alone.

**Sources.**
[1] Sherwin, K. (2014, 11 May; reviewed 2018). Placeholders in Form Fields Are Harmful. Nielsen Norman Group. https://www.nngroup.com/articles/form-design-placeholders/
[2] W3C (2023). Understanding SC 3.3.2: Labels or Instructions (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html
[3] W3C (2023). Understanding SC 1.3.1: Info and Relationships (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/info-and-relationships.html
[4] W3C WAI. Forms tutorial: Instructions. https://www.w3.org/WAI/tutorials/forms/instructions/
[5] GOV.UK Design System. Text input. https://design-system.service.gov.uk/components/text-input/
[6] Baymard Institute (undated page). Form Design: 6 Best Practices for Better Ecommerce UI. https://baymard.com/blog/form-design

---

### FRM-03 Use a single column with labels above fields

**What it is.** Stack fields in one vertical column, one per row, with each label directly above its field. Let only two or three short fields that make up one value share a row (city, state, ZIP; expiry and security code).

**Why it works.** One column gives the eye a single path down the page, and a label near its field shortens the jump between them.
- Penzo (UXmatters, 2006, 20 years old; participant count not reported): label-to-field eye jumps of about 50 ms with labels above, against about 500 ms with left-aligned labels beside the field [1].
- Seckler et al. (CHI 2014, N = 65, three real newspaper registration forms) applied 20 guidelines together, including labels above and a single column. Improved forms were 18 to 33% faster (two of three significant), needed fewer submissions and fixations. NN/g summarises first-try success as 78% versus 42% [2][3].
- CXL/Speero (June 2016, n = 702 desktop users): 102.3 s for a single column versus 117.8 s for multi-column, 15.5 s faster (p = 0.004) [4].
- Baymard (2023): in repeated tests people skipped fields or mistook optional ones for required in multicolumn layouts; 16% of benchmark sites use extensive multicolumn forms [5].

**Evidence: Moderate.** Consistent lab and practitioner results, but the strongest study bundles many guidelines, Penzo's sample is unreported, and the CXL test measured time only.

**Limitations.**
- A HubSpot test on a 13-field form found the two-column version converted 22% better (99% confidence; sample and year not published). The author's explanation: one column looked longer [6]. Perceived length can outweigh scan path; see FRM-12 for long forms.
- The CXL test was desktop-only and everyone finished, so it says nothing about abandonment or mobile [4]. Phones are single-column anyway.
- NN/g allows labels beside fields on very long desktop forms [3]. Penzo found right-aligned labels beside fields halved fixations and time versus left-aligned ones, and bold labels above added about 60% to the label-to-field jump (50 to 80 ms) [1].
- Autofill and address lookup shrink the multicolumn penalty because people type less, though most still review entries [5] (search snippet; not in the fetched text).

**How to measure it works.**
- Time from first focus to submit and skipped-required-field rate from validation logs; expect faster completion (CXL measured 13%) and fewer skipped fields.
- Conversion in an A/B test, not just speed: the HubSpot result shows the two can diverge.
- Five-user test or eye tracking for label-field mismatches.

**Implemented by.**
- Baymard cites Etsy (ZIP and city on one row) and Apple (card expiry and security code on one row) as acceptable pairs inside a single-column form [5].
- Baymard cites Staples and Sea Paradise as multicolumn forms where people missed fields [5].
- NN/g's guidance (2016): one column, with short related fields such as City, State and ZIP allowed to share a row [3].

**How to detect it.**
- *Applied:* one left edge of inputs; each label closer to its own field than to the field above; only related short fields paired.
- *Violated:* first name | last name | email | phone in a two- or three-column grid; labels in a left gutter; a label equally close to two fields; full-width inputs for 4-character values.
- *In code:* `grid-template-columns: repeat(2` or `1fr 1fr` on a form; Bootstrap `col-md-6` around `.form-group`; MUI `<Grid item xs={6}>` around `TextField`; `float: left` on inputs; `label { display: inline-block; width: ... }`.
- *Quick test:* view at 1280 px and trace a path with a finger. A zigzag means multi-column. Check the label-to-field gap is smaller than the gap between fields.

**How to implement.**
1. Lay the form out as one column; stack each label above its input; keep the label-to-field gap smaller than the field-to-field gap.
2. Share a row only for inseparable fields (city, state, ZIP; expiry and CVC; day, month, year), and keep everything else single-column.
3. Size each field to the expected answer. Seckler et al. list this as a guideline; NN/g's data (2,130 participants) found 99.9% of city names were 19 characters or fewer [2][3].
4. For long forms, split into steps rather than adding columns (FRM-12).
5. Keep the same order on mobile and desktop.

**Sources.**
[1] Penzo, M. (2006, 12 Jul). Label Placement in Forms. UXmatters. https://www.uxmatters.com/mt/archives/2006/07/label-placement-in-forms.php
[2] Seckler, M., Heinz, S., Bargas-Avila, J. A., Opwis, K., Tuch, A. N. (2014). Designing Usable Web Forms: Empirical Evaluation of Web Form Improvement Guidelines. CHI 2014, 1275-1284. https://research.google.com/pubs/archive/42513.pdf
[3] Whitenton, K. (2016, 1 May). Website Forms Usability: Top 10 Recommendations. Nielsen Norman Group. https://www.nngroup.com/articles/web-form-design/
[4] Speero/CXL (2016, Oct). Form Field Usability: single or multi-column forms (original research). https://speero.com/post/form-field-usability-should-you-use-single-or-multi-column-forms-original-research
[5] Baymard Institute (2023, 31 Oct). Form Field Usability: Avoid Extensive Multicolumn Layouts. https://baymard.com/blog/avoid-multi-column-forms
[6] HubSpot (test year not stated; page updated 2023-10-14). Disproving Best Practices: The One- vs. Two-Column Form Test. https://blog.hubspot.com/marketing/one-vs-two-column-form-conversion-test

---

### FRM-04 Validate inline, at the right moment

**What it is.** Check an answer when the person finishes it (on leaving the field, or on reaching the expected length), show the message beside the field, and clear the message the moment the value becomes valid. Never flag a half-typed answer.

**Why it works.** Feedback arrives while the person still has the context, so fixes are small.
- Etre study reported by Wroblewski (A List Apart, 1 Sep 2009, 17 years old; 22 participants, six versions of a registration form): the best inline version beat the submit-only control on success (+22%), errors (-22%), satisfaction (+31%), completion time (-42%) and eye fixations (-47%) [1].
- "After the field" variants were 7 to 10 seconds faster than "while typing" ones. Validating both before and while typing raised time and errors and lowered satisfaction [1].
- Baymard (9 Jan 2024): 31% of benchmark sites have no inline validation; flagging an email before it was finished frustrated testers. Check most fields on blur, fixed-length fields (ZIP, phone, card, CVC) on reaching length, and after an error re-check on every keystroke [2].

**Evidence: Mixed.** One small study (2009; no raw data; Etre called the results indicative) and consistent Baymard observations. GOV.UK advises against validating on blur or while typing, and the 20-guideline set tested by Seckler et al. says to show errors after submission, all together [3][4]. No large replication found.

**Limitations.**
- Gains were largest for fields where the answer is not obvious (usernames, passwords). For simple fields such as names, participants ignored messages [1].
- Green success ticks confused participants (they asked if it meant "correct"); persistent messages beat fading ones; in-field messages gave no clear benefit [1].
- GOV.UK validates on submit. It cites slow typists, hard cross-browser and assistive-technology reporting, and client/server rule conflicts. Add client-side checks only where research shows a need, and always validate on the server [3].
- Not tested with screen-reader users [1]. Live messages must be announced without stealing focus (A11Y-04). Message content is FRM-09.

**How to measure it works.**
- First-submit success rate and errors per submission (leading); expect success up, errors down. Time to complete; abandonment after the first error.
- Per-field error recurrence (same field failing twice) from client logs; support contacts about form failures.
- A/B test inline versus submit-only, and include screen-reader users in the usability test.

**Implemented by.**
- Etre's test design (2009) [1]. No company-level outcome for inline validation was found.
- About 69% of Baymard's benchmark sites validate inline [2].
- GOV.UK chooses the opposite: validate on submit, with an error summary and inline messages, and keep entries [3].

**How to detect it.**
- *Applied:* a message appears beside the field right after leaving it; it clears on the first valid keystroke; untouched fields stay quiet; success marks appear only on non-obvious fields.
- *Violated:* "Invalid email" after typing one character; all errors only after submit on a long form; the page reloads and clears values; ticks on name fields.
- *In code:* `blur` or `focusout` listeners that validate; `input` listeners that validate from the first character; `aria-invalid`, `aria-describedby`; CSS `:user-invalid` (after interaction) versus `:invalid` (immediately); React Hook Form `mode: "onBlur"`, Formik `validateOnBlur`.
- *Quick test:* type "a" in an email field and watch; type a full bad address and tab out; fix it and note when the message clears; submit an empty form.

**How to implement.**
1. Keep full server-side validation; treat inline checks as a convenience layer.
2. Validate on `blur` for most fields and on reaching length for fixed-length fields; skip untouched or empty fields.
3. After a field shows an error, re-validate on `input` so the message clears at once (React Hook Form: `mode: "onBlur"` with `reValidateMode: "onChange"`).
4. Show a plain-text message beside the field (FRM-09), set `aria-invalid` and `aria-describedby`, announce through a polite live region, and do not move focus.
5. Use warnings, not blocks, where a check can be wrong (names, addresses).
6. Use success ticks only for non-obvious answers such as usernames and passwords.

**Sources.**
[1] Wroblewski, L. (2009, 1 Sep). Inline Validation in Web Forms. A List Apart (reports a study by Etre). https://alistapart.com/article/inline-validation-in-web-forms/
[2] Scott, E. (2024, 9 Jan). Baymard Institute article on inline form validation. https://baymard.com/blog/inline-form-validation
[3] GOV.UK Design System. Validation pattern. https://design-system.service.gov.uk/patterns/validation/
[4] Seckler, M. et al. (2014). Designing Usable Web Forms (guidelines 16 and 17 in Table 1). CHI 2014. https://research.google.com/pubs/archive/42513.pdf

---

### FRM-05 Use the right input type, keyboard and autocomplete token

**What it is.** Tell the browser, OS and password manager what each field is: `type` for the kind of data, `inputmode` for the keyboard, and `autocomplete` for the autofill token (`given-name`, `postal-code`, `cc-number`, `one-time-code`, `current-password`).

**Why it works.** Autofill and the right keyboard remove typing and recall, which matters most on phones and for people with motor or memory difficulties.
- WCAG 2.2 SC 1.3.5 makes the purpose of fields that collect information about the user machine-readable, so browsers can fill them and assistive tools can show icons [2].
- Google's 2015 HTML5Rocks post said users complete forms "up to 30% faster" with correct `autocomplete` markup, but it cites no study; the current web.dev page leaves the claim out [3][4].
- For SMS codes, `autocomplete="one-time-code"` lets Safari 12 and later suggest the code; Chrome on Android can read it through the WebOTP API when the SMS ends with `@domain #code` [5].
- GOV.UK dropped `type="number"` in 2020: scroll wheels changed values, spinners confused NVDA, Dragon could not dictate into it, and long numbers were rounded. It uses `type="text"` with `inputmode="numeric"` [6].

**Evidence: Strong.** Required: WCAG 2.2 SC 1.3.5 Identify Input Purpose (AA) for fields about the user [2]. The speed benefit is unsourced; the keyboard guidance rests on GOV.UK research and platform documentation.

**Limitations.**
- The 30% figure is a maximum from an unreferenced internal claim (2015, 11 years old), not a measured average [3].
- `autocomplete="off"` suits one-off values; browsers may still offer password managers. WCAG 1.3.5 lets you disable browser autofill but still requires the declared purpose [1][2][4].
- `type="number"` is wrong for IDs, card numbers, phone numbers and postal codes [6]. GOV.UK avoids `inputmode="decimal"` where negatives are needed [7].
- WebOTP works only in Chromium on Android; `one-time-code` covers Safari. SMS codes are not phishing-resistant [5] (FRM-10).

**How to measure it works.**
- Time from first focus to submit on mobile; share of fields filled by autofill; per-field error rate; OTP success and resend rates; mobile conversion.
- Compliance: axe-core `autocomplete-valid` rule and a manual WCAG 1.3.5 check.

**Implemented by.**
- GOV.UK Design System: `bday-day`, `bday-month`, `bday-year` on date inputs to meet 1.3.5; `inputmode="numeric"` in place of `type="number"` [6][7].
- Google: autofill and WebOTP guidance on web.dev [4][5]. Goibibo reported 25% fewer OTP retries on sign-up with WebOTP (link title on Google's page only; snippet).
- Android: `android:autofillHints` with `PERSON_NAME`, `POSTAL_CODE`, `CREDIT_CARD_NUMBER`, `SMS_OTP` [8].

**How to detect it.**
- *Applied:* the number pad appears for numeric fields; the email field shows the @ keyboard; tapping a field offers saved address or card data; the OTP suggestion appears above the keyboard.
- *Violated:* `type="text"` everywhere; `type="number"` for card, phone or ZIP; `autocomplete="off"` on whole forms; fields named `field1` with no tokens; a card number split across four inputs.
- *In code:* `type="email|tel|url|password"`, `inputmode="numeric|decimal|tel|email"`, `autocomplete="given-name|family-name|email|tel|street-address|address-line1|postal-code|cc-number|cc-exp|cc-csc|one-time-code|username|current-password|new-password"`, `shipping`/`billing` prefixes. Native: `keyboardType` and `textContentType` (iOS), `android:inputType` and `android:autofillHints`.
- *Quick test:* on a phone, tap each field and check the keyboard and autofill offer; run axe `autocomplete-valid`.

**How to implement.**
1. Map each field to a token from the WHATWG list [1]; add `shipping` or `billing` where both exist.
2. Choose `type` for meaning (email, tel, url, password). For digit strings that are not numbers, use `type="text" inputmode="numeric"`.
3. OTP: `<input type="text" inputmode="numeric" autocomplete="one-time-code" pattern="\d{6}">`, an SMS ending in `@example.com #123456`, and WebOTP as progressive enhancement.
4. Sign-in: `autocomplete="username"` and `current-password`; sign-up and password change: `new-password` (FRM-10).
5. Do not disable autofill or paste; set `spellcheck="false"` on emails, names and reference numbers [7].
6. Test in Chrome, Safari and one password manager.

**Sources.**
[1] WHATWG. HTML Living Standard, Autofill (form control infrastructure). https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#autofill
[2] W3C (2023). Understanding SC 1.3.5: Identify Input Purpose (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/identify-input-purpose.html
[3] HTML5Rocks post credited to "idogreen" (2015, June). Help users checkout faster with Autofill (copy seen at this URL). https://mr-html5.blogspot.com/2015/06/help-users-checkout-faster-with-autofill.html
[4] Google (2021, last updated 2021-11-03). Autofill. web.dev Learn Forms. https://web.dev/learn/forms/autofill/
[5] Google (2020, updated 2020-12-09). SMS OTP form best practices. web.dev. https://web.dev/articles/sms-otp-form
[6] GOV.UK Technology blog (2020, 24 Feb). Why the GOV.UK Design System team changed the input type for numbers. https://technology.blog.gov.uk/2020/02/24/why-the-gov-uk-design-system-team-changed-the-input-type-for-numbers/
[7] GOV.UK Design System. Text input; Date input. https://design-system.service.gov.uk/components/text-input/ ; https://design-system.service.gov.uk/components/date-input/
[8] Android Developers. Optimize your app for autofill. https://developer.android.com/identity/autofill/autofill-optimize

---

### FRM-06 Accept input in the formats people type

**What it is.** Parse what people type leniently and normalise it in code. Accept spaces, dashes, brackets, mixed case and month names, and show the cleaned value back.

**Why it works.** People type values the way they appear on cards and paperwork, and strict formats turn that into avoidable errors.
- Baymard (2017, updated 5 Jun 2025): testers entered card numbers in groups like the physical card and double-checked them. On more than a third of test sites a validation error cleared the typed card data. 15% of benchmark sites still did not auto-format spaces, down from 50% in 2019 [1].
- GOV.UK's Apply for teacher training team saw many users type month names into date fields. The date input now accepts full or abbreviated month names, and errors dropped dramatically (no figure published) [2].
- The 20-guideline set tested by Seckler et al. (2014) says to allow any format when the answer is unambiguous, and to state a required format in advance. In the NZZ form, 17 initial errors in the original came from missing format specifications, against 2 in the improved version [3].
- Postel's robustness principle (RFC 761, January 1980) is the engineering ancestor: "be conservative in what you do, be liberal in what you accept from others" [4].

**Evidence: Moderate.** Practitioner testing (Baymard), design-system case evidence without figures (GOV.UK), and guidelines tested only in combination. Postel's principle is a protocol-design maxim, not UX evidence.

**Limitations.**
- Ambiguity: 03/04/2026 means different dates in the US and Europe. Accept only unambiguous forms or show your interpretation back; never swap day and month silently.
- RFC 9413 (June 2023) argues that liberal acceptance of faulty input can entrench errors and open security holes in protocols [5]. For forms: normalise once at the boundary and validate the canonical value on the server.
- Strict input masks that reject keystrokes or paste break autofill and international formats. Auto-format as people type, but never block. GOV.UK also avoids `maxlength` because it truncates pasted input without feedback [6].
- Baymard's card article keeps its 2017 headline figure (80% of sites) while the updated body says 15% [1]; use the body figure.
- If a format cannot be relaxed (a national ID), show the pattern before typing (FRM-09).
- Phone formatting numbers are thin: a Baymard article (2017) on localized phone input masks has a title saying 64% of sites use none, but we saw only the title in a listing (snippet) and could not open it.

**How to measure it works.**
- "Invalid format" error counts per field, the share of first submissions rejected for formatting, and related support tickets; expect all to fall.
- Card or phone validation failures caused by spaces, dashes or brackets; expect close to zero.
- Usability test: enter the same value in three formats.

**Implemented by.**
- GOV.UK Apply for teacher training: date input accepts month names [2].
- Sites in Baymard's tests that auto-formatted card spaces made entry and checking easier [1].
- No company outcome figure was found for lenient parsing.

**How to detect it.**
- *Applied:* "4242 4242 4242 4242" and "4242-4242-4242-4242" both pass; phone accepted with spaces and brackets; date accepts "3 Apr 1990"; whitespace trimmed; postal codes case-insensitive.
- *Violated:* a hint "digits only, no spaces" that errors on spaces; pasted spaced numbers rejected; `maxlength="16"` on a card field; a date field that requires exactly `MM/DD/YYYY`.
- *In code:* `maxlength="16"`, `pattern="[0-9]{16}"`, `pattern="^\d{10}$"`; strict mask libraries (`imask`, `inputmask`, `cleave.js`) with no paste handling; no `.replace(/[\s-]/g, "")` or `trim()` before validation.
- *Quick test:* paste "4242 4242 4242 4242" and "(555) 010-0199" into card and phone fields; type a date three ways; enter a postal code in lower case with a trailing space.

**How to implement.**
1. Strip spaces, dashes, dots and brackets before validating phone, card, tax and ID numbers; trim whitespace; case-fold codes.
2. Auto-format groups as the user types when the pattern is certain (card grouping by brand), keep the caret stable, and allow paste.
3. Parse phone numbers with a library given a default region; store one canonical form (E.164) and show it back.
4. Dates: accept numbers and month names (GOV.UK); never guess an ambiguous order.
5. If a format cannot be relaxed, state it before typing (Seckler guideline 13) and keep the user's text on error.
6. Remove `maxlength` and character-class patterns that block valid input.

**Sources.**
[1] Baymard Institute (2017, 11 Jan; updated 2025, 5 Jun). The "Credit Card Number" Field Must Allow and Auto-Format Spaces. https://baymard.com/blog/credit-card-field-auto-format-spaces
[2] GOV.UK Design System. Date input. https://design-system.service.gov.uk/components/date-input/
[3] Seckler, M. et al. (2014). Designing Usable Web Forms (Table 1 guidelines 1, 2, 13; Table 4). CHI 2014. https://research.google.com/pubs/archive/42513.pdf
[4] Postel, J. (1980, Jan). RFC 761: DoD Standard Transmission Control Protocol, section 2.10. https://www.rfc-editor.org/rfc/rfc761.txt
[5] Thomson, M., Schinazi, D. (2023, Jun). RFC 9413: Maintaining Robust Protocols. https://www.rfc-editor.org/rfc/rfc9413.html
[6] GOV.UK Design System. Text input. https://design-system.service.gov.uk/components/text-input/

---

### FRM-07 Don't force account creation before purchase or value

**What it is.** Let people finish the main task (buy, request, submit) without registering. Offer an account after the task, reusing the details already entered.

**Why it works.** A registration wall asks for effort and a password before any value, and many returning customers cannot remember their credentials.
- Baymard's abandonment-reasons list (page updated 22 Sep 2025; sample size and survey year not shown on the page): 18% of abandoners (excluding people just browsing) said the site wanted them to create an account, next to 17% for a too long or complicated checkout [1].
- Spool, "The $300 Million Button" (UIE, 14 Jan 2009, 17 years old): an unnamed retailer replaced Register with Continue plus a note that no account was needed. Purchasing customers rose 45%, reported as $15 million extra in month one and $300 million in year one. Analytics had shown 45% of customers with multiple registrations and about 160,000 password requests a day; 75% of requesters never bought [2].
- Baymard (2024): 84% of benchmark sites do not delay account creation until after the order [3].

**Evidence: Moderate.** A Baymard survey of stated reasons (self-reported) and a consistent direction in case reports. The single famous case has no published method.

**Limitations.**
- The $300M story names no retailer, test design or sample; the dollar figures are reported estimates (Weak for magnitude) [2].
- ASOS is often cited as +50% after dropping "register". We found only second-hand Econsultancy pieces: one reads it as a 50% conversion lift for new visitors, another as a 50% drop in abandonment at that step, with no ASOS data. Another Econsultancy piece asks why ASOS removed its guest checkout option and expects a conversion hit; the sequence and dates of the two changes are unconfirmed and the accounts conflict [4]. Do not cite ASOS as proof.
- Accounts have real benefits: saved details, order history, fraud control, and services that need identity (subscriptions, downloads, regulated goods). Ask at the point of need, not at the start.
- Stated reasons are not observed behaviour; test your own funnel.
- Wallet, passkey or email-code sign-in lowers the cost of accounts (FRM-10, FRM-11).

**How to measure it works.**
- Cart-to-order conversion, guest versus account share, post-purchase account-creation rate, 90-day repeat purchase rate.
- Leading: drop-off at the login step; password-reset requests started during checkout.
- A/B test guest-first against account-first.

**Implemented by.**
- The unnamed "$25 billion" retailer in Spool's story (2009): anecdote [2].
- ASOS: second-hand and unverified (see Limitations) [4].
- Only about 16% of Baymard's benchmark sites delay account creation until after the order, so the practice is still uncommon [3].

**How to detect it.**
- *Applied:* "Continue as guest" is the primary path, or an email-only first step; an optional "Create account" after confirmation using the order email.
- *Violated:* a login or register wall between cart and payment; "Create an account to continue" for a one-time purchase; the guest link is tiny; a password field in a one-time checkout.
- *In code:* a route guard on `/checkout` (`requireAuth`, `redirect("/login")`); a checkout form with `autocomplete="new-password"` or a `required` `name="password"`; no "guest" strings; a login modal on the Checkout click.
- *Quick test:* in a private window add an item and click checkout. Count screens and fields before payment. Can you pay without choosing a password?

**How to implement.**
1. Make guest checkout the default path and ask for an email only (for the receipt).
2. After payment, offer "Save your details for next time" with one extra step (password or passkey, FRM-10), reusing the order data.
3. Show sign-in for returning customers beside the guest path, not before it; support social, passkey or email-code sign-in.
4. If an account is truly needed (a subscription), say why in one line and ask late.
5. Show cart contents and total costs before any sign-in prompt.

**Sources.**
[1] Baymard Institute (page updated 2025-09-22). Cart abandonment rate statistics. https://baymard.com/lists/cart-abandonment-rate
[2] Spool, J. M. (2009, 14 Jan). The $300 Million Button. UIE (now Center Centre). https://articles.centercentre.com/three_hund_million_button/
[3] Baymard Institute (2024). Checkout form-field benchmark (84% do not delay account creation). https://baymard.com/blog/checkout-flow-average-form-fields
[4] Econsultancy (dates not confirmed). Why has ASOS removed its guest checkout option?; ASOS's new mobile site is usable but unspectacular. https://econsultancy.com/why-has-asos-removed-its-guest-checkout-option/ ; https://econsultancy.com/asos-s-new-mobile-site-is-usable-but-unspectacular/ (snippets; pages redirect to the Econsultancy home page)

---

### FRM-08 Mark required and optional fields clearly

**What it is.** Tell people which answers are needed and which are not, using one convention that is visible in the label and exposed in code. Keep optional fields few.

**Why it works.** Without markers people guess: they skip required fields and hit errors, or spend effort on optional ones.
- Baymard (article 2018; benchmark figures from 2021): only 14% of sites mark both kinds (42% mark only required, 37% only optional). At L.L. Bean 22% tried to continue without a required email. Where only optional fields were marked, 32% hit validation errors, and at Amazon 44% came to a complete stop at the last shipping section. 75% of mobile testers had severe form problems where neither kind was clear [1].
- In Seckler et al. (2014), missing format specifications and unclear required/optional marking were the issues users named most about the original forms [2].
- NN/g (Budiu, 2019) says to mark every required field, preferably with an asterisk before the label or the word "required"; it treats labelling optional fields as a nice extra, not a requirement [3].

**Evidence: Mixed.** All sources agree on clarity and disagree on convention. NN/g marks required [3]; GOV.UK marks optional with "(optional)" and bans asterisks for required [4]; Baymard marks both [1]. Only Baymard publishes test figures; NN/g's piece cites no study.

**Limitations.**
- Pick one convention per product and use it everywhere. State it in text, not by colour or symbol alone (A11Y-02); WCAG 3.3.2 requires instructions [5][6].
- When nearly every field is required, GOV.UK marks the minority (optional); when most are optional, mark required. Login and three-field forms can omit marks (NN/g, Baymard).
- Marking optional does not stop people filling it: 86% completed an unmarked optional phone field at AllPosters and 89% a clearly marked one at L.L. Bean [1]. Fewer optional fields beat better labels (FRM-01).
- Native `required` bubbles are inconsistent. W3C WAI uses `required`, `aria-required` and a visible "(required)"; GOV.UK says not to add `required` and to validate on the server [4][5].
- An unexplained asterisk can be misread; add a legend.

**How to measure it works.**
- Share of first submissions that fail on empty required fields; share of optional fields completed; time to complete.
- Usability question: "which fields can you skip?" Expect correct answers without reading help.
- Logs: "field is required" errors per 1,000 submissions.

**Implemented by.**
- Baymard test sites: L.L. Bean (clearly marked fields) and AllPosters (unmarked optional phone field) [1].
- GOV.UK Design System: "(optional)" convention; ask only for what you need [4].
- NN/g reviewed required-field marking at Citibank, American Express, UPS, USPS, Sephora and Kayak; no outcome figures [3].

**How to detect it.**
- *Applied:* a legend ("Fields marked * are required") or "(optional)" in labels; markers inside the label text; the same convention on every page; `required` exposed to assistive tech.
- *Violated:* no markers on a long form; a red border as the only cue; asterisks that do not match server validation; both conventions on one page; "optional" fields that fail when empty.
- *In code:* `required`, `aria-required="true"`, label text containing `*`, `(optional)` or `(required)`, `label.required::after { content: "*" }`; compare against server rules; `novalidate` on the form.
- *Quick test:* submit the empty form. Every field that errors should have been marked; every unmarked field must pass empty. Listen for "required" with a screen reader.

**How to implement.**
1. Cut optional fields first; keep at most one or two (FRM-01).
2. Choose one convention: "(optional)" on the minority-optional fields (GOV.UK), or an asterisk plus legend for required fields (NN/g). On checkout and long forms, mark both (Baymard).
3. Put the marker in the label text and set `required` or `aria-required`; never rely on colour alone.
4. Add a legend before the form if you use asterisks.
5. Make server rules match the markers; explain sensitive optional fields (FRM-01).

**Sources.**
[1] Scott, E. (2018, 2 Oct). Baymard Institute article on required and optional form fields. https://baymard.com/blog/required-optional-form-fields
[2] Seckler, M. et al. (2014). Designing Usable Web Forms (comments analysis; guideline 4). CHI 2014. https://research.google.com/pubs/archive/42513.pdf
[3] Budiu, R. (2019, 16 Jun). Marking Required Fields in Forms. Nielsen Norman Group. https://www.nngroup.com/articles/required-fields/
[4] GOV.UK Design System. Question pages; Validation. https://design-system.service.gov.uk/patterns/question-pages/ ; https://design-system.service.gov.uk/patterns/validation/
[5] W3C WAI. Forms tutorial: Instructions; Validating input. https://www.w3.org/WAI/tutorials/forms/instructions/ ; https://www.w3.org/WAI/tutorials/forms/validation/
[6] W3C (2023). Understanding SC 3.3.2: Labels or Instructions. https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html

---

### FRM-09 Put error messages next to the field and say how to fix it

**What it is.** When an entry fails, name the field, say what is wrong and say how to fix it, in text beside the field. On pages with several errors add a summary at the top that links to each field. Keep what the user typed. Message wording in general is ERR-04.

**Why it works.** People must find the field and know the fix; a generic message forces guessing.
- WCAG 3.3.1 requires the item in error to be identified and described in text; 3.3.3 requires a suggested fix when the system knows one [1][2].
- Seckler et al. (2012, Interacting with Computers) found messages near the faulty field performed better than messages at the top or bottom of the form; we read this only as cited in their 2014 CHI paper [3][4].
- Baymard (14 Dec 2023): 98% of benchmark sites use generic messages that ignore the exact failed rule. Some testers needed up to five minutes to fix a simple error, a subset got stuck and abandoned, and specific messages improved recovery time for everyone [5].
- GOV.UK pairs an error summary (focus moves to it, links to fields, "Error:" title prefix) with identical inline messages [6][7].

**Evidence: Strong.** Required: WCAG 2.2 SC 3.3.1 Error Identification (A) and SC 3.3.3 Error Suggestion (AA). WCAG allows a list or dialog; "beside the field" rests on Seckler et al. and platform guidance.

**Limitations.**
- Credential forms: a specific message ("no account with that email") can leak which accounts exist. Baymard says add rate limits, else keep sign-in and reset messages vague; WCAG 3.3.3 exempts suggestions that would compromise security [5][2].
- Summary plus inline messages is deliberate duplication; use the same words in both [6].
- Colour alone is not enough; text is required [1].
- Tone: GOV.UK avoids "invalid", blame, "oops", "please" and "sorry" [7].
- Timing of the message is FRM-04; keeping input after errors is also covered by WCAG 3.3.7 (FRM-11).

**How to measure it works.**
- Time to recover from an error; repeat-error rate on the same field; abandonment after an error; support contacts about form failures.
- Audit: share of messages that are generic ("Invalid input", "This field is required"); Baymard's benchmark baseline is 98%.
- Screen-reader test: is the error announced, and can you reach the field?

**Implemented by.**
- GOV.UK Design System: error summary plus inline message, reused across GOV.UK services [6][7].
- Away is cited by Baymard for a card message that says the number is incomplete instead of invalid (snippet) [5].
- Only 2% of Baymard's benchmark sites use adaptive messages [5].

**How to detect it.**
- *Applied:* red text naming the field beside or below it; "Enter your first name"; "Name must be 35 characters or less"; a summary with working links; values kept; page title starts "Error:".
- *Violated:* a banner "Please correct the errors below"; "Invalid input"; a red border only; `alert()` popups; fields cleared after an error; the message far from the field.
- *In code:* `aria-invalid="true"`, `aria-describedby="...-error"`, `role="alert"` or `aria-live`, summary anchors `href="#email"`, `<title>Error:`; strings "Invalid", "An error occurred", "This field is required"; `alert(`; `setCustomValidity(`; `form.reset()` on failure.
- *Quick test:* submit empty and with bad values. Is each message beside its field, specific, with a fix? Does focus land on the summary? Are values kept?

**How to implement.**
1. Write each message as what is wrong plus how to fix it, reusing the label's words; one message per failed rule (Baymard suggests at least 4 to 7 messages for complex fields such as card number, password, phone) [5][7].
2. Place the inline message between hint and input, with a red border and an icon or "Error:" text so colour is not the only cue.
3. For submit-time errors add a summary at the top with a heading and links to the fields; move focus to it; prefix `<title>` with "Error:" [6].
4. Connect messages with `aria-describedby` and set `aria-invalid="true"`.
5. Keep all entered values.
6. On sign-in and reset use neutral wording plus rate limits.

**Sources.**
[1] W3C (2023). Understanding SC 3.3.1: Error Identification (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html
[2] W3C (2023). Understanding SC 3.3.3: Error Suggestion (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/error-suggestion.html
[3] Seckler, M. et al. (2014). Designing Usable Web Forms (related work). CHI 2014. https://research.google.com/pubs/archive/42513.pdf
[4] Seckler, M., Tuch, A. N., Opwis, K., Bargas-Avila, J. A. (2012). User-friendly locations of error messages in web forms: Put them on the right side of the erroneous input field. Interacting with Computers, 24(3), 107-118. (cited in [3]; not opened)
[5] Baymard Institute (2023, 14 Dec). Adaptive validation error messages. https://baymard.com/blog/adaptive-validation-error-messages
[6] GOV.UK Design System. Error summary. https://design-system.service.gov.uk/components/error-summary/
[7] GOV.UK Design System. Error message. https://design-system.service.gov.uk/components/error-message/

---

### FRM-10 Remove needless friction from passwords and sign-in

**What it is.** Make sign-in and password creation cost as little effort as security allows: allow paste and password managers, let people reveal what they typed, drop composition rules and forced rotation, block breached passwords, and offer passkeys.

**Why it works.** Rules such as "one capital, one symbol, change every 90 days" push people toward predictable passwords and workarounds, and blocked paste defeats password managers.
- NIST SP 800-63B-4 (final 31 Jul 2025, replaces the 2020 edition): verifiers must not impose composition rules or periodic changes (force a change only on evidence of compromise); require at least 15 characters for single-factor passwords (8 if used only with another factor) and allow at least 64; should allow paste and offer a show-password option; must check against common or compromised passwords; accept Unicode and spaces [1].
- WCAG 2.2 SC 3.3.8 (AA): authentication cannot depend on a cognitive function test unless an alternative or helper (password manager, paste) exists. Blocking paste or autofill fails it [2].
- FIDO Alliance Passkey Index, October 2026 (15 consumer organisations, self-reported averages): passkey sign-in success 93% versus 78% for passwords and traditional MFA (n = 12), 2.8 times faster, about 27 s saved per sign-in (n = 9) [3]. The October 2025 index (9 organisations) gave 93% versus 63% for "other methods" and 8.5 s versus 31.2 s [4].

**Evidence: Strong.** Required: NIST SP 800-63B-4 (US federal systems, widely adopted); WCAG 2.2 SC 3.3.8 Accessible Authentication (Minimum) (AA). Passkey figures are member-reported, not controlled.

**Limitations.**
- The Passkey Index averages are unweighted, from self-selected members, with a different baseline each year (63% "other methods" in 2025, 78% "passwords and traditional MFA" in 2026). Do not compare years [3][4]. Case results on Google's page (KAYAK -50% sign-in time, Mercari 3.9 times faster, pixiv +29% login success, X 2 times login success in 2024, Dashlane +70% sign-in conversion) are company-reported [5].
- Some sectors (PCI DSS, banks, some governments) still mandate composition or rotation. GOV.UK's password pattern says minimum 8, no maximum, allow paste, no forced changes, which is below NIST's 15 [6].
- Reveal toggles expose secrets to onlookers; default to masked. Passkeys need recovery and fallback design; 38% of accounts had one enrolled in 2026 and fallbacks keep passwords alive [3].
- SMS codes are not phishing-resistant (FRM-05). Lockouts and rate limits are still needed (GOV.UK: 5 to 10 attempts) [6].

**How to measure it works.**
- Sign-in success rate, time to sign in, password-reset volume, sign-in help-desk tickets, sign-up completion; passkey enrolment and usage share; account-takeover counts.
- Leading: reset requests per 1,000 sign-ins; paste and password-manager use (client events).

**Implemented by.**
- FIDO Passkey Index 2026 participants include Amazon, Google, Microsoft, PayPal, Shopify, TikTok, WhatsApp, CVS and JPMorgan Chase [3].
- Company-reported passkey results on Google's case-studies page: KAYAK, Mercari, pixiv, X, Zoho, Dashlane, Tokyu [5].
- GOV.UK: paste allowed, no forced change, reset by link or code, no reset questions [6].

**How to detect it.**
- *Applied:* a show/hide toggle; paste and password-manager fill work; a passkey prompt in the username field; rejected passwords explained ("found in a data breach").
- *Violated:* paste blocked; "must contain uppercase, number, symbol"; expiry every 90 days; maximum length 16 to 20; security questions; CAPTCHA at login with no alternative; prompts for "characters 2, 5 and 7".
- *In code:* `onpaste="return false"`, `addEventListener("paste", e => e.preventDefault())`, `ondrop`, `oncopy`; `autocomplete="off"` on password fields; `maxlength` under 64; lookahead patterns `(?=.*[A-Z])(?=.*\d)`; missing `autocomplete="current-password|new-password"`; presence of `autocomplete="username webauthn"` and `PublicKeyCredential` (good).
- *Quick test:* paste a 20-character password; open a password manager; try a 64-character passphrase with spaces; look for a reveal toggle; try "Password1!" and see if it is rejected as common.

**How to implement.**
1. Allow paste, drag and password-manager fill; set `autocomplete="username"` and `current-password` on sign-in, `new-password` on sign-up and reset (FRM-05).
2. Policy: minimum 15 characters (8 only alongside MFA), accept 64 or more, spaces and Unicode, no composition rules, no scheduled expiry; force a change only after compromise [1].
3. Check passwords against a breached or common list, for example the Pwned Passwords k-anonymity API (send the first 5 characters of the SHA-1 hash), and say why a password was rejected [1][8].
4. Add a show-password button (hidden by default) with an accessible name and `aria-pressed`.
5. Add passkeys: `autocomplete="username webauthn"` and `navigator.credentials.get({ mediation: "conditional" })` [7]. Offer the passkey first to users who have one; in the 2026 Index one participant estimated this would roughly double passkey sign-ins [3].
6. Avoid cognitive tests at login (3.3.8; A11Y-07); reset by link or code, not security questions.

**Sources.**
[1] NIST (2025, 31 Jul). SP 800-63B-4: Digital Identity Guidelines: Authentication and Authenticator Management. https://pages.nist.gov/800-63-4/sp800-63b.html ; record: https://csrc.nist.gov/pubs/sp/800/63/b/4/final
[2] W3C (2023). Understanding SC 3.3.8: Accessible Authentication (Minimum) (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html
[3] FIDO Alliance (2026, Oct). Passkey Index October 2026 (results compiled 21 Sep 2026). https://fidoalliance.org/wp-content/uploads/2026/10/Passkey-Index-October-2026.pdf
[4] FIDO Alliance (2025, Oct). Passkey Index October 2025. https://fidoalliance.org/wp-content/uploads/2025/10/FIDO-Passkey-Index-October-2025.pdf
[5] Google. Passkeys case studies. https://developers.google.com/identity/passkeys/case-studies
[6] GOV.UK Design System. Passwords pattern. https://design-system.service.gov.uk/patterns/passwords/
[7] Google. Sign in with a passkey through form autofill. web.dev. https://web.dev/articles/passkey-form-autofill
[8] Have I Been Pwned. API v3: Pwned Passwords range. https://haveibeenpwned.com/API/v3#PwnedPasswords

---

### FRM-11 Use smart defaults and pre-fill what you already know

**What it is.** Fill in what the system already knows or can infer (country from locale, billing equal to shipping, city and state from postal code, saved address and payment through a wallet or returning-user recognition) and let the user change it.

**Why it works.** Re-typing known data costs time and invites errors.
- WCAG 2.2 SC 3.3.7 Redundant Entry (A) requires information entered earlier in the same process to be auto-filled or selectable. Its examples include a "billing same as shipping" checkbox and keeping the card number after a validation error [1].
- Baymard (2024) lists hiding the billing address by default among its main field-cutting tactics (24% of sites do not) [2]. Its 2023 article notes that autofill and fully automatic address lookup soften multicolumn problems [3] (search snippet).
- Vendor claims: Shopify says Shop Pay gives "as much as 50%" better conversion than guest checkout, citing an external study with a Big Three consulting firm, April 2023, sample not stated [4]. Stripe says Link raises returning-user conversion 14% on average and makes checkout 3 times faster, with no method or footnote [5].
- We found no published keystroke-saving figure for address autocomplete; three Google Maps Platform pages had none [6].

**Evidence: Moderate.** Required in part: WCAG 2.2 SC 3.3.7 Redundant Entry (A) for data entered earlier in the same process. Wallet and autocomplete figures are vendor claims.

**Limitations.**
- Defaults persuade. Pre-checked marketing opt-ins or add-ons are deceptive patterns (CHO-01). Prefill neutral facts; leave consent and extras unchecked.
- Wrong prefill is easy to miss: NN/g notes autofill can enter wrong data unnoticed when labels are missing [7]. Show the value and keep it editable; geo-IP defaults can be wrong.
- Vendor figures mix identity recognition, payment method and traffic mix, use an unspecified guest-checkout baseline, and disclose no sample [4][5].
- Privacy: avoid prefilling sensitive data on shared devices; mask card numbers.
- WCAG 3.3.7 exempts security re-entry (confirming a new password) and data that is no longer valid [1].
- Related: INT-06 argues for absorbing complexity in the system; FRM-01 and FRM-13 apply the same idea to fields.

**How to measure it works.**
- Characters typed or fields completed per order; time to pay for returning versus new users; share of prefilled values later edited (a wrong-default signal).
- Address-correction and failed-delivery rates; returns.
- Conversion by segment with an A/B hold-out.

**Implemented by.**
- Shopify (Shop Pay) and Stripe (Link): returning-user wallets; claims above are vendor-reported [4][5].
- Baymard-observed practice: billing equals shipping by default, with optional fields hidden [2].
- GOV.UK: avoid asking for information users have already given; Check answers keeps prior answers pre-filled behind Change links [8].

**How to detect it.**
- *Applied:* "Billing same as shipping" checked; country preselected; city and state filled from the postal code; address suggestions as you type; returning users see a saved address or a wallet button; Back keeps values.
- *Violated:* email, name or address asked again in a later step; a blank 200-option country list; values wiped after an error; pre-ticked upsells.
- *In code:* `autocomplete="shipping ..."` and `billing ...`; `<input type="checkbox" id="same-as-shipping" checked>`; `defaultValue` or `value={profile.x}`; address-autocomplete SDK calls (`google.maps.places`); Payment Request API; Shop Pay or Link buttons; `checked` on a marketing checkbox (flag it).
- *Quick test:* enter a shipping address and continue to billing: is anything retyped? Press Back: are values kept? Is the country right for your locale?

**How to implement.**
1. Keep answers in the session and reuse them across steps; default "billing same as shipping" to checked.
2. Add `autocomplete` tokens (FRM-05) and address lookup with a manual fallback; derive city and state from the postal code.
3. Choose defaults that are the most common, neutral, visible and reversible; never default to consent, add-ons or paid options (CHO-01).
4. Offer a wallet or email-code/passkey recognition for returning users instead of forcing an account (FRM-07).
5. Log how often prefilled values are edited and fix defaults with high edit rates.

**Sources.**
[1] W3C (2023). Understanding SC 3.3.7: Redundant Entry (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/redundant-entry.html
[2] Baymard Institute (2024). Checkout form-field benchmark. https://baymard.com/blog/checkout-flow-average-form-fields
[3] Baymard Institute (2023, 31 Oct). Form Field Usability: Avoid Extensive Multicolumn Layouts. https://baymard.com/blog/avoid-multi-column-forms
[4] Shopify. Shop Pay (claims dated April 2023 in its footnote; checked 2026-10-31). https://www.shopify.com/shop-pay
[5] Stripe. Link (checked 2026-10-31). https://stripe.com/payments/link
[6] Google Maps Platform pages checked, no keystroke figures: https://mapsplatform.google.com/maps-products/address-validation/ ; https://mapsplatform.google.com/maps-products/places/ ; https://developers.google.com/maps/documentation/places/web-service/autocomplete
[7] Sherwin, K. (2014, 11 May; reviewed 2018). Placeholders in Form Fields Are Harmful. Nielsen Norman Group. https://www.nngroup.com/articles/form-design-placeholders/
[8] GOV.UK Design System. Question pages; Check answers. https://design-system.service.gov.uk/patterns/question-pages/ ; https://design-system.service.gov.uk/patterns/check-answers/

---

### FRM-12 Split long forms into steps with visible progress

**What it is.** Break a long or complex form into short steps (GOV.UK starts with one question per page), show where the user is, allow going back, and end with a "check your answers" page.

**Why it works.** A short page lowers apparent effort and gives each question attention. The page heading can double as the label, so screen-reader users hear it once, and errors are easier to handle [1].
- Baymard's checkout guide: the best flows feel manageable, linear and transparent whether on one page or several, so page count is not the deciding factor. A progress indicator should map to the real steps, past steps should be clickable, and the same page should never appear twice [2].
- Baymard also lists splitting checkout into steps or collapsible sections as a way to cut visible fields [3].
- GOV.UK's Check answers pattern ends the flow with a summary and Change links [5].

**Evidence: Mixed.** Strong consensus in design systems, little controlled evidence. Villar, Callegaro and Yang (2013, 32 randomized web-survey experiments): constant progress indicators did not reduce drop-off, fast-to-slow ones did, slow-to-fast ones increased it, and with incentives constant ones raised drop-off [4]. We did not find a controlled test of multi-step against single-page forms; vendor claims of large lifts were not checked.

**Limitations.**
- The meta-analysis covers surveys, not forms; extrapolation is uncertain [4].
- GOV.UK says grouping questions can suit users who repeat tasks quickly (internal staff tools) and that research should decide [1].
- More steps mean more page loads and more places to quit. Non-linear flows confused Baymard testers [2].
- A bar that moves fast early and slowly at the end can mislead; show real step counts [4].
- Short forms do not need steps; cut fields first (FRM-01).
- Preserve data on Back and refresh (ERR, NAV, PLT-06); update the title and focus on each step (A11Y-03).

**How to measure it works.**
- Step-level funnel (drop-off per step), overall completion, time per step, Back-button use, error rate; leading: first-step starts.
- A/B test steps against one page with identical fields, judged on total completion.
- Perceived effort (single ease question) in usability tests.

**Implemented by.**
- GOV.UK services: one question per page and a Check answers page [1][5].
- Baymard reports no outcome data tied to page count; it judges flows by effort, linearity and clarity [2].

**How to detect it.**
- *Applied:* "Step 2 of 4" or a step list; a Back link; one heading per step; a summary page before submit; answers kept on Back.
- *Violated:* 20+ fields on one scroll with no grouping; multi-step with no total or no Back; a progress bar that jumps; a wizard that loses data on refresh; a stepper that hides steps.
- *In code:* `aria-current="step"`, `<ol class="steps">`, routes like `/step-2`, `history.pushState` per step, `<fieldset><legend>` used as the page heading, stepper components.
- *Quick test:* count steps and fields per screen. Is the total visible at the start? Press Back and reload: are answers kept?

**How to implement.**
1. Group fields by topic; keep each step short; use one question per page when questions are complex or unfamiliar.
2. Show the full step list up front with the current step; keep counts accurate.
3. Add a Back link, save answers per step, and give each step its own URL.
4. Finish with "Check your answers" with Change links, then a submit button that names the action [5].
5. Update `<title>` and move focus to the step heading on each change; announce errors (FRM-09).
6. A/B test against a one-page version on total completion.

**Sources.**
[1] GOV.UK Design System. Question pages. https://design-system.service.gov.uk/patterns/question-pages/
[2] Baymard Institute. The Checkout UX Guide (undated page). https://baymard.com/blog/checkout-flow-ux-optimization
[3] Baymard Institute (undated page). Form Design: 6 Best Practices for Better Ecommerce UI. https://baymard.com/blog/form-design
[4] Villar, A., Callegaro, M., Yang, Y. (2013). Where Am I? A Meta-Analysis of Experiments on the Effects of Progress Indicators for Web Surveys. Social Science Computer Review, 31(6), 744-762. doi:10.1177/0894439313497468 (abstract read via https://api.crossref.org/works/10.1177/0894439313497468; the SAGE page returned 403)
[5] GOV.UK Design System. Check answers. https://design-system.service.gov.uk/patterns/check-answers/

---

### FRM-13 Use one field for one value

**What it is.** Ask for a name, phone number, card number or address line in one input, not in several parts. Split only when the parts are separate real-world values (day, month, year; expiry and security code).

**Why it works.** Splitting a single value adds fields, tab stops, paste failures and cultural assumptions.
- Baymard's mobile tests of a three-field phone number (Macy's, Feb 2013, 13 years old) showed people struggling to move between fields and the keyboard closing between them. It advises against splitting single entities on mobile; desktop results were inconclusive [1].
- In 2024, 89% of benchmark checkouts still did not use a single name field [2].
- W3C Internationalization advises one full-name field where possible, because names vary: patronymics, family name first, two family names, one name only. Avoid "first/last" labels and do not require a family name [3].
- GOV.UK says not everyone's name fits first-name/last-name; a single field suits the widest range but is hard to split reliably [4]. Android's autofill hints distinguish whole-value hints (`PERSON_NAME`, `PHONE_NUMBER`, `POSTAL_ADDRESS`) from parts [5].

**Evidence: Moderate.** Practitioner testing (Baymard 2013, mobile only), internationalization guidance and design-system consensus. No effect size is published, and guidance conflicts on dates.

**Limitations.**
- Dates: GOV.UK uses three fields (day, month, year) for dates people know, accepting month names, and advises against that component when people do not know the date. Seckler et al.'s guideline 12 prefers one field with a visible format [6][7].
- Back ends sometimes need parts (sort by surname, shipping labels). GOV.UK warns that separate fields add entry errors; collect one field and parse it, or ask for "given names" and "family name" with neutral labels [3][4].
- Baymard's finding is mobile-only [1].
- Card numbers: one field with auto-spacing (FRM-06), never four boxes. Postal addresses normally use separate line, town and postcode fields; city, state and ZIP may share a row (FRM-03).

**How to measure it works.**
- Fields per form; invalid or skipped entries on name and phone; paste success; time to complete; autofill fill rate; support tickets about names.
- Usability test with names from several cultures (one name, two family names, apostrophes, hyphens).

**Implemented by.**
- GOV.UK Design System: names pattern (single or multiple fields by need) and a date input of three fields with month names accepted [4][6].
- W3C Internationalization guidance for names [3]. Android autofill hints [5].

**How to detect it.**
- *Applied:* one "Full name" input; one phone input; one card-number input with grouped display.
- *Violated:* required first and last name plus title and middle name; phone split into area, prefix and line; card number in four inputs; date of birth as three selects with no month names.
- *In code:* `name="(first|last|given|family)_?name"` pairs on forms that only display the name; `name="(area|prefix|line)"` with `maxlength="3"`; four `cc-number` inputs; `maxlength="4"` with auto-advance `focus()` on `keyup`.
- *Quick test:* enter a one-word name, a name with two family names, a pasted phone number with spaces and a pasted card number. Do they all work?

**How to implement.**
1. Use one "Full name" field with `autocomplete="name"` unless the business needs the parts. If it does, label them "Given names" and "Family name", do not require a family name, allow spaces, hyphens and apostrophes, and set no tight length limits [3].
2. Use one phone field with `type="tel"` and `autocomplete="tel"`; parse it with a library (FRM-06).
3. Use one card-number field with grouped display and `autocomplete="cc-number"`; keep expiry and CVC as a short row.
4. For dates people know, use day, month and year inputs that accept month names; for dates they cannot look up, use a picker or a text field with a visible format [6].
5. Remove auto-advance between fields; it breaks paste and autofill.

**Sources.**
[1] Holst, J. (2013, 12 Feb). Mobile Form Usability: Avoid Splitting Single Input Entities. Baymard Institute. https://baymard.com/blog/mobile-form-usability-single-input-fields
[2] Baymard Institute (2024). Checkout form-field benchmark (89% do not use a single name field). https://baymard.com/blog/checkout-flow-average-form-fields
[3] W3C Internationalization. Personal names around the world. https://www.w3.org/International/questions/qa-personal-names
[4] GOV.UK Design System. Names pattern. https://design-system.service.gov.uk/patterns/names/
[5] Android Developers. Optimize your app for autofill. https://developer.android.com/identity/autofill/autofill-optimize
[6] GOV.UK Design System. Date input. https://design-system.service.gov.uk/components/date-input/
[7] Seckler, M. et al. (2014). Designing Usable Web Forms (Table 1, guideline 12). CHI 2014. https://research.google.com/pubs/archive/42513.pdf
