#
# Evaluator.py
# Holdout-set evaluation: load a saved ModelBundle, apply it to a
# held-out DataFrame, and produce a Metrics object containing accuracy
# / precision / recall / F1 plus model size and inference timing.
#
# Same logic as the existing eval_holdout.py script - this class just
# packages it so the pipeline diagram has a class to point at and so
# the three tracks (SHAP, UbiQTree, combined) can reuse it.
#

import os
import time

import numpy as np
import pandas as pd

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix,
)

from Pc_backend.Ml_pipeline.ModelBundle import ModelBundle
from Pc_backend.Ml_pipeline.Metrics import Metrics


class Evaluator:

    def __init__(self, bundle_path):
        # Bundle path is the directory that ModelBundle.save() wrote.
        self.bundle_path = bundle_path
        self.bundle = ModelBundle.load(bundle_path)

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def evaluate(self, holdout_df):
        # Same shape as eval_holdout.py main(): drop NaN rows on the
        # scaler's input features, apply the saved scaler, subset to
        # the model's feature list, predict, score.
        bundle = self.bundle
        scaler_features = list(bundle.scaler.feature_names_in_)
        feature_list = list(bundle.feature_list)

        print(f"Evaluating on {len(holdout_df)} rows, track={bundle.track_name}")
        print(f"  Final model features ({len(feature_list)}): {feature_list}")
        print(f"  Scaler was fit on {len(scaler_features)} features")

        # Drop rows with NaN in the scaler features. Same rule as
        # training so the holdout pre-processing matches.
        n_before = len(holdout_df)
        df = holdout_df.dropna(subset=scaler_features).reset_index(drop=True)
        n_dropped = n_before - len(df)
        if n_dropped > 0:
            print(f"  Dropped {n_dropped} rows with NaN in scaler features")

        X = df[scaler_features].copy()
        y = df["Label"].astype(int).values

        X_scaled = pd.DataFrame(
            bundle.scaler.transform(X),
            columns=X.columns,
            index=X.index,
        )
        X_for_model = X_scaled[feature_list]

        # Inference (and timing)
        inference_time_ms = self._measure_inference_time(X_for_model)
        y_proba = bundle.model.predict(X_for_model)
        y_pred = (y_proba >= 0.5).astype(int)

        # Per-session breakdown for diagnostic console output. Doesn't
        # go into the Metrics object - that's the overall summary.
        self._print_per_session(df, y, y_pred)

        accuracy = accuracy_score(y, y_pred)
        precision = precision_score(y, y_pred, zero_division=0)
        recall = recall_score(y, y_pred, zero_division=0)
        f1 = f1_score(y, y_pred, zero_division=0)
        cm = confusion_matrix(y, y_pred)

        per_sample_ms = inference_time_ms / max(len(X_for_model), 1)
        model_size_bytes = self._measure_model_size(bundle)

        # Console summary identical in shape to eval_holdout.py
        print(f"\n=== Held-out evaluation ===")
        print(f"  Rows evaluated: {len(df)}")
        print(f"  Accuracy:       {accuracy:.4f}")
        print(f"  Precision:      {precision:.4f}")
        print(f"  Recall:         {recall:.4f}")
        print(f"  F1:             {f1:.4f}")
        print(f"  Confusion matrix:")
        print(f"              pred=0  pred=1")
        print(f"    true=0:  {cm[0,0]:>6d}  {cm[0,1]:>6d}")
        print(f"    true=1:  {cm[1,0]:>6d}  {cm[1,1]:>6d}")
        print(f"  Model size:        {model_size_bytes/1024:.2f} KB")
        print(f"  Inference total:   {inference_time_ms:.2f} ms ({len(X_for_model)} samples)")
        print(f"  Per-sample:        {per_sample_ms:.4f} ms")

        return Metrics(
            track_name=bundle.track_name,
            accuracy=float(accuracy),
            precision=float(precision),
            recall=float(recall),
            f1=float(f1),
            model_size_bytes=int(model_size_bytes),
            inference_time_ms=float(inference_time_ms),
            confusion_matrix=cm.tolist(),
            inference_per_sample_ms=float(per_sample_ms),
            n_rows=int(len(df)),
            n_features=len(feature_list),
            feature_list=list(feature_list),
        )

    # -----------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------

    def _measure_inference_time(self, X):
        # Times a full predict() call. Run twice and keep the second
        # measurement so any first-call lazy-init cost (JIT warmup,
        # buffer allocation) doesn't pollute the number.
        _ = self.bundle.model.predict(X.iloc[:1] if hasattr(X, "iloc") else X[:1])
        t0 = time.perf_counter()
        _ = self.bundle.model.predict(X)
        return (time.perf_counter() - t0) * 1000.0

    def _measure_model_size(self, bundle):
        # Size of the model file on disk - the deployable artefact.
        # If for some reason there's no model.txt (loaded from elsewhere)
        # fall back to 0 so callers can still get the other metrics.
        model_path = os.path.join(self.bundle_path, "model.txt")
        if os.path.exists(model_path):
            return os.path.getsize(model_path)
        return 0

    @staticmethod
    def _print_per_session(df, y, y_pred):
        # Each held-out session reported separately so we can see
        # whether the model degrades on a same-route session
        # specifically vs a different-route session.
        if "session_id" not in df.columns:
            return
        print("\nPer-session results:")
        for sid in sorted(df["session_id"].unique()):
            mask = (df["session_id"] == sid).values
            if mask.sum() == 0:
                continue
            sess_y = y[mask]
            sess_pred = y_pred[mask]
            if len(np.unique(sess_y)) > 1:
                acc = accuracy_score(sess_y, sess_pred)
                print(f"  {sid[:65]:<65s} rows={mask.sum():>4d}  acc={acc:.4f}")
            else:
                # Only one class present - accuracy is just "did we
                # guess the single class correctly"
                single = sess_y[0]
                n_correct = (sess_pred == single).sum()
                label = 'spoof' if single == 1 else 'legit'
                print(f"  {sid[:65]:<65s} rows={mask.sum():>4d}  "
                      f"all-{label}: {n_correct}/{mask.sum()} correct")
