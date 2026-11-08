# Logseq refine plugin

Adds **Refine with <style>** to the right-click menu of a Logseq block (Logseq 2.x, database graphs). The block's text
goes to the agent stack's voice typing app on this PC, which rewrites it with the stack's local model, checks the
reply, keeps a before/after entry in its refine log, and only then lets the plugin write the block. Install and use:
[docs/manuals/user-guide.md](../../docs/manuals/user-guide.md#refine-a-logseq-block-from-its-right-click-menu).
Design and measurements: [docs/design/plans/2026-11-08-logseq-refine-plugin.md](../../docs/design/plans/2026-11-08-logseq-refine-plugin.md).

```
src/index.html, style.css   the plugin's page: the "Refine with..." picker
src/core.js                 logic that does not touch Logseq (also loaded by the tests)
src/main.js                 menu items, refine, undo, picker
build.mjs                   copies src/ and @logseq/libs' lsplugin.user.js into dist/ (no bundler)
test/core.test.mjs          node --test
e2e/sandbox.mjs             a throwaway copy of Logseq with its own profile (Windows)
e2e/server.py               the real plugin API on a test port, with a fake model or a private gateway
e2e/run.mjs                 drives the copy over DevTools: right-clicks, menu clicks, keys; checks blocks and the log
```

Build and test (Node.js 20 or later):

```bash
npm ci && npm run build && npm test
```

`uv run scripts/stack.py logseq-plugin` from the repository root does the build, adds `REFINE_BEARER` to `.env` and
copies it to the clipboard.

End to end, from the repository root. These commands copy the installed Logseq (about 570 MB) into
`.run/logseq-test`; the installed Logseq and your `~/.logseq` are only read.

```bash
uv run python integrations/logseq-refine/e2e/server.py --root .run/logseq-test --key test-key --port 8791
```

```bash
node integrations/logseq-refine/e2e/run.mjs --key test-key --server-port 8791
```

`--model gateway` on the server and `--mode gateway` on the run use the real model through a private copy of the
gateway on port 4010, with a throwaway master key. `node integrations/logseq-refine/e2e/sandbox.mjs clean` deletes the
copy.
