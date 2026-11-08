# Privacy for LLM systems: keeping personal data away from model providers

Related: [Confidential computing](confidential-computing.md) (how a cloud VM can process data its provider cannot read).

Status note, as of 2026-11-01: the privacy gate described below is **planned, not built**. The current build is
private-only: `policy/privacy.yaml` holds `external.enabled: false`, and the build refuses `true` until the gate exists.

## What this is and why the project needs it

When you send a prompt to a hosted model, the company that runs the model can read it. It may log it, review it, or
keep it for a while, depending on its terms. For a personal agent that sees chats, files, photos, code and secrets,
that is a real exposure. This project is built so that the default answer to "who can read my data?" is "only
hardware the owner controls, or a cloud machine the cloud company cannot look inside". Outside models stay off. If an
admin ever turns them on, a local check must stop anything sensitive from leaving. This note explains the ideas behind
that design: where the line is drawn, how sensitive content is found, how the finder is tested, and how several people
can sign in without weakening any of it.

## The ideas, built up from zero

### The provider can read your prompt

Think of a postcard and a sealed letter. A prompt sent to a hosted model is closer to a postcard. The connection is
encrypted on the way (that is the envelope), but the model company opens it at the other end, because the model must
read the words to answer. Encryption in transit protects you from people on the network. It does not protect you from
the company that is the destination. "The provider can read your prompt" means exactly this: the party running the
model sees the plain text, and what it then does with it (logging, retention, human review, training) is governed by
its policy, not by your wishes.

Where the analogy stops: a postcard is read once by whoever handles it. A prompt may be copied into logs, backups and
abuse-review queues, so exposure can last longer than the request.

### Trust boundaries and the privacy boundary

A **trust boundary** is a line around the parties you rely on. Inside the line, you accept that they see your data.
Outside it, you do not. A household keeps its documents in a locked drawer: the family is inside the boundary, the
postal worker is not.

This project draws one line, called the **privacy boundary**. Inside it are the owner's own machines, a confidential
cloud VM in the project's own account (see the companion note), the LiteLLM gateway, Open WebUI, and open-source
clients whose only model endpoint is the gateway (OpenCode, Continue). Outside it are clients that talk to their own
vendor cloud: Claude Code on a subscription ("profile A"), Claude Desktop and vendor chat apps. Source:
[SHARED-COMPONENTS.md section 0, principle 4](../plans/SHARED-COMPONENTS.md).

```
  Inside the boundary (enforced)                 Outside (no integration on purpose)
  +--------------------------------------+       +---------------------------------+
  | Open WebUI --> LiteLLM gateway --+   |       | Claude Code (subscription),     |
  | OpenCode, Continue --------------+   |       | Claude Desktop, vendor chat apps|
  |                                  v   |       |  --> talk to their own cloud    |
  |                 private models       |       +---------------------------------+
  |        (owned GPU / confidential VM) |
  +--------------------------------------+
        |  optional, off by default, behind the privacy gate
        v
   external model API
```

### Enforcement versus advice

A rule is **enforced** when the system makes breaking it impossible. It is **advice** when the system only asks
people or programs to behave. A lock is enforcement. A sign saying "please do not enter" is advice.

The project can enforce rules only where all model traffic passes through a component it controls. The gateway is that
component. A client that connects straight to its own cloud never passes through it. A skill, hook or plug-in added to
such a client can warn the user, but cannot stop the client from sending data; it would also suggest a protection that
does not exist, which is worse than nothing. So the project builds no privacy add-ons for those clients and counts a
client as protected only when its sole model endpoint is the gated gateway. Sources: `AGENTS.md` rule 9;
`memory/lessons.md`, bullet of 2026-10-26 on privacy add-ons.

Claude Code profile B (`claude-local`) is a middle case. It sends model calls through the gateway, switches off
non-essential traffic and denies the web tools. The client is closed-source, so the project treats it as the owner's
development tool and does not include it in the promise made to other users. Source: SHARED-COMPONENTS section 0.

### Data classes and private tiers

Each model deployment in the generated gateway config carries a label, `data_class`, set to `private` or `external`.
A private deployment also carries a `location`: `onprem` (hardware the owner has) or `confidential-cloud`. The build
fails if a label is missing. A **tier** is a step in the complexity router: simple, medium, complex, reasoning, media,
embeddings. The rule is that no tier, fallback, default, task model or embedding alias may point at an `external`
deployment. The build checks this and fails otherwise. Think of colour-coded folders: private folders can never be
filed into a shelf that leaves the building. Source: SHARED-COMPONENTS section 1; `policy/privacy.yaml`.

Why fallbacks matter: a router that silently retries on a cloud model when the local one is busy would leak data
without anyone choosing it. The label check turns that mistake into a build error.

### Detecting sensitive content

If outside models are ever enabled, something must decide what is too sensitive to send. The plan splits this into
detectors, each built from an existing open-source tool, with the project writing only the glue
([SHARED-COMPONENTS.md S1](../plans/SHARED-COMPONENTS.md)).

**Personal identifiers and names (PII, NER).** PII means personally identifiable information: email addresses, phone
numbers, card numbers, national IDs. Some have a fixed shape that a pattern (and a checksum, such as the Luhn check on
card numbers) can recognise. Names, places and organisations have no fixed shape, so a statistical **named-entity
recognition** (NER) model reads the sentence and tags them. The plan uses **Microsoft Presidio**, which bundles
pattern recognisers and plugs in an NLP model. The model is a **spaCy** model, a pretrained language pipeline that
comes in sizes. The trade-off is size and speed against accuracy. A "small" model (`en_core_web_sm`) is quick and light
but misses more; a "large" one (`en_core_web_lg`) is more accurate but heavy. Measured on the owner's machine, Presidio
with the small English model used 394-435 MB and took 7 ms per text, while Presidio's default large model alone used
978 MB, over the 900 MB target. Source: SHARED-COMPONENTS V4.

**Secrets.** API keys, tokens, private keys and passwords have patterns, and random-looking strings give themselves
away through high **entropy** (a measure of how unpredictable a string is). **detect-secrets** combines both kinds of
check. Left on defaults it is noisy: 191 raw hits on 20 test texts, so it needs filters. Source: V4. gitleaks rules are
named as an alternative.

**Topics.** Health, religion, politics, sexual orientation and similar "special categories" are not strings; they are
subjects. Two approaches exist. With **embedding exemplars**, you write example sentences for each topic, turn all of
them into vectors (lists of numbers that place meaning in space), and flag a message whose vector sits close to an
exemplar. It is fast. With a **zero-shot classifier**, a larger model is asked directly whether a text fits a label,
with no examples. It is easier to set up but slower. Measured: 0.56-2.9 s per text with five labels, against a 50 ms
target, so the exemplar method is the default and LLM Guard's zero-shot BanTopics is kept only as a comparison (G7).
Source: V4, section 6 of SHARED-COMPONENTS.

**The personal-disclosure rule.** Topic categories count only when they are about a person. "How do I true a bicycle
wheel" is not sensitive; "I ride every Saturday at 6 from the park next to my flat" is. Two or more
**quasi-identifiers** (age, small-area location, employer, school, nationality) linked to one person also count, because
combined they can point to one individual even when none does alone.

### Media

Images, video, audio and documents carry personal data that text scanners miss. The plan assembles existing tools:

- **Faces:** `deface`, which uses the CenterFace detector; it can blur faces in images and video.
- **People and bodies:** a small person detector (RT-DETR, Apache-2.0).
- **Text inside pictures** (ID cards, screenshots): **OCR**, optical character recognition. Presidio Image Redactor
  uses the Tesseract engine to read the text, then applies the text detectors to it.
- **Metadata:** hidden fields in files, such as GPS position and camera model in a photo's EXIF block, or author name in
  a document. **ExifTool** reads and strips them on Windows; **mat2** does it on Linux; **qpdf** rewrites PDFs.
  Stripping matters because a photo with no visible face can still show where the owner lives.
- **Audio:** a voice is biometric data, so audio is sensitive by default. Anything the gate cannot scan is labelled
  `unscannable`, and counts as sensitive.

Source: SHARED-COMPONENTS S1b and V11.

### Licences

A detector is only usable if its licence fits. NudeNet looked like the natural choice for nudity detection, but its
code and weights are AGPL-3.0, a strong copyleft licence: using it in a networked service can oblige you to publish
your own source. The project excluded it and chose permissive tools (deface and CenterFace: MIT; Tesseract: Apache-2.0;
Presidio: MIT; RT-DETR: Apache-2.0). A nudity classifier is still to be chosen. Sources: V5; `memory/lessons.md`,
2026-10-26. Check the licence before naming a tool in a plan.

### Consent and refusal design

The design has two kinds of decision. A **refusal** by the gate for sensitive content has **no override**: no user and
no admin can approve a single sensitive request (decision G6, "never"). Without an override, no one can be pressured or
tricked into using it, and the guarantee is simple to state. **Consent** is a separate, user-level step for non-sensitive
requests to an external model. The first message of a conversation opens a dialog naming the provider and what will be
sent. The consent is recorded against the chat, using the Open WebUI chat id as the key. Where the chat id is missing,
consent falls back to per user for 30 minutes. Source: SHARED-COMPONENTS section 2, S4, V3.

When the gate is unhealthy, it fails closed: an error, timeout or missing verdict counts as sensitive, and external
models become unavailable. Verdict logs hold categories and counts, never the matched text.

### Generalise and redact

Two optional steps (both off by default, G4) can make a request safer to send. **Redact** removes or masks the
sensitive parts, for example replacing a name with a placeholder, or blurring a face. **Generalise** rewrites the text
locally so it keeps its meaning without personal details, and shows the result to the user, who decides whether to send
it. The result is scanned again. A rewrite can still leak, which is why the second scan exists.

### Evaluating a detector

A detector makes two kinds of mistake. It can miss something sensitive (a **false negative**), or flag something
harmless (a **false positive**). Two numbers describe this.

- **Recall** asks: of all the sensitive items, how many did the detector catch? High recall means few leaks.
- **Precision** asks: of all the things the detector flagged, how many were truly sensitive? High precision means few
  false alarms.

Formulas: recall = TP / (TP + FN); precision = TP / (TP + FP). Here TP (true positives) are sensitive items flagged;
FN (false negatives) are sensitive items missed; FP (false positives) are harmless items flagged.

Worked example (illustrative numbers, made up for this note): a test set holds 100 texts with a personal address and
300 ordinary texts. The detector flags 96 of the 100 and also flags 12 of the 300. Then TP = 96, FN = 4, FP = 12.
Recall = 96 / (96 + 4) = 0.96. Precision = 96 / (96 + 12) = 0.89. The false-positive rate (taken here as FP / (FP + TN);
the release gate's "false positives <= 10 %" does not define it) is 12 / 300 = 4 %, where TN (true negatives) is the 288 ordinary texts left alone.

For a privacy gate, recall matters most, since a miss is a leak. Precision matters for usability, because a gate that
blocks ordinary coding work will be switched off. The plan's release gate asks for recall at least 0.98 for secrets,
identifiers and media, at least 0.90 for special categories and profilable context, and false positives at most 10 %.
Source: S8.

Tools: **presidio-evaluator** generates test text from templates filled with fake personal data, and reports
per-entity recall. Test data must be synthetic; no photos of real people without consent. A **leak canary** is a mock
external provider that records every byte it receives. The test passes only if the canary received nothing it should
not have: nothing at all when `external.enabled: false`, and with it on, no sensitive request, nothing without consent,
nothing from a user outside the `external` group, nothing while the gate is down, nothing through a fallback, and no
user identifiers. The canary tests the whole system, not just the detector, so it catches routing mistakes that
detector scores cannot.

### Identity for several users

A shared deployment needs to know who is asking. Terms:

- **OIDC** (OpenID Connect): a standard in which an identity provider signs users in and tells another app, here Open
  WebUI, who they are. Open WebUI keeps no passwords of its own.
- **TOTP** (general background): a six-digit code from an authenticator app that changes every 30 seconds, derived from a shared secret and
  the clock.
- **Passkey**: a sign-in credential made of a key pair stored on a device. It is tied to the site's address, so a fake
  site cannot collect it.
- **Invitation**: a one-time link from an existing user. In the plan, invited accounts stay inactive until an admin
  enables them.

Two identity servers were evaluated; both offer TOTP, passkeys, OIDC, invitations and an admin view of users. Authentik
is for Plan A (containers inside the confidential VM); Keycloak is for Plan B (a Java program that runs natively on
Windows). Memory: the earlier draft put Authentik (server and worker) at about 2 GB RAM; Keycloak's sizing guide
baseline is about 1.25 GB and the plan budgets 1.3-1.5 GB, but measured on the owner's machine it idled at 411 MB and
reached 514-517 MB after 300 logins, with `kc.bat` capping the heap at 512 MB. Sources: S7, V7, archived GCP draft
section 2. The Keycloak runtime figures came from `start-dev` with an H2 database, not a production setup.

## Rules of thumb and typical numbers

| Rule or figure | Value | Source |
|---|---|---|
| Resident memory target for the gate, media models loaded on demand | 900 MB | S1 |
| Text latency target (p95) | 50 ms for 4k new tokens, 400 ms for 32k | S1 |
| Image latency target (p95) | 300 ms | S1 |
| Video | 20 s per minute; sample 1 frame per second plus scene changes, max 120 | S1b |
| Presidio + `en_core_web_sm` | 394-435 MB, 7 ms per text | V4 |
| Presidio default `en_core_web_lg` alone | 978 MB (over target) | V4 |
| Small + `xx_ent_wiki_sm` | 680 MB | V4 |
| Small + xx + DeBERTa-v3-xsmall zero-shot + detect-secrets | 821 MB | V4 |
| Zero-shot topic model, five labels | 0.56-2.9 s per text | V4 |
| Test set size | at least 40 positives per category per language; at least 300 negatives | S8 |
| Release gate | recall >= 0.98 (secrets, identifiers, media); >= 0.90 (special categories); false positives <= 10 % | S8 |
| Verdict cache | SHA-256 of parts, LRU 10k entries, 24 h; hashes only | S1 |
| Consent fallback without chat id | per user, 30 minutes | V3 |
| Sessions (set in the identity provider, not custom code) | users 12 h idle / 7 d absolute; admins 1 h / 12 h | S7 |

The latency, memory and recall targets are design goals. They are not yet measured against a built gate.

## Common misconceptions and edge cases

- **"The connection is encrypted, so the provider cannot read it."** Encryption in transit ends at the provider.
- **"Our client has a privacy plug-in, so it is protected."** A plug-in in a client that talks to its own cloud can only
  advise. Count a client as protected only if its sole endpoint is the gateway.
- **"A per-user header makes model access safe."** LiteLLM's `user_header_name` mapping fails open without a database:
  the lookup error is logged at debug level only and the request passes. The project uses a `custom_auth` function plus
  `enable_post_custom_auth_checks: true`. Source: V2; `memory/lessons.md`, 2026-10-26.
- **"A blocked request is simply an error."** A plain exception in a LiteLLM hook returns HTTP 500, and the router
  retries it three times and may answer from a fallback. A refusal must raise a non-retryable 4xx. Source: V1.
- **"A bigger NER model is always the better choice."** Here it breaks the memory target. Also, long install paths
  (over 260 characters) broke spaCy and the Hugging Face cache on Windows. Source: V4.
- **"Zero-shot topic detection is just as good and easier."** Measured at 0.56-2.9 s per text, roughly 11-58 times the 50 ms target, and
  heavier. It remains a comparison.
- **"Redacted text is safe."** The redaction itself can miss things; hence the second scan. Also, many harmless-looking
  requests can let a provider profile a person; the gate's second job is to limit that.
- **"Removing the visible face removes the person."** Metadata, background text and voice still identify people.
- **"ExifTool handles every format."** It is read-only for DOCX/XLSX/PPTX, MP3 and WAV, and its PDF edits are
  incremental, so old data stays until `qpdf --linearize`. Source: V11.
- **"A free tool is free to use."** NudeNet is AGPL-3.0, weights included.
- **Edge cases:** a user may paste text in a language the gate has no model for (G1 starts with US and English); an
  unreadable file type counts as sensitive; a chat id may be missing on API calls, so consent falls back to per user.

## How the project uses it

Status, as of 2026-11-01: **the gate (S1-S3) is planned, not built.** The shipped build is private-only. The build
fails if a router tier, fallback, default or profile B alias names a non-private deployment, and it refuses
`external.enabled: true` until the gate exists. Still open from S6: the guardrail entry, `database_url`, the gate
config, the Open WebUI assets and the compose output. Source: `memory/state.md` item 4.

Work packages, all in [SHARED-COMPONENTS.md](../plans/SHARED-COMPONENTS.md):

- **S1 / S1b / S1c:** the `privacy-gate` package (detectors, media, redaction).
- **S2:** the gate service and its endpoints (`/v1/classify`, `/v1/redact`, `/v1/generalize`, `/v1/consent`,
  `/v1/embeddings`, `/v1/private-status`, `/healthz`).
- **S3:** the LiteLLM custom guardrail and access groups; the final check in `async_pre_call_deployment_hook`.
- **S4:** Open WebUI settings and the `privacy_notice.py` filter that shows the consent dialog.
- **S5:** an MCP server for privacy checks was dropped on purpose (no add-ons for clients inside the boundary add
  nothing; none for outside clients, per rule 9).
- **S6:** the build changes (already partly done: private-only routers, `data_class`, `location`, profile B settings).
- **S7:** identity (Authentik in Plan A, Keycloak in Plan B).
- **S8:** the evaluation set, the leak canary and the release gate (`stack.py gate-eval`).
- Plan B: [B-S0](../plans/PLAN-B-LOCAL-LED.md) ran in part on 2026-10-26 (Keycloak `start-dev` and Caddy ran;
  `winget configure` and the Windows service install did not); [Plan A](../plans/PLAN-A-CLOUD-LED.md) acceptance
  tests 1-2 (leak canary) and 9 (cross-user) cover the same ground.

Simplified or deferred: the orchestrator MCP server, `record_lesson`, Phoenix and prompt-text traces are slated for
removal (package R) because they store or spread prompt text; the nudity classifier is not chosen; media models are not
picked beyond the licence check; `generalize` and `redact` are off by default; only English and US identifiers at first.

Decisions: [../design/DECISIONS.md](../design/DECISIONS.md) (entries of 2026-10-26: private first, no privacy add-ons,
existing tools, small spaCy models, NudeNet dropped, `custom_auth`, non-retryable 4xx, consent keyed on chat id). Plans:
[README](../plans/README.md), [Plan A](../plans/PLAN-A-CLOUD-LED.md), [Plan B](../plans/PLAN-B-LOCAL-LED.md). The
earlier Google Cloud draft, which defaulted to Vertex AI and Google Secret Manager, was archived because it
contradicted private first: [archive](../archive/GCP-DESIGN-DRAFT-2026-10-26.md).

## What we found

All results are from 2026-10-26 on the owner's machine (the reference machine) unless stated, recorded in
[SHARED-COMPONENTS.md section 7](../plans/SHARED-COMPONENTS.md).

- **V1, confirmed:** `async_pre_call_deployment_hook` runs after routing and fallback selection and sees the chosen
  deployment in `kwargs["model_info"]`. Raise a non-retryable 4xx; a plain exception becomes a retried 500.
- **V2, refuted as stated:** `user_header_name` fails open without Postgres. A `custom_auth` function plus
  `enable_post_custom_auth_checks: true` returned 403 `key_model_access_denied` in a test. JWT auth is enterprise-only.
- **V3, confirmed with gaps:** Open WebUI 0.12.3 forwards `X-OpenWebUI-Chat-Id` once header forwarding is on; some API
  calls lack it.
- **V4, confirmed for small models:** memory and latency figures in the table above. detect-secrets needs filters.
- **V5, partly:** licences recorded; NudeNet is out; nudity classifier open.
- **V6, confirmed (docs 2026.8):** Authentik invitation stage plus "create users as inactive".
- **V7, docs mostly confirmed, runtime partly:** Keycloak 26.8.1 started in 13.8 s; admin-created user disabled then
  enabled; admin can end single sessions; organisation invites fail with HTTP 500 until SMTP is set. Not run: the
  Windows service install (needs an elevated shell) and the production start with PostgreSQL. Use at least 26.7.3
  (CVE-2026-16072).
- **V11, partly:** ExifTool coverage as listed above; mat2 does not run natively on Windows.

## Open questions

- Which nudity classifier has a permissive licence and acceptable accuracy? (V5)
- Do the embedding exemplars reach recall 0.90 on special categories within the memory target, or does BanTopics beat
  them? (G7, decided in the S1 test)
- Can a Windows-only setup strip Office and audio metadata reliably, or should those uploads be blocked? (V11)
- How will the gate handle languages beyond English, and national IDs beyond the US? (G1)
- Does the gate hold its latency and memory targets once built? Not measured yet.
- Is the 30-minute per-user consent fallback acceptable where the chat id is absent? (V3)
- Are the release-gate thresholds the right ones? They are plan targets, not tested values.

## Sources and further reading

The plans do not record URLs for the third-party tools below. "URL not recorded" means a reader should look the tool up
by name; this note does not guess addresses.

| Title | Org | Year | Link | Good for |
|---|---|---|---|---|
| Shared components for Plan A and Plan B | this repo | 2026 | [SHARED-COMPONENTS.md](../plans/SHARED-COMPONENTS.md) | the gate design, V1-V11 results |
| Plans overview | this repo | 2026 | [README.md](../plans/README.md) | the two plans side by side |
| Plan B: local-led | this repo | 2026 | [PLAN-B-LOCAL-LED.md](../plans/PLAN-B-LOCAL-LED.md) | Keycloak spike, acceptance tests |
| Privacy policy file | this repo | 2026 | `policy/privacy.yaml` | the `external.enabled: false` switch |
| Design decisions log | this repo | 2026 | [DECISIONS.md](../design/DECISIONS.md) | why each choice was made |
| Archived Google Cloud draft | this repo | 2026 | [archive](../archive/GCP-DESIGN-DRAFT-2026-10-26.md) | what was dropped and why |
| Lessons | this repo | 2026 | `memory/lessons.md` | the 2026-10-26 bullets |
| Presidio, spaCy, detect-secrets, deface, ExifTool, mat2, qpdf, Tesseract, presidio-evaluator, LLM Guard, Keycloak, Authentik | various | - | URL not recorded | tool documentation |

## Changes

- 2026-11-01: first version.
