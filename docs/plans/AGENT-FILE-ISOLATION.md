# Plan: hard block on AI agents reading personal files (2026-10-29, draft)

Goal: no AI agent on SEKAIHOME (Claude Code, Claude Desktop and Cowork, Gemini CLI and the Gemini app, GitHub Copilot
in the CLI, VS Code and Windows, browser agents, Windows agent workspaces, and this stack's own agents) can read or
change the owner's personal files, even if the agent is prompt-injected, misconfigured or ignores its own settings.

Status: research and plan only. Nothing here has been run. Checks marked **V-F** must run on SEKAIHOME first.

## 1. What "hard" means here

A block is hard only when the operating system or a separate machine enforces it, and the agent process cannot turn
it off. That rules out everything an agent's own app enforces:

| Mechanism | Why it is not a hard block |
|---|---|
| Claude Code `permissions.deny` on `Read(...)`, hooks, CLAUDE.md rules | Apply to built-in tools and Bash commands Claude Code recognises; `python -c "open(...)"` reads the file anyway. AGENTS.md rule 9 and the 2026-10-26 lesson already say client-side add-ons only advise. |
| Claude Code `/sandbox` (`sandbox.filesystem.denyRead`) | Real OS enforcement, but only on macOS, Linux and WSL2; not on native Windows. WSL2 is not installed by choice, and WSL mounts `C:\` as `/mnt/c` with the owner's rights. |
| Claude Desktop Cowork folder grants | The VM only mounts granted folders, but which folders may be granted is enforced by the desktop app, and Claude Desktop's MCP servers, extensions and computer use run as the owner. |
| Copilot local sandbox (GA 2026-10-07) | Off by default in the CLI; built-in file edits follow the policy "best effort", not inside the OS sandbox. |
| Gemini CLI sandbox | Off by default; the Windows Native backend lowers integrity on what it writes, it does not deny reads elsewhere. |
| Copilot on Windows "File search / File read", Gemini app local files | Opt-in toggles inside the app. Off is good; it is not enforcement. |
| Defender Controlled Folder Access | Blocks writes by unknown apps, not reads. |

So the boundary is the **Windows account**: every agent runs as a separate standard user that the file system does not
let into the owner's data. App sandboxes stay on as extra layers, never as the boundary.

## 2. Design

```
owner account "Sekai" (admin)          agent account "ai-agent" (standard user, member of group AI-Agents)
  personal files: Deny AI-Agents  <-X-   Claude Code, Gemini CLI, Copilot CLI, OpenCode, Codex
  browser profile with sign-ins   <-X-   Claude Desktop/Cowork, Gemini app, Copilot app (own sign-in session)
  personal cloud connectors       <-X-   own claude.ai / Google / Microsoft sign-ins without personal connectors
                                  --->   C:\AgentWork (repos the agents may touch): Modify for AI-Agents
```

### L1. Inventory personal roots (V-F1)
List every place personal data lives, on every drive:
- `C:\Users\Sekai\` (Documents, Desktop, Pictures, Downloads, Videos, Music, AppData with browser profiles and app
  tokens), any OneDrive / Google Drive / Dropbox sync folders, the Logseq graph, Notion's local cache.
- `D:\` (USB SSD). **Check its file system** (`Get-Volume`): NTFS can carry ACLs; exFAT/FAT32 cannot, and then every
  user, the agent included, can read everything on it. If it is not NTFS: keep only `D:\ollama` there, or reformat to NTFS.
- Default NTFS ACLs on a non-system drive root give Authenticated Users rights to create folders and read; personal
  folders on `D:` need explicit ACLs. Under `C:\Users\Sekai` Windows already allows only Sekai, SYSTEM and
  Administrators (confirm with `icacls`).

### L2. Account split (the hard block)
1. Create local group `AI-Agents` and local **standard** user `ai-agent` (no Microsoft account, not an administrator,
   strong password kept by the owner). An admin can take ownership of any file, so the agent account must never be
   an admin and agents must never run elevated.
2. Add an explicit **Deny (read, write, list, execute)** ACE for `AI-Agents` on each personal root from L1, inherited by
   children. The profile ACL already excludes other users; the deny ACE guards against a later broad grant (a share,
   "Everyone" on a folder, a sync client resetting ACLs). Using a group lets other agent identities join later (L5).
3. Create `C:\AgentWork` with Modify for `AI-Agents` and move or clone the repos agents may work on there. Repos keep
   their own `.env` only if the agent may read those secrets; this repo's `.env` (gateway keys, `ORCHESTRATOR_BEARER`)
   is a decision (D2).
4. Turn on Object Access auditing (failure) and a SACL for `AI-Agents` on the personal roots, so every denied attempt
   lands in the Security log (events 4656/4663) as evidence.

### L3. Run every agent as `ai-agent`
| Agent | How it runs as `ai-agent` |
|---|---|
| CLI agents (Claude Code, Gemini CLI, Copilot CLI, OpenCode, Codex) | `scripts/agent-shell.ps1` / `.sh`-style wrapper opens a terminal as `ai-agent` (`runas /user:ai-agent` or a stored-credential Task Scheduler task). Each tool signs in again under that profile, so the owner's tokens are not reachable either. Turn the tool's own sandbox on as a second layer. |
| VS Code with Copilot or the Claude Code extension | Preferred: OpenSSH server on localhost, VS Code Remote-SSH as `ai-agent`; the window stays the owner's while the extension host, terminals and agent tools run as `ai-agent` (V-F4: confirm Copilot Chat's agent tools run on the remote side). Fallback: run VS Code itself in the `ai-agent` session. The owner's local VS Code gets no AI extensions. |
| Desktop apps (Claude Desktop and Cowork, Gemini app, Copilot app, ChatGPT) | Install per user under `ai-agent` and use them only in that account's own sign-in session (fast user switching). Computer use and screen sharing then see only that desktop, and clipboards are not shared between sessions. Uninstall or disable them in the owner account (Copilot "File search"/"File read" off at minimum). |
| Browser agents (Claude in Chrome, Gemini in Chrome, Copilot in Edge) | They act with the browser's sign-ins, which reach Gmail and Drive. Only in a browser profile inside the `ai-agent` session; in the owner's Chrome and Edge, block the extensions and built-in assistants by policy (V-F5: exact Chrome/Edge policy names, for example Chrome `GeminiSettings`, `ExtensionInstallBlocklist`). |
| Windows "Experimental agentic features" / Agent Workspace | Keep **off**: agent accounts there get the known folders (Documents, Desktop, Downloads, Pictures, Music, Videos) by default. If ever turned on, add those accounts to `AI-Agents` and test that the deny ACE wins (V-F6). |
| This stack (orchestrator, Open WebUI tools, OpenCode departments) | Today they run as the owner, so a delegated agent with file or shell tools has the owner's reach. Run the B2b Task Scheduler tasks as `ai-agent` (or a dedicated `agent-stack` account in `AI-Agents`), with `.run/`, traces and the repo under `C:\AgentWork`. |

### L4. Paths that bypass the file system
- **Personal cloud connectors** are attached to the AI account, not to Windows: whoever signs in as the owner's
  claude.ai account gets Google Drive, Gmail, Calendar and Notion connectors on any machine. The same holds for
  Gemini (Google account: Drive, Gmail) and Copilot (Microsoft account: OneDrive). Hard options: disconnect personal
  connectors from the account the agents use, or give agents separate accounts (D3).
- **Local services running as the owner** that serve personal data on localhost (the Logseq HTTP API behind
  `mcp-logseq`, any file-serving MCP server, SMB shares): `ai-agent` can reach localhost ports. Keep each behind a
  token that lives only in the owner's profile, or bind them to a firewall rule limited to the owner (V-F7:
  `New-NetFirewallRule -LocalUser`). Admin shares (`\\localhost\C$`) need admin credentials and stay closed.
- **Shared writable places** (`C:\Users\Public`, `C:\Windows\Temp`, `C:\ProgramData`): fine as long as the owner does
  not drop personal files there.
- **Copying in**: the block holds only for files the owner does not paste or copy into `C:\AgentWork` or a chat.

### L5. Verification (repeatable, part of `stack.py smoke` later)
1. Place a canary file with a random marker in each personal root.
2. `scripts/agent-isolation-check.ps1`, run as `ai-agent`, tries to list and read each root with PowerShell,
   `cmd type`, Python and `robocopy`; every attempt must fail with access denied, and each must appear in the
   Security log. It also tries the localhost services from L4 without a token.
3. Ask each agent, in its normal mode and with its sandbox and permission prompts off, to read the canary path;
   the marker must not appear in its reply or transcript.
4. Rerun after Windows feature updates, sync-client updates and any new agent install.

### V-F1 results (2026-10-30, read-only)
- **D: is exFAT** ("No permissions are set. All users have full control."). Any account, `ai-agent` included, can
  read everything on it: `shows`, `songs`, `mem`, loose photos at the root, `keycloak`, `ollama`. Before L2 means
  anything, move personal data off D: or reformat it to NTFS (copy out first), keeping `D:\ollama` there.
- `C:\Users\Sekai`: SYSTEM, Administrators and Sekai have full control; one AppContainer capability SID has traverse
  only. Another standard user cannot read it, as expected.
- Accounts: only `Sekai` is enabled, and it is an administrator (built-in Administrator is disabled). No agent
  account exists yet. Every agent today runs with admin-capable rights (D1).
- Documents, Desktop and Pictures are redirected to `C:\Users\Sekai\OneDrive\...`: inside the profile, so covered
  locally, but also reachable through the Microsoft account (Copilot, OneDrive connectors; L4).
- Other personal roots in the profile: `logseq`, `JoplinBackup`, `StudioProjects`, `ansel`, `Downloads`, `Music`,
  `Videos`. Not checked yet: the ACL on `C:\Code` and other folders outside the profile.

## 3. Alternatives considered

| Option | Verdict |
|---|---|
| App deny rules, hooks, privacy skills | Advisory only (section 1). Keep as convenience, never count them. |
| WSL2 + Claude Code sandbox | Real sandbox, but WSL2 reserves RAM the models need (the binding constraint here) and `/mnt/c` must be unmounted or restricted for it to help. |
| Windows Sandbox or a Hyper-V VM for agents | Strongest isolation; costs 2-4 GB RAM per VM and has no GPU access for local models. Keep as an option for untrusted one-off runs. |
| Separate physical machine | Strongest and simplest to reason about; costs hardware. |
| Account split (chosen) | Native, no RAM cost, enforced by NTFS; gaps are the cloud connectors and localhost services, handled in L4. |

## 4. Work packages

| # | Package | Size | Elevated |
|---|---|---|---|
| I0 | Decisions D1-D4 | S | - |
| I1 | V-F checks: drive file systems, profile ACLs, sync folders, VS Code remote behaviour, browser policies | S | partly |
| I2 | `stack.py isolate plan|apply|check`: group, user, deny ACEs, `C:\AgentWork`, auditing; idempotent, prints every ACL change before applying; PowerShell and bash wrappers per rule 7 | M | apply only |
| I3 | `agent-shell` launcher; VS Code Remote-SSH to `ai-agent` | S | sshd install |
| I4 | Move agent installs and sign-ins to `ai-agent`; remove or disable AI apps and extensions in the owner account; browser policies | S | policies |
| I5 | Cloud connectors per D3 | S | - |
| I6 | Stack services under `ai-agent` (with B2b) | M | task install |
| I7 | Canary check in smoke; lesson and state entries | S | - |

## 5. Decisions for the owner
- **D1** Account and group names; whether the owner account stays an admin (recommended: owner as standard user plus
  a separate admin account, so even owner-run tools cannot silently take ownership).
- **D2** Which repos move to `C:\AgentWork`, and whether agents may read this repo's `.env`.
- **D3** Cloud connectors: disconnect Drive/Gmail/Calendar/Notion from the claude.ai account agents use, or separate AI
  accounts per vendor (a second Claude subscription costs money).
- **D4** VS Code mode: Remote-SSH to `ai-agent` (owner window) or VS Code only in the agent session.

## 6. Sources
- Claude Code sandboxing docs (platforms; `denyRead`): https://code.claude.com/docs/en/sandboxing
- Native Windows sandbox request: https://github.com/anthropics/claude-code/issues/46740
- Deny rule bypass with `python -c`: https://amitkoth.com/secure-claude-enterprise-baseline/
- Cowork sandbox and folder grants: https://claude.com/docs/government/security/security-and-data-handling,
  https://claude.com/docs/third-party/claude-desktop/local-access
- Copilot local sandboxing GA: https://github.blog/changelog/2026-10-07-local-sandboxing-for-github-copilot-now-generally-available
- Copilot CLI built-in edits best effort: https://github.com/github/copilot-cli/releases/tag/v1.0.69
- Gemini CLI sandbox: https://geminicli.com/docs/cli/sandbox/
- Copilot on Windows file permissions: https://www.elevenforum.com/t/enable-or-disable-file-search-and-file-read-in-copilot-on-windows-11.35268/latest
- Gemini app for Windows: https://blog.google/innovation-and-ai/products/gemini-app/the-gemini-app-is-now-available-for-windows/
- Windows Agent Workspace and known folders: https://windowslatest.com/2025/11/18/windows-11-to-add-an-ai-agent-that-runs-in-background-with-access-to-personal-folders-warns-of-security-risk
