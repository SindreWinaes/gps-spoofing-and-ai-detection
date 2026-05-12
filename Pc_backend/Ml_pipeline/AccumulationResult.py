#
# AccumulationResult.py
# Data holder for the "feature accumulation curve" - train LGBM with
# top-k features for k=2..N and record validation accuracy at each k.
# Knows how to plot itself and how to dump to a DataFrame for the
# thesis tables.
#

import os
from dataclasses import dataclass, field

import matplotlib.pyplot as plt
import pandas as pd


@dataclass
class AccumulationResult:
    k_values: list = field(default_factory=list)
    accuracies: list = field(default_factory=list)
    # Same ranked feature list the curve was built from. Useful when
    # picking optimal_k - the chosen features are ranked_features[:optimal_k].
    ranked_features: list = field(default_factory=list)
    max_accuracy: float = 0.0
    optimal_k: int = 0
    delta_tolerance: float = 0.01

    def plot(self, save_path):
        # Same plot the existing train_shap.py produces. Markers + line,
        # axis labels and grid; nothing fancy.
        # Make sure the parent directory exists so this works when the
        # track folder is brand new (the combined track has no other
        # plot saved into it first).
        save_dir = os.path.dirname(save_path)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)

        plt.figure(figsize=(8, 5))
        plt.plot(self.k_values, self.accuracies,
                 marker='o', color='steelblue', linewidth=2)
        plt.xlabel('Number of features (top-k by ranking)')
        plt.ylabel('Validation accuracy')
        plt.title('Feature Accumulation Curve')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(save_path, dpi=120, bbox_inches='tight')
        plt.close()

    def to_dataframe(self):
        return pd.DataFrame({
            "k": self.k_values,
            "accuracy": self.accuracies,
        })
