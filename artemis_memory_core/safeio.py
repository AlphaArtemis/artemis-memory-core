"""Bounded regular-file reads and immutable custody writes; POSIX only."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat


class MemoryError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def fail(code):
    raise MemoryError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail('duplicate_json_key')
            result[key] = value
        return result
    def invalid(value):
        fail('nonfinite_json')
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        if isinstance(error, MemoryError):
            raise
        fail('invalid_json')


def signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def secure_directory(path, create=False):
    """Walk absolute components without following symlinks."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        fail('unsafe_directory')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            try:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o700, dir_fd=fd)
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def open_readonly(path):
    path = Path(path)
    folder = secure_directory(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=folder)
    finally:
        os.close(folder)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        fail('invalid_regular_source')
    return fd


def read_bytes(path, maximum=32 * 1024 * 1024, expected=None):
    fd = None
    try:
        fd = open_readonly(path)
        before = os.fstat(fd)
        if before.st_size > maximum:
            fail('source_size_limit')
        raw = bytearray()
        while len(raw) <= maximum:
            chunk = os.read(fd, min(65536, maximum + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        if len(raw) > maximum:
            fail('source_size_limit')
        if signature(before) != signature(os.fstat(fd)):
            fail('source_changed_during_read')
        if expected is not None and sha(raw) != expected:
            fail('source_integrity_mismatch')
        return bytes(raw)
    except FileNotFoundError:
        fail('source_missing')
    except OSError:
        fail('source_inaccessible')
    finally:
        if fd is not None:
            os.close(fd)


def write_immutable(path, raw):
    """Atomic, no-overwrite publication of an independently written copy."""
    path = Path(path)
    folder = secure_directory(path.parent, create=True)
    temporary = '.' + path.name + '.pending-' + secrets.token_hex(8)
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=folder)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path.name, src_dir_fd=folder, dst_dir_fd=folder,
                    follow_symlinks=False)
        except FileExistsError:
            read_bytes(path, max(len(raw), 1), sha(raw))
        finally:
            os.unlink(temporary, dir_fd=folder)
        os.fsync(folder)
    finally:
        try:
            os.unlink(temporary, dir_fd=folder)
        except FileNotFoundError:
            pass
        os.close(folder)
