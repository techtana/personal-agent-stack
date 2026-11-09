"""Entry point of the voice typing app, run in its own environment (stack.py dictate starts it with the right Python):

    python -m stacklib.dictation run                  the app: button, hotkey, microphone
    python -m stacklib.dictation transcribe FILE.wav  the same pipeline on a recording: phrases, transcript, cleanup
    python -m stacklib.dictation check                imports, GPU, model, microphones, hotkey
    python -m stacklib.dictation speak "TEXT"         read aloud's voices: speak text (--out F.wav, --voice, --speed),
                                                      --list the voices, --download Kokoro's files (the installer),
                                                      --download-zh the Mandarin voices' files
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave

from .. import env_value
from .. import profile as prof
from .. import usage_log
from . import Config, control, hotkey, model_cached


def _read_wav(path: str):
    import numpy as np

    with wave.open(path, "rb") as w:
        rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        data = w.readframes(w.getnframes())
    if width != 2:
        raise SystemExit(f"{path}: need 16-bit PCM, got {8 * width}-bit")
    audio = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != 16000:  # linear resampling is plenty for speech recognition
        n = int(len(audio) * 16000 / rate)
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)
    return audio.astype(np.int16)


def cmd_transcribe(a, profile: dict) -> int:
    """Feed a recording through VAD, segmenter, Whisper and the cleanup exactly as a live session would."""
    import numpy as np

    from . import cleanup
    from .app import POST_PAD, PRE_PAD
    from .engine import Engine
    from .segment import FRAME, Segmenter
    from .textops import joiner, strip_fillers
    from .vad import make_vad

    cfg = Config.from_profile(profile)
    cfg.mode = a.mode or cfg.mode
    cfg.style = a.style or cfg.style
    if a.language:
        cfg.language = a.language
    if a.device:
        cfg.device = a.device
    if a.vocabulary is not None:
        cfg.vocabulary = a.vocabulary
    pcm = _read_wav(a.file)
    engine = Engine(cfg, lambda m: print(m, file=sys.stderr, flush=True), client="Stack scripts")
    t0 = time.monotonic()
    if not engine.wait_ready():
        print(engine.note, file=sys.stderr)
        return 1
    print(f"model {engine.model_name} on {engine.device}, loaded in {time.monotonic() - t0:.1f} s"
          f"{f' ({engine.note})' if engine.note else ''}", file=sys.stderr)
    vad = make_vad(lambda m: print(m, file=sys.stderr))
    seg = Segmenter(phrase_pause_s=cfg.phrase_pause_s, silence_stop_s=cfg.silence_stop_s,
                    start_timeout_s=cfg.start_timeout_s, max_s=cfg.max_minutes * 60, auto_stop=not a.no_auto_stop)
    phrases: list[str] = []
    language = ""
    whisper_s = 0.0
    typed = ""

    def phrase(start: int, end: int) -> None:
        nonlocal language, whisper_s, typed
        lo, hi = max(0, start * FRAME - PRE_PAD), min(len(pcm), end * FRAME + POST_PAD)
        audio = pcm[lo:hi].astype(np.float32) / 32768.0
        t = time.monotonic()
        text, lang = engine.transcribe(audio, prompt=" ".join(phrases)[-200:], language=language)
        whisper_s += time.monotonic() - t
        if cfg.language in ("", "auto") and lang and not language:
            language = lang
        print(f"  phrase {start * FRAME / 16000:6.2f}-{end * FRAME / 16000:6.2f} s  ({time.monotonic() - t:.2f} s)  {text}")
        if text:
            phrases.append(text)
            out = text if cfg.style == "verbatim" else strip_fillers(text)
            typed += joiner(typed, out) + out

    stop = ""
    for i in range(0, len(pcm) - FRAME + 1, FRAME):
        frame = pcm[i:i + FRAME].astype(np.float32) / 32768.0
        for ev in seg.push(vad(frame)):
            if ev.kind == "phrase":
                phrase(ev.start, ev.end)
            elif ev.kind == "stop":
                stop = ev.reason
        if seg.stopped:
            break
    for ev in seg.finish("manual"):
        if ev.kind == "phrase":
            phrase(ev.start, ev.end)
        elif ev.kind == "stop" and not stop:
            stop = ev.reason
    raw = ""
    for p in phrases:
        raw += joiner(raw, p) + p
    print(f"\nstopped: {stop} after {seg.elapsed_s:.1f} s; VAD {vad.name}; language {language or cfg.language}; "
          f"Whisper {whisper_s:.2f} s in total")
    print(f"\nTRANSCRIPT ({len(raw)} chars):\n{raw}")
    if cfg.mode == "live":
        print(f"\nLIVE MODE WOULD TYPE:\n{typed}")
        return 0
    if cfg.style != "verbatim" and raw:
        gateway = f"http://127.0.0.1:{profile['ports']['litellm']}"
        res = cleanup.polish(raw, cfg.style, base_url=gateway, api_key=env_value("LITELLM_MASTER_KEY"),
                             model=cfg.cleanup_model, prompt=cfg.cleanup_prompt)
        prompt = "custom" if cfg.cleanup_prompt else "built-in"
        status = f"cleaned by {cfg.cleanup_model}, {prompt} prompt" if res.polished else f"NOT cleaned ({res.note})"
        print(f"\n{cfg.style.upper()} ({status}, {res.seconds:.2f} s):\n{res.text}")
    return 0


def cmd_speak(a, profile: dict) -> int:
    """Speak text the way read aloud does (the same cleanup, pieces and voice choice), to the speakers or into a WAV
    file, and say how long each piece took. One usage record, client Stack scripts."""
    from . import speak, tts
    from .player import Player
    from .reader import silence

    def note(msg: str) -> None:
        print(msg, file=sys.stderr, flush=True)

    if a.download:
        print(tts.download(profile, note))
        return 0
    if a.download_zh:
        print(tts.download_zh(profile, note))
        return 0
    cfg = speak.Config.from_profile(profile, warn=note)
    cfg.voice = a.voice or cfg.voice
    cfg.speed = a.speed or cfg.speed
    cfg.kokoro = a.kokoro or cfg.kokoro
    speech = tts.Speech(note)
    voices = speech.voices(cfg)
    if a.list:
        for v in voices:
            print(f"{v.id:34} {v.label}")
        return 0
    if a.text:
        text = a.text
    elif a.file:
        with open(a.file, encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()
    clean = speak.speech_text(text)
    voice, why = speak.pick_voice(cfg, clean, voices) if not a.voice else (speak.find_voice(a.voice, voices), "")
    if voice is None:
        note(f"no voice {a.voice or cfg.voice!r}; `speak --list` shows them")
        return 1
    note(f"voice {voice.label}" + (f" ({why})" if why else ""))
    t0 = time.monotonic()
    pcm, audio_s, run_s, load_s, tokens = bytearray(), 0.0, 0.0, 0.0, 0
    run = 0
    for i, piece in enumerate(speak.pieces(clean)):
        audio = speech.synth(piece.text, voice, cfg.speed, cfg)
        note(f"  piece {i + 1}: {audio.seconds:5.2f} s of speech in {audio.run_s:.2f} s"
             f"{f' (+{audio.load_s:.1f} s loading)' if audio.load_s else ''}: {piece.text[:70]}")
        pause, run = speak.pause_after(piece, cfg, run)
        pcm += audio.pcm + silence(pause)
        audio_s, run_s, load_s, tokens = audio_s + audio.seconds, run_s + audio.run_s, load_s + audio.load_s, tokens + audio.tokens
    speech.record(voice, cfg, audio_s=audio_s, run_s=run_s, load_s=load_s, tokens=tokens,
                  wall_s=time.monotonic() - t0, stopped=False, client="Stack scripts")
    note(f"{audio_s:.1f} s of speech in {run_s:.2f} s ({audio_s / run_s if run_s else 0:.1f}x real time), "
         f"load {load_s:.1f} s, {tokens} phoneme tokens")
    if a.out:
        with wave.open(a.out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(speak.SAMPLE_RATE)
            w.writeframes(bytes(pcm))
        print(a.out)
        return 0
    player = Player(speak.SAMPLE_RATE)
    player.start()
    player.play(bytes(pcm))
    player.finish()
    player.wait()
    return 0


def cmd_check(a, profile: dict) -> int:
    from . import audio, gpu

    cfg = Config.from_profile(profile)
    out: dict = {"python": sys.executable}
    try:
        import ctranslate2
        import faster_whisper
        import onnxruntime

        out.update(faster_whisper=faster_whisper.__version__, ctranslate2=ctranslate2.__version__,
                   onnxruntime=onnxruntime.__version__, cuda_devices=ctranslate2.get_cuda_device_count())
    except Exception as e:  # noqa: BLE001
        out["import_error"] = str(e)
    out["cublas_dir"] = str((gpu.cublas_dirs() or [""])[0])
    out["model"] = cfg.model
    out["model_cached"] = model_cached(profile, cfg.model)
    out["microphones"] = audio.devices()
    try:
        hotkey.parse(cfg.hotkey)
        out["hotkey"] = cfg.hotkey
    except hotkey.HotkeyError as e:
        out["hotkey_error"] = str(e)
    try:
        out["running"] = control.call(int(profile["ports"]["dictation"]), "health", timeout=1.5)
    except OSError:
        out["running"] = False
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if "import_error" not in out else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m stacklib.dictation")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    t = sub.add_parser("transcribe")
    t.add_argument("file")
    t.add_argument("--mode", choices=["polish", "live"])
    t.add_argument("--style", choices=["verbatim", "clean", "concise"])
    t.add_argument("--language")
    t.add_argument("--device", choices=["auto", "cuda", "cpu"])
    t.add_argument("--vocabulary", help="words Whisper should expect (overrides dictation.vocabulary)")
    t.add_argument("--no-auto-stop", action="store_true", help="read the whole file, ignoring the silence stop")
    sub.add_parser("check")
    s = sub.add_parser("speak")
    s.add_argument("text", nargs="?", help="what to say (or --file, or standard input)")
    s.add_argument("--file")
    s.add_argument("--voice", help="a voice id (speak --list); default read_aloud.voice")
    s.add_argument("--speed", type=float)
    s.add_argument("--kokoro", choices=["fp32", "int8", "off"])
    s.add_argument("--out", help="write a WAV file instead of playing")
    s.add_argument("--list", action="store_true", help="list the voices")
    s.add_argument("--download", action="store_true", help="fetch Kokoro's weights and voices into the HF cache")
    s.add_argument("--download-zh", action="store_true",
                   help="fetch the Mandarin voices (Kokoro v1.1-zh) into the HF cache")
    a = ap.parse_args(argv)
    profile = prof.resolve_profile()
    if usage_log.ENV not in os.environ:  # started by hand, not by stack.py or the tray: follow the profile's switch
        usage_log.configure(profile)
    if a.cmd == "run":
        from .app import main as run

        return run()
    if a.cmd == "transcribe":
        return cmd_transcribe(a, profile)
    if a.cmd == "speak":
        return cmd_speak(a, profile)
    return cmd_check(a, profile)


if __name__ == "__main__":
    raise SystemExit(main())
