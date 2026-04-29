"""
ml/pipeline/merge.py

Reads all PC logs (spoof, label=1) and A SD card logs (legit, label=1) from 
the dataset folder, merges them into a single training dataframe and sets aside
the Kiwi-Joker-2 session as a held-out test set.

Outputs:
    ml/data/processed/train.csv
    ml/data/processed/holdout.csv
"""

import os
import glob
import pandas as pd

# Where the CSV's live (PC logs (spoofed) and legit from the SD card)
DATA_DIR = r"C:\Users\sindre\gps-spoofing-and-ai-detection\ml\data\dataset"
OUT_DIR = r"C:\Users\sindre\gps-spoofing-and-ai-detection\ml\data\processed"

# Feature colums the model will see. 
FEATURE_COLS = [
    #GPS
    "Speed","HDOP", "Satelites", "Latitude", "Longitude", "Altitude",
    #Orientation
    "Roll Degrees", "Pitch Degrees", 
    #Motion magnitude
    "Dynamic Magnitude", "Jerk", "Jerk Std",
    #Directional accel
    "Acceleration X", "Acceleration Y", "Acceleration Z",
    # Windowed stats
    "Standard Deviation", "Energy", "Zero Crossings",
]

HOLDOUT_TOKENS = [
    "Kiwi-Joker-2",
    "(Real Kiwi-Joker)",
]

# --------------------------------------------------------------------------------------------
# Helpers                                                                                    
# --------------------------------------------------------------------------------------------

# Uses the filename without extension for session ID.
def session_id_from_filename(path):
    return os.path.splitext(os.path.basename(path))[0]

# True if any HOLDOUT_TOKENS substring appears in the session ID
def is_holdout_session(session_id):
    return any(tok in session_id for tok in HOLDOUT_TOKENS)


# --------------------------------------------------------------------------------------------
# Load one CSV file
# --------------------------------------------------------------------------------------------


# Read one CSV, normalize column names, keep only what is needed and tags row with the session_id
def load_one_file(path):

    df = pd.read_csv(path)

    # Some firmware verisons wrote headers with a leading space.
    # Strips column names
    df.columns = [c.strip() for c in df.columns]

    # Build a unified utc column from whichever UTC fields the file provides.
    # SD log: "UTC Date" + "UTC Time" -> concatenate to DDMMYY_HHMMSS.SSS
    # PC log: "UTC Time" already in DDMMYY_HHMMSS.SSS format -> use as-is
    if "UTC Date" in df.columns:
        df["utc"] = df["UTC Date"].astype(str) + "_" + df["UTC Time"].astype(str)
    elif "UTC Time" in df.columns:
        df["utc"] = df["UTC Time"].astype(str)
    else:
        df["utc"] = pd.NA

    # Normalize utc: parse the HHMMSS.SSS portion and re-format with 3 decimals
    # so PC log (was 6 decimals) and SD log (was 1 decimal) match.
    def _normalize_utc(s):
        if pd.isna(s) or "_" not in str(s):
            return s
        try:
            d, t = str(s).split("_", 1)
            return f"{d}_{float(t):010.3f}"
        except (ValueError, TypeError):
            return s

    df["utc"] = df["utc"].apply(_normalize_utc)

    keep_cols = ["utc", "Label"] + FEATURE_COLS

    # If missing column, fill it with NaN so later concat does not error
    # Print warning

    missing = [c for c in keep_cols if c not in df.columns]
    if missing:
        print(f"WARNING {os.path.basename(path)} missing columns: {missing}")
        for c in missing:
            df[c] = pd.NA

    df = df[keep_cols].copy()
    df["session_id"] = session_id_from_filename(path)
    return df


# --------------------------------------------------------------------------------------------
# Combine all files                                               
# --------------------------------------------------------------------------------------------

# Glob every CSV in data_dir, run load_one_file on each, concat
def load_all_files(data_dir):
    paths = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    paths = [p for p in paths
        if not os.path.basename(p).startswith(".~")
        and not os.path.basename(p).startswith("route_")
        and not os.path.basename(p).startswith("accel_raw_")]
    
    print(f"Found {len(paths)} CSV files in {data_dir}\n")

    dfs = []
    for p in paths:
        try:
            df = load_one_file(p)
            n_spoof = (df["Label"] == 1).sum()
            n_legit = (df["Label"] == 0).sum()
            print(f" {os.path.basename(p)[:65]:<65s} "
                f"rows={len(df):>5d} spoof={n_spoof:>5d} legit={n_legit:>5}")
            dfs.append(df)
        except Exception as e:
            print(f" FAIL {os.path.basename(p)}: {e}")
    
    if not dfs:
        raise RuntimeError(f"No usable CSVs in {data_dir}")
    
    big = pd.concat(dfs, ignore_index=True)
    print(f"\nCombined: {len(big)} rows from {len(dfs)} files")
    return big


# --------------------------------------------------------------------------------------------
# Cross-modal features (GPS-vs-accel comparison)
# --------------------------------------------------------------------------------------------

# These features directly test the spoof-detection hypothesis: when GPS
# claims one motion regime and the accelerometer measures a different one,
# we are likely seeing a spoof. Computed per row from existing columns,
# no temporal grouping required, no protocol-cadence leak.
def add_cross_modal_features(df):

    # Binary: does the GPS think the device is moving?
    gps_moving = df["Speed"] > 1.0
    # Binary: does the accel think the device is moving?
    accel_moving = df["Dynamic Magnitude"] > 0.04

    # 1 if GPS and accel disagree (one says "moving", the other says "still"),
    # 0 if they agree. The cleanest spoof tell when the spoofer replays a
    # walking route while A is sitting still or driving.
    df["motion_disagreement"] = (gps_moving != accel_moving).astype(int)

    # Continuous version of the same idea: scaled |Speed - DynMag|.
    # Speed in km/h is on 0-115 range, DynMag in g is on 0-0.5 range.
    # We rescale both to roughly 0-1 so the subtraction is meaningful.
    df["motion_mismatch"] = (
        (df["Speed"] / 100.0) - (df["Dynamic Magnitude"] * 2.0)
    ).abs()

    # Speed-per-DynMag ratio. Captures motion "style":
    #   high (driving cruise): smooth, fast - few small accelerations
    #   low (walking):         jerky, slow  - many small accelerations
    #   stationary:            ~0
    df["speed_per_dyn_mag"] = df["Speed"] / (df["Dynamic Magnitude"] + 0.001)

    # Speed-per-Jerk-Std. Higher Jerk Std means more variable jerk
    # (lots of step-like accelerations). Walking has high Jerk Std at
    # low speed; driving has lower Jerk Std at high speed.
    df["speed_per_jerk_std"] = df["Speed"] / (df["Jerk Std"] + 0.01)

    print(f"\nAdded 4 cross-modal features:")
    print(f"  motion_disagreement   (binary GPS vs accel motion)")
    print(f"  motion_mismatch       (continuous |Speed - DynMag|)")
    print(f"  speed_per_dyn_mag     (motion style)")
    print(f"  speed_per_jerk_std    (speed vs jerk variability)")
    return df


# --------------------------------------------------------------------------------------------
# Train / holdout split
# --------------------------------------------------------------------------------------------

# Split by session, not by row
def split_train_holdout(df):

    is_h = df["session_id"].apply(is_holdout_session)
    train_df = df.loc[~is_h].copy()
    holdout_df = df.loc[is_h].copy()

    print("\nTrain sessions")
    for sid in sorted(train_df["session_id"].unique()):
        sub = train_df[train_df["session_id"] == sid]
        print(f" {sid[:66]:<66s} rows={len(sub):>5d} "
              f"spoof={(sub['Label']==1).sum():>5d}")

    print("\nHoldout sessions:")
    for sid in sorted(holdout_df["session_id"].unique()):
        sub = holdout_df[holdout_df["session_id"] == sid]
        print(f" {sid[:66]:<66s} rows={len(sub):>5d} "
              f"spoof={(sub['Label']==1).sum():>5d}")
        
    return train_df, holdout_df


def save(train_df, holdout_df, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    tp = os.path.join(out_dir, "train.csv")
    hp = os.path.join(out_dir, "holdout.csv")
    train_df.to_csv(tp, index=False)
    holdout_df.to_csv(hp, index=False)
    print("\nWrote:")
    print(f" {tp} rows={len(train_df):>5d} "
          f"spoof={(train_df['Label']==1).sum()} "
          f"legit={(train_df['Label']==0).sum()}")
    
    print(f" {hp} rows={len(holdout_df):>5d} "
          f"spoof={(holdout_df['Label']==1).sum()} "
          f"legit={(holdout_df['Label']==0).sum()}")
    

# --------------------------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------------------------
        
if __name__ == "__main__":
    df = load_all_files(DATA_DIR)
    df = add_cross_modal_features(df)
    numeric_cols = df.select_dtypes(include=['float64']).columns
    df[numeric_cols] = df[numeric_cols].round(6)
    train_df, holdout_df = split_train_holdout(df)
    save(train_df, holdout_df, OUT_DIR)
    print("\nDone.")
