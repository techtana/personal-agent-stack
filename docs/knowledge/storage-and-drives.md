# Storage and drives

## What this is and why the project needs it

Agent Stack stores tens of gigabytes of models on disk and starts several services from disk every time the PC
signs in. Where those files live decides how long a model takes to load, whether the stack starts at all when a
drive is missing, and whether a cache fills the system drive. This file explains how drive speed works, what makes
a USB drive slow, and why some files belong on the internal drive and others do not. The practical rules are in
[../manuals/choosing-drives.md](../manuals/choosing-drives.md).

## The ideas, built up from zero

**Two kinds of reading.** Think of a library. Fetching one long book from one shelf is quick: you walk there once
and carry it back. Fetching a thousand single pages from a thousand shelves takes far longer, even though the total
paper is the same, because most of the time goes on walking. Drives behave the same way. A **sequential read** takes
one large file from start to end; its speed is measured in megabytes per second (MB/s). A **random read** takes many
small pieces from scattered places; what matters there is **latency**, the time the drive takes to answer each
request, measured in milliseconds (ms).

A model file is the long book: Ollama reads several gigabytes in order, once, and then runs the model from the GPU's
memory (VRAM). A Python environment, a git repository or `node_modules` is the thousand pages: thousands of small
files, each opened separately.

**How long a load takes.** The time to read a file sequentially is its size divided by the read speed:

time (s) = size (MB) / read speed (MB/s)

For example, qwen3.5:9b is 6.6 GB, about 6,600 MB. At 41 MB/s that is 6,600 / 41 ≈ 161 s. At 376 MB/s it is about
18 s. At 2,800 MB/s it is under 3 s. Other work during a load (setting up the GPU, building the KV cache) adds some
time on top, so the disk time is a floor, not the whole load.

**The link can be slower than the drive.** A USB SSD is an SSD inside a box with a USB controller. Data has to pass
through the USB link, and the link has its own speed limit. USB 2.0 carries 480 megabits per second on paper, which
works out to about 35 to 42 MB/s in practice. USB 3.2 Gen 1 (5 Gbps) gives about 400 to 450 MB/s in practice, and
Gen 2 (10 Gbps) about 1,000 MB/s. Whichever is slowest, the drive or the link, sets the speed. A fast SSD on a USB 2.0
link reads at about 40 MB/s, slower than a spinning hard disk (about 150 MB/s).

A telltale sign of a USB 2.0 link: reads, writes and even random reads all come out at about the same 40 MB/s. The
link, not the flash memory, is the bottleneck, so the kind of access stops mattering.

**Why turning a USB-C plug over can matter.** A USB-C plug can go in either way round because it has contacts on both
sides. The slow USB 2.0 wires work in either orientation, but the fast USB 3 data uses one of two sets of contact
pairs, chosen by orientation. If a contact in one set is worn or dirty, that orientation cannot set up a USB 3 link,
and the drive quietly falls back to USB 2.0. Turned over, it uses the other set and runs at full speed. That is what
happened on SEKAIHOME on 2026-11-01.

**Measuring past the cache.** Windows keeps recently read files in spare RAM (the file cache). If a test writes a
file and immediately reads it back normally, the read comes from RAM and reports an impossibly high speed. The
project's check opens the file with `FILE_FLAG_NO_BUFFERING`, a Windows flag that makes every read go to the drive,
and it flushes the written data to the drive before timing stops. Windows' own tool, `winsat`, measures the drive
directly but needs administrator rights.

**Removable means it can disappear.** Anything the PC needs at sign-in should not depend on a drive that can be
unplugged. Ollama itself is on the internal drive, so with the models drive missing it still starts; only model
loads and downloads fail.

## Rules of thumb and typical numbers

| Item | Typical value | Source |
|---|---|---|
| USB 2.0 in practice | 35 to 42 MB/s | general knowledge; measured 41.6 MB/s on SEKAIHOME |
| USB 3.2 Gen 1 (5 Gbps) in practice | about 400 MB/s | measured 376 MB/s with `winsat` on SEKAIHOME |
| USB 3.2 Gen 2 (10 Gbps) | about 1,000 MB/s | the Crucial X8's rated speed, source not recorded in the repo |
| Spinning hard disk, sequential | about 150 MB/s | general knowledge, source not recorded |
| PCIe NVMe SSD (consumer) | 2,000 to 7,000 MB/s | measured 2,762 to 2,990 MB/s on SEKAIHOME's Kingston SNV3S |
| "Slow" threshold in `disks.py` | under 100 MB/s | project choice: below a hard disk |
| "Good" threshold in `disks.py` | 200 MB/s or more | project choice: a 6.6 GB model in about 30 s |
| Free space to keep on the system drive | 15 to 20 percent | common advice, source not recorded |

## Common misconceptions and edge cases

- **"A USB SSD is always fast."** Only on a USB 3 link. The same drive measured 41 and 376 MB/s an hour apart.
- **"Drive speed changes how fast the model talks."** No. Once loaded, a model runs from VRAM; the disk affects only
  the load. The exception is a model partly kept in memory-mapped RAM, such as the 35B mixture-of-experts model with
  `use_mmap: true`: under memory pressure Windows drops those pages and reads them back from the disk mid-reply.
- **"The test file's write figure is the drive's write speed."** It includes flushing every byte, so it reads lower
  than `winsat` (1,022 to 1,282 MB/s against 3,443 MB/s on C:). Read figures agree closely.
- **"winsat ran fine."** Without administrator rights `winsat disk` prints nothing and exits with code 0, which looks
  like success.
- **exFAT and symbolic links.** Portable SSDs often ship as exFAT, which has no symbolic links. Hugging Face's cache
  then stores copies instead of links. It works but uses more space.

## How the project uses it

- `scripts/stacklib/disks.py` lists the local drives, asks Windows which bus each is on (`Get-Disk` reports `USB`,
  `NVMe`, `SATA` and so on), measures each, and turns the results into warnings and a suggested models drive.
- The installer step **Check drive speed** (`step_disks` in `scripts/stacklib/install.py`) runs that check and marks
  itself with a warning instead of failing. `uv run scripts/stack.py disks` runs it on demand.
- The **Set up the Hugging Face cache** step puts `HF_HOME` next to the models, and the token on the internal drive.
- What it leaves out: it does not detect the USB link version directly (Windows does not report it simply), so it
  infers USB 2.0 from the speed and the bus type. It does not move files on its own when it warns.

## What we found

- 2026-11-01, SEKAIHOME: D: (Crucial X8, USB) read 41.6 MB/s with `winsat`; turning the USB-C plug over gave
  376 MB/s. C: (NVMe) read 2,762 to 2,990 MB/s. A second USB drive, E:, read 42 to 43 MB/s with the test file,
  likely the same USB 2.0 problem. Full table in [../manuals/choosing-drives.md](../manuals/choosing-drives.md).
- The 130 to 161 s cold loads of the 9B recorded on 2026-10-24 and 2026-10-25 (`memory/state.md`) match the 41 MB/s
  reading, so the drive was probably on a USB 2.0 link then.

## Open questions

- The cold-load time of the 9B over the fixed USB 3 link has not been measured yet.
- Whether a 10 Gbps port on SEKAIHOME brings the X8 near 1,000 MB/s is untested.
- Why E: is slow (cable, port, or the drive) is not known.

## Sources and further reading

- USB Implementers Forum, USB 2.0 and USB 3.2 specifications (usb.org): the signalling rates behind the practical
  figures above.
- Microsoft, `CreateFileW` documentation, section on `FILE_FLAG_NO_BUFFERING` (learn.microsoft.com): how uncached reads
  work and why buffers must be aligned.
- Microsoft, `winsat` command-line reference (learn.microsoft.com): what `winsat disk` measures.
- Hugging Face, "Manage huggingface_hub cache-system" (huggingface.co/docs): `HF_HOME`, `HF_TOKEN_PATH` and the
  symbolic-link fallback on Windows.

## Changes

- 2026-11-01: first version, from the drive measurements and the installer's speed check.
