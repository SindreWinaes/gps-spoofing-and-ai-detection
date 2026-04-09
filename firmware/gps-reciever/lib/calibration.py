
'''
Accelerometer calibration 
Removes offset writings when stationary and level. 

'''

import time

# Congiuration
CALIBRATION_SAMPLES = 50
SAMPLE_DELAY_MS = 20
GRAVITY_REFERENCE = 1.0


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

       print("Calibrating accelerometer, keep the device still and level")

       for i in range (num_samples):
           #read raw acceleration

           ax, ay, az = accel_sensor.acceleration()
           
           sum_x += ax
           sum_y += ay
           sum_z += az

           time.sleep_ms(SAMPLE_DELAY_MS)

        # Avereges the readings
       self.bias_x = sum_x / num_samples
       self.bias_y = sum_y / num_samples
       self.bias_z = (sum_z / num_samples) - GRAVITY_REFERENCE

       self.is_calibrated = True

       print("Calibration complete")
       print("  Bias X: {:.6f}".format(self.bias_x))
       print("  Bias Y: {:.6f}".format(self.bias_y))
       print("  Bias Z: {:.6f}".format(self.bias_z))

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
