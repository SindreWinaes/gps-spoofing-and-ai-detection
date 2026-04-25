
'''
Jerk is the rate of the change of acceleration (derivative of acceleration)
It captures how sharply acceleration changes.
'''


import math
import time


# Sanity bounds.
# MIN_DT_MS: at 100 Hz ODR the expected dt is ~10 ms. Anything below this is
#   suspicious (double-read of same sample, or ticks_ms rollover artifact).
# MAX_DT_MS: if dt > 1 sec, the previous state is stale (e.g. carried over
#   from a previous burst or the main loop paused). Reset instead of dividing
#   by a huge-but-nonzero dt and producing garbage.
# MAX_JERK: 1000 g/s would mean going from 0 to 100 g in 0.1 sec - well beyond
#   any realistic vehicle motion. Clamp as a safety net against transient
#   spikes during EMA warmup or sensor glitches.
MIN_DT_MS = 2
MAX_DT_MS = 1000
MAX_JERK = 1000.0


class VectorJerk:

    def __init__(self):
        # Previous acceleration values (for computing difference)
        self.prev_x = None
        self.prev_y = None
        self.prev_z = None
        self.prev_time_ms = None

    def reset(self):
        # Clear previous state so the next update() re-seeds.
        # Call this at the start of each accel burst.
        self.prev_x = None
        self.prev_y = None
        self.prev_z = None
        self.prev_time_ms = None

    def update(self, dyn_x, dyn_y, dyn_z, current_time_ms):
        # Compute jerk from the current and previous acceleration values.
        if current_time_ms is None:
            current_time_ms = time.ticks_ms()

        if self.prev_x is None:
            self.prev_x = dyn_x
            self.prev_y = dyn_y
            self.prev_z = dyn_z
            self.prev_time_ms = current_time_ms
            return None

        # Compute delta time
        dt_ms = time.ticks_diff(current_time_ms, self.prev_time_ms)

        # Stale previous state (paused main loop, cross-burst carryover, or
        # ticks_ms rollover edge case). Re-seed and skip this sample.
        if dt_ms <= 0 or dt_ms > MAX_DT_MS:
            self.prev_x = dyn_x
            self.prev_y = dyn_y
            self.prev_z = dyn_z
            self.prev_time_ms = current_time_ms
            return None

        # Floor dt to avoid exploding the quotient on abnormally fast reads.
        if dt_ms < MIN_DT_MS:
            dt_ms = MIN_DT_MS

        dt_s = dt_ms / 1000.0

        # Compute jerk vector
        jerk_x = (dyn_x - self.prev_x) / dt_s
        jerk_y = (dyn_y - self.prev_y) / dt_s
        jerk_z = (dyn_z - self.prev_z) / dt_s

        # Magnitude of jerk vector
        jerk_mag = math.sqrt(jerk_x * jerk_x + jerk_y * jerk_y + jerk_z * jerk_z)

        # Clamp pathological spikes - protects downstream windowed stats
        if jerk_mag > MAX_JERK:
            jerk_mag = MAX_JERK

        # Store current values for next iteration
        self.prev_x = dyn_x
        self.prev_y = dyn_y
        self.prev_z = dyn_z
        self.prev_time_ms = current_time_ms

        return {
            'jerk': (jerk_x, jerk_y, jerk_z),
            'jerk_magnitude': jerk_mag
        }
