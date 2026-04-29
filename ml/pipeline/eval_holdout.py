"""
ml/pipeline/eval_holdout.py

Loads the saved final model + scaler + feature list,
applies them to the held-out Kiwi-Joker-2 session,
reports how well the model generalizes to never-seen-during-training data.

Inputs:
  ml/data/processed/holdout.csv
  ml/models/lgbm_final.txt
  ml/models/scaler.pkl
  ml/models/feature_list.json
  ml/outputs/metrics.json   (for val-vs-holdout comparison)

Outputs:
  ml/outputs/holdout_metrics.json
"""

import os
import json
import time
import pickle

import numpy as np
import pandas as pd

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix,
)

import lightgbm as lgb


DATA_DIR   = r"C:\Users\sindre\gps-spoofing-and-ai-detection\ml\data\processed"
MODEL_DIR  = r"C:\Users\sindre\gps-spoofing-and-ai-detection\ml\models"
OUTPUT_DIR = r"C:\Users\sindre\gps-spoofing-and-ai-detection\ml\outputs"

HOLDOUT_CSV       = os.path.join(DATA_DIR, "holdout.csv")
MODEL_PATH        = os.path.join(MODEL_DIR, "lgbm_final.txt")
SCALER_PATH       = os.path.join(MODEL_DIR, "scaler.pkl")
FEATURE_LIST_PATH = os.path.join(MODEL_DIR, "feature_list.json")
VAL_METRICS_PATH  = os.path.join(OUTPUT_DIR, "metrics.json")
HOLDOUT_OUT_PATH  = os.path.join(OUTPUT_DIR, "holdout_metrics.json")


def main():
    # ------------------------------------------------------------------
    # Load held-out data
    # ------------------------------------------------------------------
    df = pd.read_csv(HOLDOUT_CSV)
    print(f"Loaded {len(df)} rows from {HOLDOUT_CSV}")
    print(f"Class balance: {(df['Label']==1).sum()} spoof, {(df['Label']==0).sum()} legit")
    print(f"Sessions:")
    for sid in sorted(df['session_id'].unique()):
        sub = df[df['session_id'] == sid]
        print(f"  {sid[:65]:<65s}  rows={len(sub):>4d}  "
              f"spoof={(sub['Label']==1).sum():>4d}  "
              f"legit={(sub['Label']==0).sum():>4d}")

    # ------------------------------------------------------------------
    # Load the saved artifacts produced by train_shap.py
    # ------------------------------------------------------------------
    print("\nLoading saved model artifacts...")
    booster = lgb.Booster(model_file=MODEL_PATH)

    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)

    with open(FEATURE_LIST_PATH) as f:
        feature_list = json.load(f)

    scaler_features = list(scaler.feature_names_in_)
    print(f"  Final model features ({len(feature_list)}): {feature_list}")
    print(f"  Scaler was fit on {len(scaler_features)} features")

    # ------------------------------------------------------------------
    # Same NaN drop rule as training: drop rows where ANY scaler input is NaN.
    # The 1 PC-log row with no accel was dropped during training; it would
    # also be dropped here for the same reason.
    # ------------------------------------------------------------------
    n_before = len(df)
    df = df.dropna(subset=scaler_features).reset_index(drop=True)
    n_dropped = n_before - len(df)
    if n_dropped > 0:
        print(f"  Dropped {n_dropped} rows with NaN in scaler features")

    # ------------------------------------------------------------------
    # Apply the saved scaler, then subset to the columns the final model needs
    # ------------------------------------------------------------------
    X = df[scaler_features].copy()
    y = df["Label"].astype(int).values

    X_scaled = pd.DataFrame(
        scaler.transform(X),
        columns=X.columns,
        index=X.index,
    )
    X_for_model = X_scaled[feature_list]

    # ------------------------------------------------------------------
    # Predict
    # ------------------------------------------------------------------
    print(f"\nRunning inference on {len(X_for_model)} held-out rows...")
    t0 = time.time()
    y_proba = booster.predict(X_for_model)
    inference_time = time.time() - t0
    y_pred = (y_proba >= 0.5).astype(int)
    per_sample_ms = inference_time / len(X_for_model) * 1000

    # ------------------------------------------------------------------
    # Per-session results (each held-out session reported separately so we
    # can see whether the model degrades on the same-route hard case
    # specifically vs the legit Kiwi-Joker-2 session)
    # ------------------------------------------------------------------
    print("\nPer-session results:")
    for sid in sorted(df['session_id'].unique()):
        mask = (df['session_id'] == sid).values
        if mask.sum() == 0:
            continue
        sess_y = y[mask]
        sess_pred = y_pred[mask]
        if len(np.unique(sess_y)) > 1:
            acc = accuracy_score(sess_y, sess_pred)
            print(f"  {sid[:65]:<65s} rows={mask.sum():>4d}  acc={acc:.4f}")
        else:
            # Only one class present in this session - accuracy is just
            # "did we guess the single class correctly".
            single = sess_y[0]
            n_correct = (sess_pred == single).sum()
            print(f"  {sid[:65]:<65s} rows={mask.sum():>4d}  "
                  f"all-{'spoof' if single==1 else 'legit'}: "
                  f"{n_correct}/{mask.sum()} correct")

    # ------------------------------------------------------------------
    # Overall metrics
    # ------------------------------------------------------------------
    accuracy  = accuracy_score(y, y_pred)
    precision = precision_score(y, y_pred, zero_division=0)
    recall    = recall_score(y, y_pred, zero_division=0)
    f1        = f1_score(y, y_pred, zero_division=0)
    cm        = confusion_matrix(y, y_pred)

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
    print(f"  Inference total:   {inference_time*1000:.2f} ms")
    print(f"  Per-sample:        {per_sample_ms:.4f} ms")

    # ------------------------------------------------------------------
    # Compare to validation metrics from train_shap.py
    # ------------------------------------------------------------------
    if os.path.exists(VAL_METRICS_PATH):
        with open(VAL_METRICS_PATH) as f:
            val_metrics = json.load(f)
        print(f"\nComparison: validation set vs held-out set")
        print(f"  {'Metric':<12s} {'Validation':>11s} {'Holdout':>11s} {'Delta':>10s}")
        print(f"  {'Accuracy':<12s} {val_metrics['accuracy']:>11.4f} {accuracy:>11.4f} {accuracy - val_metrics['accuracy']:>+10.4f}")
        print(f"  {'Precision':<12s} {val_metrics['precision']:>11.4f} {precision:>11.4f} {precision - val_metrics['precision']:>+10.4f}")
        print(f"  {'Recall':<12s} {val_metrics['recall']:>11.4f} {recall:>11.4f} {recall - val_metrics['recall']:>+10.4f}")
        print(f"  {'F1':<12s} {val_metrics['f1']:>11.4f} {f1:>11.4f} {f1 - val_metrics['f1']:>+10.4f}")
        print(f"\n  Negative delta = degradation on held-out (expected: model")
        print(f"  saw similar but not identical data; some drop is normal).")
        print(f"  Large drop = model overfitted; small drop or none = generalized well.")

    # ------------------------------------------------------------------
    # Save results
    # ------------------------------------------------------------------
    holdout_metrics = {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "confusion_matrix": cm.tolist(),
        "inference_total_ms": float(inference_time * 1000),
        "inference_per_sample_ms": float(per_sample_ms),
        "n_rows": int(len(df)),
        "n_features": len(feature_list),
        "feature_list": feature_list,
        "sessions": sorted(df['session_id'].unique().tolist()),
    }
    with open(HOLDOUT_OUT_PATH, "w") as f:
        json.dump(holdout_metrics, f, indent=2)
    print(f"\nSaved holdout metrics to {HOLDOUT_OUT_PATH}")


if __name__ == "__main__":
    main()
