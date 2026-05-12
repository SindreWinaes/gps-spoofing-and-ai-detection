#
# TrainingPipeline.py
# Top-level orchestrator that wires the whole Ml_pipeline package
# together. Runs three feature-selection tracks against the same train
# set and produces three ModelBundles plus their holdout metrics:
#
#   SHAP track     -> features ranked by mean(|SHAP|)
#   UbiQTree track -> features ranked by UbiQTree's mean |SHAP| with
#                     uncertainty bounds
#   Combined track -> features ranked by fusing SHAP + UbiQTree
#
# All three tracks train the SAME final model architecture (LGBM with
# the same hyperparameters); they only differ in WHICH features make
# it into the final model. That isolates "did the feature-selection
# method matter" from "did the model matter" cleanly for the thesis.
#

import os

import pandas as pd

from Pc_backend.Ml_pipeline.DatasetMerger import DatasetMerger
from Pc_backend.Ml_pipeline.Trainer import Trainer
from Pc_backend.Ml_pipeline.FeatureRanker import FeatureRanker
from Pc_backend.Ml_pipeline.UbiQTreeRanker import UbiQTreeRanker
from Pc_backend.Ml_pipeline.RankingCombiner import RankingCombiner
from Pc_backend.Ml_pipeline.Evaluator import Evaluator
from Pc_backend.Ml_pipeline.ThesisPlots import ThesisPlots


# Same lists merge.py and train_shap.py used. Kept here because the EA
# constructor only takes the three paths; feature definitions are part
# of the pipeline's responsibility, not its inputs.
DEFAULT_FEATURE_COLS = [
    # GPS
    "Speed", "HDOP", "Satelites", "Latitude", "Longitude", "Altitude",
    # Orientation
    "Roll Degrees", "Pitch Degrees",
    # Motion magnitude
    "Dynamic Magnitude", "Jerk", "Jerk Std",
    # Directional accel
    "Acceleration X", "Acceleration Y", "Acceleration Z",
    # Windowed stats
    "Standard Deviation", "Energy", "Zero Crossings",
]

DEFAULT_HOLDOUT_TOKENS = [
    "Kiwi-Joker-2",
    "(Real Kiwi-Joker)",
]

# These columns are present in train.csv (so the CSV matches merge.py's
# output) but are NOT fed to the model. Geographic columns leak the
# session - any model trained on lat/lon learns "this lat/lon is the
# walking route" rather than the actual spoof signal.
NON_FEATURE_COLS = [
    "utc", "session_id", "Label",
    "Latitude", "Longitude", "Altitude",
    "HDOP", "Satelites",
]


class TrainingPipeline:

    def __init__(self, data_dir, out_dir, model_dir,
                 delta_tolerance=0.01,
                 feature_cols=None,
                 holdout_tokens=None):
        self.data_dir = data_dir
        self.out_dir = out_dir
        self.model_dir = model_dir
        self.delta_tolerance = delta_tolerance

        feature_cols = feature_cols if feature_cols is not None else DEFAULT_FEATURE_COLS
        holdout_tokens = holdout_tokens if holdout_tokens is not None else DEFAULT_HOLDOUT_TOKENS

        # Sub-components. shap_ranker / ubiq_ranker are built lazily
        # inside the per-track methods because they need a fitted model.
        self.merger = DatasetMerger(data_dir, out_dir, feature_cols, holdout_tokens)
        self.trainer = Trainer(delta_tolerance=delta_tolerance)
        self.combiner = RankingCombiner(method="rank_sum")
        self.shap_ranker = None
        self.ubiq_ranker = None
        self.evaluator = None   # one per saved bundle
        self.plots = ThesisPlots()

        # State carried between phases. Populated by run() before any
        # track is run; the track methods read from this so all three
        # tracks see the same train/val split.
        self._train_df = None
        self._holdout_df = None
        self._X_tr = None
        self._X_val = None
        self._y_tr = None
        self._y_val = None
        self._feature_cols = None
        self._shap_result = None
        self._ubiq_result = None
        # Track-name -> AccumulationResult, so summary_dashboard can
        # find the right curve when the dashboard is built per track.
        self._accum_results = {}

    # -----------------------------------------------------------------
    # End-to-end run
    # -----------------------------------------------------------------

    def run(self):
        # 1. Merge the raw CSVs into train + holdout (writes train.csv,
        #    holdout.csv to out_dir/processed - same files merge.py wrote).
        self._prepare_data()

        # 2. Train baselines used by the rankers
        baseline_lgb = self.trainer.train_baseline_lgb(
            self._X_tr, self._y_tr, self._X_val, self._y_val)
        baseline_rf = self.trainer.train_baseline_rf(
            self._X_tr, self._y_tr)

        # 3. Rank features each way once. The combined track reuses
        #    these results, so there's no point computing them twice.
        self.shap_ranker = FeatureRanker(baseline_lgb, self._feature_cols)
        self._shap_result = self.shap_ranker.rank(self._X_val)
        self.shap_ranker.plot_summary(
            self._shap_result,
            os.path.join(self.model_dir, "shap", "plots", "shap_summary.png"),
        )

        # Extra SHAP plots Sofie had for the preliminary work
        shap_plots_dir = os.path.join(self.model_dir, "shap", "plots")
        self.plots.shap_importance(
            self.shap_ranker._last_shap_values,
            self.shap_ranker._last_X_val,
            self._feature_cols,
            os.path.join(shap_plots_dir, "shap_importance.png"),
        )
        self.plots.shap_global_uncertainty(
            self.shap_ranker._last_shap_values,
            self._feature_cols,
            os.path.join(shap_plots_dir, "shap_global_uncertainty.png"),
        )
        self.plots.shap_violin_top3(
            self.shap_ranker._last_shap_values,
            self._feature_cols,
            os.path.join(shap_plots_dir, "shap_violin_top3.png"),
        )

        self.ubiq_ranker = UbiQTreeRanker(
            baseline_rf, self._X_tr, self._y_tr, self._feature_cols)
        self._ubiq_result = self.ubiq_ranker.rank(self._X_val)
        self.ubiq_ranker.plot_uncertainty_bars(
            self._ubiq_result,
            os.path.join(self.model_dir, "ubiqtree", "plots", "ubiq_bars.png"),
        )
        self.ubiq_ranker.plot_uncertainty_comparison(
            self._ubiq_result,
            os.path.join(self.model_dir, "ubiqtree", "plots", "ubiq_comparison.png"),
        )

        # Dempster-Shafer belief/plausibility (extra UbiQTree plot)
        self.plots.belief_plausibility(
            self._ubiq_result,
            os.path.join(self.model_dir, "ubiqtree", "plots",
                         "ubiq_belief_plausibility.png"),
        )

        # Cross-ranker comparison plots
        combined_plots_dir = os.path.join(self.model_dir, "combined", "plots")
        self.plots.combined_ranking_3panel(
            self._shap_result, self._ubiq_result,
            os.path.join(combined_plots_dir, "combined_ranking_plot.png"),
        )
        self.plots.rank_agreement_scatter(
            self._shap_result, self._ubiq_result,
            os.path.join(combined_plots_dir, "rank_agreement_scatter.png"),
        )

        # 4. Run each track. Each method trains the final LGBM on its
        #    own feature subset and saves the bundle to model_dir/<track>/.
        shap_bundle = self.run_shap_track()
        ubiq_bundle = self.run_ubiqtree_track()
        combined_bundle = self.run_combined_track()

        # 5. Evaluate each bundle on the held-out session
        self._evaluate_track("shap")
        self._evaluate_track("ubiqtree")
        self._evaluate_track("combined")

        return shap_bundle, ubiq_bundle, combined_bundle

    # -----------------------------------------------------------------
    # Tracks
    # -----------------------------------------------------------------

    def run_shap_track(self):
        # Ranked feature names from shap_result, then accumulation
        # curve + final LGBM on the top-k.
        ranked = [f for f, _ in self._shap_result.ranked_by_mean_abs()]
        return self._train_and_save_track(ranked, "shap")

    def run_ubiqtree_track(self):
        ranked = [f for f, _ in self._ubiq_result.ranked_by_mean_abs()]
        return self._train_and_save_track(ranked, "ubiqtree")

    def run_combined_track(self):
        combined = self.combiner.combine(self._shap_result, self._ubiq_result)
        # CombinedRanking exposes top_k via combined_ranks. We pass the
        # ranked feature names (all of them) to the accumulation curve;
        # it picks k itself.
        ranked = combined.top_k_features(k=len(combined.feature_names))
        return self._train_and_save_track(ranked, "combined")

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _prepare_data(self):
        # Merge -> add cross-modal -> round floats -> split sessions ->
        # save. Mirrors merge.py's __main__ block.
        df = self.merger.load_all()
        df = self.merger.add_cross_modal_features(df)

        # Same round-to-6-decimals pass merge.py did at the end. Kept
        # here so train.csv exactly matches what merge.py wrote.
        numeric_cols = df.select_dtypes(include=['float64']).columns
        df[numeric_cols] = df[numeric_cols].round(6)

        train_df, holdout_df = self.merger.split_train_holdout(df)
        self.merger.save(train_df, holdout_df)

        self._train_df = train_df
        self._holdout_df = holdout_df

        # Drop NaN rows on the feature columns (same as load_train_data
        # in train_shap.py). Geographic/HDOP/sat columns are kept in
        # the CSV but excluded from features.
        feature_cols = [c for c in train_df.columns if c not in NON_FEATURE_COLS]
        n_before = len(train_df)
        train_df = train_df.dropna(subset=feature_cols).reset_index(drop=True)
        n_dropped = n_before - len(train_df)
        if n_dropped:
            print(f"Dropped {n_dropped} train rows with NaN in feature cols")

        X = train_df[feature_cols].copy()
        y = train_df["Label"].astype(int).values
        self._feature_cols = feature_cols

        # 80/20 split + StandardScaler. Trainer stashes the scaler so
        # the bundle can pick it up later.
        self._X_tr, self._X_val, self._y_tr, self._y_val = \
            self.trainer.split_and_normalize(X, y)

    def _train_and_save_track(self, ranked_features, track_name):
        # Accumulation curve to pick optimal k, then train final LGBM
        # on those features and save the bundle.
        print(f"\n=== Track: {track_name} ===")
        accum = self.trainer.feature_accumulation_curve_lgb(
            self._X_tr, self._y_tr,
            self._X_val, self._y_val,
            ranked_features,
        )
        accum.plot(os.path.join(
            self.model_dir, track_name, "plots", "feature_accumulation.png"))

        # Stash for the summary_dashboard built later in _evaluate_track
        self._accum_results[track_name] = accum

        top_k = ranked_features[:accum.optimal_k]
        bundle = self.trainer.train_final_lgb(
            self._X_tr, self._y_tr,
            self._X_val, self._y_val,
            top_k,
            track_name,
        )

        out_path = os.path.join(self.model_dir, track_name)
        bundle.save(out_path)
        print(f"Saved {track_name} bundle to {out_path}")
        return bundle

    def _evaluate_track(self, track_name):
        # Load the bundle we just saved and evaluate on the holdout split
        bundle_path = os.path.join(self.model_dir, track_name)
        evaluator = Evaluator(bundle_path)
        metrics = evaluator.evaluate(self._holdout_df)
        metrics_path = os.path.join(bundle_path, "holdout_metrics.json")
        metrics.to_json(metrics_path)
        print(f"Saved {track_name} holdout metrics to {metrics_path}")

        # Per-track thesis plots: confusion matrix + summary dashboard
        plots_dir = os.path.join(bundle_path, "plots")
        self.plots.confusion_matrix(
            metrics,
            os.path.join(plots_dir, "confusion_matrix.png"),
        )
        accum = self._accum_results.get(track_name)
        if accum is not None:
            self.plots.summary_dashboard(
                self._shap_result, accum, metrics,
                os.path.join(plots_dir, "summary_dashboard.png"),
            )

        return metrics


# -----------------------------------------------------------------
# Convenience entry point - matches the train_shap.py / eval_holdout.py
# script style so the pipeline can be run from a single command.
# -----------------------------------------------------------------

if __name__ == "__main__":
    DATA_DIR = r"C:\Users\sindre\gps-spoofing-and-ai-detection\ml\data\dataset"
    OUT_DIR = r"C:\Users\sindre\gps-spoofing-and-ai-detection\ml\data\processed"
    MODEL_DIR = r"C:\Users\sindre\gps-spoofing-and-ai-detection\ml\models"

    pipeline = TrainingPipeline(DATA_DIR, OUT_DIR, MODEL_DIR)
    pipeline.run()
    print("\nAll three tracks done.")
