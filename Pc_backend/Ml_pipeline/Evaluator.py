import os
import time

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_curve, auc,
)

from Pc_backend.Ml_pipeline.ModelBundle import ModelBundle
from Pc_backend.Ml_pipeline.Metrics import Metrics


# ROC plot styling
_BG_COLOR    = "#EEF3F7"
_GRID_COLOR  = "#C9D2DA"
_DIAG_COLOR  = "#8E97A1"
_SPINE_COLOR = "#B8C0C8"
_TITLE_COLOR = "#1F2937"
_SUBT_COLOR  = "#6B7280"

_TRACK_COLORS = {
    "shap":     "#5BB6C4",
    "ubiqtree": "#F0A05A",
    "combined": "#7FCB9B",
}
_TRACK_LABELS = {
    "shap":     "SHAP track",
    "ubiqtree": "UBiQTree track",
    "combined": "Combined track",
}


class Evaluator:

    def __init__(self, bundle_path):
        self.bundle_path = bundle_path
        self.bundle = ModelBundle.load(bundle_path)

    def evaluate(self, holdout_df):
        bundle = self.bundle
        scaler_features = list(bundle.scaler.feature_names_in_)
        feature_list = list(bundle.feature_list)

        print(f"Evaluating on {len(holdout_df)} rows, track={bundle.track_name}")
        print(f"  Final model features ({len(feature_list)}): {feature_list}")
        print(f"  Scaler was fit on {len(scaler_features)} features")

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

        inference_time_ms = self._measure_inference_time(X_for_model)
        y_proba = bundle.model.predict(X_for_model)
        y_pred = (y_proba >= 0.5).astype(int)

        self._print_per_session(df, y, y_pred)

        accuracy = accuracy_score(y, y_pred)
        precision = precision_score(y, y_pred, zero_division=0)
        recall = recall_score(y, y_pred, zero_division=0)
        f1 = f1_score(y, y_pred, zero_division=0)
        cm = confusion_matrix(y, y_pred)

        per_sample_ms = inference_time_ms / max(len(X_for_model), 1)
        model_size_bytes = self._measure_model_size(bundle)

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

    def roc_data(self, holdout_df):
        bundle = self.bundle
        scaler_features = list(bundle.scaler.feature_names_in_)
        feature_list = list(bundle.feature_list)

        df = holdout_df.dropna(subset=scaler_features).reset_index(drop=True)
        X = df[scaler_features].copy()
        y = df["Label"].astype(int).values

        X_scaled = pd.DataFrame(
            bundle.scaler.transform(X),
            columns=X.columns,
            index=X.index,
        )
        X_for_model = X_scaled[feature_list]

        y_proba = bundle.model.predict(X_for_model)
        fpr, tpr, _ = roc_curve(y, y_proba)
        auc_value = auc(fpr, tpr)

        return {
            "track":      bundle.track_name,
            "fpr":        fpr,
            "tpr":        tpr,
            "auc":        float(auc_value),
            "n_features": len(feature_list),
        }

    def plot_roc(self, holdout_df, out_path):
        data = self.roc_data(holdout_df)
        self._draw_roc_figure(
            curves=[data],
            main_title=f"ROC Curve - {_TRACK_LABELS.get(data['track'], data['track'])}",
            subtitle=(f"Binary GPS spoofing detection . LightGBM . "
                      f"{data['n_features']} features"),
            out_path=out_path,
        )
        print(f"  Wrote ROC plot to {out_path}  (AUC = {data['auc']:.4f})")
        return data

    @staticmethod
    def plot_roc_comparison(roc_data_list, out_path):
        Evaluator._draw_roc_figure(
            curves=roc_data_list,
            main_title="ROC Curves - Track Comparison",
            subtitle="Binary GPS spoofing detection . Kiwi-Joker held-out session",
            out_path=out_path,
        )
        print(f"  Wrote ROC comparison plot to {out_path}")

    @staticmethod
    def _draw_roc_figure(curves, main_title, subtitle, out_path):
        fig, ax = plt.subplots(figsize=(9, 5.5))
        fig.patch.set_facecolor(_BG_COLOR)
        ax.set_facecolor(_BG_COLOR)

        for c in curves:
            color = _TRACK_COLORS.get(c["track"], "#4C9BC0")
            ax.plot(c["fpr"], c["tpr"], color=color, lw=2.4)

        ax.plot([0, 1], [0, 1], color=_DIAG_COLOR, lw=1.0, linestyle="--")

        ax.set_xlim(-0.01, 1.0)
        ax.set_ylim(0.0, 1.01)
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.grid(True, color=_GRID_COLOR, lw=0.8, linestyle="--", alpha=0.7)
        for spine in ax.spines.values():
            spine.set_color(_SPINE_COLOR)
        ax.tick_params(colors="#4B5563")

        ax.set_title(main_title, fontsize=13, fontweight="bold",
                     color=_TITLE_COLOR, pad=22)
        ax.text(0.5, 1.02, subtitle, transform=ax.transAxes,
                ha="center", va="bottom", fontsize=10, color=_SUBT_COLOR)

        x0 = 1.04
        y = 0.92
        for c in curves:
            color = _TRACK_COLORS.get(c["track"], "#4C9BC0")
            label = _TRACK_LABELS.get(c["track"], c["track"])
            ax.plot([x0, x0 + 0.05], [y, y], transform=ax.transAxes,
                    color=color, lw=2.5, clip_on=False)
            ax.text(x0 + 0.07, y + 0.005, label, transform=ax.transAxes,
                    fontsize=10, color=color, fontweight="bold",
                    va="center", clip_on=False)
            ax.text(x0 + 0.07, y - 0.045, f"AUC = {c['auc']:.4f}",
                    transform=ax.transAxes,
                    fontsize=10, color=color, fontweight="bold",
                    va="center", clip_on=False)
            y -= 0.13

        fig.subplots_adjust(left=0.08, right=0.78, top=0.85, bottom=0.12)
        fig.savefig(out_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)

    def _measure_inference_time(self, X):
        # Warm-up call first so lazy-init cost is excluded
        _ = self.bundle.model.predict(X.iloc[:1] if hasattr(X, "iloc") else X[:1])
        t0 = time.perf_counter()
        _ = self.bundle.model.predict(X)
        return (time.perf_counter() - t0) * 1000.0

    def _measure_model_size(self, bundle):
        model_path = os.path.join(self.bundle_path, "model.txt")
        if os.path.exists(model_path):
            return os.path.getsize(model_path)
        return 0

    @staticmethod
    def _print_per_session(df, y, y_pred):
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
                single = sess_y[0]
                n_correct = (sess_pred == single).sum()
                label = 'spoof' if single == 1 else 'legit'
                print(f"  {sid[:65]:<65s} rows={mask.sum():>4d}  "
                      f"all-{label}: {n_correct}/{mask.sum()} correct")
