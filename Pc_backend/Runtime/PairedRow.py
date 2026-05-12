#
# PairedRow.py
# One log row built by StreamPairer when a GPS packet arrives and there
# is a fresh accel packet to pair it with. Carries the raw packets, the
# computed feature dict (with the column names the model was trained
# on), the classification result (if a classifier is wired up), and the
# wall-clock timestamp at row-build time.
#

from dataclasses import dataclass, field


@dataclass
class PairedRow:
    gps: object = None                # GpsPacket
    accel: object = None              # AccelPacket (may be None on stale)
    features: dict = field(default_factory=dict)
    classification: object = None     # ClassificationResult (optional)
    timestamp: str = ""
