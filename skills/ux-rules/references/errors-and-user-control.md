# Error prevention, recovery and user control (ERR)

Covers how an interface stops mistakes, makes them recoverable, and handles failure: constraints and checks, undo, confirmation, error messages, protecting user work, and clear exits. Load it when auditing destructive actions, dialogs, forms that can fail, sessions and timeouts, wizards, or Back, Esc and Cancel behaviour. Field-level form errors are in FRM-09; this category covers everything around them.

| ID | Rule | Evidence | Applies to |
|---|---|---|---|
| ERR-01 | Prevent errors with constraints and checks | Moderate | forms, destructive controls, compose and send flows |
| ERR-02 | Prefer undo to confirmation for reversible actions | Moderate | delete, archive, move, send, bulk edit |
| ERR-03 | Confirm only irreversible, costly actions, and name the consequence | Moderate | permanent delete, payments, publish, resource or account deletion |
| ERR-04 | Write error messages that are visible, plain, specific and constructive | Strong | any error surface: forms, API failures, system errors |
| ERR-05 | Never lose the user's work | Moderate | forms, editors, long tasks, sessions with timeouts |
| ERR-06 | Provide clearly marked exits: cancel, close, Esc, Back | Moderate | dialogs, wizards, overlays, single-page apps, embedded widgets |

---

### ERR-01 Prevent errors with constraints and checks

**What it is.** Design so the mistake is hard or impossible: constrained inputs, safe defaults, forgiving formats, dangerous controls kept apart. Where a mistake is likely, check before the commit (a missing attachment, an end date before the start date).

**Why it works.**
- Norman separates slips (right goal, wrong action; common on autopilot; experts are prone) from mistakes (wrong goal or wrong mental model). NN/g draws the design lesson: slips are the designer's responsibility, and constraints, suggestions, good defaults and forgiving formats prevent them [1][2].
- Heuristic 5: remove error-prone conditions, or detect them and ask for confirmation before the user commits [3].
- Microsoft's guide says to prevent the error where possible: use controls limited to valid values (lists, sliders, check boxes, radio buttons, date and time pickers) instead of free text, allow drops only on valid targets, disable controls when users can see why, and physically separate destructive commands from routine ones [4][5].
- Poka-yoke (Shingo): build mistake-proofing into the process so errors cannot occur or are caught at the source (Shingo 1986; book, not opened) [6].
- Examples: a flight-date picker that requires departure before return [2]. Gmail's forgotten-attachment detector was announced as a Labs feature on 17 September 2008 (post title and date seen; text not read) [7]. NN/g's 2023 guidance cites a missing-attachment check as a way to catch a likely mistake early [8]. We did not find when the check became a default.
- WCAG 2.2 SC 3.3.4 (AA): pages that make legal commitments, financial transactions or data changes must be reversible, checked or confirmed [9].

**Evidence: Moderate.** Peer-reviewed theory (Norman 1981, 45 years old) plus consistent NN/g and platform guidance. We found no controlled study of the forgotten-attachment prompt or of destructive-control spacing. Required (conditional): WCAG 2.2 SC 3.3.4 (AA).

**Limitations.**
- Over-constraint blocks real edge cases (names, addresses, odd dates). Prefer forgiving input and allow override (see FRM on forgiving formats).
- A disabled button with no visible reason confuses people. Microsoft allows disabling only where the reason is obvious [4].
- Heuristic checks give false positives, and a check that cries wolf trains people to dismiss it (ERR-03).
- Prevention does not fix mistakes that come from a wrong mental model. Those need better information (see CON, NAV).
- Flagging an error before the user could have made one is hostile. Show errors when the user leaves the field or submits (ERR-04) [10].

**How to measure it works.**
- Leading: slip rate per task in usability tests (wrong date, duplicate, wrong item); first-attempt success; resubmission rate.
- Lagging: support tickets for data-entry errors; reversals or refunds caused by user error; duplicate orders.
- A/B: a pre-send omission check against none; count "sent without attachment, then re-sent" messages.

**Implemented by.**
- Gmail: forgotten-attachment detector (Labs, announced 17 September 2008) [7]. No outcome data published.
- Microsoft Windows UX guidelines: constrained controls, constrained interactions, disabled controls [4].
- Travel booking date pickers: NN/g's example of constraint by design [2].

**How to detect it.**
- *Applied:* date inputs with min and max; dropdowns or pickers for finite sets; masks that accept messy input; submit checks for likely omissions with a one-click fix; destructive actions placed apart from routine ones; double-submit protection.
- *Violated:* free-text fields for dates, countries or states; end date selectable before start; "Delete" beside "Save" in the same style; no check for an obvious omission; a double click creates two records.
- *In code:* `type="date" min= max=`, `<select>`, `<input list=`, `maxlength`, `pattern`, `inputmode`, `required`, `setCustomValidity`; `disabled` plus `aria-describedby` giving the reason; server idempotency keys; a regex for "attach" with no check of `files.length`; destructive and primary buttons sharing one class.
- *Quick test:* enter impossible values (end before start, 31 February, negative quantity). Double-click Submit. Ask whether the destructive control can be hit by accident from the usual path. Draft a message that says "attached" and send it with no file.

**How to implement.**
1. List the slip types per screen: wrong item, wrong value, wrong order, duplicate, omission.
2. Swap free text for constrained controls where the domain is finite. Set sensible defaults and limits (`min`, `max`).
3. Accept messy input and normalise it (see FRM).
4. Separate dangerous controls by distance, position and style. Do not put Delete beside Save at equal weight [5].
5. Add checks for likely omissions with a one-click fix ("Attach file" or "Send anyway"). Tune them so false positives stay rare.
6. Make submits idempotent and lock the button while pending (FBK-01).
7. Add a safety net: Undo (ERR-02), and confirmation only for irreversible, costly actions (ERR-03).

**Sources.**
[1] Norman, D. A. (1981). Categorization of action slips. Psychological Review 88(1), 1-15. https://doi.org/10.1037/0033-295X.88.1.1 (bibliographic data checked at Crossref; paper not read)
[2] Laubheimer, P. (2015, 23 Aug). Preventing User Errors: Avoiding Unconscious Slips. NN/g. https://www.nngroup.com/articles/slips/
[3] Nielsen, J. (1994, reviewed 2024). 10 Usability Heuristics for User Interface Design. NN/g. https://www.nngroup.com/articles/ten-usability-heuristics/
[4] Microsoft. Error Messages (Windows 7 UX guide, still online). https://learn.microsoft.com/en-us/windows/win32/uxguide/mess-error
[5] Microsoft. Confirmations (Windows 7 UX guide). https://learn.microsoft.com/en-us/windows/win32/uxguide/mess-confirm
[6] Shingo, S. (1986). Zero Quality Control: Source Inspection and the Poka-yoke System. Productivity Press. (book; not opened)
[7] Gmail Blog (2008, 17 Sep). New in Labs: Forgotten attachment detector (listing only). https://gmail.googleblog.com/2008/
[8] Neusesser, T., Sunwall, E. (2023, 14 May). Error-Message Guidelines. NN/g. https://www.nngroup.com/articles/error-message-guidelines/
[9] W3C. Understanding SC 3.3.4 Error Prevention (Legal, Financial, Data) (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/error-prevention-legal-financial-data.html
[10] Kaplan, K. (2022, 30 Oct). Hostile Patterns in Error Messages. NN/g. https://www.nngroup.com/articles/hostile-error-messages/

---

### ERR-02 Prefer undo to confirmation for reversible actions

**What it is.** Let the action happen at once and give a way back (an Undo link, a trash, version history, a delayed send) instead of asking "Are you sure?" first.

**Why it works.**
- Habit: people click through frequent confirmations without reading, so a dialog does not guard against the slip it was built for. Raskin (A List Apart, 21 July 2007) argues that louder warnings get dismissed faster, that harder-to-ignore ones (typing a name) distract and annoy, and that the answer is to allow the action and make it reversible. He noted that Gmail already offered Undo after a delete [1]. The longer case is in The Humane Interface (2000; book, not opened) [2].
- NN/g (Nielsen, 18 February 2018): Undo is a better safeguard than confirmation, because some errors get past even well-made dialogs [3]. Heuristic 3 asks for clearly marked exits and for undo and redo [4].
- Microsoft's guide agrees: deleting a file needs no confirmation because the Recycle Bin allows recovery, and a confirmation that nearly everyone accepts (the guide's example is 98%) should go [5]. Undo only helps if people notice the mistake, so pair it with visible feedback [5] (see FBK-07).
- WCAG 2.2 SC 3.3.4 (AA) lists "reversible" as one of three ways to protect legal, financial and data-changing pages [6].
- Examples: Gmail Undo Send was in Labs from 19 March 2009 and left Labs in 2015; the bar reads "Message sent / Undo / View message" and the cancel window is 5, 10, 20 or 30 s [7][8][9]. Google Docs version history lets people open and restore earlier versions and name up to 40 [10]. GitHub can restore some deleted repositories within 90 days [11]. Google Cloud fully deletes soft-deleted projects after 30 days [12]. Apple Photos "Recently Deleted" keeps items 30 days (Apple's page not opened; unverified).

**Evidence: Moderate.** Expert argument and platform consensus (2000 to 2018). We found no head-to-head experiment of undo against confirmation. Required (conditional): WCAG 2.2 SC 3.3.4 (AA), where "reversible" is one allowed option.

**Limitations.**
- Some actions cannot be undone: payments, delivered messages, physical actions, effects on other people. Undo Send works by holding the message for up to 30 s before it leaves [8].
- A 5-second toast is easy to miss (see FBK-07). For deletions also offer a longer-lived route (trash, history).
- Soft deletion costs storage and can clash with privacy rules (right to erasure) and security. Set a retention period and offer "Delete permanently" (ERR-03).
- Undo in collaborative or multi-device apps is hard: whose action is undone? Define scope per user and per object.
- Undo does not help when people do not realise an error occurred [5].

**How to measure it works.**
- Leading: undo rate per action (a high rate may flag an error-prone control, or a net that works); time to recover from a deliberate slip in usability tests.
- Lagging: accidental-deletion tickets; data-recovery requests; "restore from trash" use.
- A/B: replace a routine confirmation with Undo; compare completion time and accidental-deletion tickets.

**Implemented by.**
- Gmail (Labs 2009; out of Labs 2015): Undo Send [7][8][9]. Delete with Undo was in place by 2007 [1].
- Google Docs (version history, named versions) [10]; GitHub (restore window for some repositories) [11]; Google Cloud (30-day soft delete) [12].
- Windows: the Recycle Bin instead of delete confirmations [5].
- No published outcome numbers for any of these.

**How to detect it.**
- *Applied:* an Undo link after delete, archive, move or send; a Trash or Recently Deleted area with a stated retention period; Ctrl/Cmd+Z in editors; version history; no dialog on routine reversible actions.
- *Violated:* "Are you sure?" before routine delete or archive; permanent deletion with no trash; no undo in editors; an Undo toast under 3 s; no undo for bulk actions.
- *In code:* `window.confirm(` in delete handlers for reversible items; `deleted_at`, `deletedAt`, `is_deleted`, `archived`; `Snackbar` with `setAction("Undo"`; undo and redo stacks; `onKeyDown` handling `ctrlKey || metaKey` with `z`; `UndoManager` (iOS and macOS); delayed-send queues.
- *Quick test:* delete, archive and move an item. Is Undo one click away? Wait 10 s: can it still be reversed (trash)? Press Ctrl/Cmd+Z in an editor. Find the trash and note the retention period.

**How to implement.**
1. Sort actions by reversibility. For reversible ones, execute at once (see FBK-04) and offer Undo.
2. Show an Undo toast for 5 to 10 s (FBK-07) and keep a durable route: Trash or Recently Deleted for a stated period (30 days is common [12]).
3. Implement soft delete (`deleted_at`) with a purge job, and a "Delete permanently" action behind ERR-03.
4. For send-type actions, hold the commit in an outbox for 5 to 30 s with Undo [8].
5. In editors add an undo stack and the standard shortcut. For documents keep version history.
6. State plainly what cannot be undone, and use ERR-03 for it.

**Sources.**
[1] Raskin, A. (2007, 21 Jul). Never Use a Warning When You Mean Undo. A List Apart. https://alistapart.com/article/neveruseawarning/
[2] Raskin, J. (2000). The Humane Interface. Addison-Wesley. (book; not opened)
[3] Nielsen, J. (2018, 18 Feb). Confirmation Dialogs Can Prevent User Errors (If Not Overused). NN/g. https://www.nngroup.com/articles/confirmation-dialog/
[4] Nielsen, J. (1994, reviewed 2024). 10 Usability Heuristics for User Interface Design. NN/g. https://www.nngroup.com/articles/ten-usability-heuristics/
[5] Microsoft. Confirmations (Windows 7 UX guide). https://learn.microsoft.com/en-us/windows/win32/uxguide/mess-confirm
[6] W3C. Understanding SC 3.3.4 (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/error-prevention-legal-financial-data.html
[7] Gmail Blog (2009, 19 Mar). New in Labs: Undo Send (listing only). https://gmail.googleblog.com/2009/03/
[8] Google. Unsend an email (Gmail Help). https://support.google.com/mail/answer/1284885
[9] Wikipedia, Gmail, citing The Next Web (2015, 23 Jun) on Undo Send leaving Labs. https://en.wikipedia.org/wiki/Gmail (primary article not opened)
[10] Google. Docs Editors Help: version history (answer 190843). https://support.google.com/docs/answer/190843
[11] GitHub Docs. Deleting a repository. https://docs.github.com/en/repositories/creating-and-managing-repositories/deleting-a-repository
[12] Google Cloud. Creating and managing projects (Resource Manager). https://docs.cloud.google.com/resource-manager/docs/creating-managing-projects

---

### ERR-03 Confirm only irreversible, costly actions, and name the consequence

**What it is.** Keep confirmation dialogs for actions that cannot be undone or that cost a lot. Say what will happen to what, use verb buttons, and default to the safe choice. For the most destructive actions, ask for a non-routine step such as typing the resource's name.

**Why it works.**
- Overused confirmations are ignored. Nielsen (2018): frequent dialogs train people to click through; "Are you sure?" gives nothing to check; label buttons with the action ("Delete file" and "Keep file"); do not default to the dangerous option; ask for a typed word only for the most dangerous actions, and rarely, or it becomes automatic [1].
- Microsoft's confirmation guide: confirm actions with significant or unintended consequences; remove a confirmation that is accepted almost always (its example is 98%); say "permanently" for irreversible actions; default to the safe response for risky ones; do not confirm when a user abandons a task [2].
- Habituation is measured. Bravo-Lillo et al. (SOUPS 2013) ran three online experiments with Amazon Mechanical Turk workers. "Inhibitive attractors" (delays or required actions that held back the hazardous option until attention was drawn to the key field) cut the share choosing the less safe option by up to 50%. After many repeats of a harmless dialog, preferred attractors made people two to three times more likely to notice a changed message [3]. Anderson et al. (CHI 2015, fMRI) report that brain responses fall with repeated exposure to the same warning and that varied "polymorphic" warnings reduce the drop (bibliographic data checked; findings not checked against the source, abstract not re-read) [4].
- Warnings can work when they are rare and well made. Akhawe and Felt (USENIX Security 2013) logged 25,405,944 browser warning impressions. Users clicked through 9% to 23% of malware and phishing warnings, 33.0% of Firefox SSL warnings and 70.2% of Chrome SSL warnings [5].
- Raskin's counterpoint: typing a name to confirm distracts, annoys and slows people, so keep it rare [6].
- Industry patterns: GitHub puts repository deletion in a Danger Zone, lists the effects and asks you to type the repository name; some deleted repositories can be restored within 90 days, not all [7]. In the AWS S3 console you type the bucket name to delete it; the bucket must be empty; AWS cannot restore a deleted bucket; another account can later claim the name [8]. Google Cloud soft-deletes projects for 30 days [9].
- WCAG 2.2 SC 3.3.4 (AA) lists "confirmed" as one option for legal, financial and data-deleting pages [10].

**Evidence: Moderate.** Habituation is shown in lab and field work (2013 to 2015). We found no controlled test of type-to-confirm or of consequence wording. Required (conditional): WCAG 2.2 SC 3.3.4 (AA), where "confirmed" is one allowed option.

**Limitations.**
- Type-the-name adds friction, becomes automatic when used often, and can be defeated by copy and paste [1][6].
- A confirmation moves the decision; it does not stop slips. Prefer Undo wherever the action can be reversed (ERR-02).
- "Don't show this again" on a risky confirmation hides information people need [2].
- Guilt-trip button text ("No, I don't want to save money") is a deceptive pattern (see CHO).
- Click-through varies from 9% to 70% by design [5], so test your own dialogs.
- Dialog accessibility: focus moves into the dialog and, for irreversible actions, may start on the least destructive button [11].

**How to measure it works.**
- Leading: proceed rate per confirmation (near 98% or more suggests removing it [2]); a comprehension check in tests ("What will be deleted?").
- Lagging: accidental-deletion and restore requests; support tickets; time added to the task.
- A/B: the current dialog against a consequence-naming version; compare regret tickets and cancel rate.

**Implemented by.**
- GitHub (repository deletion): Danger Zone, effects listed, type the name, limited restore window [7].
- AWS S3 console: type the bucket name; no restore by AWS; name-reuse warning [8].
- Google Cloud: project shutdown with 30-day soft delete [9].
- No published outcome numbers for any of them.

**How to detect it.**
- *Applied:* the title names the object ("Delete project Atlas?"); the body says what is lost and how much ("permanently deletes 14 deployments"); buttons are verbs with the safe one as default; a typed name only for catastrophic actions; confirmations are rare.
- *Violated:* "Are you sure?" with Yes/No before every delete; OK/Cancel labels; a confirmation on easily undone actions; the destructive button focused by default; "Don't ask again" on risky actions; every button red.
- *In code:* `window.confirm(`, `confirm(`; `alert(` used as a prompt; `AlertDialog` with `AlertDialogAction` (Radix, shadcn); a `<dialog>` where the destructive button has `autofocus`; `disabled={value !== resourceName}` on a confirm button; iOS `UIAlertController` with `.destructive`; Android `AlertDialog.Builder` with "OK" and "Cancel".
- *Quick test:* trigger every destructive action. Count dialogs per task. For each, can you tell from the dialog alone what will be lost? What is focused by default? Is typing required, and only for catastrophic actions?

**How to implement.**
1. Build a matrix of reversibility and cost. Reversible: no dialog, use Undo (ERR-02). Irreversible and cheap: a short confirmation. Irreversible and costly (resource, account, bulk): a consequence dialog, with a typed name for the largest.
2. Copy: title "Delete <name>?"; body says what is lost, how many items, "permanently" if true; buttons "Delete <thing>" (destructive style) and "Keep <thing>"; default focus on the safe button [1][2][11].
3. For catastrophic deletes add a cooldown or soft-delete window and an email notice.
4. Do not confirm abandoning a task, except to protect unsaved work (ERR-05) [2].
5. Log proceed rates and remove confirmations that nearly everyone accepts.
```html
<dialog id="del" aria-labelledby="t"><form method="dialog">
  <h2 id="t">Delete project Atlas?</h2>
  <p>This permanently deletes 14 deployments and cannot be undone.</p>
  <button value="keep" autofocus>Keep project</button> <button value="delete">Delete project</button>
</form></dialog>
```

**Sources.**
[1] Nielsen, J. (2018, 18 Feb). Confirmation Dialogs Can Prevent User Errors (If Not Overused). NN/g. https://www.nngroup.com/articles/confirmation-dialog/
[2] Microsoft. Confirmations (Windows 7 UX guide). https://learn.microsoft.com/en-us/windows/win32/uxguide/mess-confirm
[3] Bravo-Lillo, C., Cranor, L. F., Downs, J., Komanduri, S., Reeder, R. W., Schechter, S., Sleeper, M. (2013). Your Attention Please: Designing security-decision UIs to make genuine risks harder to ignore. SOUPS 2013. https://cups.cs.cmu.edu/soups/2013/proceedings/a6_Bravo-Lillo.pdf
[4] Anderson, B. B., Kirwan, C. B., Jenkins, J. L., Eargle, D., Howard, S., Vance, A. (2015). How Polymorphic Warnings Reduce Habituation in the Brain: Insights from an fMRI Study. CHI '15, pp. 2883-2892. https://doi.org/10.1145/2702123.2702322 (bibliographic data checked at Crossref; abstract not available to me)
[5] Akhawe, D., Felt, A. P. (2013). Alice in Warningland: A Large-Scale Field Study of Browser Security Warning Effectiveness. USENIX Security 2013. https://www.usenix.org/system/files/conference/usenixsecurity13/sec13-paper_akhawe.pdf
[6] Raskin, A. (2007, 21 Jul). Never Use a Warning When You Mean Undo. A List Apart. https://alistapart.com/article/neveruseawarning/
[7] GitHub Docs. Deleting a repository. https://docs.github.com/en/repositories/creating-and-managing-repositories/deleting-a-repository
[8] AWS. Deleting a general purpose bucket (Amazon S3 User Guide). https://docs.aws.amazon.com/AmazonS3/latest/userguide/delete-bucket.html
[9] Google Cloud. Creating and managing projects (Resource Manager). https://docs.cloud.google.com/resource-manager/docs/creating-managing-projects
[10] W3C. Understanding SC 3.3.4 (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/error-prevention-legal-financial-data.html
[11] W3C. ARIA Authoring Practices Guide: Dialog (Modal) pattern. https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/

---

### ERR-04 Write error messages that are visible, plain, specific and constructive

**What it is.** When something fails, say that it failed, which thing, why in the user's terms, and what to do next. Put the message where people look, keep the tone neutral, and expose it to assistive technology. (Field-level form errors are in FRM-09.)

**Why it works.**
- Heuristic 9: plain language without codes, a precise statement of the problem, a constructive fix [1].
- NN/g's 2023 guidelines (Neusesser and Sunwall): put the message next to the cause; use more than colour; match the style to severity; describe the specific problem; offer next steps; do not blame ("invalid", "incorrect"); keep the user's input; catch likely mistakes early. The article rests on annotated examples, not new experiments [2].
- NN/g (Kaplan, 2022): errors shown before the user could have erred, and error styling on non-errors, make forms feel hostile. Again critique-based, with no user study [3].
- Microsoft's guide: a good message states a problem, a cause and a solution, and is relevant, actionable, user-centred, brief, clear, specific, courteous and rare. It names failures to avoid: unnecessary errors, "success" errors, useless or incomprehensible text, over-long text, harsh or blaming tone, programmer messages left in release builds [4].
- Standards: WCAG 3.3.1 Error Identification (A) asks you to identify the field and describe the error in text. 3.3.3 Error Suggestion (AA) asks for correction suggestions when known, unless that would harm security or the purpose. 4.1.3 Status Messages (AA) asks for errors to be announced without moving focus [5][6][7].

**Evidence: Strong.** Formal standards cover identification, text description and suggestions. The wording and tone guidance rests on expert review (NN/g 2023; Microsoft's Windows 7-era guide). Required: WCAG 2.2 SC 3.3.1 (A), 3.3.3 (AA), 4.1.3 (AA).

**Limitations.**
- Specific can conflict with secure. A login error should not reveal which of username or password was wrong (the SC 3.3.3 security exception) [6].
- Too much detail overwhelms. Put codes and traces in an expandable detail or a log [4].
- Humour wears thin on repeat encounters [2].
- Errors that vanish (a toast) fail visibility (FBK-07). Keep them until fixed.
- Raising errors too early is hostile (see FRM on inline validation) [3].
- Machine-generated API errors need mapping to user-level text.

**How to measure it works.**
- Leading: recovery rate (users who fix the problem and continue); time to recover; repeat-error rate.
- Lagging: abandonment after an error; support contacts per error code.
- Test: ask participants what went wrong and what to do next, from the message alone. Audit SC 3.3.1, 3.3.3 and 4.1.3.

**Implemented by.**
- Microsoft (Windows UX guidelines, Windows 7 era; page dated 2022): problem, cause, solution [4].
- NN/g (2023) and W3C (WCAG 2.2) as published guidance [2][5][6].
- Apple HIG and Material error guidance: those pages are script-rendered and could not be read here. No company outcome data found.

**How to detect it.**
- *Applied:* a message beside the control, plus a summary with links when there are several; icon, text and colour together; says what and how to fix ("Enter a date after 3 Nov 2026"); `role="alert"`; focus moves to the first error or the summary; input kept; neutral tone.
- *Violated:* "Error", "Something went wrong", "Invalid input", "Error 0x80004005"; bare HTTP codes; red as the only cue; a message that disappears; blame ("You entered an invalid..."); `alert()` popups; the error below the fold; stack traces shown to users.
- *In code:* `aria-invalid="true"`, `aria-describedby`, `aria-errormessage`, `role="alert"`, `aria-live="assertive"`; literal strings such as `"Something went wrong"`, `"An error occurred"`, `"Invalid"`; `catch (e) { alert(e.message) }`; rendering `error.message` or `error.stack` raw; `catch` blocks that only `console.error`.
- *Quick test:* trigger five failures: blank required field, bad format, network offline, server 500, expired session. For each: visible without scrolling? says what, why and next step? input kept? announced by a screen reader? no blame?

**How to implement.**
1. Use a template: what happened, why (if it helps), what to do. "We could not save your changes because you are offline. They will be saved when you reconnect."
2. Map system and API errors to user-level text. Keep codes and reference IDs in an expandable detail [4].
3. Place the message at the cause. Add a summary at the top for several errors. Keep it until fixed. Do not rely on colour [2].
4. Markup: `aria-invalid`, `aria-describedby`, and `role="alert"` for dynamic errors. Move focus to the first error after a failed submit [5][7].
5. Offer a fix action: Retry, Edit field, Reconnect, or Contact support with a reference ID.
6. Have a writer review the messages and test them with real users [4].
```html
<label for="d">Delivery date</label>
<input id="d" aria-invalid="true" aria-describedby="d-err">
<p id="d-err" role="alert">Choose a date after 3 Nov 2026. We cannot deliver on past dates.</p>
```

**Sources.**
[1] Nielsen, J. (1994, reviewed 2024). 10 Usability Heuristics for User Interface Design (heuristic 9). NN/g. https://www.nngroup.com/articles/ten-usability-heuristics/
[2] Neusesser, T., Sunwall, E. (2023, 14 May). Error-Message Guidelines. NN/g. https://www.nngroup.com/articles/error-message-guidelines/
[3] Kaplan, K. (2022, 30 Oct). Hostile Patterns in Error Messages. NN/g. https://www.nngroup.com/articles/hostile-error-messages/
[4] Microsoft. Error Messages (Windows 7 UX guide). https://learn.microsoft.com/en-us/windows/win32/uxguide/mess-error
[5] W3C. Understanding SC 3.3.1 Error Identification (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html
[6] W3C. Understanding SC 3.3.3 Error Suggestion (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/error-suggestion.html
[7] W3C. Understanding SC 4.1.3 Status Messages (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html

---

### ERR-05 Never lose the user's work

**What it is.** Save drafts automatically or keep input safe. Keep what the user typed after validation errors, timeouts, crashes, Back navigation and re-login. Warn before discarding unsaved changes.

**Why it works.**
- Lost work means redoing effort and losing trust, and it hits slow or interrupted users hardest. WCAG 2.2 SC 2.2.6 Timeouts (AAA) asks you to warn users about an inactivity period that causes data loss, unless data is kept at least 20 hours. It is written for people who need more time, including people with cognitive disabilities [1].
- WCAG 2.2 SC 2.2.5 Re-authenticating (AAA): after a session expires the user can log in again and continue without losing data [2]. SC 2.2.1 (A) requires time limits to be adjustable, extendable or removable [3].
- NN/g's error-message guidance: keep the user's input so they can edit instead of starting over [4].
- Nielsen (2000): a Reset button beside Submit wipes input when pressed by mistake. Remove it from most forms and make every entry easy to undo [5].
- The back/forward cache restores a page from memory as it was left, with no network requests. Chrome data cited by web.dev says about 1 in 10 desktop and 1 in 5 mobile navigations are back or forward [6].
- Google Docs keeps version history with restore [7]. Autosave itself is widely known, but we did not find a help page stating it.
- Baymard (a lead from the brief): we could not find a public figure for how many checkouts clear card fields after an error. Treat any such number as unverified.

**Evidence: Moderate.** Standards (SC 2.2.1 at A, 3.3.4 at AA, 2.2.5 and 2.2.6 at AAA) plus NN/g guidance. No controlled study of abandonment after data loss found. Required: WCAG 2.2 SC 2.2.1 (A) for time limits; SC 3.3.4 (AA) for data-changing pages. SC 2.2.5 and 2.2.6 are AAA (optional).

**Limitations.**
- Privacy and security: do not persist card numbers, CVV or passwords. WCAG notes that privacy law may require consent before storing data [1].
- Autosave collides with multi-device edits and stale drafts. Version and merge, or lock.
- Banking-style timeouts are legitimate. Warn and let users extend them (SC 2.2.1) [3].
- Autosave can confuse people who expect an explicit Save or Publish. Show state ("Saving", "Saved", "Offline") and keep publishing explicit.
- `beforeunload` prompts are generic and annoying. Use them only while changes are unsaved.

**How to measure it works.**
- Leading: restore-draft acceptance rate; share of failed submits that keep all input.
- Lagging: "lost my work" tickets; abandonment after a validation error or timeout; resubmission rate.
- Test: fill a long form, trigger an error, refresh, close the tab, expire the session; record what survives.

**Implemented by.**
- Google Docs: version history with restore, and up to 40 named versions in Docs [7].
- Web platform: back/forward cache restores pages instantly [6]. W3C techniques G105 and G181 keep data across re-authentication [2].
- No published outcome numbers found.

**How to detect it.**
- *Applied:* after a failed submit every field except passwords keeps its value; a save indicator ("Saved"); "Restore draft?" after a crash; session expiry shows an in-place login that keeps the form; leaving with unsaved changes prompts; Back returns to a filled form.
- *Violated:* the form comes back empty after a server error; card fields cleared on any error; a session timeout loses a long form; Reset beside Submit; closing a modal discards typed text silently; a refresh wipes an editor.
- *In code:* server templates that do not re-populate `value=`; `form.reset()` after a failed request; `localStorage.setItem('draft'` or IndexedDB drafts; `beforeunload` handlers; `visibilitychange` flushes; `<input type="reset">`; debounced save hooks; `autocomplete` attributes; a session-expiry path that redirects without saving.
- *Quick test:* fill a long form and submit with one error: are the other fields kept? Delete the session cookie and submit: is the data kept? Type in an editor, then refresh, close the tab and go offline: what comes back?

**How to implement.**
1. Autosave on change to a server draft (or local storage for non-sensitive data), debounced to a second or two (design judgement). Show Saving, Saved, Offline.
2. On validation failure, re-render with the submitted values. Clear only passwords or CVV, and say so.
3. Sessions: warn before timeout with an Extend action (SC 2.2.1). On expiry show re-login in place and keep the form state (SC 2.2.5; techniques G105 or G181) [2][3].
4. Use `beforeunload` only while changes are unsaved, and remove it after saving.
5. Queue writes while offline and retry when back (see PLT on poor networks).
6. Drop Reset buttons. Where reset is needed, confirm it or offer Undo [5].
7. For documents, keep version history [7].
```js
let dirty = false;                                   // set true on input, false after save
addEventListener('beforeunload', e => { if (dirty) e.preventDefault(); });
```

**Sources.**
[1] W3C. Understanding SC 2.2.6 Timeouts (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/timeouts.html
[2] W3C. Understanding SC 2.2.5 Re-authenticating (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/re-authenticating.html
[3] W3C. Understanding SC 2.2.1 Timing Adjustable (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html
[4] Neusesser, T., Sunwall, E. (2023, 14 May). Error-Message Guidelines. NN/g. https://www.nngroup.com/articles/error-message-guidelines/
[5] Nielsen, J. (2000, 15 Apr). Reset and Cancel Buttons. NN/g. https://www.nngroup.com/articles/reset-and-cancel-buttons/
[6] Google. Back/forward cache. web.dev (published 25 May 2023). https://web.dev/articles/bfcache
[7] Google. Docs Editors Help: version history (answer 190843). https://support.google.com/docs/answer/190843

---

### ERR-06 Provide clearly marked exits: cancel, close, Esc, Back

**What it is.** Every mode, dialog, wizard, overlay and flow has an obvious way out that returns the user to a safe state: a visible Close or Cancel, Esc, a Back button that works, and no keyboard traps.

**Why it works.**
- Heuristic 3: people choose functions by mistake and need a clearly marked emergency exit that does not take a long process. Support undo and redo [1].
- WCAG 2.2 SC 2.1.2 No Keyboard Trap (A): if keyboard focus can enter a component, it can leave by keyboard. If the way out needs more than standard keys, tell the user. A modal dialog may restrict focus if it closes with Cancel, OK or Esc [2].
- ARIA Authoring Practices, modal dialog: Esc closes the dialog, Tab and Shift+Tab stay inside it, and focus returns to the element that opened it [3].
- Back is heavily used. Chrome data cited by web.dev: about 1 in 10 desktop and 1 in 5 mobile navigations are back or forward [4]. Early browsing-log studies (Catledge and Pitkow 1995; Tauscher and Greenberg 1997, IJHCS 47(1):97-137) are the usual citations for heavy Back use. We could not open them, so no percentages are given [5].
- Nielsen (2000): people usually leave an unwanted page with Back, so a Cancel button matters mainly in multi-step processes. He also asks for a Stop control on actions that take more than a few seconds [6].
- Single-page apps can break Back. Content swapped without a history entry makes Back skip past the app's own navigation. The fix is `history.pushState`, a `popstate` handler, and `replaceState` for the initial entry [7].

**Evidence: Moderate.** Heuristic- and standards-based, with usage data. No controlled study of exit visibility found. Required: WCAG 2.2 SC 2.1.2 (A) for keyboard exit.

**Limitations.**
- Exiting can lose work. Pair with ERR-05: offer Save draft or Discard, not a silent loss.
- "Cancel" is ambiguous (cancel the dialog or the order?). Use specific labels ("Keep editing", "Discard changes"). Microsoft advises against OK and Cancel on confirmations [8].
- Some steps cannot be abandoned midway (payment authorisation, required consent). Still provide an exit from the whole flow.
- Hijacking Back, or hiding a tiny close button on a full-screen interstitial, is a deceptive pattern (see CHO).
- Mobile: system Back, swipe-back and Esc differ by platform. Overriding them breaks conventions (see PLT, A11Y).
- Stacked modals make exits unclear (see INT on modes and modals).

**How to measure it works.**
- Leading: time and success to leave each dialog in a usability test; keyboard-only exit pass; Esc handler coverage.
- Behaviour: rage clicks on overlays; share of sessions with Back right after a navigation; SPA Back error reports.
- Lagging: bounce from interstitials; abandonment in wizards; "I'm stuck" support contacts.

**Implemented by.**
- W3C ARIA Authoring Practices (modal dialog pattern) and WCAG 2.1.2 as published specifications [2][3].
- Web platform: the History API for SPAs [7]. The native `<dialog>` element closes on Esc and returns focus to the opener (HTML behaviour; not checked against the spec here).
- No company outcome data found.

**How to detect it.**
- *Applied:* a visible Close (X with an accessible name) and a Cancel next to the primary action; Esc closes; a click on the backdrop closes non-destructive modals; Back returns to the previous in-app state; a wizard's Back/Previous keeps entries; focus returns to the trigger.
- *Violated:* a modal with no close; a tiny low-contrast X; Esc ignored; Back leaves the site from an SPA, or exits a wizard and loses data; focus trapped with no exit; full-screen overlays; a Cancel that does not cancel; no Stop on a running operation.
- *In code:* `<dialog>` with `showModal()`; `aria-modal="true"`; `onKeyDown` checking `Escape`; `aria-label="Close"`; `history.pushState`, `popstate`, `replaceState`; `navigate(-1)`; `location.replace(` or `window.location.href =` used for in-app navigation; `focus-trap` with `escapeDeactivates: false`; positive `tabindex` loops.
- *Quick test:* keyboard only: open every dialog, menu and overlay, press Esc, then Tab. Can you leave? Go three steps into a flow and press Back: where do you land? On mobile use system Back and swipe-back: does the overlay close or does the app exit? Start a long operation: is there Stop?

**How to implement.**
1. Give every modal and wizard a visible Close (with `aria-label`) and, where a decision is involved, an explicit Cancel in a consistent place.
2. Use native `<dialog>` with `showModal()` or the ARIA modal pattern: Esc closes, focus moves in and returns to the trigger, Tab stays inside [3].
3. Keep Back meaningful in SPAs: `pushState` for each meaningful view change, restore from `popstate`, and `replaceState` for the starting entry [7].
4. Wizards: a Back/Previous control that keeps entered data, and "Save and exit" for long flows.
5. Long operations: add Stop (FBK-02). Do not ask for confirmation to leave unless work would be lost (ERR-05).
6. If a component needs a non-standard key to exit, say so on screen (SC 2.1.2) [2].
7. Label exits by outcome, not "OK" and "Cancel".
```html
<dialog id="d" aria-labelledby="t">
  <h2 id="t">Invite people</h2>
  <form method="dialog"><button value="cancel">Cancel</button> <button value="send">Send invites</button></form>
</dialog>
<button onclick="d.showModal()">Invite</button>   <!-- Esc closes; focus returns here -->
```

**Sources.**
[1] Nielsen, J. (1994, reviewed 2024). 10 Usability Heuristics for User Interface Design (heuristic 3). NN/g. https://www.nngroup.com/articles/ten-usability-heuristics/
[2] W3C. Understanding SC 2.1.2 No Keyboard Trap (WCAG 2.2). https://www.w3.org/WAI/WCAG22/Understanding/no-keyboard-trap.html
[3] W3C. ARIA Authoring Practices Guide: Dialog (Modal) pattern. https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
[4] Google. Back/forward cache. web.dev (published 25 May 2023). https://web.dev/articles/bfcache
[5] Tauscher, L., Greenberg, S. (1997). How people revisit web pages: empirical findings and implications for the design of history systems. International Journal of Human-Computer Studies 47(1), 97-137. https://doi.org/10.1006/ijhc.1997.0125 (bibliographic data checked at Crossref; paper not opened). Catledge, L. D., Pitkow, J. E. (1995). Characterizing browsing strategies in the World-Wide Web. WWW3 (not opened).
[6] Nielsen, J. (2000, 15 Apr). Reset and Cancel Buttons. NN/g. https://www.nngroup.com/articles/reset-and-cancel-buttons/
[7] MDN. Working with the History API. https://developer.mozilla.org/en-US/docs/Web/API/History_API/Working_with_the_History_API
[8] Microsoft. Confirmations (Windows 7 UX guide). https://learn.microsoft.com/en-us/windows/win32/uxguide/mess-confirm
