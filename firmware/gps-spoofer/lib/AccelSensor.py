import math 
import time

class AccelSensor:
    
    def __init__(self, accel):
        
        self.accel = accel
        
        self.accel_x = 0
        
        self.accel_y = 0
        
        self.accel_z = 0
        
        self.roll = 0
        
        self.pitch = 0
        
        self.magnitude = 0
        
        self.previous_mag = None
        
        self.previous_time = None
        
        self.jerk = 0
        
        
        
    
    def read(self):

        current_time = time.time()
        
        self.accel_x, self.accel_y, self.accel_z = self.accel.acceleration()
        
        self.roll = self.accel.roll()
        
        self.pitch = self.accel.pitch()

        self.magnitude = math.sqrt(self.accel_x**2 + self.accel_y**2 + self.accel_z**2)
        
        if self.previous_mag is not None and self.previous_time is not None:
            delta_time = current_time - self.previous_time
            if delta_time > 0:
                self.jerk = (self.magnitude - self.previous_mag) / delta_time
        else:
            self.jerk = 0
            
        self.previous_mag = self.magnitude 
        self.previous_time = current_time
        
        return{
            'accel_x' : self.accel_x,
            'accel_y' : self.accel_y,
            'accel_z' : self.accel_z,
            'roll' : self.roll,
            'pitch' : self.pitch,
            'magnitude' : self.magnitude,
            'previous_mag' : self.previous_mag,
            'jerk' : self.jerk
        }