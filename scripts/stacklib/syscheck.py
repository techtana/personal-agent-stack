"""Check this PC, then say which models and features are recommended on it, which work, and which are not recommended
and why. The installer's drive speed check grew into this: it still times each drive, and also reads

- the GPU: vendor, memory, what the desktop and the stack's own models hold on it now, driver, the CUDA version the
  driver runs, compute capability, PCIe link, and whether Vulkan is there (Canary-Qwen runs on it);
- the processor: name, cores, threads, AVX2 and AVX-512 (ONNX Runtime and ggml want AVX2);
- memory: total, free now, speed and modules;
- Windows: Smart App Control, long paths, battery, microphones and speakers (voice typing, read aloud), and the
  languages Windows is set up for (the speech models differ in the languages they know);
- the tools setup needs: Ollama, a python.org Python, git, winget, Node.js.

recommend() turns those facts into one Verdict per feature and per choice (chat model, its context, the speech model,
where read aloud runs, the image size) and Notes on the PC itself. The figures it compares with come from
config/installer.yaml and features.py's estimates, measured on the reference PC (RTX 3060 12 GB, Ryzen 5 5500, 32 GB of
DDR4-2133).

Where it runs: the installer starts it when its first page opens (in a thread: the drive test writes and reads a 256
MB file per drive, then deletes it), marks each feature and choice with its verdict and starts the choices that the
machine profile does not set yet at the recommended values; setup's "Check this PC" step runs it when the installer did
not (or reuses the installer's report, REUSE_S); `stack.py check` prints it; the tray's Features card shows the
verdicts of the last report. The report is kept in .run/install/system-check.json: this PC's own facts, never committed
(the folder is gitignored).
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import platform
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import IS_WINDOWS, REPO, catalog, disks, features, which
from .dictation.models import SPEECH, WHISPER_LANGUAGES, SpeechModel

CHECK_FILE = REPO / ".run" / "install" / "system-check.json"
REUSE_S = 2 * 3600            # setup reuses a report this young instead of testing the drives again
LEVELS = ("recommended", "ok", "not_recommended", "unavailable")
CUDA_FOR_TORCH = (13, 0)      # ComfyUI's PyTorch (media.torch_index cu130) and onnxruntime-gpu 1.31 need CUDA 13
CUDA_FOR_WHISPER = (12, 0)    # faster-whisper borrows cuBLAS 12 from Ollama
MOE_RAM_GB = 28               # machines/_defaults.yaml moe-12gb-32ram: a MoE model's experts live in system RAM
GPU_MARGIN_GB = 0.5           # left free on the card for the desktop's own growth
COLD_LOAD_WARN_S = 90         # a cold model load longer than this is worth a sentence
REFERENCE_CORES = 6           # the reference PC's Ryzen 5 5500, where the CPU speeds were measured
CPU_OK_S = 3.0                # seconds per 15 s of speech: a model this quick runs on the processor itself (engine.py)
CPU_FALLBACK = "small"        # dictation.cpu_model's default: what a GPU model gives way to on the processor


# ---------------------------------------------------------------- facts

@dataclass
class Gpu:
    vendor: str = ""          # NVIDIA | AMD | Intel | "" (none found)
    name: str = ""
    vram_gb: float = 0.0
    used_gb: float = 0.0      # in use on the card now, by everything
    stack_gb: float = 0.0     # of that, held by the stack's own models (Ollama, voice typing, ComfyUI)
    driver: str = ""
    cuda: str = ""            # the newest CUDA the driver runs, "13.3"
    compute: str = ""         # compute capability, "8.6"
    pcie_gen: int = 0
    pcie_width: int = 0
    vulkan: bool = False      # a Vulkan loader is installed (the graphics driver ships it)

    @property
    def desktop_gb(self) -> float:
        """What Windows and other programs hold: the card's use now, less the stack's own models."""
        return max(0.0, self.used_gb - self.stack_gb)

    @property
    def free_gb(self) -> float:
        return max(0.0, self.vram_gb - self.desktop_gb)

    @property
    def cuda_version(self) -> tuple[int, int]:
        m = re.match(r"(\d+)\.(\d+)", self.cuda or "")
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    @property
    def cuda_known(self) -> bool:
        return self.cuda_version != (0, 0)

    @property
    def nvidia(self) -> bool:
        return self.vendor == "NVIDIA" and self.vram_gb > 0


@dataclass
class Cpu:
    name: str = ""
    cores: int = 0
    threads: int = 0
    avx2: bool = False
    avx512: bool = False


@dataclass
class Memory:
    total_gb: float = 0.0
    available_gb: float = 0.0
    speed_mts: int = 0
    modules: int = 0


@dataclass
class System:
    os: str = ""
    smart_app_control: bool = False
    long_paths: bool | None = None
    on_battery: bool | None = None
    microphones: int = -1     # -1: not known (not Windows, or the registry could not be read)
    speakers: int = -1
    languages: list[str] = field(default_factory=list)   # Windows' languages, BCP-47 ("en-US")
    ollama: str = ""          # version when it answers, "installed" when only the program is there
    python_org: bool = False
    git: bool = False
    winget: bool = False
    node: str = ""


@dataclass(frozen=True)
class Verdict:
    """What the check says about a feature (key = feature id, value '') or one value of a choice (key = section.key)."""
    key: str
    value: str = ""
    level: str = "ok"         # recommended | ok | not_recommended | unavailable
    text: str = ""


@dataclass(frozen=True)
class Note:
    level: str                # ok | warn | bad
    text: str


@dataclass
class Report:
    checked_at: float = 0.0
    gpu: Gpu = field(default_factory=Gpu)
    cpu: Cpu = field(default_factory=Cpu)
    memory: Memory = field(default_factory=Memory)
    system: System = field(default_factory=System)
    drives: list[dict] = field(default_factory=list)      # disks.DriveSpeed as dicts
    verdicts: list[Verdict] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    seconds: float = 0.0      # how long the check took

    def verdict(self, key: str, value: str = "") -> Verdict | None:
        return next((v for v in self.verdicts if v.key == key and v.value == str(value)), None)

    def recommended(self, key: str) -> str | None:
        """The recommended value of a choice, or None when the check recommends none."""
        return next((v.value for v in self.verdicts if v.key == key and v.level == "recommended"), None)

    def speeds(self) -> list[disks.DriveSpeed]:
        """The drives, ignoring fields a report from another version has or lacks."""
        names = disks.DriveSpeed.__dataclass_fields__
        return [disks.DriveSpeed(**{k: v for k, v in d.items() if k in names}) for d in self.drives if d.get("root")]

    def hardware(self) -> features.Hardware:
        """The installer's Hardware, from what was measured now rather than what doctor saved."""
        g = self.gpu
        return features.Hardware(gpu=g.name, vram_gb=g.vram_gb if g.nvidia else 0.0,
                                 desktop_vram_gb=min(g.desktop_gb, g.vram_gb) if g.nvidia else 0.0,
                                 ram_gb=self.memory.total_gb, threads=self.cpu.threads or (os.cpu_count() or 1),
                                 smart_app_control=self.system.smart_app_control)

    def describe(self) -> str:
        """One line: 'NVIDIA GeForce RTX 3060, 12.0 GB (1.0 GB in use by the desktop; driver 610.88, CUDA 13.3), AMD
        Ryzen 5 5500 (6 cores, 12 threads, AVX2), 32 GB of RAM at 2133 MT/s (18 GB free)'."""
        g, c, m = self.gpu, self.cpu, self.memory
        if g.vram_gb:
            extra = [f"{g.desktop_gb:.1f} GB in use by the desktop"]
            if g.driver:
                extra.append(f"driver {g.driver}" + (f", CUDA {g.cuda}" if g.cuda else ""))
            gpu = f"{g.name or g.vendor + ' GPU'}, {g.vram_gb:.1f} GB ({'; '.join(extra)})"
        else:
            gpu = "no graphics card with its own memory found"
        flags = "AVX-512" if c.avx512 else "AVX2" if c.avx2 else "no AVX2"
        cpu = f"{c.name or 'processor'} ({c.cores} cores, {c.threads} threads, {flags})"
        ram = f"{m.total_gb:.0f} GB of RAM" + (f" at {m.speed_mts} MT/s" if m.speed_mts else "") + (
            f" ({m.available_gb:.0f} GB free)" if m.available_gb else "")
        return f"{gpu}; {cpu}; {ram}"


# ---------------------------------------------------------------- probes (each one never raises)

def _run(cmd: list[str], timeout: float = 15) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False,
                              creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def parse_cuda(text: str) -> str:
    """The CUDA version from nvidia-smi's banner: 'CUDA Version: 12.4' or (drivers 600 and later) 'CUDA UMD Version:
    13.3'."""
    m = re.search(r"CUDA (?:UMD )?Version:\s*(\d+\.\d+)", text or "")
    return m.group(1) if m else ""


def probe_nvidia() -> Gpu | None:
    smi = which("nvidia-smi")
    if not smi:
        return None
    def query(fields: str) -> list[str]:
        out = _run([smi, f"--query-gpu={fields}", "--format=csv,noheader,nounits"])
        line = next((x for x in out.splitlines() if x.strip()), "")
        return [x.strip() for x in line.split(",")]

    parts = query("name,memory.total,memory.used,driver_version")
    if len(parts) < 4:
        return None

    def num(value: str) -> float:
        try:
            return float(value)
        except ValueError:
            return 0.0
    g = Gpu(vendor="NVIDIA", name=parts[0], vram_gb=num(parts[1]) / 1024, used_gb=num(parts[2]) / 1024,
            driver=parts[3], cuda=parse_cuda(_run([smi])))
    # Asked one by one: an older driver rejects a field it does not know, and that must not lose the card.
    compute = query("compute_cap")
    g.compute = compute[0] if compute and compute[0][:1].isdigit() else ""
    g.pcie_gen = int(num((query("pcie.link.gen.max") or ["0"])[0]))
    g.pcie_width = int(num((query("pcie.link.width.max") or ["0"])[0]))
    return g


def probe_display_adapter() -> Gpu | None:
    """An AMD or Intel card on Windows, from the display class in the registry (its memory size is exact there, where
    WMI's AdapterRAM stops at 4 GB)."""
    if not IS_WINDOWS:
        return None
    import winreg

    best: Gpu | None = None
    base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    for i in range(16):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{i:04d}") as key:
                name = str(winreg.QueryValueEx(key, "DriverDesc")[0])
                try:
                    size = int(winreg.QueryValueEx(key, "HardwareInformation.qwMemorySize")[0])
                except OSError:
                    raw = winreg.QueryValueEx(key, "HardwareInformation.MemorySize")[0]
                    size = int.from_bytes(raw, "little") if isinstance(raw, bytes) else int(raw)
                try:
                    driver = str(winreg.QueryValueEx(key, "DriverVersion")[0])
                except OSError:
                    driver = ""
        except (OSError, ValueError):
            continue
        vendor = "AMD" if re.search(r"AMD|Radeon", name, re.I) else "Intel" if "Intel" in name else \
            "NVIDIA" if "NVIDIA" in name else ""
        gb = size / 2 ** 30
        if vendor and (best is None or gb > best.vram_gb):
            best = Gpu(vendor=vendor, name=name, vram_gb=gb, driver=driver)
    return best


def stack_gpu_gb(profile: dict) -> float:
    """GB the stack's own models hold on the GPU now (tray GPU card's rows), asked in parallel: a refused localhost
    connection takes about 2 s on Windows."""
    from . import gpu_models, ollama
    from .dictation import control

    ports = profile.get("ports") or {}

    def ps():
        return ollama.ps(f"http://127.0.0.1:{ports.get('ollama', 11434)}")

    def health():
        try:
            return control.call(int(ports.get("dictation", 8790)), "health", timeout=1.5)
        except (OSError, ValueError):
            return None

    def comfy():
        return gpu_models.comfy_stats(int(ports.get("comfyui", 8188)))
    try:
        with concurrent.futures.ThreadPoolExecutor(3) as pool:
            a, b, c = pool.submit(ps), pool.submit(health), pool.submit(comfy)
            rows = gpu_models.rows(a.result() or [], b.result(), c.result())
    except Exception:  # noqa: BLE001 - the check goes on with what Windows says is in use
        return 0.0
    total = 0.0
    for r in rows:
        share = str(r.get("gpu") or "")
        frac = 1.0 if share == "100%" else float(share.rstrip("%")) / 100 if share.endswith("%") else 0.0
        total += int(r.get("bytes") or 0) * frac / 2 ** 30
    return total


def vulkan_present() -> bool:
    if IS_WINDOWS:
        return (Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "vulkan-1.dll").exists()
    return any(Path(p).exists() for p in ("/usr/lib/x86_64-linux-gnu/libvulkan.so.1", "/usr/lib/libvulkan.so.1"))


def probe_gpu(profile: dict) -> Gpu:
    g = probe_nvidia() or probe_display_adapter() or Gpu()
    g.vulkan = vulkan_present()
    if g.vram_gb:
        g.stack_gb = min(stack_gpu_gb(profile), g.used_gb)
    return g


def probe_cpu() -> Cpu:
    c = Cpu(threads=os.cpu_count() or 1)
    try:
        import psutil

        c.cores = int(psutil.cpu_count(logical=False) or c.threads)
    except Exception:  # noqa: BLE001
        c.cores = c.threads
    if IS_WINDOWS:
        import ctypes
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                c.name = str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
        try:
            present = ctypes.windll.kernel32.IsProcessorFeaturePresent
            c.avx2, c.avx512 = bool(present(40)), bool(present(41))   # PF_AVX2_..., PF_AVX512F_INSTRUCTIONS_AVAILABLE
        except (AttributeError, OSError):
            pass
    else:
        try:
            info = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
            m = re.search(r"^model name\s*:\s*(.+)$", info, re.M)
            c.name = m.group(1).strip() if m else platform.processor()
            flags = set((re.search(r"^flags\s*:\s*(.+)$", info, re.M) or [None, ""])[1].split())
            c.avx2, c.avx512 = "avx2" in flags, "avx512f" in flags
        except OSError:
            c.name = platform.processor()
    return c


def parse_ram_modules(text: str) -> tuple[int, int]:
    """(MT/s, number of modules) from doctor's '16 GB @ 2133 MT/s, 16 GB @ 2133 MT/s'."""
    speeds = [int(x) for x in re.findall(r"@\s*(\d+)\s*MT/s", text or "")]
    return (min(speeds) if speeds else 0), len(re.findall(r"\d+\s*GB", text or ""))


def probe_memory(profile: dict) -> Memory:
    m = Memory()
    try:
        import psutil

        vm = psutil.virtual_memory()
        m.total_gb, m.available_gb = vm.total / 2 ** 30, vm.available / 2 ** 30
    except Exception:  # noqa: BLE001
        m.total_gb = float((profile.get("detected") or {}).get("ram_gb") or 0)
    m.speed_mts, m.modules = parse_ram_modules(str((profile.get("detected") or {}).get("ram_modules") or ""))
    return m


def _reg(root, path: str, name: str):
    import winreg

    try:
        with winreg.OpenKey(root, path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def audio_endpoints(kind: str) -> int:
    """Active microphones (kind 'Capture') or speakers and headphones ('Render') Windows lists; -1 when unknown.
    DeviceState 1 is DEVICE_STATE_ACTIVE (2 disabled, 4 not present, 8 unplugged)."""
    if not IS_WINDOWS:
        return -1
    import winreg

    path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\{kind}"
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    except OSError:
        return -1
    n = 0
    with root:
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            state = _reg(winreg.HKEY_LOCAL_MACHINE, f"{path}\\{sub}", "DeviceState")
            if isinstance(state, int) and state & 0xF == 1:
                n += 1
    return n


def windows_languages() -> list[str]:
    """The languages in Windows' Settings > Time & language > Language, in their order ('en-US', 'th')."""
    if not IS_WINDOWS:
        lang = os.environ.get("LANG", "").split(".")[0].replace("_", "-")
        return [lang] if lang and lang not in ("C", "POSIX") else []
    import winreg

    value = _reg(winreg.HKEY_CURRENT_USER, r"Control Panel\International\User Profile", "Languages")
    return [str(x) for x in value if x] if isinstance(value, list) else []


def probe_system(profile: dict) -> System:
    from . import install, ollama

    s = System(os=f"{platform.system()} {platform.release()} {platform.version()}".strip(),
               smart_app_control=features.smart_app_control_on())
    if IS_WINDOWS:
        import winreg

        long_paths = _reg(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem", "LongPathsEnabled")
        s.long_paths = bool(long_paths) if long_paths is not None else None
    try:
        import psutil

        battery = psutil.sensors_battery()
        s.on_battery = None if battery is None else not battery.power_plugged
    except Exception:  # noqa: BLE001
        s.on_battery = None
    s.microphones, s.speakers = audio_endpoints("Capture"), audio_endpoints("Render")
    s.languages = windows_languages()
    port = (profile.get("ports") or {}).get("ollama", 11434)
    s.ollama = ollama.version(f"http://127.0.0.1:{port}") or ("installed" if which("ollama") else "")
    try:
        from . import media

        py = media.system_python() or ""
        s.python_org = bool(py) and "\\uv\\python\\" not in py.lower() and "/uv/python/" not in py.lower()
    except Exception:  # noqa: BLE001
        s.python_org = False
    s.git, s.winget = bool(which("git")), bool(which("winget"))
    try:
        v = install._node_version()
        s.node = ".".join(map(str, v)) if v else ""
    except Exception:  # noqa: BLE001
        s.node = ""
    return s


def probe(profile: dict, report=lambda *a: None, drives: bool = True) -> Report:
    """Every fact the recommendations need. report(text, fraction) follows the slow part, the drive test."""
    r = Report(checked_at=time.time())
    report("reading the graphics card, processor and memory", 0.02)
    with concurrent.futures.ThreadPoolExecutor(3) as pool:
        gpu, system = pool.submit(probe_gpu, profile), pool.submit(probe_system, profile)
        r.cpu, r.memory = probe_cpu(), probe_memory(profile)
        r.gpu, r.system = gpu.result(), system.result()
    if drives:
        speeds = disks.measure_all(disks.list_drives(), lambda text, frac: report(text, 0.1 + 0.85 * frac))
        r.drives = [asdict(s) for s in speeds]
    return r


# ---------------------------------------------------------------- recommendations

def whisper_code(tag: str) -> str:
    """A Windows language tag as a Whisper code: 'en-US' -> 'en', 'nb-NO' -> 'no', 'fil-PH' -> 'tl', 'zh-Hant-TW' ->
    'zh'; '' when Whisper does not know it."""
    base = (tag or "").replace("_", "-").split("-")[0].lower()
    base = {"nb": "no", "fil": "tl", "jv": "jw", "iw": "he", "in": "id"}.get(base, base)
    return base if base in WHISPER_LANGUAGES else ""


def _languages(r: Report) -> list[str]:
    return list(dict.fromkeys(c for c in (whisper_code(t) for t in r.system.languages) if c))


def _names(codes) -> str:
    names = [WHISPER_LANGUAGES.get(c, c) for c in codes]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _store_drive(r: Report, profile: dict) -> disks.DriveSpeed | None:
    root = disks.drive_of(features.effective_model_store(profile)).lower()
    return next((s for s in r.speeds() if s.root.lower() == root and s.read_mbps), None)


def _cold_load(size_gb: float, drive: disks.DriveSpeed | None) -> str:
    if not drive or not drive.read_mbps or not size_gb:
        return ""
    secs = size_gb * 1000 / drive.read_mbps
    if secs < COLD_LOAD_WARN_S:
        return ""
    return f" A cold load from {drive.letter} ({drive.read_mbps:.0f} MB/s) takes about {secs / 60:.0f} min."


def _with(profile: dict, section: str, **values) -> dict:
    return {**profile, section: {**(profile.get(section) or {}), **values}}


def chat_verdicts(r: Report, profile: dict, hw: features.Hardware) -> list[Verdict]:
    """One verdict per chat model the installer offers, at the profile's context: the largest model that fits the
    card whole is recommended; a mixture-of-experts model whose experts sit in system RAM works where RAM allows."""
    cat = profile.get("catalog") or {}
    ctx = int((profile.get("models") or {}).get("primary_num_ctx") or 32768) or 32768
    names = [n for n, c in cat.items() if (c or {}).get("role") in ("small", "primary")]
    current = (profile.get("models") or {}).get("primary")
    if current and current not in names:
        names.append(current)
    store = _store_drive(r, profile)
    rows = []
    for name in names:
        vram, ram, _basis, speed = features.chat_model_memory(_with(profile, "models", primary=name,
                                                                     primary_num_ctx=ctx), hw)
        rows.append((name, vram, ram, speed, float((cat.get(name) or {}).get("size_gb") or 0),
                     features.is_moe(profile, name)))
    free = hw.gpu_free_gb - GPU_MARGIN_GB
    if hw.vram_gb <= 0:
        out = []
        for name, _v, ram, _s, size, moe in rows:
            if moe or size > r.memory.total_gb / 2:
                out.append(Verdict("models.primary", name, "not_recommended",
                                   f"Without an NVIDIA GPU it would run on the processor alone, far too slowly "
                                   f"({size:.0f} GB)."))
            else:
                out.append(Verdict("models.primary", name, "ok", "Runs on the processor alone: a few tokens per "
                                   "second, so replies take minutes." + _cold_load(size, store)))
        return out
    fits = [x for x in rows if x[2] < 0.3 and x[1] <= free]
    best = max(fits, key=lambda x: (x[4], x[0] == current), default=None)
    out = []
    for name, vram, ram, speed, size, moe in rows:
        load = _cold_load(size, store)
        tps = f", about {speed} tokens per second on {features.REFERENCE}" if speed else ""
        if best and name == best[0]:
            out.append(Verdict("models.primary", name, "recommended",
                               f"Fits the GPU whole: {vram:.1f} of the {hw.gpu_free_gb:.1f} GB free{tps}." + load))
        elif ram < 0.3 and vram <= free:
            out.append(Verdict("models.primary", name, "ok", f"Fits the GPU whole ({vram:.1f} GB){tps}; smaller than "
                               f"{best[0]}." + load if best else f"Fits the GPU whole ({vram:.1f} GB){tps}." + load))
        elif moe:
            need = max(ram, size - max(0.0, free))
            if r.memory.total_gb < MOE_RAM_GB:
                out.append(Verdict("models.primary", name, "not_recommended",
                                   f"A mixture of experts whose experts sit in system RAM: it needs {MOE_RAM_GB} GB of "
                                   f"RAM, and this PC has {r.memory.total_gb:.0f} GB." + load))
            elif r.memory.available_gb and r.memory.available_gb < need + 2:
                out.append(Verdict("models.primary", name, "not_recommended",
                                   f"Its experts need about {need:.0f} GB of free system RAM; {r.memory.available_gb:.0f}"
                                   " GB are free now, so Windows would page and loading may time out." + load))
            else:
                speed_text = (f"about {speed} tokens per second on {features.REFERENCE}" if speed else
                              "its speed was not measured (a sibling made about 25 tokens per second)")
                out.append(Verdict("models.primary", name, "ok",
                                   f"{vram:.1f} GB on the GPU and about {need:.0f} GB of experts in system RAM: "
                                   f"{speed_text}, with little RAM left for other programs." + load))
        else:
            spill = max(0.0, vram + ram - max(0.0, free))
            out.append(Verdict("models.primary", name, "not_recommended",
                               f"Needs {vram + ram:.1f} GB of GPU memory and {hw.gpu_free_gb:.1f} GB are free: Ollama "
                               f"would keep {spill:.1f} GB in system RAM, and replies would be several times slower."
                               + load))
    return out


def speech_on_gpu(r: Report, m: SpeechModel) -> bool:
    """Whether the model's GPU path exists here: CUDA for faster-whisper and onnx-asr, Vulkan for transcribe.cpp."""
    if m.engine == "transcribe.cpp":
        return r.gpu.vulkan and r.gpu.vram_gb >= m.vram_gb + 1
    return r.gpu.nvidia and (not r.gpu.cuda_known or r.gpu.cuda_version >= CUDA_FOR_WHISPER)


def _room(r: Report, m: SpeechModel, room_gb: float) -> float:
    """GPU memory the speech model may use: what the chat model leaves on an NVIDIA card; on an AMD or Intel card,
    which the stack's chat model does not use, all that is free there (Canary-Qwen reaches it through Vulkan)."""
    if not r.gpu.nvidia and m.engine == "transcribe.cpp":
        return r.gpu.free_gb - GPU_MARGIN_GB
    return room_gb


def speech_verdicts(r: Report, profile: dict, room_gb: float) -> list[Verdict]:
    """One verdict per speech model. room_gb: GPU memory left next to the recommended chat model. The choice, in
    order: languages Windows has that Parakeet does not know -> Whisper large-v3-turbo (or small without a GPU);
    English only with room on the GPU -> Canary-Qwen, the most accurate; Parakeet's languages with a processor that
    has AVX2 and 4 cores -> Parakeet, which holds no GPU memory; else Whisper large-v3-turbo or small."""
    langs = _languages(r)
    cpu_ok = r.cpu.avx2 and r.cpu.cores >= 4
    scale = REFERENCE_CORES / max(1, min(r.cpu.cores or REFERENCE_CORES, 16))
    out: dict[str, Verdict] = {}
    for name, m in SPEECH.items():
        missing = [c for c in langs if not m.speaks(c)]
        gpu_here = speech_on_gpu(r, m) and _room(r, m, room_gb) >= m.vram_gb
        if missing:
            out[name] = Verdict("dictation.model", name, "not_recommended",
                                f"Does not transcribe {_names(missing)}, which Windows here is set up for.")
        elif m.device == "gpu" and gpu_here:
            out[name] = Verdict("dictation.model", name, "ok",
                                f"On the GPU: 15 s of speech in about {m.speed_gpu:.1f} s, {m.vram_gb:.1f} GB of GPU "
                                "memory" + ("" if m.measured else " (estimate)") + ".")
        elif m.device == "gpu":
            cpu_s = m.speed_cpu * scale
            why = ("no Vulkan graphics driver" if m.engine == "transcribe.cpp" and not r.gpu.vulkan else
                   "no NVIDIA GPU with CUDA 12" if not speech_on_gpu(r, m) else
                   f"only {max(0.0, room_gb):.1f} GB of GPU memory left next to the chat model")
            if 0 < cpu_s <= CPU_OK_S or name in (CPU_FALLBACK, "base"):   # the fallback itself is always usable
                out[name] = Verdict("dictation.model", name, "ok",
                                    f"On the processor ({why}): 15 s of speech in about {cpu_s:.1f} s.")
            else:
                out[name] = Verdict("dictation.model", name, "not_recommended",
                                    f"Needs the GPU ({why}); on the processor voice typing would run "
                                    f"{SPEECH[CPU_FALLBACK].label if CPU_FALLBACK in SPEECH else 'a small model'} "
                                    "instead.")
        elif cpu_ok:
            out[name] = Verdict("dictation.model", name, "ok",
                                f"On the processor, with no GPU memory: 15 s of speech in about "
                                f"{m.speed_cpu * scale:.1f} s" + (" (scaled from the reference PC's 6 cores)"
                                                                  if r.cpu.cores != REFERENCE_CORES else "") + ".")
        else:
            out[name] = Verdict("dictation.model", name, "not_recommended",
                                "Slow on this processor (it lacks AVX2 or has fewer than 4 cores).")
    usable = {n for n, v in out.items() if v.level == "ok"}
    english = bool(langs) and set(langs) == {"en"}
    hints = bool(str((profile.get("dictation") or {}).get("vocabulary") or "").strip())
    pick = ""
    if hints and "large-v3-turbo" in usable and speech_on_gpu(r, SPEECH["large-v3-turbo"]) \
            and _room(r, SPEECH["large-v3-turbo"], room_gb) >= SPEECH["large-v3-turbo"].vram_gb:
        pick = "large-v3-turbo"   # only Whisper takes dictation.vocabulary's hints
    elif english and "canary-qwen-2.5b" in usable and speech_on_gpu(r, SPEECH["canary-qwen-2.5b"]) \
            and _room(r, SPEECH["canary-qwen-2.5b"], room_gb) >= SPEECH["canary-qwen-2.5b"].vram_gb:
        pick = "canary-qwen-2.5b"
    elif langs and "parakeet-tdt-0.6b-v3" in usable:
        pick = "parakeet-tdt-0.6b-v3"
    elif "large-v3-turbo" in usable and speech_on_gpu(r, SPEECH["large-v3-turbo"]) \
            and _room(r, SPEECH["large-v3-turbo"], room_gb) >= SPEECH["large-v3-turbo"].vram_gb:
        pick = "large-v3-turbo"
    elif "parakeet-tdt-0.6b-v3" in usable and not langs:
        pick = "parakeet-tdt-0.6b-v3"
    elif "small" in usable:
        pick = "small"
    if pick:
        why = {"canary-qwen-2.5b": "the most accurate for English",
               "parakeet-tdt-0.6b-v3": "it leaves the GPU to the chat model",
               "large-v3-turbo": ("it keeps your vocabulary hints" if hints else
                                  "it knows all of Whisper's 100 languages"),
               "small": "light enough for the processor"}.get(pick, "")
        v = out[pick]
        out[pick] = Verdict(v.key, v.value, "recommended", f"{why[:1].upper()}{why[1:]}. {v.text}")
    return list(out.values())


def context_verdicts(profile: dict, hw: features.Hardware, model: str, speech_gb: float) -> list[Verdict]:
    """The chat model's context sizes: the largest that fits on the card next to the speech model is recommended."""
    out, fitting = [], []
    for n in catalog.context_choices():
        vram, ram, _b, _s = features.chat_model_memory(_with(profile, "models", primary=model, primary_num_ctx=n), hw)
        fits = hw.vram_gb > 0 and ram < 0.3 and vram + speech_gb <= hw.gpu_free_gb - GPU_MARGIN_GB
        out.append([n, vram, fits])
        if fits:
            fitting.append(n)
    # Recommended: the largest context that fits and was measured with this model (16k and 32k for the 9B), or up to
    # 32k when none was; a larger one that fits only by the estimate works, but is not recommended unmeasured.
    measured = {c for (n, c) in features.MEASURED_MODELS if n == model}
    best = max((n for n in fitting if n in measured), default=None) or max(
        (n for n in fitting if n <= 32768), default=None)
    verdicts = []
    for n, vram, fits in out:
        if n == best:
            verdicts.append(Verdict("models.primary_num_ctx", str(n), "recommended",
                                    f"{n // 1024}k tokens: {model} takes {vram:.1f} GB and fits beside the speech model."))
        elif fits:
            verdicts.append(Verdict("models.primary_num_ctx", str(n), "ok", f"{n // 1024}k tokens fit ({vram:.1f} GB"
                                    + ("" if n in measured else ", estimated") + ")."))
        else:
            verdicts.append(Verdict("models.primary_num_ctx", str(n), "not_recommended",
                                    f"{n // 1024}k tokens need {vram:.1f} GB with {model}: more than fits next to the "
                                    "other models."))
    return verdicts


def feature_verdicts(r: Report, profile: dict, hw: features.Hardware, chat_gb: float, speech: str) -> list[Verdict]:
    g, sysinfo = r.gpu, r.system
    out = [Verdict("models", "", "recommended", "Required."), Verdict("gateway", "", "recommended", "Required."),
           Verdict("web_filter", "", "recommended", "A few MB of lists; nothing runs.")]
    out.append(Verdict("chat", "", "recommended" if r.memory.total_gb >= 8 else "not_recommended",
                       "Chat in the browser, about 0.7 GB of RAM." if r.memory.total_gb >= 8 else
                       f"Open WebUI needs about 0.7 GB of RAM; this PC has {r.memory.total_gb:.0f} GB in all."))
    if sysinfo.smart_app_control:
        out.append(Verdict("tracing", "", "not_recommended",
                           "Smart App Control is on, and it blocked Phoenix's compiled modules on the reference PC."))
    else:
        out.append(Verdict("tracing", "", "recommended", "For debugging; the tray's Usage tab works without it."))
    free_room = max(0.0, hw.gpu_free_gb - chat_gb)
    need = catalog.feature_footprint("images")["vram_busy_gb"] or 10.5
    if not g.nvidia:
        out.append(Verdict("images", "", "unavailable", "ComfyUI's PyTorch needs an NVIDIA card; without one an image "
                                                        "takes many minutes."))
    elif g.cuda_known and g.cuda_version < CUDA_FOR_TORCH:
        out.append(Verdict("images", "", "not_recommended",
                           f"The NVIDIA driver runs CUDA {g.cuda or 'older than 13'}; ComfyUI's PyTorch needs CUDA 13 "
                           "(driver 580 or newer): update the driver first."))
    elif g.vram_gb < 8:
        out.append(Verdict("images", "", "not_recommended",
                           f"An image needs about {need:.1f} GB of GPU memory and the card has {g.vram_gb:.0f} GB: "
                           "ComfyUI would keep most of the model in RAM, and each image takes minutes."))
    elif g.vram_gb < 10:
        out.append(Verdict("images", "", "ok", f"Works, more slowly: an image needs about {need:.1f} GB, so ComfyUI "
                                               "moves parts of the model to RAM while it works."))
    else:
        out.append(Verdict("images", "", "recommended",
                           f"Z-Image-Turbo needs about {need:.1f} GB while it works; with the chat model loaded "
                           f"{free_room:.1f} GB are left, so click Media on the tray's GPU card before a batch."
                           if free_room < need else f"Z-Image-Turbo needs about {need:.1f} GB while it works: it fits."))
    mics = sysinfo.microphones
    label = SPEECH[speech].label if speech in SPEECH else "Whisper"
    if mics == 0:
        out.append(Verdict("voice_typing", "", "not_recommended", "Windows lists no working microphone; plug one in "
                                                                  "first (a headset works best)."))
    else:
        out.append(Verdict("voice_typing", "", "ok", f"With {label}" + (
            " and the microphone Windows lists." if mics > 0 else "; the microphone was not checked.")))
    if sysinfo.speakers == 0:
        out.append(Verdict("read_aloud", "", "not_recommended", "Windows lists no speakers or headphones."))
    else:
        out.append(Verdict("read_aloud", "", "ok", "Kokoro on the GPU (about 1 GB) or the processor."
                           if g.nvidia and g.cuda_version >= CUDA_FOR_TORCH else "Kokoro on the processor, about 3x "
                                                                                  "faster than real time."))
    node_ok = False
    try:
        from .install import node_ok_for_openclaw

        node_ok = node_ok_for_openclaw(catalog.version_tuple(sysinfo.node)) if sysinfo.node else False
    except Exception:  # noqa: BLE001
        pass
    out.append(Verdict("openclaw", "", "recommended" if node_ok or sysinfo.winget else "ok",
                       "Node.js is new enough." if node_ok else "Setup upgrades Node.js with winget (Windows asks for "
                       "admin)." if sysinfo.winget else "Needs a newer Node.js, which you install from nodejs.org."))
    return out


def option_verdicts(r: Report, hw: features.Hardware, room_gb: float) -> list[Verdict]:
    g = r.gpu
    out = []
    gpu_ok = g.nvidia and (not g.cuda_known or g.cuda_version >= CUDA_FOR_TORCH) and room_gb >= 1.0
    out.append(Verdict("read_aloud.device", "auto", "recommended" if gpu_ok else "ok",
                       "The GPU, where a sentence takes about 0.3 s (1 GB of GPU memory)." if gpu_ok else
                       "Picks the GPU when its libraries are there, else the processor."))
    out.append(Verdict("read_aloud.device", "cpu", "ok" if gpu_ok else "recommended",
                       ("" if gpu_ok else "The GPU has no room or no CUDA 13 here. ")
                       + "The processor: about 1.5 s per sentence, no GPU memory."))
    small_ram = r.memory.total_gb and r.memory.total_gb < 12
    out.append(Verdict("read_aloud.kokoro", "fp32", "ok" if small_ram else "recommended", "The full weights (0.5 GB of "
                                                                                          "RAM)."))
    out.append(Verdict("read_aloud.kokoro", "int8", "recommended" if small_ram else "ok",
                       ("Little RAM here. " if small_ram else "") + "As fast on the processor, 0.3 GB of RAM."))
    sizes = [str(s) for s in catalog.images().get("sizes") or ()]
    want = "1024x1024" if g.vram_gb >= 10 else "768x768"
    for s in sizes:
        out.append(Verdict("media.image_size", s, "recommended" if s == want else "ok",
                           "Fits this card's memory best." if s == want else ""))
    return out


def system_notes(r: Report, profile: dict) -> list[Note]:
    out: list[Note] = []
    g, s, m = r.gpu, r.system, r.memory
    if g.nvidia and g.cuda_version and g.cuda_version < CUDA_FOR_TORCH:
        out.append(Note("warn", f"The NVIDIA driver {g.driver} runs CUDA {g.cuda}: images and read aloud on the GPU "
                                "need CUDA 13 (driver 580 or newer). Update it from nvidia.com or the NVIDIA app."))
    if g.nvidia and g.pcie_width and g.pcie_width < 8:
        out.append(Note("warn", f"The card runs on {g.pcie_width} PCIe lanes: models that spill into system RAM (a "
                                "mixture of experts, or one too big for the card) are slower than on 16."))
    if g.vram_gb and not g.nvidia:
        out.append(Note("warn", f"{g.name}: the stack's estimates count only NVIDIA cards. Whisper and ComfyUI need "
                                "CUDA, and Ollama runs on some AMD cards only; Canary-Qwen uses this card through "
                                "Vulkan."))
    if s.smart_app_control:
        out.append(Note("warn", "Smart App Control is on: Windows judges every new program file. The stack's pinned "
                                "packages loaded on the reference PC; Phoenix did not."))
    if s.long_paths is False and IS_WINDOWS:
        out.append(Note("ok", "Windows' 260-character path limit is on: keep the folders' paths short."))
    if s.on_battery:
        out.append(Note("warn", "This PC runs on battery: Windows slows the GPU and processor to save power."))
    if m.available_gb and m.available_gb < 8:
        out.append(Note("warn", f"Only {m.available_gb:.0f} GB of RAM are free now: close programs before loading big "
                                "models or making images."))
    if m.modules == 1:
        out.append(Note("warn", "One memory module: the processor reads RAM on one channel, half the speed of two."))
    if not s.ollama:
        out.append(Note("warn", "Ollama is not installed yet; setup installs it with winget."))
    if not s.python_org and IS_WINDOWS:
        out.append(Note("warn", "No python.org Python found: voice typing and images build their environments from "
                                "one (Smart App Control refused uv's own builds). Install Python from python.org."))
    if not s.git:
        out.append(Note("warn", "git is missing: setup needs it for ComfyUI (winget install Git.Git)."))
    speeds = r.speeds()
    if speeds:
        need = sum(float(((profile.get("catalog") or {}).get(x) or {}).get("size_gb") or 0)
                   for x in features.models_to_pull(profile))
        from . import install

        warnings, suggestion = disks.advise(speeds, features.effective_model_store(profile),
                                            install.current_tool_dir(), need)
        out += [Note("warn", w) for w in warnings]
        if suggestion:
            out.append(Note("warn", suggestion))
        measured = [x for x in speeds if not x.error]
        if measured and not warnings and not suggestion:
            out.append(Note("ok", "Drives: " + "; ".join(x.summary() for x in measured) + "."))
    return out


def _explicit(profile: dict, section: str, key: str) -> bool:
    try:
        from .install import explicit_options

        return (section, key) in explicit_options(profile)
    except Exception:  # noqa: BLE001
        return False


def recommend(r: Report, profile: dict) -> Report:
    """Fill the report's verdicts and notes from its facts."""
    hw = r.hardware()
    chat = chat_verdicts(r, profile, hw)
    best_chat = next((v.value for v in chat if v.level == "recommended"),
                     (profile.get("models") or {}).get("primary") or "")
    if _explicit(profile, "models", "primary"):   # the owner's model stays: size the rest around it
        best_chat = (profile.get("models") or {}).get("primary") or best_chat
    ctx = int((profile.get("models") or {}).get("primary_num_ctx") or 32768) or 32768
    chat_gb = 0.0
    if best_chat and hw.vram_gb > 0:
        chat_gb = features.chat_model_memory(_with(profile, "models", primary=best_chat, primary_num_ctx=ctx), hw)[0]
    room = hw.gpu_free_gb - chat_gb - GPU_MARGIN_GB
    speech = speech_verdicts(r, profile, room)
    best_speech = next((v.value for v in speech if v.level == "recommended"), "")
    m = SPEECH.get(best_speech)
    # GPU memory the speech model takes from the chat model's card (none on another card or on the processor)
    speech_gb = m.vram_gb if m and m.device == "gpu" and speech_on_gpu(r, m) and r.gpu.nvidia else 0.0
    contexts = context_verdicts(profile, hw, best_chat, speech_gb) if best_chat and hw.vram_gb > 0 else []
    r.verdicts = [*feature_verdicts(r, profile, hw, chat_gb, best_speech), *chat, *contexts, *speech,
                  *option_verdicts(r, hw, room - speech_gb)]
    r.notes = system_notes(r, profile)
    return r


# ---------------------------------------------------------------- run, keep, read

def run(profile: dict, report=lambda *a: None, drives: bool = True, save_to: Path | None | bool = True) -> Report:
    """Check, recommend and keep the report (save_to: True for CHECK_FILE, a path, or None/False not to keep it)."""
    t0 = time.monotonic()
    r = recommend(probe(profile, report, drives), profile)
    r.seconds = time.monotonic() - t0
    if save_to:
        try:
            save(r, None if save_to is True else save_to)
        except OSError:
            pass
    report("done", 1.0)
    return r


def save(r: Report, path: Path | None = None) -> None:
    path = path or CHECK_FILE   # looked up now, not when the function was defined (tests point it elsewhere)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(r), indent=1), encoding="utf-8")
    os.replace(tmp, path)


def from_dict(d: dict) -> Report:
    def make(cls, raw):
        names = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (raw or {}).items() if k in names})
    return Report(checked_at=float(d.get("checked_at") or 0), gpu=make(Gpu, d.get("gpu")), cpu=make(Cpu, d.get("cpu")),
                  memory=make(Memory, d.get("memory")), system=make(System, d.get("system")),
                  drives=[x for x in d.get("drives") or [] if isinstance(x, dict)],
                  verdicts=[make(Verdict, v) for v in d.get("verdicts") or []],
                  notes=[make(Note, n) for n in d.get("notes") or []], seconds=float(d.get("seconds") or 0))


def load(path: Path | None = None, max_age_s: float | None = None) -> Report | None:
    """The last saved report, or None (none yet, unreadable, or older than max_age_s)."""
    try:
        r = from_dict(json.loads((path or CHECK_FILE).read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001 - a missing, broken, hand-edited or older file means no report
        return None
    if max_age_s is not None and time.time() - r.checked_at > max_age_s:
        return None
    return r


# ---------------------------------------------------------------- words

LEVEL_WORDS = {"recommended": "Recommended", "ok": "Works here", "not_recommended": "Not recommended",
               "unavailable": "Not available"}
LEVEL_MARKS = {"recommended": "✓", "ok": "·", "not_recommended": "!", "unavailable": "✗"}   # the installer
TEXT_MARKS = {"recommended": "+", "ok": "-", "not_recommended": "!", "unavailable": "x"}   # a console (cp1252)


def tag(v: Verdict | None) -> str:
    """' · recommended' or ' · not recommended' for a drop-down entry; '' otherwise."""
    if v is None or v.level == "ok":
        return ""
    return f"  · {LEVEL_WORDS[v.level].lower()}"


def lines(r: Report, profile: dict | None = None) -> list[str]:
    """The report as text, for `stack.py check` and the setup log."""
    f = features
    out = [f"This PC: {r.describe()}."]
    s = r.system
    parts = [f"Smart App Control {'on' if s.smart_app_control else 'off'}"]
    if s.microphones >= 0:
        parts.append(f"{s.microphones} microphone{'s' if s.microphones != 1 else ''}")
    if s.speakers >= 0:
        parts.append(f"{s.speakers} speaker output{'s' if s.speakers != 1 else ''}")
    langs = _languages(r)
    if langs:
        parts.append(f"Windows languages {', '.join(langs)}")
    out.append("Windows: " + ", ".join(parts) + ".")
    for d in r.speeds():
        out.append(f"Drive {d.summary()}")
    out.append("")
    out.append("Features:")
    for feat in f.FEATURES:
        v = r.verdict(feat.id)
        if v and feat.offered:
            out.append(f"  {TEXT_MARKS[v.level]} {feat.title}: {LEVEL_WORDS[v.level]}. {v.text}")
    for key, title in (("models.primary", "Chat model"), ("models.primary_num_ctx", "Context"),
                       ("dictation.model", "Speech model"), ("read_aloud.device", "Read aloud runs on"),
                       ("media.image_size", "Image size")):
        vs = [v for v in r.verdicts if v.key == key]
        if not vs:
            continue
        out.append(f"{title}:")
        for v in vs:
            name = SPEECH[v.value].label if key == "dictation.model" and v.value in SPEECH else v.value
            out.append(f"  {TEXT_MARKS[v.level]} {name}: {LEVEL_WORDS[v.level]}." + (f" {v.text}" if v.text else ""))
    if r.notes:
        out.append("Notes:")
        out += [f"  {'!' if n.level != 'ok' else '-'} {n.text}" for n in r.notes]
    return out
