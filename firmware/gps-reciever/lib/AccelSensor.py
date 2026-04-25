import math 
import time
from gravity_seperation import GravitySeperator
from world_frame import WorldFrameTransform
from vector_jerk import VectorJerk
from windowed_stats import WindowStats


class AccelSensor:

    def __init__(self, accel, calibration=None):

        self.accel = accel
        self.calibration = calibration

        # Initialize processing pipeline
        # alpha for gravity EMA tuned for 100 Hz sampling:
        #   tau ~= T/alpha ~= 0.01/0.02 = 0.5 sec (cutoff ~0.32 Hz)
        self.grav_sep = GravitySeperator(alpha=0.02)
        self.world_tf = WorldFrameTransform()
        self.jerk_calc = VectorJerk()

        # Windowed stats: 50 samples @ 100 Hz = 0.5 sec window
        self.stats_dyn = WindowStats(window_size=50)
        self.stats_jerk = WindowStats(window_size=50)
        self.stats_signed = WindowStats(window_size=50)


    # Reads one accelerometer sample and runs it through the full processing pipeline.
    # Returns (features_dict, raw_row_dict).
    def _process_one(self):

        now = time.ticks_ms()

        # Read raw values
        raw_x, raw_y, raw_z = self.accel.acceleration()

        # Apply calibration (bias correction)
        if self.calibration is not None:
            cal_x, cal_y, cal_z = self.calibration.apply(raw_x, raw_y, raw_z)
        else:
            cal_x, cal_y, cal_z = raw_x, raw_y, raw_z

        # Gravity separation
        grav_result = self.grav_sep.update(cal_x, cal_y, cal_z)
        dyn_x, dyn_y, dyn_z = grav_result['dynamic']
        dyn_mag = grav_result['dynamic_magnitude']
        grav_x, grav_y, grav_z = grav_result['gravity']

        # World frame transform
        world_result = self.world_tf.process(dyn_x, dyn_y, dyn_z, grav_x, grav_y, grav_z)
        world_x, world_y, world_z = world_result['world_accel']
        roll_deg = world_result['roll_deg']
        pitch_deg = world_result['pitch_deg']

        # Vector jerk on dynamic acceleration
        jerk_result = self.jerk_calc.update(dyn_x, dyn_y, dyn_z, now)
        jerk_mag = 0.0
        if jerk_result is not None:
            jerk_mag = jerk_result['jerk_magnitude']

        # Windowed statistics
        self.stats_dyn.add_sample(dyn_mag)
        self.stats_signed.add_sample(dyn_z)
        self.stats_jerk.add_sample(jerk_mag)

        dyn_stats = self.stats_dyn.compute()
        jerk_stats = self.stats_jerk.compute()
        signed_stats = self.stats_signed.compute()

        features = {
            'roll': roll_deg,
            'pitch': pitch_deg,
            'dyn_mag': dyn_mag,
            'jerk_mag': jerk_mag,
            'jerk_std': jerk_stats['std_dev'] if jerk_stats else None,
            'accel_x': world_x,
            'accel_y': world_y,
            'accel_z': world_z,
            'accel_std': dyn_stats['std_dev'] if dyn_stats else None,
            'accel_energy': dyn_stats['energy'] if dyn_stats else None,
            'accel_zero_cross': signed_stats['zero_crossings'] if signed_stats else None,
        }

        raw_row = {
            'ts_ms': now,
            'raw_x': raw_x, 'raw_y': raw_y, 'raw_z': raw_z,
            'cal_x': cal_x, 'cal_y': cal_y, 'cal_z': cal_z,
            'world_x': world_x, 'world_y': world_y, 'world_z': world_z,
            'dyn_mag': dyn_mag,
            'jerk_mag': jerk_mag,
            'roll_deg': roll_deg, 'pitch_deg': pitch_deg,
        }

        return features, raw_row


    # Reads one sample (backwards-compatible thin wrapper)
    def read(self):
        features, _ = self._process_one()
        return features


    # Burst-samples the accelerometer for `duration_ms` milliseconds, running the
    # pipeline on each sample. Returns the LAST feature dict (for LoRa packet).
    # If `raw_file` (already-open append-mode file) is given, each raw sample
    # is written as a CSV row for full high-rate preservation on SD.
    def read_burst(self, duration_ms=3000, raw_file=None, sample_period_ms=10):
        # Reset jerk state so cross-burst stale prev_time_ms can't produce garbage.
        try:
            self.jerk_calc.reset()
        except Exception:
            pass

        start = time.ticks_ms()
        last_features = None
        sample_idx = 0

        while time.ticks_diff(time.ticks_ms(), start) < duration_ms:
            features, raw_row = self._process_one()
            last_features = features

            if raw_file is not None:
                try:
                    raw_file.write(
                        "{},{},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f},{:.6f}\n".format(
                            raw_row['ts_ms'], sample_idx,
                            raw_row['raw_x'], raw_row['raw_y'], raw_row['raw_z'],
                            raw_row['cal_x'], raw_row['cal_y'], raw_row['cal_z'],
                            raw_row['world_x'], raw_row['world_y'], raw_row['world_z'],
                            raw_row['dyn_mag'], raw_row['roll_deg'], raw_row['pitch_deg']
                        )
                    )
                except Exception as e:
                    print("Raw accel SD write error:", e)

            sample_idx += 1
            time.sleep_ms(sample_period_ms)

        # Fallback: if duration was too short to get even one sample, do a single read
        if last_features is None:
            last_features, _ = self._process_one()

        return last_features
