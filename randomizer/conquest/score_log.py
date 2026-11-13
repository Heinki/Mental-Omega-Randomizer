"""Read fresh native score bytes without accepting previous games."""

from pathlib import Path

def debug_logs(directory):
    directory = Path(directory)
    if directory.is_file() or directory.suffix.lower() == '.log':
        directory = directory.parent
    if not directory.is_dir():
        return []
    return [path for path in directory.iterdir() if path.is_file()
            and path.name.upper().startswith('DEBUG') and path.suffix.lower() == '.log']


def anchor(handle, offset):
    handle.seek(max(0, offset - 128))
    return handle.read(min(offset, 128))


class ScoreLog:
    """Ignore old games, SYNC dumps and overwritten/partial log fragments."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.baseline = {}
        self.path = None
        self.offset = 0
        self.anchor = b''
        self.tail = b''
        for path in debug_logs(self.directory):
            stat = path.stat()
            with path.open('rb') as handle:
                self.baseline[path] = (stat.st_size, stat.st_mtime_ns, anchor(handle, stat.st_size))

    def read_text(self, *, final=False):
        if self.path is None:
            changed = []
            paths = ([self.directory] if self.directory.is_file() else []) if self.directory.suffix.lower() == '.log' else debug_logs(self.directory)
            for path in paths:
                stat = path.stat()
                previous = self.baseline.get(path)
                if previous is None or (stat.st_size, stat.st_mtime_ns) != previous[:2]:
                    changed.append((stat.st_mtime_ns, path))
            if not changed:
                return ''
            self.path = max(changed, key=lambda item: item[0])[1]
            previous = self.baseline.get(self.path)
            if previous:
                self.offset, _, self.anchor = previous
        with self.path.open('rb') as handle:
            size = self.path.stat().st_size
            if size < self.offset or anchor(handle, self.offset) != self.anchor:
                self.offset = 0
                self.tail = b''
            handle.seek(self.offset)
            data = self.tail + handle.read()
            self.offset = handle.tell()
            self.anchor = anchor(handle, self.offset)
        if final:
            self.tail = b''
            return data.decode('utf-8', errors='replace') + ('\n' if data and not data.endswith(b'\n') else '')
        complete, separator, self.tail = data.rpartition(b'\n')
        if not separator:
            self.tail = data
            return ''
        return (complete + separator).decode('utf-8', errors='replace')
