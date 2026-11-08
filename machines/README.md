# Machine profiles

`machines/_defaults.yaml` holds the hardware classes, the model catalog, Ollama environment, ports and service modes.
Each computer also has its own profile, `machines/<HOST>.yaml` (`<HOST>` is the computer name, or
`AGENT_STACK_MACHINE=<name>`), which records what was detected and what you chose to override.

The profile stays on its computer. The installer writes it (`install.cmd` or `uv run scripts/stack.py install`), the
tray's Settings tab edits it, and git ignores it: it names the computer and holds your folders, and this repository is
public. A git worktree of this repository, such as a Claude Code session's, uses the main checkout's profile.

```bash
uv run scripts/stack.py doctor                      # show detected hardware, tools, ports
uv run scripts/stack.py doctor --write-profile      # create machines/<HOST>.yaml if missing
uv run scripts/stack.py doctor --write-profile --refresh   # re-detect, keep your overrides
uv run scripts/stack.py profile                     # print the resolved profile (class + models + env)
uv run scripts/stack.py build                       # regenerate everything that depends on it
```

Adding a machine: run the installer on it, then `build`. Do not commit the profile.
Upgrading RAM/GPU: run `doctor --write-profile --refresh`; if the hardware class changes the
generated LiteLLM config and agent files change with it.
