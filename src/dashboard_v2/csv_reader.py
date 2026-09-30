"""Bounded binary tail, incremental UTF-8 and quoted CSV record framing."""
import codecs
import csv
import io
import os
from pathlib import Path


class CsvTail:
    def __init__(self, path):
        self.path = Path(path)
        self.reset()

    def reset(self):
        self.offset = 0
        self.identity = None
        self.last_mtime = None
        self.prefix = b""
        self.anchor = b""
        self.decoder = codecs.getincrementaldecoder("utf-8-sig")()
        self.record = []
        self.record_length = 0
        self.quoted = False
        self.header = None
        self.seq = 0
        self.generation = getattr(self, "generation", 0) + 1
        self.mtime = None
        self.eof = False
        self.header_error = None
        self.fatal_error = None

    def parse_record(self, text):
        if self.header is not None:
            self.seq += 1
        try:
            values = next(csv.reader(io.StringIO(text, newline=""), strict=True))
            if self.header is None:
                if len(set(values)) != len(values):
                    raise ValueError("Duplicate CSV column")
                required = {"Elapsed Time [s]", "Motor Model", "Motor ID", "PC Time",
                            "Hardware Error Status", "Moving", "Moving Status", "Present PWM",
                            "Present Velocity", "Present Position", "Velocity Trajectory",
                            "Position Trajectory", "Present Input Voltage", "Present Temperature"}
                if not required.issubset(values):
                    raise ValueError("CSV header does not match the experiment schema")
                self.header = values
                return None
            if len(values) != len(self.header):
                raise ValueError("CSV column count mismatch")
            return self.seq, dict(zip(self.header, values)), None
        except (ValueError, csv.Error, StopIteration) as exc:
            if self.header is None:
                self.header_error = f"Invalid header: {exc}"
                raise ValueError(self.header_error) from exc
            return self.seq, None, str(exc)

    def poll(self, terminal=False, chunk_size=262144):
        with self.path.open("rb") as handle:
            # Stat the opened file so an atomic replacement between stat/open cannot mix generations.
            stat = os.fstat(handle.fileno())
            identity = (stat.st_dev, stat.st_ino)
            prefix = handle.read(min(128, stat.st_size))
            handle.seek(max(0, self.offset - len(self.anchor)))
            anchor_changed = bool(self.anchor) and handle.read(len(self.anchor)) != self.anchor
            replaced = self.identity is not None and (
                identity != self.identity or stat.st_size < self.offset or anchor_changed
                or (self.prefix and not prefix.startswith(self.prefix))
                or (stat.st_size == self.offset and self.last_mtime != stat.st_mtime_ns))
            if replaced:
                self.reset()
            if self.header_error or self.fatal_error:
                raise ValueError(self.header_error or self.fatal_error)
            self.identity = identity
            self.prefix = prefix
            self.last_mtime = stat.st_mtime_ns
            self.mtime = stat.st_mtime
            handle.seek(self.offset)
            data = handle.read(min(chunk_size, max(0, stat.st_size - self.offset)))
            self.offset += len(data)
            handle.seek(max(0, self.offset - 128))
            self.anchor = handle.read(min(128, self.offset))
            self.eof = self.offset >= stat.st_size
        records = []
        try:
            decoded = self.decoder.decode(data)
        except UnicodeError as exc:
            self.fatal_error = "Invalid UTF-8 in CSV"
            raise ValueError(self.fatal_error) from exc
        for char in decoded:
            self.record.append(char)
            self.record_length += 1
            if self.record_length > 1048576:
                self.fatal_error = "CSV record exceeds 1 MiB"
                self.record.clear()
                raise ValueError(self.fatal_error)
            if char == '"':
                self.quoted = not self.quoted
            if char == "\n" and not self.quoted:
                result = self.parse_record("".join(self.record))
                self.record.clear()
                self.record_length = 0
                if result:
                    records.append(result)
        if terminal and self.eof and self.record and not self.quoted and not self.decoder.getstate()[0]:
            result = self.parse_record("".join(self.record))
            self.record.clear()
            self.record_length = 0
            if result:
                records.append(result)
        return records, replaced
