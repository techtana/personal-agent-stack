# Eval gate

`evals/<dept>/promptfooconfig.yaml` and `prompt.json` are generated from the `evals:` block of
`agents/<dept>.yaml` (`uv run scripts/stack.py build`). They run the department's **local** deployment
through the gateway so a prompt or routing change can be regression-checked before it is committed.

```bash
uv run scripts/stack.py up litellm                       # gateway must be running
npx promptfoo@0.125.0 eval -c evals/docs/promptfooconfig.yaml --repeat 3
npx promptfoo@0.125.0 view                               # browse results
```

Rules (from the research): run each case 3x so flaky cases are flagged rather than counted; a change
must not regress any previously passing case; add a golden case whenever a thumbs-down or a failed task
exposes a gap. Keep 15-30 cases per department over time; the shipped sets are seeds.
