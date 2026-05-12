#
# UbiQTreeRanker.py
# Wraps UBiQTree's ExplainerClassification so the ML pipeline can produce
# a feature ranking with uncertainty bounds in addition to plain SHAP.
#
# UBiQTree's explain() works on ONE instance at a time and gives back a
# SHAP distribution (Dirichlet-resampled trees). For a GLOBAL feature
# ranking we run explain() on a subsample of the validation set and
# stack the per-row distributions into one big matrix. That stacked
# matrix is what aggregate stats (mean / std / CI / entropy /
# sign_stability) are computed from, which captures both within-row
# tree-sampling uncertainty AND across-row instance variation.
#
# Defaults are tuned for thesis-grade runtime (~1-2 minutes on a laptop).
# Bump n_subsample / n_samples for sharper bounds if you have time.
#

import os

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

from Pc_backend.Ml_pipeline.ExplainerClassification import ExplainerClassification
from Pc_backend.Ml_pipeline.UbiqResult import UbiqResult


class UbiQTreeRanker:

    def __init__(self, rf_model, X_train, y_train, feature_names,
                 beta=5.0, random_state=42):
        # rf_model must already be fitted and must have an
        # `estimators_` attribute. RandomForestClassifier is the
        # natural choice, but anything with the same shape works
        # (e.g. ExtraTreesClassifier).
        self.rf_model = rf_model
        self.feature_names = list(feature_names)
        self.X_train = X_train
        self.y_train = y_train

        # Convert to ndarray if pandas - UBiQTree indexes positionally
        X_arr = X_train.values if hasattr(X_train, "values") else np.asarray(X_train)
        y_arr = y_train.values if hasattr(y_train, "values") else np.asarray(y_train)

        self.explainer = ExplainerClassification(
            model=rf_model,
            X_train=X_arr,
            y_train=y_arr,
            beta=beta,
            random_state=random_state,
        )

    # -----------------------------------------------------------------
    # Ranking
    # -----------------------------------------------------------------

    def rank(self, X_val, n_samples=100, alpha=1.0,
             n_subsample=20, class_idx=1, random_state=42):
        # Pull a deterministic subsample of X_val to keep runtime sane.
        # If X_val is small enough, use it all.
        X_arr = X_val.values if hasattr(X_val, "values") else np.asarray(X_val)
        n_rows = len(X_arr)

        if n_subsample is not None and n_rows > n_subsample:
            rng = np.random.RandomState(random_state)
            idx = rng.choice(n_rows, n_subsample, replace=False)
            X_sub = X_arr[idx]
        else:
            X_sub = X_arr

        print(f"\nUbiQTree ranking: {len(X_sub)} rows x {n_samples} samples "
              f"= {len(X_sub) * n_samples} SHAP evaluations")
        print(f"  alpha={alpha}, class_idx={class_idx}")

        # Run explain() on each subsampled row and stack the per-row
        # `samples` matrices. UBiQTree's explain() expects shape (1, n_features).
        all_samples = []
        for i in range(len(X_sub)):
            row = X_sub[i:i + 1]
            result = self.explainer.explain(
                row,
                n_samples=n_samples,
                alpha=alpha,
                class_idx=class_idx,
            )
            # samples shape per call: (n_samples, n_features)
            all_samples.append(result["samples"])

        # Stack -> (n_rows * n_samples, n_features). This is the
        # combined "hypothesis space" we aggregate stats from.
        stacked = np.vstack(all_samples)

        mean = stacked.mean(axis=0)
        std = stacked.std(axis=0)
        ci_95 = np.percentile(stacked, [2.5, 97.5], axis=0).T   # shape (n_features, 2)
        entropy = self._compute_entropy(stacked)
        sign_stability = self._compute_sign_stability(stacked, mean)

        result = UbiqResult(
            feature_names=self.feature_names,
            mean=mean,
            std=std,
            ci_95=ci_95,
            entropy=entropy,
            sign_stability=sign_stability,
            samples=stacked,
        )

        # Print a ranking table similar to the SHAP one
        print("\nUbiQTree ranking by |mean SHAP|:")
        print(f"  {'rank':<5s}{'feature':<22s}{'|mean|':>10s}{'std':>10s}{'sign_stab':>12s}")
        for i, (feat, val) in enumerate(result.ranked_by_mean_abs(), start=1):
            f_idx = self.feature_names.index(feat)
            print(f"  {i:<5d}{feat:<22s}{val:>10.6f}"
                  f"{std[f_idx]:>10.6f}{sign_stability[f_idx]:>12.4f}")

        return result

    # -----------------------------------------------------------------
    # Stats helpers (matches UBiQTree's internal versions)
    # -----------------------------------------------------------------

    @staticmethod
    def _compute_entropy(samples):
        # Per-feature explanation entropy. Histogram each column, treat
        # the bin probabilities as a discrete distribution, compute entropy.
        from scipy.stats import entropy as _entropy
        out = np.zeros(samples.shape[1])
        for i in range(samples.shape[1]):
            hist, edges = np.histogram(samples[:, i], bins=10, density=True)
            probs = hist * np.diff(edges)
            out[i] = _entropy(probs)
        return out

    @staticmethod
    def _compute_sign_stability(samples, mean):
        # Fraction of samples that share the sign of the mean for each feature.
        # Close to 1 = feature consistently pushes the prediction the same way.
        mean_sign = np.sign(mean)
        return np.mean(np.sign(samples) == mean_sign[np.newaxis, :], axis=0)

    # -----------------------------------------------------------------
    # Plots
    # Re-implemented here (rather than calling UBiQTree's plot methods)
    # because UBiQTree's versions save to hardcoded filenames and call
    # plt.show() - both are awkward for a thesis pipeline that wants to
    # write to specific paths.
    # -----------------------------------------------------------------

    def plot_uncertainty_bars(self, result, save_path):
        # Horizontal bar chart of mean SHAP per feature, with std error bars.
        # Ordered ascending so the biggest |mean| ends up at top after invert.
        order = np.argsort(result.mean)
        names_ord = [result.feature_names[i] for i in order]

        fig, ax = plt.subplots(figsize=(10, max(4, 0.4 * len(names_ord))))
        ax.barh(names_ord, result.mean[order],
                xerr=result.std[order],
                color='steelblue', alpha=0.8,
                edgecolor='black', linewidth=0.5,
                error_kw={'ecolor': 'black', 'alpha': 0.6})
        ax.axvline(0, color='black', linestyle='--', linewidth=0.8)
        ax.set_xlabel('Mean SHAP value (error bars = ±1 std)')
        ax.set_title('UbiQTree feature importance with epistemic uncertainty')
        ax.grid(axis='x', linestyle='--', alpha=0.3)

        self._ensure_dir(save_path)
        plt.tight_layout()
        plt.savefig(save_path, dpi=120, bbox_inches='tight')
        plt.close()
        print(f"Saved UbiQTree uncertainty bars to {save_path}")

    def plot_uncertainty_comparison(self, result, save_path):
        # Three stacked horizontal bars: std, entropy, sign_stability.
        # Same idea as UBiQTree's plot_uncertainty_comparison but writes
        # to a file path the caller chooses.
        order = np.argsort(result.mean)
        names_ord = [result.feature_names[i] for i in order]

        fig, axes = plt.subplots(3, 1, figsize=(12, 14))
        colors = plt.cm.plasma(np.linspace(0, 1, len(names_ord)))

        # Std
        axes[0].barh(names_ord, result.std[order],
                     color=colors, alpha=0.85, edgecolor='gray', linewidth=0.5)
        axes[0].axvline(np.mean(result.std), color='red', linestyle='--', alpha=0.7)
        axes[0].set_title('Standard deviation of SHAP values', pad=8)
        axes[0].set_xlabel('Magnitude of uncertainty')
        axes[0].grid(axis='x', alpha=0.2)

        # Entropy
        axes[1].barh(names_ord, result.entropy[order],
                     color=colors, alpha=0.85, edgecolor='gray', linewidth=0.5)
        axes[1].axvline(np.mean(result.entropy), color='red', linestyle='--', alpha=0.7)
        axes[1].set_title('Explanation entropy', pad=8)
        axes[1].set_xlabel('Entropy value')
        axes[1].grid(axis='x', alpha=0.2)

        # Sign stability
        axes[2].barh(names_ord, result.sign_stability[order],
                     color=colors, alpha=0.85, edgecolor='gray', linewidth=0.5)
        axes[2].set_xlim(0, 1)
        axes[2].set_title('Sign stability (direction consistency)', pad=8)
        axes[2].set_xlabel('Probability of consistent direction')
        axes[2].grid(axis='x', alpha=0.2)
        # Confidence-threshold guide lines
        axes[2].axvline(0.9, color='green', linestyle='--', linewidth=1, alpha=0.8)
        axes[2].axvline(0.7, color='orange', linestyle='--', linewidth=1, alpha=0.8)
        axes[2].axvline(0.4, color='red', linestyle='--', linewidth=1, alpha=0.8)
        legend_lines = [
            mlines.Line2D([], [], color='green', linestyle='--', label='High (>= 0.9)'),
            mlines.Line2D([], [], color='orange', linestyle='--', label='Medium (>= 0.7)'),
            mlines.Line2D([], [], color='red', linestyle='--', label='Low (< 0.7)'),
        ]
        axes[2].legend(handles=legend_lines, loc='upper right', frameon=True, framealpha=0.9)

        self._ensure_dir(save_path)
        plt.tight_layout()
        plt.savefig(save_path, dpi=120, bbox_inches='tight')
        plt.close()
        print(f"Saved UbiQTree uncertainty comparison to {save_path}")

    def plot_uncertainty_distribution(self, result, feature_idx, save_path):
        # Per-feature density plot of the SHAP distribution. Useful for
        # eyeballing whether a feature's SHAP is unimodal, bimodal, etc.
        from scipy.stats import gaussian_kde

        if result.samples is None:
            raise ValueError(
                "plot_uncertainty_distribution: UbiqResult.samples is None - "
                "cannot draw a density without the raw samples."
            )

        col = result.samples[:, feature_idx]
        feat_name = result.feature_names[feature_idx]
        mean_val = result.mean[feature_idx]
        std_val = result.std[feature_idx]
        ci_low, ci_high = result.ci_95[feature_idx]
        sign_stab = result.sign_stability[feature_idx]

        kde = gaussian_kde(col)
        x = np.linspace(col.min() * 1.2, col.max() * 1.2, 1000)

        plt.figure(figsize=(11, 6))
        plt.plot(x, kde(x), lw=2.5, color='navy', label='Probability density')
        plt.axvline(mean_val, color='crimson', linestyle='--', lw=2, label='Mean SHAP')
        plt.axvspan(ci_low, ci_high, alpha=0.25, color='skyblue', label='95% CI')
        plt.axvline(0, color='black', linestyle=':', alpha=0.7, lw=1)

        # Annotations
        plt.text(0.01, 0.92,
                 f"Std = {std_val:.3f}\nSign stability = {sign_stab:.1%}",
                 transform=plt.gca().transAxes,
                 fontsize=11,
                 bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray'))

        plt.xlabel(f'SHAP value for {feat_name}')
        plt.ylabel('Probability density')
        plt.title(f'UbiQTree SHAP distribution - {feat_name}')
        plt.legend(loc='upper right')
        plt.grid(alpha=0.2)

        self._ensure_dir(save_path)
        plt.tight_layout()
        plt.savefig(save_path, dpi=120, bbox_inches='tight')
        plt.close()
        print(f"Saved UbiQTree distribution plot to {save_path}")

    @staticmethod
    def _ensure_dir(path):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
