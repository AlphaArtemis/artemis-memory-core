"""Exercise the installed allowlisted zip application, outside the checkout."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

import install


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.package = self.root / "source"
        self.package.mkdir()
        source = Path(install.__file__).resolve().parent
        for name in ("install.py", *install.FILES):
            target = self.package / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target)
        self.output = self.root / "app.pyz"
        self.home = self.root / "empty-home"
        self.home.mkdir()
        self.env = {"PATH": os.defpath, "HOME": str(self.home),
                    "TMPDIR": str(self.root), "PYTHONDONTWRITEBYTECODE": "1"}

    def run_python(self, *args):
        return subprocess.run([sys.executable, "-B", *map(str, args)],
                              cwd=self.root, env=self.env, text=True,
                              capture_output=True, timeout=30)

    def build(self):
        result = self.run_python(self.package / "install.py", "--output", self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_exported_app_runs_from_unrelated_directory(self):
        result = self.build()
        self.assertEqual(result["network_requests"], 0)
        state = self.root / "demo-state"
        run = self.run_python(self.output, "demo", "--state", state)
        self.assertEqual(run.returncode, 0, run.stderr)
        demo = json.loads(run.stdout)
        fetched = self.run_python(self.output, "fetch", "--state", state, demo["ids"]["short"])
        self.assertEqual(fetched.returncode, 0, fetched.stderr)
        self.assertTrue(json.loads(fetched.stdout)["source_integrity_verified"])
        # Repeat from the installed application, preserving the same originals.
        before = {p.name: p.read_bytes() for p in (state / "originals").iterdir()}
        repeat = self.run_python(self.output, "demo", "--state", state)
        self.assertEqual(repeat.returncode, 0, repeat.stderr)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (state / "originals").iterdir()})

    def test_installer_ignores_unlisted_state_and_dotenv(self):
        (self.package / ".env").write_text("FICTIONAL_PRIVATE_MARKER")
        (self.package / "registry.sqlite").write_bytes(b"FICTIONAL_PRIVATE_MARKER")
        self.build()
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(set(archive.namelist()), set(install.FILES) | {"__main__.py"})
            self.assertFalse(any(b"FICTIONAL_PRIVATE_MARKER" in archive.read(n) for n in archive.namelist()))

    def test_existing_destination_is_preserved(self):
        self.output.write_bytes(b"keep-existing-file")
        result = self.run_python(self.package / "install.py", "--output", self.output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.output.read_bytes(), b"keep-existing-file")

    def test_source_symlink_and_fifo_are_rejected(self):
        target = self.package / "VERSION"
        target.unlink()
        target.symlink_to(self.package / "LICENSE")
        result = self.run_python(self.package / "install.py", "--output", self.output)
        self.assertEqual(result.returncode, 2)
        target.unlink()
        os.mkfifo(target)
        result = self.run_python(self.package / "install.py", "--output", self.output)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())

    def test_destination_parent_link_is_rejected(self):
        link = self.root / "link"
        link.symlink_to(self.home, target_is_directory=True)
        result = self.run_python(self.package / "install.py", "--output", link / "app.pyz")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.home / "app.pyz").exists())


if __name__ == "__main__":
    unittest.main()
