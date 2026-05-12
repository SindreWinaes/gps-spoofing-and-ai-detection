#
# FeatureComputer.py
# Cross-modal features: GPS-vs-accelerometer comparisons. These directly
# test the spoof-detection hypothesis - when GPS claims one motion regime
# and the accelerometer measures a different one, we are likely looking
# at a spoof. Computed per row from existing columns; no temporal
# grouping required, no protocol-cadence leak.
#
# Single source of truth for the four cross-modal features used by
# DatasetMerger. Lives in Pc_common because both the offline training
# pipeline and the runtime classifier need to compute them the same way.
#

import numpy as np
import pandas as pd


class FeatureComputer:

    # Names produced by compute_one() / added by compute_batch(). Same
    # order the existing merge.py prints them in.
    FEATURE_NAMES = [
        "motion_disagreement",
        "motion_mismatch",
        "speed_per_dyn_mag",
        "speed_per_jerk_std",
    ]

    # "Moving" thresholds. Above these the device is considered to be
    # moving by that modality. Tuned for walking pace - faster motion
    # is well past both thresholds anyway.
    MOVING_SPEED_THRESHOLD = 1.0      # km/h
    MOVING_DYN_MAG_THRESHOLD = 0.04   # g

    def _motion_disagreement(self, speed, dyn_mag):
        # 1 if GPS and accel disagree about whether the device is
        # moving, 0 if they agree. Cleanest spoof tell when the spoofer
        # replays a walking route while A is sitting still or driving.
        gps_moving = speed > self.MOVING_SPEED_THRESHOLD
        accel_moving = dyn_mag > self.MOVING_DYN_MAG_THRESHOLD
        return int(gps_moving != accel_moving)

    def _motion_mismatch(self, speed, dyn_mag):
        # Continuous version of motion_disagreement: scaled |Speed - DynMag|.
        # Speed in km/h is on 0-115 range; DynMag in g is on 0-0.5 range.
        # Rescale both to roughly 0-1 so the subtraction means something.
        return abs((speed / 100.0) - (dyn_mag * 2.0))

    def _speed_per_dyn_mag(self, speed, dyn_mag):
        # Captures motion "style":
        #   high (driving cruise): smooth, fast - few small accelerations
        #   low  (walking):        jerky, slow  - many small accelerations
        #   stationary:            ~0
        # +0.001 avoids div-by-zero when the device is stock-still.
        return speed / (dyn_mag + 0.001)

    def _speed_per_jerk_std(self, speed, jerk_std):
        # Higher Jerk Std = more variable jerk (lots of step-like
        # accelerations). Walking = high Jerk Std at low speed;
        # driving = lower Jerk Std at high speed.
        return speed / (jerk_std + 0.01)

    def compute_one(self, speed, dyn_mag, jerk_std):
        # Per-row version - used by the runtime classifier on a single
        # GPS+accel row pair.
        return {
            "motion_disagreement": self._motion_disagreement(speed, dyn_mag),
            "motion_mismatch": self._motion_mismatch(speed, dyn_mag),
            "speed_per_dyn_mag": self._speed_per_dyn_mag(speed, dyn_mag),
            "speed_per_jerk_std": self._speed_per_jerk_std(speed, jerk_std),
        }

    def compute_batch(self, df):
        # DataFrame-vectorised version - used by DatasetMerger during
        # offline training prep. Same arithmetic as compute_one(), just
        # in pandas form so it runs over the whole frame at once.
        gps_moving = df["Speed"] > self.MOVING_SPEED_THRESHOLD
        accel_moving = df["Dynamic Magnitude"] > self.MOVING_DYN_MAG_THRESHOLD

        df["motion_disagreement"] = (gps_moving != accel_moving).astype(int)
        df["motion_mismatch"] = (
            (df["Speed"] / 100.0) - (df["Dynamic Magnitude"] * 2.0)
        ).abs()
        df["speed_per_dyn_mag"] = df["Speed"] / (df["Dynamic Magnitude"] + 0.001)
        df["speed_per_jerk_std"] = df["Speed"] / (df["Jerk Std"] + 0.01)

        return df
