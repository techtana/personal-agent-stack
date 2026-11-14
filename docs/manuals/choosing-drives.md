# Choosing drives

This manual helps you decide which drive holds each part of Agent Stack: the Ollama models, the Hugging Face cache,
the Python tools, OpenClaw, and other large things such as games. It also explains the drive part of the installer's
system check (**This PC** on its first page, and setup's **Check this PC** step) and what to do when it warns you.

For the ideas behind it (sequential and random reads, USB link speeds, why a model load reads the disk only once),
see [../knowledge/storage-and-drives.md](../knowledge/storage-and-drives.md).

## The short rule

- **Internal drive (usually C:):** things that are made of many small files, or that must work when the PC starts.
- **Second or USB drive (for example D:):** large files that are read once and then kept in memory, and bulk storage.
  This works only if the drive reads at **200 MB/s or more**. Check it first (below).

## What goes where

| Keep on the internal drive (C:) | Can go on a second or USB drive (D:) |
|---|---|
| Windows, the page file, installed programs | Ollama models (`OLLAMA_MODELS`, for example `D:\ollama\models`) |
| The Python tools folder (`UV_TOOL_DIR`: LiteLLM, Phoenix, Open WebUI, the `hf` command) | The Hugging Face cache (`HF_HOME`, for example `D:\huggingface`) |
| Code repositories, `.venv` folders, `node_modules`, the uv cache | Your game library |
| OpenClaw (npm installs it in your user profile) and its settings | Downloads, installers, media, archives |
| The Hugging Face token file (`HF_TOKEN_PATH`) | Generated images, video and audio |
| Build output and temp folders | A second copy of your backups |

Why:

- **Startup.** The tray app starts the services at sign-in. If the Python tools or OpenClaw were on a USB drive that
  is unplugged, nothing would start. A missing models drive only makes model loads fail; on 2026-11-01 it broke
  every model download until the drive was plugged back in.
- **Small files.** A repository, a Python environment or `node_modules` is thousands of small files. The internal
  NVMe drive answers each read in about 0.02 ms; the USB SSD on the reference machine took about 0.2 ms.
- **Large files read once.** Ollama reads a model from disk only when it loads it, then runs it from the GPU's
  memory. Hugging Face weights work the same way. A drive at 200 MB/s or more adds only seconds to each cold load.
- **Credentials.** The Hugging Face token and OpenClaw's keys stay on the internal drive, not on one that can be
  unplugged and carried away.

Keep the internal drive at least 15 to 20 percent free. Windows updates, the page file and the SSD itself need room.

Use short folder paths, such as `D:\huggingface` or `D:\games`. Some Python tools fail past Windows' 260-character
path limit.

### One exception: the 35B mixture-of-experts model

With `use_mmap: true`, Ollama keeps part of the 35B model's experts in mapped memory and reads them back from disk
whenever Windows needs the RAM for something else. A USB drive slows that down. If you make the 35B the primary model
again, it runs better from the internal drive, but it needs 22 GB there.

## Check a drive's speed

### With Windows' own tool (as administrator)

Windows' own disk test is the most reliable figure. It needs an administrator terminal:

1. Right-click **Start** and choose **Terminal (Admin)**. Click **Yes** when Windows asks.
2. Run this for each drive you want to check, with that drive's letter:

   ```powershell
   winsat disk -drive c
   ```

   ```powershell
   winsat disk -drive d
   ```

3. Find the line that starts `Disk  Sequential 64.0 Read`. The number before `MB/s` is the drive's read speed. For
   example:

   ```
   > Disk  Sequential 64.0 Read                   376.26 MB/s          8.0
   ```

4. Decide with the table in [What the numbers mean](#what-the-numbers-mean) and [What goes where](#what-goes-where):
   - **Under 100 MB/s:** fix the connection first ([below](#fix-a-usb-drive-that-reads-at-about-40-mbs)), then test
     again. Don't put models or games on it yet.
   - **100 to 200 MB/s:** use it for storage, downloads and backups. Put models on a faster drive if you have one.
   - **200 MB/s or more:** fine for Ollama models, the Hugging Face cache and games.
   - **Whatever the speed,** keep the Python tools and OpenClaw on the internal drive (usually C:), because they start
     at sign-in.
5. If the models folder should move, run the installer again (`install.cmd`) and choose a folder on the drive you
   picked.

Without administrator rights, `winsat` prints nothing at all and looks as if it worked.

### In the installer

The installer's first page checks this PC when it opens, and that check times every local drive (`stack.py check`
does the same in a terminal). The setup step **Check this PC (drives, GPU, memory)** then uses that check, or runs it
again when it is more than two hours old, and shows the models drive's result, for example:

```
models drive D: read 389 MB/s, write 325 MB/s (USB, 869 GB free, test file).
```

The installer is not run as administrator, so it measures with a test file (below). The step then also prints the
exact `winsat` commands for your drives and the decision rules above, so you can confirm the figures yourself.

If a drive is slow, the step gets an amber **!** instead of a tick, the heading reads **Setup finished with
warnings.**, and the step says what to do. Setup still runs every other step. A warning never moves your files: to
use another drive, click **Change folders and run again** or run the installer again and choose a folder there.

### From the command line

```powershell
uv run scripts/stack.py disks
```

To test only some drives:

```powershell
uv run scripts/stack.py disks C: D:
```

It prints one line per drive, a `WARN` line for each problem, and, when it used the test file, the `winsat` commands
to run as administrator. Run it from an administrator terminal and it uses `winsat` itself.

This command is part of the installer changes on branch `claude/nervous-euclid-8357d0`. Until that branch is merged,
the main checkout answers `invalid choice: 'disks'`.

### How it measures

- **As administrator**, it runs Windows' own `winsat disk -drive <letter>` and reads the sequential read, sequential
  write and random read figures.
- **Otherwise** (the normal case), `winsat` cannot run: without administrator rights it prints nothing. The check then
  writes a 256 MB test file, flushes it to the drive, and reads it back past Windows' file cache. On the system drive
  the file goes in your temp folder; on other drives it goes in `<drive>:\agent-stack-speedtest\`. Both are deleted
  afterwards. The line ends in `test file` instead of `winsat`.

Each drive needs about 0.5 GB free for the test. At USB 2.0 speed a drive takes about 15 seconds; a fast drive takes
a second or two.

### What the numbers mean

| Read speed | What it means | What to do |
|---|---|---|
| Under 100 MB/s | Slower than a hard disk. A USB SSD this slow is almost always on a USB 2.0 link (about 40 MB/s). | Fix the connection (next section). Don't keep models or games here until you have. |
| 100 to 200 MB/s | Works, but every cold model load is slow. | Fine for storage and backups. Use a faster drive for models if you have one. |
| 200 MB/s or more | Good for models, the Hugging Face cache and games. | Nothing to do. |

When the models drive is under 200 MB/s, the step also suggests a better drive: one that reads at 200 MB/s or more and
has at least 20 GB more free space than the models need. It prefers an internal drive, then the fastest one.

When the Python tools folder is on a USB drive, the step warns that the stack will not start while that drive is
unplugged.

## Fix a USB drive that reads at about 40 MB/s

About 40 MB/s for both reading and writing, with random reads no faster than sequential ones, means the drive is
connected at USB 2.0 speed. The drive itself is usually fine. Try these in order, running the check again after each:

1. **Turn the USB-C plug over.** A USB-C plug has its fast-data contacts on both sides, and each orientation uses a
   different set. On the reference machine on 2026-11-01, turning the plug over took drive D: from 41 MB/s to 376 MB/s. If that
   fixes it, a contact is worn or dirty: mark which way round the plug works, or replace the cable.
2. **Use a USB 3 port on the back of the PC.** These are usually blue or teal, or marked `SS`, `5Gbps` or `10Gbps`.
   Avoid front-panel ports and hubs.
3. **Use the cable that came with the drive.** Many USB-C cables, especially phone charging cables, carry only USB 2.0
   data.

About 375 MB/s is what a 5 Gbps USB port gives. A USB 3.2 Gen 2 SSD such as the Crucial X8 can reach about
1,000 MB/s on a 10 Gbps port.

## Measured on the reference machine (2026-11-01)

| Drive | Connection | Read | Write | How measured |
|---|---|---|---|---|
| C: Kingston NVMe | internal | 2,762 to 2,990 MB/s | 3,443 MB/s | `winsat` |
| C: | internal | 2,823 to 2,938 MB/s | 1,022 to 1,282 MB/s | test file |
| D: Crucial X8 | USB, plug the wrong way round | 41.6 MB/s | 41.7 MB/s | `winsat` |
| D: Crucial X8 | USB, plug turned over | 376 MB/s | 372 MB/s | `winsat` |
| D: | USB | 275 to 389 MB/s | 293 to 325 MB/s | test file |
| E: (another USB drive) | USB | 42 to 43 MB/s | 25 to 32 MB/s | test file |

The test file's write figure is lower than `winsat`'s because it includes flushing every byte to the drive. Read
figures from both methods are close. At 41 MB/s the 6.6 GB qwen3.5:9b model takes about 160 s to read, which
matches the 130 to 161 s cold loads recorded earlier. At 376 MB/s it should take about 18 s; that figure is
calculated, not measured.

## Hugging Face cache

The installer's option **Put the Hugging Face cache in `<models drive>`:\huggingface (HF_HOME) and install the hf
command** (on by default) does three things in the step **Set up the Hugging Face cache**:

1. Sets the user environment variable `HF_HOME` to `huggingface` at the root of the models drive, for example
   `D:\huggingface`. Hugging Face libraries download model weights and datasets there. On Linux and macOS it keeps
   the default, `~/.cache/huggingface`.
2. Moves the `hub`, `xet`, `datasets` and `assets` folders from the old cache (the old `HF_HOME`, or
   `%USERPROFILE%\.cache\huggingface`) to the new one. Files the new folder already has are kept.
3. If the cache is on another drive than your user profile, sets `HF_TOKEN_PATH` to
   `%USERPROFILE%\.cache\huggingface\token`, so the token stays on the internal drive where it already was.

It also installs the `hf` command (`huggingface_hub`) as a uv tool. Open a new terminal afterwards so programs see the
new variables.

**Drive format.** Hugging Face's cache uses symbolic links. Portable SSDs often come formatted as exFAT, which has no
symbolic links. The cache still works, but it stores copies instead of links, takes more space and prints a warning.
To check, open the drive's **Properties** in Explorer. If you use the drive only with this PC, NTFS avoids this, but
reformatting erases the drive.

## OpenClaw

The installer's feature **OpenClaw** (ticked by default when OpenClaw is not installed) runs the step **Install
OpenClaw**:

1. Checks the Node.js version. OpenClaw 2026.10.9 needs Node.js 24.22.1 or later in the 24 line, or 26.12.1 or later.
2. If Node.js is older, runs `winget install --id OpenJS.NodeJS.LTS`, which upgrades it to the current LTS (26.13.0 on
   2026-11-01). Windows asks for administrator approval.
3. Runs `npm install -g openclaw@latest`. npm puts it in your user profile on the system drive, which is where it
   belongs: it runs in the background and keeps its settings and keys there.

4. Points OpenClaw at the gateway. By the repository's rules, OpenClaw counts as private only while the gateway is
   its only model endpoint, so this step:
   - Onboards OpenClaw if it has no `~/.openclaw/openclaw.json` yet. This runs without questions and creates a
     workspace and a local OpenClaw gateway that listens only on this PC. It installs no background service and sets
     up no chat channels, skills or web search. Add those later with `openclaw configure`.
   - Adds a provider named `agent-stack` (`http://127.0.0.1:4000/v1`) with the six departments and `local-primary`.
     It makes `agent-stack/app-dev` the default model with no fallbacks. It also removes any image, utility or PDF
     model, and any per-agent model, that points somewhere else. OpenClaw saves the config it replaces as
     `openclaw.json.bak`.
   - Writes the gateway key (`LITELLM_MASTER_KEY` from `.env`) to `~/.openclaw/.env`, which OpenClaw reads.
     `openclaw.json` refers to the key by name only.

If OpenClaw is already installed, the installer runs only step 4, and only when OpenClaw sends prompts somewhere other
than the gateway: its row then reads `Bypasses the gateway` (or `Not set up`), ticked; untick it to leave OpenClaw as
it is.

Afterwards, open OpenClaw with `openclaw dashboard` (in the browser) or `openclaw chat` (in the terminal). Inside a chat,
`/model` switches between departments.

**Checking it later.** The Features card on the tray's Overview tab has an OpenClaw row:

- **Gateway only** (green): every model OpenClaw calls goes through the gateway.
- **Not set up** (amber): OpenClaw is installed but has not been onboarded yet.
- **Bypasses the gateway** (amber): a model talks to Ollama or another local server directly. The prompt stays on this
  PC, but it skips the gateway's traces and policy.
- **Uses an outside model** (red): a model sends prompts off this machine.

Whenever the row is not green, a **Use gateway** button appears, and it runs step 4. In a terminal the same is:

```powershell
uv run scripts/stack.py openclaw          # set it up
uv run scripts/stack.py openclaw --check  # only report where its models point
```

Large files OpenClaw downloads or creates can go on the second drive, in a short path such as `D:\openclaw-files`.

## Related

- [installation.md](installation.md): the whole setup, step by step.
- [troubleshooting.md](troubleshooting.md): symptoms and fixes, including slow drives.
- `scripts/stacklib/disks.py`: the speed check and its thresholds.
