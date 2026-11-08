# Voice typing that learns the owner's voice

Date: 2026-11-08. Status: proposed; nothing built. Builds on [Voice typing in every app](2026-11-07-voice-typing.md)
(decisions V1-V14). Code: `scripts/stacklib/dictation/`.

## Ask

The owner wants voice typing to get better for their own voice and words over time, like Pixel's keyboard: fewer
mis-heard names and terms, a cleanup that keeps their wording, and a path to adapt Whisper itself to their voice.

Whisper does not learn while it runs. Each run starts from the same weights. So "learning" here means three things,
cheapest first:

1. **Tell it more.** Better prompts and word lists for Whisper and for the cleanup model.
2. **Fix it after.** Rules that replace known mis-hearings.
3. **Train it.** A LoRA fine-tune of Whisper on the owner's own recordings and corrections, only if 1 and 2 are not
   enough.

## Start here (next session)

1. Read the voice-typing plan above, `scripts/stacklib/dictation/cleanup.py`, `engine.py` and `textops.py`, and the
   `dictation:` block in `machines/_defaults.yaml`.
2. Packages P1 and P2 need no owner decision and change no privacy behaviour. Start with them.
3. Before P3, ask the owner decisions L1-L3 below. P3 and P4 store the owner's voice on disk, which V13 forbids today.
4. Work on a branch, keep `tests/test_dictation.py` and `tests/test_tray_coverage.py` passing, and follow AGENTS.md
   (rule 10: no owner identity in the repo; rule 11: every new setting shows in the tray).

## What exists already (2026-11-07)

| Piece | Where | State |
|---|---|---|
| Whisper hotwords | `dictation.vocabulary` -> `engine._decode(hotwords=...)` | Works; the setting is empty on the reference machine. |
| Whisper prompt | `initial_prompt` = the text so far in the recording | Works; carries context between phrases only. |
| Cleanup | `cleanup.polish()` via `local-small`, JSON mode, `think: false`, temperature 0.2, `acceptable()` guard | Works; system prompt has rules but no examples; no vocabulary. |
| Rule fallback | `textops.strip_fillers()` | Works. |
| Spoken formatting | "new line", "new paragraph" | Works; nothing for lists or punctuation words. |
| Audio | Memory only (V13) | No recordings, no transcripts, no corrections kept. |
| Evaluation | `tests/test_dictation.py` (unit) | No word error rate, no cleanup quality set. |

## Decisions to ask the owner

| # | Question | Options | Proposed default |
|---|---|---|---|
| L1 | May the app keep recordings and transcripts for learning? (changes V13) | Never / opt-in per session / opt-in setting | Opt-in setting `dictation.learn: off`; when on, the button shows a visible "learning" mark. |
| L2 | Where does the learning data live? | A folder under `agent_access.allowed_roots`, chosen by the owner | `dictation.learn_dir: ''` = refuse to store. No default path is guessed. |
| L3 | How long is it kept? | 30 days / 90 days / until deleted | 90 days, then the audio is deleted and only text pairs stay. |
| L4 | When is fine-tuning worth it? | Gate in P5 | At least 1 h of paired speech, and P1-P2 leave pronunciation errors, not vocabulary errors. |

## Packages

### P1. Better prompts (no new data, no privacy change)

- Add 3-4 few-shot examples to the cleanup request as earlier user/assistant turns in the same JSON shape. One example
  must be a dictated question that comes back as a question. Small models follow examples better than rules.
- Pass `dictation.vocabulary` to the cleanup prompt as "Spell these exactly: ...", so the 9B fixes near-misses that
  Whisper's hotwords did not.
- Give Whisper a fixed prompt prefix built from the vocabulary when the recording has no text yet (first phrase), then
  the text so far as today.
- Extend spoken formatting: "bullet point" / "next bullet" -> `- ` at line start; "comma", "period", "full stop",
  "question mark" when said as commands. Do it in `textops` by rule before the cleanup, so it works in live mode and
  when the gateway is down.
- Add a rule for numbers, times, money and units in standard form (e.g. "3:30 pm", "$20").

### P2. Replacements and an offline eval (no privacy change)

- New setting `dictation.replacements`: a list of `heard -> meant` pairs (e.g. `are to are -> R2R`), applied by
  `textops` after Whisper, whole words, case-insensitive. Show and edit it in the tray's Settings (rule 11).
- New eval set `evals/dictation-cleanup/`: 30-50 synthetic raw transcripts with expected outputs, covering fillers,
  self-corrections, questions, instructions, lists, numbers and non-English text. Score: exact or near match,
  "answered instead of cleaned", "dropped content", "added content". Run it through `local-small` from a
  `stack.py dictate eval-cleanup` command. Record the baseline before P1 lands and the result after.

### P3. A personal test set and word error rate (needs L1-L3)

- `stack.py dictate record-test`: shows 20-30 sentences (generic plus the vocabulary words), records the owner reading
  each, saves WAV + reference text in `learn_dir/testset/`.
- `stack.py dictate eval-asr`: word error rate per model (`small`, `large-v3-turbo`), per device, with and without the
  vocabulary prompt and replacements. This set never goes into training.

### P4. Correction capture (needs L1-L3)

The app is system-wide, so it cannot see what the owner edits after pasting. Capture corrections where the owner gives
them:

- When `learn` is on, keep each recording's audio, Whisper text and cleaned text in `learn_dir/sessions/` with an ID.
- New button-menu and tray action **Correct last dictation**: opens the last text in an editable box; on save, store the
  corrected text as the reference for that recording. Optionally paste the corrected text in place of the clipboard.
- Suggest new vocabulary and replacement entries from corrections (words that changed, seen twice or more). The owner
  accepts them; nothing is added silently.
- Retention job per L3. Logs still carry lengths and timings only (V13 stays true for logs).

### P5. LoRA fine-tune of Whisper (gated by L4)

- Script in the dictation venv: `transformers` + `peft`, LoRA on `large-v3-turbo`, data from `learn_dir/sessions/`
  pairs that have a corrected reference. Hold out the P3 test set.
- Run with the tray's GPU mode set to media so the 9B is not on the card. Measure VRAM and time on the RTX 3060.
- Convert the merged model to CTranslate2 int8_float16 so `engine.py` loads it like any other model
  (`dictation.model` points at the local folder).
- Accept only if word error rate on the P3 set falls and does not rise on a few clips of other speakers (to catch
  overfitting). Keep the stock model one setting away.
- Check that every new package loads under Smart App Control before relying on it (V3 pattern).

## Tasks

| ID | Task | Package | Needs | Done when |
|---|---|---|---|---|
| DL01 | Cleanup few-shot examples (incl. a dictated question) | P1 | - | `test_dictation.py` checks the request body has them |
| DL02 | Vocabulary in the cleanup prompt | P1 | - | unit test; manual check with a mis-spelled name |
| DL03 | Vocabulary prefix for the first phrase's `initial_prompt` | P1 | - | unit test on the prompt passed to `_decode` |
| DL04 | Spoken list and punctuation commands in `textops` | P1 | - | unit tests for each command, live and polish modes |
| DL05 | Number, time and money rule in the cleanup prompt | P1 | - | eval cases pass (DL07) |
| DL06 | `dictation.replacements` setting, applied after Whisper, in tray Settings | P2 | - | unit tests; `test_tray_coverage.py` passes |
| DL07 | `evals/dictation-cleanup` set and `stack.py dictate eval-cleanup` | P2 | gateway | baseline and post-P1 scores recorded in `memory/state.md` |
| DL08 | Ask L1-L3; record answers in `DECISIONS.md` and as an amendment to V13 | P3 | owner | decisions logged |
| DL09 | `learn`, `learn_dir`, retention settings; visible learning mark on the button | P3 | DL08 | refuses to store when `learn_dir` is empty or outside allowed roots |
| DL10 | `record-test` and `eval-asr` commands | P3 | DL09 | WER table for small / turbo, with and without P1-P2 |
| DL11 | Session storage and **Correct last dictation** action | P4 | DL09 | a correction round-trips to disk and shows in the tray |
| DL12 | Vocabulary and replacement suggestions from corrections | P4 | DL11 | owner can accept or ignore each suggestion |
| DL13 | Retention job | P4 | DL09 | old audio deleted on schedule; test with a fake clock |
| DL14 | LoRA spike: packages load under Smart App Control; VRAM and time on the 3060 | P5 | L4 met | numbers in `memory/state.md` |
| DL15 | Train, convert to CTranslate2, compare on the P3 set | P5 | DL14 | accept or reject recorded with WER numbers |
| DL16 | User guide "Voice typing" updates and plan Outcome note | all | each package | guide covers new settings and actions |

## Not in scope

- An OpenAI-compatible `/v1/audio/transcriptions` endpoint for Open WebUI (a follow-up in the voice-typing plan).
- Sending any audio or transcript off the machine. The cleanup stays on private aliases (AGENTS.md rule 9).
