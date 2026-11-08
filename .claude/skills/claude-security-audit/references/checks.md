# What the audit checks

Verified against the Claude Code docs and changelog for version 2.1.319 on 2026-11-07. Each run also compares the
docs and changelog with the previous run, so settings added later show up as "New in Claude Code". When this file
and the current docs disagree, the docs win; update this file.

Docs root: https://code.claude.com/docs/en/ (append `.md` to any page for plain markdown).

## Contents

1. Paste-ready baseline
2. Data that leaves the machine
3. Retention on this machine
4. Permissions and isolation
5. Extensions: MCP servers, plugins, hooks, scheduled tasks
6. Updates and advisories
7. Identity (details in identity.md)
8. Drift

## 1. Paste-ready baseline

For `~/.claude/settings.json` (user scope). Merge it into what is there; don't replace the file. Items marked
*trade-off* in the sections below are left out here.

```json
{
  "env": {
    "DISABLE_ERROR_REPORTING": "1",
    "DISABLE_FEEDBACK_COMMAND": "1",
    "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "1",
    "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1"
  },
  "feedbackDrafts": "off",
  "cleanupPeriodDays": 14,
  "desktopSessionCleanupPeriodDays": 14,
  "attribution": { "sessionUrl": false },
  "permissions": {
    "disableBypassPermissionsMode": "disable",
    "deny": [
      "Read(~/.claude/.credentials.json)",
      "Read(~/.ssh/**)",
      "Read(~/.config/gh/**)",
      "Read(~/AppData/Roaming/GitHub CLI/**)",
      "Read(~/.aws/**)",
      "Read(~/.git-credentials)",
      "Read(~/.npmrc)",
      "Read(//**/.env)",
      "Read(//**/.env.*)",
      "Read(//**/*.pem)",
      "Read(//**/.claude/settings.local.json)"
    ]
  }
}
```

Rule syntax: `//` starts an absolute path (`//c/...` on Windows drive C, `//**/x` on every drive) and `~/` is your home
folder. Rules written as `.env` or `./x` only cover the current project. Windows paths are matched in POSIX form
(`C:\Users\x` becomes `/c/Users/x`).

## 2. Data that leaves the machine

| ID | Checks | Recommended | Trade-off and notes |
|---|---|---|---|
| FEEDBACK-UPLOAD | `/feedback`, `/bug`, `/share` | `DISABLE_FEEDBACK_COMMAND=1` (older name `DISABLE_BUG_COMMAND`) | They upload the conversation, code included; Anthropic keeps feedback for 5 years. No feature loss. (data-usage) |
| FEEDBACK-DRAFTS | Claude-drafted feedback | `"feedbackDrafts": "off"` | A draft can carry the transcript if you tick it. |
| ERROR-REPORTS | error reports to a third-party tracker | `DISABLE_ERROR_REPORTING=1` | On for Pro/Max/Ultra sign-ins since 2.1.198; secrets, paths and emails are redacted first. No feature loss. |
| TELEMETRY | usage metrics | `DISABLE_TELEMETRY=1`, *trade-off* | Metrics never contain code, prompts or paths. Turning them off also stops feature-flag fetching: Remote Control, cross-machine session messaging and, since 2.1.319, auto mode's server-side review stop working. |
| (umbrella) | `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | *trade-off* | Covers auto-updates, telemetry, error reports, `/feedback`, drafted feedback, release notes, PR badge checks and availability checks, plus feature flags. **Any non-empty value, including `0` or `false`, turns it on**: unset it to undo. |
| AUTO-MODE-SERVER | telemetry or flags off, 2.1.319+ | optional `CLAUDE_CODE_AUTO_MODE_SERVER=0` | With flags off, auto mode asks about or denies what its server check can't review. `0` uses Claude Code's own classifier requests instead. |
| CONNECTORS | claude.ai connectors loaded into Claude Code | `"disableClaudeAiConnectors": true` if unused there | They let every session read your mail, files or notes; a prompt injection could too. `ENABLE_CLAUDEAI_MCP_SERVERS=false` does the same through the environment. |
| OTEL-REMOTE | OpenTelemetry export | local collector only | Events always carry the account email; `OTEL_LOG_USER_PROMPTS` and `OTEL_LOG_TOOL_DETAILS` add prompts and tool input; `OTEL_METRICS_INCLUDE_ACCOUNT_UUID=false` drops the account ID. (monitoring-usage) |
| WEBFETCH-PREFLIGHT | `skipWebFetchPreflight` | leave unset | The check sends each hostname to `api.anthropic.com`, but the fetched page reaches the model anyway, so skipping it buys little privacy and loses a safety check. Meant for networks that block Anthropic. |
| BASE-URL | `ANTHROPIC_BASE_URL` | Anthropic or a local gateway | Any other host receives every prompt. |
| (share) | `/share` | `CLAUDE_CODE_ENABLE_SHARE_BUNDLE=1` if you keep `/share` | Saves the report and transcript under `~/.claude/feedback-bundles/` instead of sending it. |

Not configurable: Claude Code adds the signed-in account's email to each session's context. No setting or variable
turns that off (docs checked 2026-11-07; the audit's `email_switch` watches for one). Model training and chat
retention are claude.ai account settings (a manual check in the report): with training on, consumer chats are kept
for 5 years.

## 3. Retention on this machine

| ID | Checks | Recommended | Notes |
|---|---|---|---|
| TRANSCRIPT-RETENTION | `cleanupPeriodDays` (default 30) | 14, or 7 | `~/.claude/projects/*.jsonl` holds whole conversations in plain text, including the system prompt with your email. Older sessions leave `/resume`. |
| DESKTOP-RETENTION | `desktopSessionCleanupPeriodDays` | 14 to 30 | Without it, transcripts of sessions started in Claude Desktop or Cowork are kept at any age. A transcript is deleted once older than both this and `cleanupPeriodDays`. |

## 4. Permissions and isolation

| ID | Checks | Recommended | Notes |
|---|---|---|---|
| DENY-SECRETS | credential files that exist here and no Read deny rule covers | the rules in section 1 | Anything Claude reads enters the conversation. Deny rules stop Claude's file tools and shell commands that name the file; not `grep -r` from a parent folder, and not a script that opens the file itself. |
| DENY-SECRET-PATTERNS | `.env`, `.env.*`, `*.pem`, `.claude/settings.local.json` in every project | `Read(//**/...)` rules | `.env.*` also hides `.env.example`. This stack keeps its MCP bearer in `.claude/settings.local.json`. `.claudeignore` has no effect. |
| DENY-NOOP | `Grep(...)`, `Glob(...)`, `Write(...)` deny rules with a path | delete or rewrite as `Read`/`Edit` | Claude Code accepts them but never matches them. |
| BYPASS-AVAILABLE | `permissions.disableBypassPermissionsMode` | `"disable"` | Stops any session from entering bypassPermissions mode. |
| BYPASS-DEFAULT, BYPASS-PROMPT-SKIPPED | `defaultMode: bypassPermissions`, `skipDangerousModePermissionPrompt` | neither | |
| BROAD-ALLOW | allow rules for a whole shell, interpreter, package runner, network tool, any WebFetch, every MCP tool, any edit, or inline code (`python -c`, `powershell -Command`) with a wildcard; in user and current-project settings, every other repository's `.claude/settings*.json`, and per-project `allowedTools` in `~/.claude.json` | exact commands | `Bash(uv run *)` means any code; `Bash(uv run scripts/stack.py status*)` is fine. A `*` anywhere in a Bash rule matches any text, spaces and `;` included, so a wildcard inside an approved PowerShell one-liner admits any command. |
| PROJECT-MCP-AUTO | `enableAllProjectMcpServers` | unset | A cloned repo could start any program as an MCP server. |
| ADDITIONAL-DIRS-BROAD | `additionalDirectories` with the home folder or a drive | project folders | |
| ENV-SCRUB | `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` | `1` | Strips credentials (by name or value shape) from the environment of Bash commands, hooks and stdio MCP servers; keeps GitHub tokens and proxy settings. Check that MCP servers still connect. |
| READS-OUTSIDE | `permissions.blockReadsOutsideWorkingDirectories` | optional `true`, *trade-off* | File tools refuse other folders in every mode; blocks cross-project reads too. `blockWritesOutsideWorkingDirectories` is the write counterpart. |
| NO-SANDBOX / SANDBOX-OFF | OS sandbox | WSL2 on Windows; `sandbox.enabled` elsewhere | Native Windows runs commands unsandboxed. The sandbox is the only OS-level enforcement for shell commands. |
| NO-MANAGED, MANAGED-LEGACY | `C:\Program Files\ClaudeCode\managed-settings.json` (macOS `/Library/Application Support/ClaudeCode/`, Linux `/etc/claude-code/`) | optional, needs admin | Managed settings outrank everything. Useful keys: `allowManagedPermissionRulesOnly`, `disableBypassPermissionsMode`, `disableSideloadFlags`, `allowManagedHooksOnly`. The old `C:\ProgramData\ClaudeCode\` file is ignored. |
| SECRET-IN-SETTINGS | env values shaped like a known token (`sk-`, `ghp_`, JWTs and the like) whatever their name, and credential-like names (`*_KEY`, `*TOKEN*`, `*SECRET*`, `MASTER_KEY`, `*PASSWORD*`) holding written-out values | `apiKeyHelper` or the OS credential store | A git-ignored `.claude/settings.local.json` is acceptable (low); a committed one is high. |
| (auto mode) | `autoMode.classifyAllShell` | optional `true` | Sends every shell command through the auto mode classifier, even ones an allow rule matches. |
| (unattended) | `permissions.denyInsteadOfPrompting` (2.1.319, not yet in the docs) | optional for unattended runs | A call that would wait for a prompt is denied and the turn continues. |

## 5. Extensions: MCP servers, plugins, hooks, scheduled tasks

| ID | Checks | Recommended |
|---|---|---|
| MCP-UNPINNED | `npx`, `bunx`, `pnpm dlx`, `uvx`, `uv tool run` and `pipx run` without a version | pin (`pkg@1.2.3`, `pkg==1.2.3`) and update on purpose |
| MCP-PLAINTEXT-SECRET | credential-like `env` or `headers` values written out (a `${VAR}` reference, even after `Bearer `, is fine) | references; high when the file is committed |
| MCP-HTTP | remote servers over `http://` | https |
| MARKETPLACE-THIRD-PARTY | plugin marketplaces not run by Anthropic | keep only trusted ones; plugins bring hooks and MCP servers (plugins/security) |
| PLUGIN-HOOKS, HOOK-NETWORK | hooks that run automatically, and hooks calling network tools or non-local URLs | review after each update |
| (manual) | scheduled tasks' permission mode | auto or default. The desktop app keeps the mode outside the task file, so the report lists this as a manual check. |

Inventoried for drift as well: Claude Desktop's MCP servers (`claude_desktop_config.json`) and extensions, user and
project skills, the claude.ai-synced skills, and scheduled tasks.

## 6. Updates and advisories

- **UPDATE-CLI, UPDATE-VSCODE, UPDATE-DESKTOP-CODE**: each Claude Code install against the latest npm release. Medium
  when the changelog between the two mentions security fixes. Claude Desktop updates its own copy.
- **AUTOUPDATE-OFF**: with non-essential traffic off, updates are manual and this audit is how you notice them.
- **ADVISORY `<id>`**: OSV (which includes GitHub advisories) for `@anthropic-ai/claude-code` at each installed
  version, for MCP servers with pinned versions, and for `uv tool` packages (LiteLLM, Open WebUI and the rest of the
  stack). Severity comes from the advisory database. Only package names and versions are sent.
- Claude Desktop itself has no advisory feed. The audit reports its version; check vendor news when something is
  announced.

## 7. Identity

See identity.md. Findings: IDENTITY-PUBLISHED (high when the repository has a remote), IDENTITY-INSTRUCTIONS,
IDENTITY-CONTACT-API, IDENTITY-NAME-PART, OTHER-EMAILS, UNITY-ORG, IDENTITY-KEPT, IDENTITY-CONFIG, HOSTNAME-IN-FILES,
IDENTITY-UNPUSHED, IDENTITY-PUSHED, GIT-EMAIL, GIT-EMAIL-REPO, NPM-INIT-AUTHOR, ATTRIBUTION-SESSION-LINK and
STANDING-RULE.

## 8. Drift

From the second run on, the audit compares a fingerprint of the configuration with the last accepted run. The
fingerprint holds versions, env names (values only for known on/off switches), the tracked settings above, permission
rules, MCP servers, hooks, plugins, marketplaces, skills, scheduled tasks and Desktop extensions. Additions and
changes to MCP servers, hooks, plugins, marketplaces, rules, skills or tasks are medium: confirm you made each one.
The fingerprint holds hashes and redacted rule text, never secret values or identifiers.
