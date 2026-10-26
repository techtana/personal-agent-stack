# Machine profiles

One YAML per machine, selected by hostname (`$env:COMPUTERNAME` / `hostname`) or by
`AGENT_STACK_MACHINE=<name>`. `machines/_defaults.yaml` holds the hardware classes, the
model catalog, Ollama environment, ports and service modes; a machine file only records what
was detected and what you chose to override.

```bash
uv run scripts/stack.py doctor                      # show detected hardware, tools, ports
uv run scripts/stack.py doctor --write-profile      # create machines/<HOST>.yaml if missing
uv run scripts/stack.py doctor --write-profile --refresh   # re-detect, keep your overrides
uv run scripts/stack.py profile                     # print the resolved profile (class + models + env)
uv run scripts/stack.py build                       # regenerate everything that depends on it
```

Adding a machine: run `doctor --write-profile` on it, commit the new file, run `build`.
Upgrading RAM/GPU: run `doctor --write-profile --refresh`; if the hardware class changes the
generated LiteLLM config and agent files change with it.
