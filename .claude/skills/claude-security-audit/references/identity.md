# Keeping the owner's identity out of what Claude writes

The owner's rule: Claude may see their identity while it works, but never writes it down. Wherever it is already
written, Claude replaces it with a placeholder. "Identity" means email addresses, the full name, account and
organization IDs, the GitHub account name, and the operating-system user name, including inside paths. It also covers guesses about the owner
(language, nationality, gender, location), which are never written either.

## How it gets into Claude's hands, and then into files

| Path | How it leaks | What the audit does |
|---|---|---|
| Git config | `git log`, `git show` and `git config` print `user.email`; commit authors carry it. | GIT-EMAIL / GIT-EMAIL-REPO; IDENTITY-UNPUSHED before a push; the fix is the GitHub no-reply address |
| Claude's own context | Claude Code adds the account email to each session (no switch exists). | Nothing to fix; the standing rule covers what Claude writes |
| Repository files | Author fields in `package.json`, `pyproject.toml`, `setup.cfg`, `Cargo.toml`, `*.csproj`, `*.gemspec`, `CITATION.cff`; LICENSE headers; READMEs; Unity `ProjectSettings.asset` (`companyName`, `organizationId`, `cloudProjectId`) | IDENTITY-PUBLISHED, scrub |
| Scaffolding | `uv init`, `npm init`, `cargo new`, `poetry init` copy the git name and email (or npm's `init-author-*`) into the new manifest. | NPM-INIT-AUTHOR; scrub afterwards |
| Web APIs that ask for a contact | Nominatim/OpenStreetMap, SEC EDGAR, NCBI E-utilities, Crossref, OpenAlex and similar ask for an email in the `User-Agent`, `mailto=` or `email=`. A helpful script pulls it from git config or a file. | IDENTITY-CONTACT-API; rewrite to `CONTACT_EMAIL` (below) |
| Instructions and memory | `CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md`, auto memory (`~/.claude/projects/*/memory/`), skills, scheduled-task prompts and pasted config that mention the owner. Claude copies from them. | IDENTITY-INSTRUCTIONS, scrub |
| Home paths | `C:\Users\<name>\...`, `/c/Users/<name>`, `//c/Users/<name>` (permission rules), `/home/<name>`, and the bare user name in prose ("SYSTEM, Administrators and <name>") | scrub to `%USERPROFILE%`, `~`, `%USERNAME%` |
| GitHub links | A link to one of the repository's own pull requests or issues (`https://github.com/<owner>/<repo>/pull/13`), a clone address, or `<owner>/<repo>` names the account. Docs skills that ask for a PR link add them. | IDENTITY-PUBLISHED, scrub; IDENTITY-LOGIN-CODE in code and config |
| Computer name | A host name built from the user name ends up in docs and file names. | HOSTNAME-IN-FILES, report only (this stack names machine profiles after the host) |
| Commit trailers | `Co-authored-by` or `Signed-off-by` with a personal address; `Claude-Session:` links from cloud sessions | IDENTITY-UNPUSHED; ATTRIBUTION-SESSION-LINK (`"attribution": {"sessionUrl": false}`) |
| Environment | `EMAIL`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_EMAIL` set to a personal address; Claude reads the environment | taken as identity to search for; IDENTITY-CONFIG for config files |
| OpenTelemetry | Events always carry the account email. | OTEL-REMOTE |

## What the scanner looks for, and where

**Identifiers.** They are read at run time only and never printed or saved:

- **Emails:** the Claude account email, git `user.email` (global and system, unless it is a no-reply address), and
  `EMAIL` and `GIT_*_EMAIL`.
- **Names:**
  - The account's full name and display name, and git `user.name`, when they have two or more words.
  - Long single words of a name (eight letters or more) are only reported, because they may belong to someone else.
  - Short one-word names are only hidden in the audit's own output; matching a common word in files would corrupt
    them.
- **The OS user name:** in paths always; on its own only when it is distinctive (at least five letters, and not a word
  like `admin` or `user`).
- **The computer name:** when it contains the user name.
- **The GitHub account name:**
  - from the GitHub CLI when it is signed in (`gh config get -h github.com user`, and `gh api user` unless
    `--offline`), from a GitHub no-reply address in git config or `GIT_*_EMAIL`, and from `logins` in
    `identity.local.json`;
  - from the owner part of a github.com `origin` remote only when it is one of those accounts or, when none names
    one, when it owns the current repository. Other remote owners are organizations or projects the owner only
    cloned, and their names are not identity; `identity.github` counts them without naming them;
  - never from commit history, which also carries other people's accounts (`Merge pull request #44 from ...`);
  - matched inside GitHub addresses always, and on its own only when it is distinctive (as for the user name). A
    hyphen counts as part of the name, so `<owner>-bot` is another account.
- **Extras:** anything listed in `identity.local.json` in the state folder.
- **Account-like IDs:** UUIDs (such as the claude.ai account IDs in synced skill folder names) and cloud billing IDs
  are hidden as `[id]` in the audit's output. They aren't searched for or replaced in files.

**Places.** Every git repository Claude Code has worked in (from `~/.claude.json`), the current one, `--repo`
paths and `repos` in `config.json`. In each it reads tracked files and untracked files that aren't ignored, but not
lock files, vendored folders or binaries. It also reads Claude's own files under `~/.claude` and `~/.claude-local`,
and Claude's config files (for email addresses only). Paths covered by the owner's Read deny rules are never read.

## Placeholders `scrub` writes

| Found | Replaced with |
|---|---|
| owner email | `you@example.com` |
| owner full name | `Your Name`; in LICENSE, COPYING and NOTICE files: `The <repo> Authors` |
| Unity `companyName` equal to the owner's name | `DefaultCompany`. This changes `Application.persistentDataPath`, so existing local saves move. |
| `C:\Users\<name>` (any drive, either slash, JSON-escaped) | `%USERPROFILE%` |
| `/c/Users/<name>`, `//c/Users/<name>`, `/mnt/c/Users/<name>`, `/home/<name>`, `/Users/<name>` | `~` (`//c/Users/<name>/x/**` becomes `~/x/**`, still a valid permission rule) |
| link to the repository's own PR or issue, in prose and Claude's files | `PR #13`, `issue #4`; a link whose text says something else keeps it: `the tray PR (PR #3)`; an address in parentheses after text that already names it is dropped |
| any other mention of the GitHub account name, in prose and Claude's files | `<owner>`. In code and config it is reported, not replaced. GitHub no-reply addresses (`<id>+<owner>@users.noreply.github.com`) stay: every commit already carries them |
| bare user name in prose and in Claude's instruction files | `%USERNAME%` (`$USER` outside Windows); in code it is reported, not replaced |

## Contact email for public APIs

Read it at run time and keep the literal out of the file:

```python
import os
CONTACT = os.environ.get("CONTACT_EMAIL", "you@example.com")
headers = {"User-Agent": f"my-tool/1.0 ({CONTACT})"}                    # Nominatim, SEC EDGAR
params = {"mailto": CONTACT}                                              # Crossref, OpenAlex
params = {"tool": "my-tool", "email": CONTACT}                            # NCBI E-utilities
```

```javascript
const CONTACT = process.env.CONTACT_EMAIL ?? "you@example.com";
```

```bash
curl -A "my-tool/1.0 (${CONTACT_EMAIL:-you@example.com})" "https://nominatim.openstreetmap.org/search?q=..."
```

```powershell
$contact = if ($env:CONTACT_EMAIL) { $env:CONTACT_EMAIL } else { "you@example.com" }
```

SEC EDGAR refuses requests without a real contact. The owner sets `CONTACT_EMAIL` in their own shell when they need
it; Claude never fills it in.

## Standing rule for `~/.claude/CLAUDE.md`

The audit checks for the marker comment (finding STANDING-RULE). The block, verbatim:

```markdown
<!-- claude-security-audit:identity-rule -->
## Keep my identity out of everything you write

You may see my email addresses, full name, account and organization IDs and operating-system user name: in git
authors and config, in Claude's account context, in files. Using them to understand a request is fine. Writing them
anywhere is not, and neither are guesses about me (language, nationality, gender, location).

- Never put them in files, code, comments, commits, PR or issue text, memory, prompts for other models, URLs, HTTP
  headers or request bodies. Use placeholders: `you@example.com`, `Your Name`, `%USERPROFILE%` or `~` for a home
  path, `%USERNAME%` for the user name, `<account-id>`; in a LICENSE, "The <project> Authors".
- When a public API wants a contact email (Nominatim/OpenStreetMap, SEC EDGAR, NCBI, Crossref, OpenAlex and the
  like), read it at run time from the `CONTACT_EMAIL` environment variable, default `you@example.com`. Never take it
  from git config, `~/.claude.json` or other files, and never write a literal address into a `User-Agent`, `mailto=`
  or `email=`.
- After scaffolding (`uv init`, `npm init`, `cargo new`, `poetry init`) and when editing manifests, LICENSE headers,
  READMEs or Unity ProjectSettings, replace author, email and company fields that carry my identity with placeholders.
- If you find my identity already written somewhere (repository files, CLAUDE.md, memory, skills, scheduled-task
  prompts, pasted config), replace it with a placeholder and tell me where.
```

## Files the owner may add to the state folder

- `identity.local.json`: `{"emails": ["..."], "names": ["..."], "logins": ["..."]}` for further identifiers to search
  for, such as an old address, a nickname or a second GitHub account. Only the owner writes it; the audit reads it, never writes it, and never copies its
  values anywhere.
- `config.json`: `{"repos": ["D:/projects/game"], "keep": ["skills/job-search/**"]}`. `repos` adds repositories to
  scan; `keep` lists files whose identity is deliberate.
