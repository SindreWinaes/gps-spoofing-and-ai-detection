#
# ThesisPlots.py
# Thesis-quality plots over the rankers' result objects. Same visual
# style Sofie built for the preliminary work so the two pipeline runs
# can be compared side-by-side in the thesis.
#
# Eight plots in total:
#   1. shap_importance.png           bar+beeswarm (FeatureRanker output)
#   2. shap_global_uncertainty.png   std / entropy / sign-stability of SHAP
#   3. shap_violin_top3.png          per-feature SHAP distribution, top 3
#   4. combined_ranking_plot.png     additive / geometric / reliability-weighted
#   5. rank_agreement_scatter.png    SHAP rank vs UbiQTree rank
#   6. ubiq_belief_plausibility.png  Dempster-Shafer bands
#   7. confusion_matrix.png          per-track heatmap (on held-out set)
#   8. summary_dashboard.png         per-track 3-panel summary
#

import os

import matplotlib.pyplot as plt
import numpy as np

# Avoid GUI backend issues when running headless
import matplotlib
matplotlib.use("Agg")


class ThesisPlots:

    # -----------------------------------------------------------------
    # Shared utilities
    # -----------------------------------------------------------------

    @staticmethod
    def _ensure_dir(path):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)

    @staticmethod
    def _entropy_per_feature(samples):
        # Same per-feature entropy used by UbiQTree internally
        from scipy.stats import entropy as _entropy
        out = np.zeros(samples.shape[1])
        for i in range(samples.shape[1]):
            col = samples[:, i]
            if col.std() < 1e-12:
                # All values identical - entropy is 0
                out[i] = 0.0
                continue
            hist, edges = np.histogram(col, bins=10, density=True)
            probs = hist * np.diff(edges)
            out[i] = _entropy(probs)
        return out

    @staticmethod
    def _sign_stability_per_feature(samples, mean):
        # Fraction of samples whose sign matches the mean's sign
        mean_sign = np.sign(mean)
        return np.mean(np.sign(samples) == mean_sign[np.newaxis, :], axis=0)

    @staticmethod
    def _ubiq_rank_array(ubiq_result):
        # Build feature_names-ordered ranks from a UbiqResult.
        # 1 = most important (by |mean SHAP|).
        abs_mean = np.abs(np.asarray(ubiq_result.mean))
        order = np.argsort(-abs_mean)
        ranks = np.zeros(len(abs_mean), dtype=int)
        for rank_pos, feat_idx in enumerate(order, start=1):
            ranks[feat_idx] = rank_pos
        return ranks

    # -----------------------------------------------------------------
    # 1. shap_importance.png - bar + manual beeswarm
    # -----------------------------------------------------------------

    def shap_importance(self, shap_values, X_val, feature_names, save_path):
        # `shap_values` is (n_rows, n_features) - the raw matrix the
        # FeatureRanker cached. We compute mean(|SHAP|) for the bar and
        # use the raw values for the beeswarm scatter on the right.
        mean_abs = np.abs(shap_values).mean(axis=0)
        std_abs = np.abs(shap_values).std(axis=0)
        order = np.argsort(mean_abs)  # ascending so largest ends up on top
        n_feat = len(feature_names)

        fig, axes = plt.subplots(1, 2, figsize=(15, max(5, 0.45 * n_feat)))

        # Left: bar with error bars
        axes[0].barh([feature_names[i] for i in order], mean_abs[order],
                     xerr=std_abs[order], color='steelblue', alpha=0.85,
                     edgecolor='black', linewidth=0.5,
                     error_kw={'ecolor': 'black', 'alpha': 0.6})
        axes[0].set_xlabel('Mean |SHAP value| ± std')
        axes[0].set_title(f'SHAP Feature Importance (top {n_feat})')
        axes[0].grid(axis='x', linestyle='--', alpha=0.3)

        # Right: manual beeswarm - dot per (row, feature), coloured by
        # the feature value. Same idea as shap.summary_plot but drawn
        # inline so we can put it next to the bar in one figure.
        # Use a fixed RNG so jitter is reproducible.
        rng = np.random.RandomState(42)
        X_arr = X_val.values if hasattr(X_val, "values") else np.asarray(X_val)
        for i_pos, feat_idx in enumerate(order):
            shap_col = shap_values[:, feat_idx]
            feat_col = X_arr[:, feat_idx]
            f_min, f_max = feat_col.min(), feat_col.max()
            if f_max - f_min < 1e-12:
                norm_feat = np.zeros_like(feat_col)
            else:
                norm_feat = (feat_col - f_min) / (f_max - f_min)
            colors = plt.cm.coolwarm(norm_feat)
            y_jitter = i_pos + rng.normal(0, 0.08, size=len(shap_col))
            axes[1].scatter(shap_col, y_jitter, c=colors, s=4, alpha=0.55,
                            edgecolors='none')

        axes[1].axvline(0, color='black', linewidth=0.8, alpha=0.5)
        axes[1].set_yticks(range(n_feat))
        axes[1].set_yticklabels([feature_names[i] for i in order])
        axes[1].set_xlabel('SHAP value (impact on model output)')
        axes[1].set_title('SHAP Beeswarm')
        axes[1].grid(axis='x', linestyle='--', alpha=0.3)

        # Discrete-ish colorbar showing low/high feature value
        cbar_ax = fig.add_axes([0.92, 0.25, 0.012, 0.5])
        sm = plt.cm.ScalarMappable(cmap='coolwarm',
                                   norm=plt.Normalize(vmin=0, vmax=1))
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cbar_ax)
        cbar.set_label('Feature value')
        cbar.set_ticks([0, 1])
        cbar.set_ticklabels(['Low', 'High'])

        self._ensure_dir(save_path)
        plt.savefig(save_path, dpi=120, bbox_inches='tight')
        plt.close()
        print(f"Saved SHAP importance plot to {save_path}")

    # -----------------------------------------------------------------
    # 2. shap_global_uncertainty.png - 3-panel
    # -----------------------------------------------------------------

    def shap_global_uncertainty(self, shap_values, feature_names, save_path):
        # SHAP equivalent of UbiQTreeRanker.plot_uncertainty_comparison.
        # Here the "uncertainty" comes from variation across the validation
        # rows (UbiQTree's came from Dirichlet tree resampling per row).
        mean_vals = shap_values.mean(axis=0)
        std = shap_values.std(axis=0)
        entropy = self._entropy_per_feature(shap_values)
        sign_stab = self._sign_stability_per_feature(shap_values, mean_vals)

        fig, axes = plt.subplots(1, 3, figsize=(18, max(5, 0.4 * len(feature_names))))

        # Panel 1: Std of SHAP
        order = np.argsort(std)
        axes[0].barh([feature_names[i] for i in order], std[order],
                     color='orange', alpha=0.85, edgecolor='gray', linewidth=0.5)
        axes[0].axvline(std.mean(), color='red', linestyle='--', alpha=0.7)
        axes[0].set_title('Std of SHAP Values')
        axes[0].set_xlabel('Magnitude of uncertainty')
        axes[0].grid(axis='x', alpha=0.2)

        # Panel 2: Entropy
        order = np.argsort(entropy)
        axes[1].barh([feature_names[i] for i in order], entropy[order],
                     color='green', alpha=0.85, edgecolor='gray', linewidth=0.5)
        axes[1].axvline(entropy.mean(), color='red', linestyle='--', alpha=0.7)
        axes[1].set_title('Explanation Entropy')
        axes[1].set_xlabel('Entropy value')
        axes[1].grid(axis='x', alpha=0.2)

        # Panel 3: Sign stability
        order = np.argsort(sign_stab)
        axes[2].barh([feature_names[i] for i in order], sign_stab[order],
                     color='purple', alpha=0.85, edgecolor='gray', linewidth=0.5)
        axes[2].set_xlim(0, 1)
        axes[2].set_title('Sign Stability (Directional Reliability)')
        axes[2].set_xlabel('Probability of consistent direction')
        axes[2].grid(axis='x', alpha=0.2)

        plt.suptitle('SHAP Global Uncertainty Comparison')
        self._ensure_dir(save_path)
        plt.tight_layout()
        plt.savefig(save_path, dpi=120, bbox_inches='tight')
        plt.close()
        print(f"Saved SHAP global uncertainty plot to {save_path}")

    # -----------------------------------------------------------------
    # 3. shap_violin_top3.png
    # -----------------------------------------------------------------

    def shap_violin_top3(self, shap_values, feature_names, save_path, top_n=3):
        mean_abs = np.abs(shap_values).mean(axis=0)
        top_idx = np.argsort(-mean_abs)[:top_n]

        fig, axes = plt.subplots(1, top_n, figsize=(5 * top_n, 6))
        if top_n == 1:
            axes = [axes]

        for ax, idx in zip(axes, top_idx):
            vals = shap_values[:, idx]
            parts = ax.violinplot([vals], showmeans=True, showmedians=False,
                                  showextrema=True)
            for pc in parts['bodies']:
                pc.set_facecolor('steelblue')
                pc.set_alpha(0.5)
                pc.set_edgecolor('navy')

            std_v = vals.std()
            sign_v = (np.sign(vals) == np.sign(vals.mean())).mean()
            ax.set_title(f'SHAP dist: {feature_names[idx]}\n'
                         f'σ={std_v:.3f}  sign_stab={sign_v:.2f}')
            ax.axhline(0, color='black', linestyle=':', alpha=0.5)
            ax.set_xticks([])
            ax.grid(axis='y', alpha=0.3)

        plt.suptitle('SHAP Distribution (Top 3 Features)')
        self._ensure_dir(save_path)
        plt.tight_layout()
        plt.savefig(save_path, dpi=120, bbox_inches='tight')
        plt.close()
        print(f"Saved SHAP violin top-3 plot to {save_path}")

    # -----------------------------------------------------------------
    # 4. combined_ranking_plot.png - 3-panel
    # -----------------------------------------------------------------

    def combined_ranking_3panel(self, shap_result, ubiq_result, save_path):
        # Three rank-fusion variants side by side. RankingCombiner uses
        # one of these methods to pick the combined-track feature order;
        # showing all three lets the thesis compare them.
        feature_names = list(shap_result.feature_names)
        shap_imp = np.asarray(shap_result.mean_abs_shap)
        ubiq_imp = np.abs(np.asarray(ubiq_result.mean))
        sign_stab = np.asarray(ubiq_result.sign_stability)

        eps = 1e-12
        additive = shap_imp + ubiq_imp
        geometric = np.sqrt((shap_imp + eps) * (ubiq_imp + eps))
        # Reliability-weighted: SHAP importance times UbiQTree directional
        # consistency - rewards features that BOTH matter AND are stable
        reliability = shap_imp * sign_stab

        fig, axes = plt.subplots(1, 3, figsize=(18, max(5, 0.4 * len(feature_names))))
        for ax, scores, title, color in [
            (axes[0], additive, 'Additive Score (SHAP + UBiQ)', 'tab:blue'),
            (axes[1], geometric, 'Geometric Mean Score', 'tab:green'),
            (axes[2], reliability, 'Reliability-Weighted Score', 'tab:purple'),
        ]:
            order = np.argsort(scores)
            ax.barh([feature_names[i] for i in order], scores[order],
                    color=color, alpha=0.85, edgecolor='gray', linewidth=0.5)
            ax.set_title(title)
            ax.grid(axis='x', linestyle='--', alpha=0.3)

        plt.suptitle('Combined SHAP + UBiQTree Feature Ranking')
        self._ensure_dir(save_path)
        plt.tight_layout()
        plt.savefig(save_path, dpi=120, bbox_inches='tight')
        plt.close()
        print(f"Saved combined ranking plot to {save_path}")

    # -----------------------------------------------------------------
    # 5. rank_agreement_scatter.png
    # -----------------------------------------------------------------

    def rank_agreement_scatter(self, shap_result, ubiq_result, save_path):
        feature_names = list(shap_result.feature_names)
        shap_ranks = np.asarray(shap_result.ranks)
        ubiq_ranks = self._ubiq_rank_array(ubiq_result)
        n = len(feature_names)

        avg_rank = (shap_ranks + ubiq_ranks) / 2.0

        plt.figure(figsize=(10, 9))
        sc = plt.scatter(shap_ranks, ubiq_ranks, c=avg_rank,
                         cmap='plasma_r', s=120,
                         edgecolors='black', linewidth=0.5)

        # Diagonal: perfect agreement
        plt.plot([1, n], [1, n], '--', color='gray', alpha=0.5,
                 label='Perfect agreement')

        # Label every point
        for i, name in enumerate(feature_names):
            plt.annotate(name, (shap_ranks[i], ubiq_ranks[i]),
                         fontsize=8, xytext=(6, 5),
                         textcoords='offset points')

        plt.xlabel('SHAP Rank')
        plt.ylabel('UBiQTree Rank')
        plt.title('SHAP vs UBiQTree Rank Agreement')
        plt.grid(alpha=0.3)
        plt.gca().invert_yaxis()
        plt.gca().invert_xaxis()   # rank 1 in top-left like Sofie's plot

        self._ensure_dir(save_path)
        plt.tight_layout()
        plt.savefig(save_path, dpi=120, bbox_inches='tight')
        plt.close()
        print(f"Saved rank agreement scatter to {save_path}")

    # -----------------------------------------------------------------
    # 6. ubiq_belief_plausibility.png
    # -----------------------------------------------------------------

    def belief_plausibility(self, ubiq_result, save_path):
        # Dempster-Shafer style interpretation of the UbiQTree samples.
        # For each feature we normalise |SHAP| samples to [0, 1] using
        # the max across the whole matrix, then take:
        #   belief        = 5th percentile  (lower bound of importance)
        #   plausibility  = 95th percentile (upper bound of importance)
        # The bar between them is the "uncertainty interval" - wide bars
        # mean we are very unsure where the feature ranks; narrow bars
        # are confident.
        samples = ubiq_result.samples
        feature_names = list(ubiq_result.feature_names)

        if samples is None:
            print("belief_plausibility: ubiq_result.samples is None - skipping")
            return

        abs_samples = np.abs(samples)
        max_val = abs_samples.max() if abs_samples.size else 1.0
        if max_val < 1e-12:
            max_val = 1.0
        normalized = abs_samples / max_val

        belief = np.percentile(normalized, 5, axis=0)
        plausibility = np.percentile(normalized, 95, axis=0)
        mean_imp = abs_samples.mean(axis=0)

        # Sort top-down by mean importance
        order = np.argsort(mean_imp)[::-1]

        fig, ax = plt.subplots(figsize=(12, max(5, 0.4 * len(feature_names))))
        for y_pos, idx in enumerate(order):
            ax.barh(y_pos, plausibility[idx] - belief[idx],
                    left=belief[idx],
                    color='lightblue', alpha=0.75,
                    edgecolor='steelblue', linewidth=0.5)

        # Belief and plausibility dots
        for y_pos, idx in enumerate(order):
            ax.scatter(belief[idx], y_pos, color='green', s=50, zorder=3)
            ax.scatter(plausibility[idx], y_pos, color='red', s=50, zorder=3)

        ax.set_yticks(range(len(feature_names)))
        ax.set_yticklabels([feature_names[i] for i in order])
        ax.invert_yaxis()
        ax.set_xlabel('Belief-Plausibility Interval (DST)')
        ax.set_title('UBiQTree: Dempster-Shafer Uncertainty per Feature')
        ax.set_xlim(0, 1)
        ax.grid(axis='x', alpha=0.3)

        # Legend
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', label='Belief (lower)',
                   markerfacecolor='green', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Plausibility (upper)',
                   markerfacecolor='red', markersize=10),
            Patch(facecolor='lightblue', label='Uncertainty interval'),
        ]
        ax.legend(handles=legend_elements, loc='upper left')

        self._ensure_dir(save_path)
        plt.tight_layout()
        plt.savefig(save_path, dpi=120, bbox_inches='tight')
        plt.close()
        print(f"Saved belief-plausibility plot to {save_path}")

    # -----------------------------------------------------------------
    # 7. confusion_matrix.png
    # -----------------------------------------------------------------

    def confusion_matrix(self, metrics, save_path, class_names=None):
        cm = np.asarray(metrics.confusion_matrix)
        if cm.size == 0:
            print("confusion_matrix: empty matrix - skipping")
            return

        if class_names is None:
            class_names = (['Legit', 'Spoof']
                           if cm.shape == (2, 2)
                           else [str(i) for i in range(cm.shape[0])])

        fig, ax = plt.subplots(figsize=(8, 7))
        im = ax.imshow(cm, cmap='Blues')

        cm_max = cm.max() if cm.max() > 0 else 1
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                text_color = 'white' if cm[i, j] > cm_max / 2 else 'black'
                ax.text(j, i, str(cm[i, j]), ha='center', va='center',
                        color=text_color, fontsize=14)

        ax.set_xticks(range(len(class_names)))
        ax.set_yticks(range(len(class_names)))
        ax.set_xticklabels(class_names)
        ax.set_yticklabels(class_names)
        ax.set_xlabel('Predicted label')
        ax.set_ylabel('True label')
        title = 'Confusion Matrix'
        if metrics.track_name:
            title = f'Confusion Matrix - {metrics.track_name}'
        ax.set_title(title)
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        self._ensure_dir(save_path)
        plt.tight_layout()
        plt.savefig(save_path, dpi=120, bbox_inches='tight')
        plt.close()
        print(f"Saved confusion matrix to {save_path}")

    # -----------------------------------------------------------------
    # 8. summary_dashboard.png
    # -----------------------------------------------------------------

    def summary_dashboard(self, shap_result, accum_result, metrics, save_path,
                          top_n=10):
        fig = plt.figure(figsize=(18, 6))

        # Panel 1: SHAP importance top-n
        ax1 = fig.add_subplot(1, 3, 1)
        mean_abs = np.asarray(shap_result.mean_abs_shap)
        feature_names = list(shap_result.feature_names)
        top_idx = np.argsort(-mean_abs)[:top_n][::-1]   # ascending for barh
        ax1.barh([feature_names[i] for i in top_idx], mean_abs[top_idx],
                 color='steelblue', alpha=0.85)
        ax1.set_title(f'SHAP Importance (top {top_n})')
        ax1.set_xlabel('Mean |SHAP value|')
        ax1.grid(axis='x', alpha=0.3)

        # Panel 2: Accumulation curve
        ax2 = fig.add_subplot(1, 3, 2)
        ax2.plot(accum_result.k_values, accum_result.accuracies,
                 'o-', color='steelblue', linewidth=2, markersize=5)
        threshold = accum_result.max_accuracy - accum_result.delta_tolerance
        ax2.axhline(threshold, color='orange', linestyle='--', alpha=0.7,
                    label=f'Max - {accum_result.delta_tolerance}')
        ax2.axvline(accum_result.optimal_k, color='red', linestyle=':',
                    alpha=0.7, label=f'k = {accum_result.optimal_k}')
        ax2.set_xlabel('# Features')
        ax2.set_ylabel('Accuracy')
        ax2.set_title('Accumulation Curve')
        ax2.legend(loc='lower right', fontsize=9)
        ax2.grid(alpha=0.3)

        # Panel 3: Metrics table
        ax3 = fig.add_subplot(1, 3, 3)
        ax3.axis('off')
        rows = [
            ['Metric', 'Value'],
            ['Accuracy', f'{metrics.accuracy:.4f}'],
            ['Precision', f'{metrics.precision:.4f}'],
            ['Recall', f'{metrics.recall:.4f}'],
            ['F1', f'{metrics.f1:.4f}'],
            ['Size', f'{metrics.model_size_bytes / 1024:.1f} KB'],
            ['Infer', f'{metrics.inference_per_sample_ms:.4f} ms'],
            ['# Feats', str(metrics.n_features)],
        ]
        table = ax3.table(cellText=rows, loc='center', cellLoc='left',
                          colWidths=[0.45, 0.55])
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1, 1.7)
        ax3.set_title('Final Model Metrics')

        title = 'ML Pipeline Summary'
        if metrics.track_name:
            title = f'ML Pipeline Summary - {metrics.track_name}'
        plt.suptitle(title, fontsize=14, fontweight='bold')

        self._ensure_dir(save_path)
        plt.tight_layout()
        plt.savefig(save_path, dpi=120, bbox_inches='tight')
        plt.close()
        print(f"Saved summary dashboard to {save_path}")
