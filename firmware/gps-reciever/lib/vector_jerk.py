
'''
Jerk is the rate of the change of acceleration (derivative of acceleration)
It captures how sharply acceleration changes. 
'''


import math
import time


class VectorJerk:

    def __init__(self):
        
        # Previous acceleration values (for computing difference)
        self.prev_x = None
        self.prev_y = None
        self.prev_z = None
        self.prev_time_ms = None

    
    def update(self, dyn_x, dyn_y, dyn_z, current_time_ms):
        # Compute jerk from the current and previous acceleration values (for computing differences)

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

        if dt_ms <= 0:
            dt_ms = 1

        dt_s = dt_ms / 1000.0

        # Compute jerk vectore
        jerk_x = (dyn_x - self.prev_x) / dt_s
        jerk_y = (dyn_y - self.prev_y) / dt_s
        jerk_z = (dyn_z - self.prev_z) / dt_s

        # Magnitude jerk vector
        jerk_mag = math.sqrt(jerk_x * jerk_x + jerk_y * jerk_y + jerk_z * jerk_z)


        # Store current values for next iteration 
        self.prev_x = dyn_x
        self.prev_y = dyn_y
        self.prev_z = dyn_z
        self.prev_time_ms = current_time_ms

        return{
            'jerk': (jerk_x, jerk_y, jerk_z), 
            'jerk_magnitude': jerk_mag
        }

        