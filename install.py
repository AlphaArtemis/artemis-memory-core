"""Offline stdlib installer: build a source-only zip application from an allowlist.

No package registry, network, shell, account, global config or external files.
The destination must not exist. The application never embeds user state.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import zipfile

FILES = (
    "artemis_memory_core/__init__.py",
    "artemis_memory_core/__main__.py",
    "artemis_memory_core/core.py",
    "artemis_memory_core/safeio.py",
    "demo/__init__.py",
    "demo/prepare.py",
    "demo/synthetic.json",
    "LICENSE",
    "docs/THIRD_PARTY.md",
    "VERSION",
)


def package_bytes(root, name):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    fd = os.open(root, flags | os.O_DIRECTORY)
    try:
        for part in Path(name).parts[:-1]:
            child = os.open(part, flags | os.O_DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = child
        child = os.open(Path(name).name, flags, dir_fd=fd)
        os.close(fd)
        fd = child
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 1_000_000:
            raise ValueError("Package file is not a bounded independent regular file")
        raw = bytearray()
        while len(raw) <= 1_000_000:
            chunk = os.read(fd, min(65536, 1_000_001 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        after = os.fstat(fd)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if len(raw) > 1_000_000 or identity(before) != identity(after):
            raise ValueError("Package changed while reading")
        return bytes(raw)
    finally:
        os.close(fd)


def install(destination):
    if sys.version_info < (3, 11):
        raise ValueError("Python 3.11 or newer is required")
    root = Path(__file__).resolve().parent
    destination = Path(destination)
    if not destination.is_absolute() or ".." in destination.parts:
        raise ValueError("Use an absolute output filename without '..'")
    if destination.suffix != ".pyz":
        raise ValueError("Output must end with .pyz")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    folder = os.open(destination.anchor, flags)
    try:
        for part in destination.parts[1:-1]:
            child = os.open(part, flags, dir_fd=folder)
            os.close(folder)
            folder = child
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in FILES:
                raw = package_bytes(root, name)
                item = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                item.external_attr = 0o100644 << 16
                item.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(item, raw)
            entry = zipfile.ZipInfo("__main__.py", date_time=(2026, 1, 1, 0, 0, 0))
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, "from artemis_memory_core.__main__ import main\nraise SystemExit(main())\n")
        raw = buffer.getvalue()
        fd = os.open(destination.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=folder)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        return {"status": "INSTALLED", "file": str(destination),
                "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "network_requests": 0, "embedded_data": "synthetic_demo_only"}
    finally:
        os.close(folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New absolute .pyz file in an existing directory")
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.output), indent=2))
        return 0
    except (OSError, ValueError):
        print("Installation refused: check Python, package files and a new absolute output path.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
