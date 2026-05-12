#
# ShapResult.py
# Pure data holder for what FeatureRanker.rank() returns. Wraps the
# raw SHAP arrays plus the names so callers don't have to keep them in
# sync as separate variables.
#

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class ShapResult:
    feature_names: list = field(default_factory=list)
    # Per-feature mean SHAP value (signed) - shape (n_features,)
    mean_shap: np.ndarray = None
    # Per-feature mean |SHAP| - shape (n_features,). This is what the
    # accumulation curve uses for ranking.
    mean_abs_shap: np.ndarray = None
    # Rank position for each feature (1 = most important). Same order
    # as feature_names so ranks[i] is the rank of feature_names[i].
    ranks: list = field(default_factory=list)

    def ranked_by_mean_abs(self):
        # Returns [(feature_name, mean_abs_shap), ...] sorted descending.
        # Same shape FeatureRanker prints today.
        pairs = list(zip(self.feature_names, self.mean_abs_shap))
        return sorted(pairs, key=lambda kv: kv[1], reverse=True)

    def to_dataframe(self):
        return pd.DataFrame({
            "feature": self.feature_names,
            "mean_shap": self.mean_shap,
            "mean_abs_shap": self.mean_abs_shap,
            "rank": self.ranks,
        }).sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
