

import math

class WindowStats:

    def __init__(self, window_size=10):
        
        self.window_size = window_size

        # Circular Buffer for dynamic acceleration magnitude
        self.buffer = [0.0] * window_size
        self.index = 0          # Current write position
        self.count = 0          # How many samples collected so far
        self.is_full = False    # Wether buffer has wrapped around at least once

    
    def add_sample(self, value):
        # Add a new sample to the circular buffer.

        self.buffer[self.index] = value
        self.index = (self.index + 1) % self.window_size
        self.count += 1

        if self.count >= self.window_size:
            self.is_full = True
        
    
    def compute(self):
        # Computes statistics over the current window. 


        # Not enough samples
        if not self.is_full:
            return None
        
        # Use the full buffer
        n = self.window_size

        # Mean
        total = 0.0
        for i in range(n):
            total += self.buffer[i]
        mean = total / n

        # Variance and standard deviation
        # Uses two-pass algorithm

        var_sum = 0.0
        for i in range(n):
            diff = self.buffer[i] - mean
            var_sum += diff * diff
        variance = var_sum / n
        std_dev = math.sqrt(variance)

        # Min and Max 
        min_val = self.buffer[0]
        max_val = self.buffer[0]

        for i in range(n):
            if self.buffer[i] < min_val:
                min_val = self.buffer[i]
            if self.buffer[i] > max_val:
                max_val = self.buffer[i]
        


        # Energy (mean of squared values)
        energy = 0.0
        for i in range(n):    
            energy += self.buffer[i] * self.buffer[i]
        energy = energy / n

        
        # Zero Crossings (How many times the signal crosses zero)
        crossings = 0
        for i in range(1, n):
            if (self.buffer[i - 1] > 0 and self.buffer[i] <= 0) or \
               (self.buffer[i - 1] <= 0  and self.buffer[i] > 0):
                
                crossings += 1

        return{
            'mean' : mean,
            'std_dev' : std_dev,
            'min_val' : min_val,
            'max_val' : max_val,
            'range_val' : max_val - min_val,
            'energy' : energy,
            'zero_crossings' : crossings,
            'window_full' : True

        }


