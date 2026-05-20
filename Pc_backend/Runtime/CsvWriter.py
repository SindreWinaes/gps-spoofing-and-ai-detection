import csv
import os


class CsvWriter:

    def __init__(self, path):
        self.path = path
        self._file = None
        self._writer = None

    def open(self, mode="a", newline=""):
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
        self._file.flush()

    def close(self):
        if self._file is not None:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None
            self._writer = None
