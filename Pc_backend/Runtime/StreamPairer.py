#
# StreamPairer.py
# Pairs the most recent accelerometer packet with each incoming GPS
# packet. Accel packets arrive on a faster cadence than GPS (~1 Hz vs
# ~0.3 Hz), so on every GPS arrival there should usually be a recent
# accel to attach. If the latest accel is older than stale_threshold_s
# seconds (default 15), the GPS row goes out with no accel - prevents
# us from training/classifying on a half-hour-old accel reading.
#
# Same pairing rule the existing reciever.py uses.
#

import time

from Pc_backend.Runtime.PairedRow import PairedRow


DEFAULT_STALE_THRESHOLD_S = 15.0


class StreamPairer:

    def __init__(self, stale_threshold_s=DEFAULT_STALE_THRESHOLD_S):
        self.stale_threshold = stale_threshold_s
        self.latest_accel = None
        self.latest_accel_time = 0.0

    def on_accel(self, packet):
        # Just refresh the cached "latest" - GPS will pull this on its
        # next arrival. We store wall-clock arrival time, not the accel
        # packet's own UTC, because the staleness check is about "how
        # long ago did the PC receive this", not about device clocks.
        self.latest_accel = packet
        self.latest_accel_time = time.time()

    def on_gps(self, packet):
        # Build a PairedRow. If no accel has arrived yet, or the latest
        # is too old, the row goes out with accel=None and features
        # populated from the GPS side only.
        row = PairedRow(gps=packet, timestamp=self._iso_now())

        if self.latest_accel is not None and not self._is_accel_stale():
            row.accel = self.latest_accel
        else:
            row.accel = None

        return row

    def _is_accel_stale(self):
        if self.latest_accel is None:
            return True
        age = time.time() - self.latest_accel_time
        return age >= self.stale_threshold

    @staticmethod
    def _iso_now():
        # ISO 8601 wall-clock timestamp for the log's first column.
        from datetime import datetime
        return datetime.now().isoformat()
