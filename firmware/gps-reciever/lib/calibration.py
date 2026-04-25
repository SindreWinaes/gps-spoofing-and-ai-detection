
'''
Accelerometer calibration
Estimates and removes sensor bias when stationary.

Orientation-invariant: the device only needs to sit STILL during calibration,
it does NOT need to be perfectly level. We measure the mean acceleration
vector, assume its magnitude equals 1 g (static => only gravity is acting),
and solve for the bias. This avoids the old failure mode where a small tilt
during calibration got baked into the X/Y bias and later poisoned the
gravity-separation EMA.

'''

import time
import math

# Configuration
# At 100 Hz sensor ODR, take 200 samples with 10 ms spacing
# -> ~2 sec of averaging, much better bias estimate than the old
#    50 samples @ 20 ms (1 sec), which was fine for 50 Hz but short for 100 Hz
CALIBRATION_SAMPLES = 200
SAMPLE_DELAY_MS = 10
GRAVITY_REFERENCE = 1.0
# If the measured mean vector magnitude deviates from 1 g by more than this
# tolerance, something is wrong (device was moving, accel scale is misconfigured,
# or the sensor is faulty). We still calibrate but warn so the operator can
# redo it.
GRAVITY_TOLERANCE = 0.15  # ~ +/-0.15 g around 1.0 g


# Stores and applies accelerometer bias correction
class AccelCalibration:

    def __init__(self):
        self.bias_x = 0.0
        self.bias_y = 0.0
        self.bias_z = 0.0
        self.is_calibrated = False


    def calibration(self, accel_sensor, num_samples=CALIBRATION_SAMPLES):

       sum_x = 0.0
       sum_y = 0.0
       sum_z = 0.0

       print("Calibrating accelerometer - keep the device STILL (level not required)")

       for i in range(num_samples):
           # read raw acceleration
           ax, ay, az = accel_sensor.acceleration()

           sum_x += ax
           sum_y += ay
           sum_z += az

           time.sleep_ms(SAMPLE_DELAY_MS)

       # Mean acceleration vector while stationary. For an ideal sensor at rest
       # this should equal the gravity vector expressed in the sensor frame;
       # i.e. magnitude = 1 g, pointing in whatever direction "up" happens to be.
       mean_x = sum_x / num_samples
       mean_y = sum_y / num_samples
       mean_z = sum_z / num_samples

       mean_mag = math.sqrt(mean_x * mean_x + mean_y * mean_y + mean_z * mean_z)

       if mean_mag < 1e-6:
           # Sensor reported essentially zero on all axes - almost certainly
           # a read error. Fall back to zero bias so the app can keep running.
           print("WARNING: mean |a| near zero, calibration skipped")
           self.bias_x = 0.0
           self.bias_y = 0.0
           self.bias_z = 0.0
           self.is_calibrated = False
           return (self.bias_x, self.bias_y, self.bias_z)

       # Unit vector pointing in the direction of gravity (in sensor frame).
       # Multiplying by GRAVITY_REFERENCE gives the "ideal" gravity reading.
       # Bias is then whatever the sensor reports ABOVE that ideal vector.
       unit_x = mean_x / mean_mag
       unit_y = mean_y / mean_mag
       unit_z = mean_z / mean_mag

       self.bias_x = mean_x - unit_x * GRAVITY_REFERENCE
       self.bias_y = mean_y - unit_y * GRAVITY_REFERENCE
       self.bias_z = mean_z - unit_z * GRAVITY_REFERENCE

       self.is_calibrated = True

       print("Calibration complete")
       print("  Mean |a|: {:.4f} g (expected ~1.000)".format(mean_mag))
       print("  Bias X: {:.6f}".format(self.bias_x))
       print("  Bias Y: {:.6f}".format(self.bias_y))
       print("  Bias Z: {:.6f}".format(self.bias_z))

       if abs(mean_mag - GRAVITY_REFERENCE) > GRAVITY_TOLERANCE:
           print("WARNING: |a| deviates from 1 g by more than {:.2f} -".format(GRAVITY_TOLERANCE))
           print("         device was likely moving or sensor scale is wrong.")
           print("         Redo calibration with the device sitting still.")

       return (self.bias_x, self.bias_y, self.bias_z)
    
    def apply(self, raw_x, raw_y, raw_z):
        
     # Subtract the bias from raw accelerometer readings

        if not self.is_calibrated:
            return (raw_x, raw_y, raw_z)
        
        return(
            raw_x - self.bias_x,
            raw_y - self.bias_y, 
            raw_z - self.bias_z
        )
