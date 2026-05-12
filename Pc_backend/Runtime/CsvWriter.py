#
# CsvWriter.py
# Thin wrapper around csv.writer plus the file it writes to. The EA
# model had this as a class to document the csv module dependency; we
# add a bit of bookkeeping (the file handle and path) so PcLogger can
# stay focused on row-building rather than file I/O plumbing.
#
# Files are opened in append mode and writerow() flushes each row -
# that means an unexpected crash never loses more than the row in
# flight. Mirrors the open/close-per-write style used elsewhere.
#

import csv
import os


class CsvWriter:

    def __init__(self, path):
        self.path = path
        self._file = None
        self._writer = None

    def open(self, mode="a", newline=""):
        # Make sure the directory exists, then open the file. Default
        # is append so adding a row never truncates an existing log.
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)
        self._file = open(self.path, mode, newline=newline)
        self._writer = csv.writer(self._file)
        return self

    def writerow(self, row):
        if self._writer is None:
            self.open()
        self._writer.writerow(row)
        # Flush so a crash mid-run still saves complete rows up to that
        # point. Slight throughput hit, big reliability win.
        self._file.flush()

    def close(self):
        if self._file is not None:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None
            self._writer = None
