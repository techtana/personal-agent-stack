# Stopping AI agents from reading personal files

Related: [Keeping background services alive on a Windows desktop](windows-service-hosting.md).

## 1. What this is and why the project needs it

AI agents such as Claude Code can read files, run commands and call tools. A hidden instruction on a web page or in a
document can make an agent do things the owner never asked for, such as reading personal photos or notes. The owner
wants a block that holds even when the agent is tricked, misconfigured or ignores its own settings. This note explains
what such a block needs. The short answer: let the operating system do the blocking, by running agents under a
different Windows account that has no right to open the owner's files. Settings inside the agent app help, but they
are not the block.

## 2. The ideas, built up from zero

### 2.1 Accounts and who is asking

Think of a building with many rooms, a guest list and keys. A Windows computer is the building. Every request to
open a file comes from some **account**, and Windows asks, for each request, "is this account on the list for this
room?" An account is a **security principal**: something Windows can name and give or refuse rights. Principals are
users (`Sekai`), groups of users (`AI-Agents`) and a few built-in ones (`SYSTEM`, `Administrators`, `Everyone`).
Internally each has a long id called a **SID**.

Every program runs as the account that started it, with that account's keys. That is the key point: a program is
never "more careful" than its account. If Claude Code runs as the owner, it holds every key the owner holds. The
analogy stops working here: a person in a building chooses which door to try; a program holds the keys and tries
whatever its code (or an attacker's text) tells it to.

### 2.2 NTFS permissions: the guest list on each door

**NTFS** is the file system Windows uses on its system drive. Each file and folder has a **security descriptor** with
an **access control list** (ACL): a list of entries, each an **ACE**, saying "this principal may (or may not) do
this". Rights include read, write, list a folder, execute and change permissions.

An ACE is either **allow** or **deny**. Windows reads the list and applies a simple rule of thumb: an explicit deny
beats an allow for the same right. So "Deny AI-Agents read" holds even if another ACE, say "Everyone: read", would
otherwise let them in. A deny is also a guard against future mistakes, such as a later broad grant.

**Inheritance** means a folder's ACEs flow down to files and folders created inside it, unless a child opts out.
One deny ACE on a personal root therefore covers everything below it. To see an ACL, run `icacls <path>`.

### 2.3 Drives with no guest list

Not every drive has ACLs. **exFAT** and **FAT32**, common on USB disks, store no per-user permissions at all. Windows
shows "No permissions are set. All users have full control." Any account can read everything on such a drive, the
agent's account included. There is nothing to deny. The fix is to keep personal data off such drives, or to
reformat to NTFS (after copying the data out). The project's `D:` drive is exFAT (section 6).

### 2.4 Administrators hold a master key

An **administrator** can take ownership of any NTFS file and then change its ACL. So an ACL protects against a
standard account but not against an admin. This has two consequences. First, the agent account must be a **standard
user**, never an admin. Second, an agent must never run **elevated** (with an admin token). Even the owner's own
account being an admin is a weakness: any program the owner runs can use admin rights after a prompt, or silently if
the prompts are off. The plan therefore recommends the owner use a standard account day to day (decision D1).

### 2.5 Why an app's own rules are advisory

Claude Code has a `permissions.deny` setting that blocks `Read(...)` of listed paths. It guards the tools Claude Code
knows about and the shell commands it recognises. But an agent that can run a shell can run
`python -c "open(...).read()"`, and the file opens, because the file system sees only the account, not the rule.
Hooks, CLAUDE.md rules and "privacy skills" fall in the same class. The project calls these **advisory**: they help a
well-behaved agent, but they depend on the agent obeying.

Agent **sandboxes** are closer to real enforcement but come with strings. Claude Code's `/sandbox` uses OS
enforcement on macOS, Linux and WSL2, not on native Windows. Gemini CLI's sandbox is off by default; Copilot's local
sandbox is off by default in the CLI, and its built-in file edits follow policy on a best-effort basis. Cowork
mounts only granted folders, but the desktop app decides what may be granted, and the desktop app's MCP servers and
extensions run as the owner. Windows Defender's Controlled Folder Access blocks writes by unknown apps, not reads.

A rule of thumb for "hard": **the operating system or a separate machine enforces it, and the agent process cannot
turn it off.**

### 2.6 Run agents as a separate standard account

If the owner's files carry ACLs that exclude the agent's account, every program in that account is locked out, no
matter what it is told. The setup in the plan:

```
owner account "Sekai" (admin today)       agent account "ai-agent" (standard user, group AI-Agents)
  personal files: Deny AI-Agents  <-X-     Claude Code, Gemini CLI, Copilot CLI, OpenCode, Codex
  browser profile with sign-ins   <-X-     desktop agent apps, in their own sign-in session
                                  --->     C:\AgentWork: Modify for AI-Agents
```

Under `C:\Users\Sekai` Windows already allows only `Sekai`, `SYSTEM` and `Administrators` (per the V-F1 ACL listing; not tested with a second account). The
explicit deny ACE for the `AI-Agents` group on each personal root is a second lock for later mistakes. A group is
used so that other agent identities can join later. Agents get a work folder, `C:\AgentWork`, with Modify rights.
The agent signs in separately to each tool, so the owner's tokens are not reachable either.

Windows can also log the denied attempts: Object Access auditing and a SACL (a list that says what to record) on the
personal roots write events 4656 and 4663 to the Security log, which gives evidence that the lock works.

### 2.7 Paths that skip the file system

An ACL guards files on this PC. Some data does not travel through files:

- **Cloud connectors.** If an agent signs in to the owner's AI account, connectors attached to that account (Drive,
  Gmail, Calendar, Notion) work on any machine. Windows permissions do not apply. The fix is on the account side:
  disconnect them, or give agents separate accounts (decision D3).
- **Localhost services.** A program running as the owner can serve personal data on `127.0.0.1` (for example the
  Logseq HTTP API behind `mcp-logseq`). The agent account can connect to a local port. Put a token only the owner
  can read in front of such a service, or restrict it with a firewall rule by user (to be tested, V-F7).
- **Synced folders.** Documents, Desktop and Pictures on SEKAIHOME are redirected into OneDrive inside the profile.
  Locally covered, but also reachable through the Microsoft account.
- **Copying in.** If the owner pastes personal data into `C:\AgentWork` or a chat, the block no longer applies to it.

### 2.8 Verification

A lock you never tested is a guess. The plan's check places a **canary file** (a file with a random marker) in each
personal root, then, as the agent account, tries to list and read each root with PowerShell, `cmd`, Python and
`robocopy`. Every attempt must fail with "access denied" and appear in the Security log. Then each agent is asked to
read a canary path with its own safeguards off, and the marker must never appear in its answer. Rerun after Windows
feature updates, sync-client updates and any new agent install.

## 3. Rules of thumb and typical numbers

| Rule | Source |
|---|---|
| Count a block as hard only if the OS or another machine enforces it and the agent cannot disable it. | AGENT-FILE-ISOLATION section 1 |
| An app's deny rules, hooks and privacy skills only advise. | AGENT-FILE-ISOLATION section 1; AGENTS.md rule 9; lessons 2026-10-26 |
| The agent account is a standard user, never an admin, never elevated. | AGENT-FILE-ISOLATION L2 |
| Keep an explicit deny ACE even when the profile ACL already excludes others. | AGENT-FILE-ISOLATION L2 |
| exFAT and FAT32 have no permissions; check with `Get-Volume`. | AGENT-FILE-ISOLATION L1, V-F1 |
| Run agent tools only inside the agent account, with app sandboxes on as a second layer. | AGENT-FILE-ISOLATION L3 |
| Windows "Experimental agentic features" agent accounts get the known folders by default; keep the feature off. | AGENT-FILE-ISOLATION L3 (source: windowslatest.com link in section 8) |
| A separate VM costs 2-4 GB RAM each and has no GPU access for local models. | AGENT-FILE-ISOLATION section 3 (source for the figure not recorded) |
| WSL2 reserves RAM the models need; the plan avoids it. | decision 2026-10-24; AGENT-FILE-ISOLATION section 3 |

## 4. Common misconceptions and edge cases

**"Deny rules in my agent's settings protect my files."** They protect against the agent's built-in tools only. A
shell command bypasses them (section 2.5).

**"The sandbox is on, so I am safe."** On native Windows several sandboxes do not exist or are off by default.
Check each tool.

**"My profile folder is private, so the agent cannot read it."** True only for a different account. If the agent runs
as you, it is you.

**"An admin account is just a stronger user."** An admin can take ownership of files an ACL denies.

**"My external drive is protected because it is plugged into my PC."** On exFAT every account has full control.

**"Deny ACEs and inheritance behave like folders in a filing cabinet."** They mostly do, but a child folder can
break inheritance, and a sync client or share can reset ACLs. That is why the plan includes re-checks.

**"Disconnecting the folder disconnects the data."** Cloud connectors reach the same data through the account, not
the folder.

**"The agent cannot see localhost."** It can. Any process on the machine can connect to a local port.

**Edge case: this stack's own agents.** The orchestrator and Open WebUI tools run as the owner today, so a delegated
agent with file or shell tools has the owner's reach (plan L3).

**Edge case: VS Code.** The editor window can stay the owner's while the extension host runs as the agent account
via Remote-SSH to localhost. Whether Copilot Chat's agent tools run on the remote side is not yet confirmed (V-F4).

## 5. How the project uses it

**Status (2026-11-01).** The isolation plan (dated 2026-10-29), [AGENT-FILE-ISOLATION.md](../plans/AGENT-FILE-ISOLATION.md), is a
**draft**. Nothing has been applied: no agent account, no group, no ACL change, no auditing exists yet. Decisions
D1 to D4 are open. The only work done is the read-only inventory V-F1 (section 6).

**Planned pieces** (work packages I0 to I7 in the plan):

- Local group `AI-Agents` and standard user `ai-agent`; deny ACEs on personal roots; `C:\AgentWork`; auditing.
- `stack.py isolate plan|apply|check` (idempotent, prints each ACL change before applying) and an
  `agent-isolation-check` script for the canary test, later part of `smoke`.
- An `agent-shell` launcher for CLI agents; VS Code Remote-SSH to `ai-agent`.
- Stack services under the agent account, tied to the Task Scheduler work in
  [windows-service-hosting.md](windows-service-hosting.md) (B2b).

**Decisions waiting for the owner.**

- D1: account and group names; whether the owner stays an admin (the plan recommends a standard owner account plus
  a separate admin account).
- D2: which repos move to `C:\AgentWork`; whether agents may read this repo's `.env`.
- D3: disconnect cloud connectors from the AI account agents use, or use separate AI accounts.
- D4: VS Code mode: Remote-SSH to `ai-agent`, or VS Code only in the agent session.

**Related rules.** AGENTS.md rule 9 says not to build privacy add-ons for clients outside the privacy boundary,
because they only advise. Secrets live only in `.env` and `.claude/settings.local.json` (rule 4). See also
[DECISIONS.md](../design/DECISIONS.md) and [PLAN-B-LOCAL-LED.md](../plans/PLAN-B-LOCAL-LED.md).

## 6. What we found

V-F1 ran on 2026-10-30 as a read-only check on SEKAIHOME:

- **`D:` is exFAT.** Any account can read all of it, including `shows`, `songs`, `mem`, loose photos at the root,
  `keycloak` and `ollama`. The plan's lock means nothing there until personal data moves off `D:` or the drive is
  reformatted to NTFS, keeping `D:\ollama`.
- **`C:\Users\Sekai`** grants full control to `SYSTEM`, `Administrators` and `Sekai`; one AppContainer capability SID
  has traverse only. The listed ACL leaves other standard users out (not tested with a second account).
- **Accounts.** Only `Sekai` is enabled, and it is an administrator (the built-in Administrator is disabled). No agent
  account exists. Every agent today runs with admin-capable rights.
- **Redirected folders.** Documents, Desktop and Pictures sit under `C:\Users\Sekai\OneDrive\...`, so they are
  covered locally but also reachable through the Microsoft account.
- **Other personal roots** in the profile: `logseq`, `JoplinBackup`, `StudioProjects`, `ansel`, `Downloads`, `Music`,
  `Videos`. Not yet checked: the ACL on `C:\Code` and other folders outside the profile.
- **2026-10-26 lesson.** Privacy add-ons for clients that talk to their own cloud can only advise, yet suggest
  enforcement.

## 7. Open questions

- Which of D1 to D4 will the owner choose, and when?
- Where does the personal data on `D:` go: move it, or reformat to NTFS?
- Do Copilot Chat's agent tools run on the remote side under VS Code Remote-SSH? (V-F4)
- Which exact Chrome and Edge policy names block built-in assistants and extensions? (V-F5)
- Does a deny ACE on `AI-Agents` still win if Windows "Experimental agentic features" is ever turned on? (V-F6)
- Can a firewall rule limited by local user close off localhost services to the agent account? (V-F7)
- What is the ACL on `C:\Code` and other folders outside the profile?
- Desktop AI apps move to `ai-agent` and are removed from the owner account (L3); the owner has not confirmed this yet.

## 8. Sources and further reading

All links come from section 6 of the plan. Descriptions are from the plan's use of each link; the pages themselves were
not re-read for this note.

| Title | Org, year | Link | Good for |
|---|---|---|---|
| Claude Code sandboxing | Anthropic, year not recorded | https://code.claude.com/docs/en/sandboxing | Which platforms get OS enforcement; `denyRead` |
| Native Windows sandbox request | Anthropic Claude Code issue 46740, year not recorded | https://github.com/anthropics/claude-code/issues/46740 | Evidence that native Windows has no sandbox |
| Securing Claude for the enterprise (baseline) | amitkoth.com, year not recorded | https://amitkoth.com/secure-claude-enterprise-baseline/ | The `python -c` deny-rule bypass |
| Security and data handling | Anthropic, year not recorded | https://claude.com/docs/government/security/security-and-data-handling | Cowork sandbox and folder grants |
| Claude Desktop local access | Anthropic, year not recorded | https://claude.com/docs/third-party/claude-desktop/local-access | Cowork folder grants |
| Local sandboxing for GitHub Copilot now GA | GitHub, 2026-10-07 | https://github.blog/changelog/2026-10-07-local-sandboxing-for-github-copilot-now-generally-available | Copilot sandbox scope |
| Copilot CLI v1.0.69 release notes | GitHub, year not recorded | https://github.com/github/copilot-cli/releases/tag/v1.0.69 | Built-in edits "best effort" |
| Gemini CLI sandbox | Google, year not recorded | https://geminicli.com/docs/cli/sandbox/ | Sandbox off by default; Windows backend |
| Enable or disable File search and File read in Copilot on Windows 11 | Eleven Forum, year not recorded | https://www.elevenforum.com/t/enable-or-disable-file-search-and-file-read-in-copilot-on-windows-11.35268/latest | Opt-in file toggles |
| The Gemini app is now available for Windows | Google, year not recorded | https://blog.google/innovation-and-ai/products/gemini-app/the-gemini-app-is-now-available-for-windows/ | Gemini local files |
| Windows 11 AI agent with access to personal folders | Windows Latest, 2025-11-18 | https://windowslatest.com/2025/11/18/windows-11-to-add-an-ai-agent-that-runs-in-background-with-access-to-personal-folders-warns-of-security-risk | Agent Workspace and known folders |

No Microsoft Learn page is recorded in the repository. Source not recorded for the general NTFS, ACL and
administrator facts in section 2; they are standard Windows behaviour and match the V-F1 output.

## Changes

- 2026-11-01: first version.
