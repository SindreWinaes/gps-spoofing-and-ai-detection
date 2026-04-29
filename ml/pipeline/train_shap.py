"""
ml/pipeline/train_shap.py

Trains an LGBM spoof-detection model using SHAP feature ranking.

Pipeline:
  1. Load train.csv from ml/data/processed/
  2. Drop rows with NaN features
  3. Stratified 80/20 train/val split
  4. Normalize features with StandardScaler
  5. Train baseline LGBM on all features
  6. Compute SHAP values, rank features by mean(|SHAP|)
  7. Loop: train LGBM with top-k features, record accuracy
  8. Plot accuracy-vs-k, pick smallest k within 1% of max
  9. Train final model with that feature set, save it
 10. Report: accuracy, precision, recall, F1, model size, inference time

Outputs:
  ml/models/lgbm_final.txt
  ml/models/scaler.pkl
  ml/models/feature_list.json
  ml/outputs/feature_accumulation.png
  ml/outputs/shap_summary.png
  ml/outputs/metrics.json
"""

import os
import json
import time
import pickle

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix,
)

import lightgbm as lgb
import shap


# Configuration
DATA_DIR   = r"C:\Users\sindre\gps-spoofing-and-ai-detection\ml\data\processed"
MODEL_DIR  = r"C:\Users\sindre\gps-spoofing-and-ai-detection\ml\models"
OUTPUT_DIR = r"C:\Users\sindre\gps-spoofing-and-ai-detection\ml\outputs"

TRAIN_CSV = os.path.join(DATA_DIR, "train.csv")

NON_FEATURE_COLS = ["utc", "session_id", "Label",
                    "Latitude", "Longitude", "Altitude",
                    "HDOP", "Satelites"]

TEST_SIZE = 0.20
RANDOM_STATE = 42
DELTA_TOLERANCE = 0.01

LGBM_PARAMS = dict(
    objective='binary',
    num_leaves=31,
    learning_rate=0.05,
    n_estimators=200,
    class_weight='balanced',
    random_state=RANDOM_STATE,
    verbose=-1,
)


# --------------------------------------------------------------------------------------------
# Load data
# --------------------------------------------------------------------------------------------

def load_train_data(path):
    """Read train.csv, separate features from label, drop NaN rows."""
    df = pd.read_csv(path)
    print(f"Loaded {len(df)} rows from {path}")
    print(f"Class balance: {(df['Label']==1).sum()} spoof, {(df['Label']==0).sum()} legit")

    feature_cols = [c for c in df.columns if c not in NON_FEATURE_COLS]

    n_before = len(df)
    df = df.dropna(subset=feature_cols).reset_index(drop=True)
    n_dropped = n_before - len(df)
    if n_dropped > 0:
        print(f"Dropped {n_dropped} rows with NaN features")

    print(f"Feature columns ({len(feature_cols)}):")
    for c in feature_cols:
        print(f"  {c}")

    X = df[feature_cols].copy()
    y = df["Label"].astype(int).values
    return X, y, feature_cols


# --------------------------------------------------------------------------------------------
# Train / val split + normalize
# --------------------------------------------------------------------------------------------

def split_and_normalize(X, y):
    """Stratified 80/20 split, then fit StandardScaler on train only."""
    X_tr, X_val, y_tr, y_val = train_test_split(
        X, y,
        test_size=TEST_SIZE,
        stratify=y,
        random_state=RANDOM_STATE,
    )

    print(f"\nTrain split: {len(X_tr)} rows  "
          f"({(y_tr==1).sum()} spoof, {(y_tr==0).sum()} legit)")
    print(f"Val split:   {len(X_val)} rows  "
          f"({(y_val==1).sum()} spoof, {(y_val==0).sum()} legit)")

    scaler = StandardScaler()
    X_tr_scaled = pd.DataFrame(
        scaler.fit_transform(X_tr),
        columns=X_tr.columns,
        index=X_tr.index,
    )
    X_val_scaled = pd.DataFrame(
        scaler.transform(X_val),
        columns=X_val.columns,
        index=X_val.index,
    )

    print(f"Scaler fitted on {len(X_tr)} training rows")
    return X_tr_scaled, X_val_scaled, y_tr, y_val, scaler


# --------------------------------------------------------------------------------------------
# Baseline LGBM
# --------------------------------------------------------------------------------------------

def train_baseline_lgbm(X_tr, y_tr, X_val, y_val):
    """Train LGBM on all features, report val accuracy, return model."""
    model = lgb.LGBMClassifier(**LGBM_PARAMS)
    model.fit(X_tr, y_tr)

    y_pred = model.predict(X_val)
    accuracy = accuracy_score(y_val, y_pred)
    print(f"\nBaseline LGBM accuracy on val set (all features): {accuracy:.4f}")
    return model, accuracy


# --------------------------------------------------------------------------------------------
# SHAP feature ranking
# --------------------------------------------------------------------------------------------

def compute_shap_ranking(model, X_val, feature_cols):
    """Compute SHAP values and rank features by mean(|SHAP|)."""
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_val)

    # Newer SHAP returns one array; older versions return a list per class.
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    mean_abs_shap = np.abs(shap_values).mean(axis=0)

    importance = sorted(
        zip(feature_cols, mean_abs_shap),
        key=lambda kv: kv[1],
        reverse=True,
    )

    print("\nFeature ranking by mean(|SHAP|):")
    print(f"  {'rank':<5s}{'feature':<22s}{'mean|SHAP|':>12s}")
    for i, (feat, val) in enumerate(importance, start=1):
        print(f"  {i:<5d}{feat:<22s}{val:>12.6f}")

    plt.figure(figsize=(10, 6))
    shap.summary_plot(shap_values, X_val, plot_type="bar", show=False)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "shap_summary.png"),
                dpi=120, bbox_inches='tight')
    plt.close()
    print(f"Saved SHAP summary plot to {OUTPUT_DIR}/shap_summary.png")

    return [feat for feat, _ in importance]


# --------------------------------------------------------------------------------------------
# Feature accumulation curve
# --------------------------------------------------------------------------------------------

def feature_accumulation_curve(X_tr, y_tr, X_val, y_val, ranked_features):
    """Train LGBM with top-k features for k=2..N, return list of (k, accuracy)."""
    print("\nFeature accumulation:")
    print(f"  {'k':<4s}{'features used':<60s}{'val accuracy':>14s}")
    results = []
    for k in range(2, len(ranked_features) + 1):
        cols = ranked_features[:k]
        model = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(X_tr[cols], y_tr)
        y_pred = model.predict(X_val[cols])
        acc = accuracy_score(y_val, y_pred)
        used = ", ".join(cols)
        if len(used) > 58:
            used = used[:55] + "..."
        print(f"  {k:<4d}{used:<60s}{acc:>14.4f}")
        results.append((k, acc))
    return results


def plot_accumulation_curve(results, save_path):
    ks   = [k for k, _ in results]
    accs = [a for _, a in results]
    plt.figure(figsize=(8, 5))
    plt.plot(ks, accs, marker='o', color='steelblue', linewidth=2)
    plt.xlabel('Number of features (top-k by SHAP)')
    plt.ylabel('Validation accuracy')
    plt.title('Feature Accumulation Curve')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=120, bbox_inches='tight')
    plt.close()
    print(f"Saved accumulation curve to {save_path}")


def find_optimal_k(results, tolerance=DELTA_TOLERANCE):
    """Smallest k whose accuracy is within `tolerance` of max accuracy."""
    max_acc = max(a for _, a in results)
    threshold = max_acc - tolerance
    for k, a in results:
        if a >= threshold:
            print(f"\nMax accuracy: {max_acc:.4f}")
            print(f"Threshold (max - {tolerance}): {threshold:.4f}")
            print(f"Smallest k that meets threshold: {k}")
            return k, max_acc
    return len(results) + 1, max_acc


# --------------------------------------------------------------------------------------------
# Final model + metrics
# --------------------------------------------------------------------------------------------

def train_final_model(X_tr, y_tr, X_val, y_val, top_k_features):
    """Train final model on the chosen subset, save it, report metrics."""
    print(f"\n=== Final model: {len(top_k_features)} features ===")
    for f in top_k_features:
        print(f"  {f}")

    model = lgb.LGBMClassifier(**LGBM_PARAMS)
    model.fit(X_tr[top_k_features], y_tr)

    model_path = os.path.join(MODEL_DIR, "lgbm_final.txt")
    model.booster_.save_model(model_path)

    t0 = time.time()
    y_pred = model.predict(X_val[top_k_features])
    inference_time = time.time() - t0
    per_sample_ms = inference_time / len(X_val) * 1000

    accuracy  = accuracy_score(y_val, y_pred)
    precision = precision_score(y_val, y_pred)
    recall    = recall_score(y_val, y_pred)
    f1        = f1_score(y_val, y_pred)
    cm        = confusion_matrix(y_val, y_pred)
    model_size_kb = os.path.getsize(model_path) / 1024

    print(f"\nMetrics on val set:")
    print(f"  Accuracy:  {accuracy:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print(f"  F1:        {f1:.4f}")
    print(f"  Confusion matrix:")
    print(f"              pred=0  pred=1")
    print(f"    true=0:  {cm[0,0]:>6d}  {cm[0,1]:>6d}")
    print(f"    true=1:  {cm[1,0]:>6d}  {cm[1,1]:>6d}")
    print(f"  Model size:        {model_size_kb:.2f} KB")
    print(f"  Inference total:   {inference_time*1000:.2f} ms ({len(X_val)} samples)")
    print(f"  Per-sample:        {per_sample_ms:.4f} ms")

    metrics = {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "confusion_matrix": cm.tolist(),
        "model_size_kb": float(model_size_kb),
        "inference_total_ms": float(inference_time * 1000),
        "inference_per_sample_ms": float(per_sample_ms),
        "n_features": len(top_k_features),
        "feature_list": list(top_k_features),
        "n_train_rows": int(len(X_tr)),
        "n_val_rows": int(len(X_val)),
    }
    with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    with open(os.path.join(MODEL_DIR, "feature_list.json"), "w") as f:
        json.dump(list(top_k_features), f, indent=2)

    print(f"\nSaved:")
    print(f"  {model_path}")
    print(f"  {os.path.join(OUTPUT_DIR, 'metrics.json')}")
    print(f"  {os.path.join(MODEL_DIR, 'feature_list.json')}")
    return model


# --------------------------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Load and prepare
    X, y, feature_cols = load_train_data(TRAIN_CSV)
    X_tr, X_val, y_tr, y_val, scaler = split_and_normalize(X, y)

    # Save the scaler so eval_holdout.py can apply identical scaling later
    scaler_path = os.path.join(MODEL_DIR, "scaler.pkl")
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    print(f"Saved scaler to {scaler_path}")

    # 2. Baseline LGBM (all features) + SHAP ranking
    baseline_model, baseline_acc = train_baseline_lgbm(X_tr, y_tr, X_val, y_val)
    ranked_features = compute_shap_ranking(baseline_model, X_val, feature_cols)

    # 3. Feature accumulation curve
    results = feature_accumulation_curve(X_tr, y_tr, X_val, y_val, ranked_features)
    plot_accumulation_curve(
        results, os.path.join(OUTPUT_DIR, "feature_accumulation.png"))
    optimal_k, max_acc = find_optimal_k(results)

    # 4. Train final model with the chosen subset and report metrics
    top_k_features = ranked_features[:optimal_k]
    final_model = train_final_model(X_tr, y_tr, X_val, y_val, top_k_features)

    print("\nDone.")
