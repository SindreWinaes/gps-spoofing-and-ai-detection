#
# Metrics.py
# Holds the evaluation metrics produced by the Evaluator. Same shape as
# the metrics.json / holdout_metrics.json files the existing scripts
# write, just bundled into a typed object so downstream code doesn't
# have to remember dict keys.
#

import json
from dataclasses import dataclass, field, asdict


@dataclass
class Metrics:
    track_name: str = ""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    model_size_bytes: int = 0
    inference_time_ms: float = 0.0
    # Optional extras the existing scripts also write. Kept here so a
    # round-trip through to_dict()/to_json() preserves everything.
    confusion_matrix: list = field(default_factory=list)
    inference_per_sample_ms: float = 0.0
    n_rows: int = 0
    n_features: int = 0
    feature_list: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    def to_json(self, path):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
