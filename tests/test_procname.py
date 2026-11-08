"""PAS-<Name> program names (scripts/stacklib/procname.py): copies, branding, fallback, and coverage of every process."""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from stacklib import IS_WINDOWS, procname, services  # noqa: E402
from stacklib import icon  # noqa: E402

REAL_BRANDING_ALLOWED = procname.branding_allowed


def _fake_venv(root: Path) -> Path:
    """<root>/base with a python.exe, pythonw.exe and two DLLs, and <root>/venv pointing at it. Returns the venv."""
    base = root / "base"
    base.mkdir()
    (base / "python.exe").write_bytes(b"MZ console")
    (base / "pythonw.exe").write_bytes(b"MZ windowless")
    (base / "python312.dll").write_bytes(b"dll")
    (base / "vcruntime140.dll").write_bytes(b"crt")
    venv = root / "venv"
    (venv / "Scripts").mkdir(parents=True)
    (venv / "Scripts" / "python.exe").write_bytes(b"launcher")
    (venv / "Scripts" / "pythonw.exe").write_bytes(b"launcherw")
    (venv / "pyvenv.cfg").write_text(f"home = {base}\nversion_info = 3.12.7\n", encoding="utf-8")
    return venv


class Names(unittest.TestCase):
    def test_every_process_has_a_pas_name(self):
        for svc in services.SERVICE_ORDER:
            self.assertIn(svc, procname.NAMES, f"add a PAS name for service {svc} in stacklib/procname.py NAMES")
        for key, name in procname.NAMES.items():
            self.assertRegex(name, r"^PAS-[A-Za-z]+$", key)
        self.assertEqual(len(set(procname.NAMES.values())), len(procname.NAMES), "names must be unique")

    def test_expected_images_include_pas_names(self):
        for svc, names in services.EXPECTED_IMAGES.items():
            self.assertIn(procname.NAMES[svc].lower(), names)


@unittest.skipUnless(IS_WINDOWS, "copies are made on Windows only")
class Copies(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.venv = _fake_venv(Path(self.tmp.name))
        patcher = mock.patch.object(procname, "branding_allowed", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_copy_of_the_base_interpreter_next_to_its_dlls(self):
        exe = procname.named(self.venv / "Scripts" / "pythonw.exe", "tray")
        self.assertEqual(exe, self.venv / "pas" / "PAS-Tray.exe")
        self.assertEqual(exe.read_bytes(), b"MZ windowless")  # the base pythonw.exe, not the venv launcher
        self.assertEqual((exe.parent / "python312.dll").read_bytes(), b"dll")
        self.assertTrue((exe.parent / "vcruntime140.dll").exists())
        console = procname.named(self.venv / "Scripts" / "python.exe", "litellm")
        self.assertEqual(console.read_bytes(), b"MZ console")

    def test_second_call_leaves_the_copy_alone_and_a_changed_base_refreshes_it(self):
        exe = procname.named(self.venv / "Scripts" / "python.exe", "litellm")
        with mock.patch.object(procname.shutil, "copy2", side_effect=AssertionError("copied again")):
            procname.named(self.venv / "Scripts" / "python.exe", "litellm")
        base = Path(self.tmp.name) / "base" / "python.exe"
        base.write_bytes(b"MZ newer python")
        os.utime(base, ns=(1, 2_000_000_000_000_000_000))
        procname.named(self.venv / "Scripts" / "python.exe", "litellm")
        self.assertEqual(exe.read_bytes(), b"MZ newer python")

    def test_branded_when_allowed(self):
        with mock.patch.object(procname, "branding_allowed", return_value=True), \
             mock.patch.object(procname, "brand_exe") as brand:
            procname.named(self.venv / "Scripts" / "python.exe", "dictation")
        path, name, version = brand.call_args.args
        self.assertEqual((name, version), ("PAS-VoiceTyping", "3.12.7"))

    def test_plain_interpreter_when_no_copy_can_be_made(self):
        lone = Path(self.tmp.name) / "lone" / "Scripts" / "python.exe"
        lone.parent.mkdir(parents=True)
        lone.write_bytes(b"x")
        self.assertEqual(procname.named(lone, "tray"), lone)  # no pyvenv.cfg: not a venv
        with mock.patch.dict(os.environ, {"AGENT_STACK_PROCESS_NAMES": "0"}):
            self.assertEqual(procname.named(self.venv / "Scripts" / "python.exe", "tray"), self.venv / "Scripts" / "python.exe")
        with mock.patch.object(procname.shutil, "copy2", side_effect=PermissionError("in use")), \
             mock.patch.object(procname, "warn"):
            self.assertEqual(procname.named(self.venv / "Scripts" / "python.exe", "kokoro"), self.venv / "Scripts" / "python.exe")

    def test_named_cmd_keeps_the_arguments(self):
        cmd = [str(self.venv / "Scripts" / "python.exe"), "-P", "-c", "pass"]
        self.assertEqual(procname.named_cmd(cmd, "phoenix"), [str(self.venv / "pas" / "PAS-Phoenix.exe"), "-P", "-c", "pass"])

    def test_mark_blocked_stops_branding_in_that_folder(self):
        exe = procname.named(self.venv / "Scripts" / "python.exe", "litellm")
        procname.mark_blocked(exe)
        self.assertTrue((exe.parent / procname.BLOCKED).exists())
        self.assertFalse((exe.parent / "PAS-LiteLLM.stamp").exists())  # rebuilt on the next start
        with mock.patch.object(procname, "smart_app_control_state", return_value=0):
            self.assertFalse(REAL_BRANDING_ALLOWED(exe.parent))


class BrandingAllowed(unittest.TestCase):
    @unittest.skipUnless(IS_WINDOWS, "Windows only")
    def test_smart_app_control_on_or_evaluating_keeps_copies_signed(self):
        with tempfile.TemporaryDirectory() as d:
            for state, allowed in ((None, True), (0, True), (1, False), (2, False)):
                with mock.patch.object(procname, "smart_app_control_state", return_value=state):
                    self.assertEqual(procname.branding_allowed(Path(d)), allowed, state)
            (Path(d) / procname.BLOCKED).write_text("x")
            with mock.patch.object(procname, "smart_app_control_state", return_value=0):
                self.assertFalse(procname.branding_allowed(Path(d)))


class Spawn(unittest.TestCase):
    def test_refused_copy_falls_back_to_the_original_command(self):
        refused = OSError("blocked")
        refused.winerror = 4551
        c = {"cmd": ["C:/v/pas/PAS-LiteLLM.exe", "-c", "x"], "plain_cmd": ["C:/v/Scripts/python.exe", "-c", "x"]}
        with mock.patch.object(services.subprocess, "Popen", side_effect=[refused, "proc"]) as popen, \
             mock.patch.object(services.procname, "mark_blocked") as blocked, mock.patch.object(services, "warn"):
            self.assertEqual(services.spawn(c, cwd="."), "proc")
        self.assertEqual(popen.call_args_list[1].args[0], c["plain_cmd"])
        blocked.assert_called_once_with(c["cmd"][0])

    def test_other_errors_are_not_hidden(self):
        with mock.patch.object(services.subprocess, "Popen", side_effect=FileNotFoundError("gone")):
            with self.assertRaises(FileNotFoundError):
                services.spawn({"cmd": ["a"], "plain_cmd": ["b"]})


class Resources(unittest.TestCase):
    def test_version_block_lengths_add_up(self):
        data = procname.version_resource("PAS-Tray", "3.12.7")
        length, value_len, wtype = struct.unpack_from("<HHH", data, 0)
        self.assertEqual((length, value_len, wtype), (len(data), 52, 0))
        self.assertIn("PAS-Tray".encode("utf-16-le"), data)
        self.assertIn(struct.pack("<I", 0xFEEF04BD), data)

    def test_icon_group_points_at_every_image(self):
        images, group = procname.icon_resources(icon.ico_bytes())
        _, kind, count = struct.unpack_from("<HHH", group, 0)
        self.assertEqual((kind, count), (1, len(images)))
        self.assertEqual(count, len(icon.ICO_SIZES))
        ids = [struct.unpack_from("<H", group, 6 + 14 * i + 12)[0] for i in range(count)]
        self.assertEqual(ids, [rid for rid, _ in images])

    @unittest.skipUnless(IS_WINDOWS, "resource editing is Windows only")
    def test_brand_a_real_interpreter_copy(self):
        base = Path(sys.base_prefix) / "python.exe"
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / "copy.exe"
            shutil.copy2(base, exe)
            procname.brand_exe(exe, "PAS-Test", "3.12.7")
            found = procname._resources(exe, (procname.RT_ICON, procname.RT_GROUP_ICON, procname.RT_VERSION))
            self.assertIn((procname.RT_GROUP_ICON, 1, 0), found)
            self.assertIn((procname.RT_VERSION, 1, procname.LANG_EN_US), found)
            self.assertEqual(sum(1 for k, *_ in found if k == procname.RT_ICON), len(icon.ICO_SIZES))
            out = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-Item '{exe}').VersionInfo.FileDescription"],
                                 capture_output=True, text=True, timeout=60).stdout.strip()
            self.assertEqual(out, "PAS-Test")


if __name__ == "__main__":
    unittest.main()
