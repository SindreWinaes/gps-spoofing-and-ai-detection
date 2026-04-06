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


        # Initilize processing pipeline
        self.grav_sep = GravitySeperator(alpha=0.15)
        self.world_tf = WorldFrameTransform()
        self.jerk_calc = VectorJerk()

        # Windowed stats for two channels
        self.stats_dyn = WindowStats(window_size=10)
        self.stats_jerk = WindowStats(window_size=10)


    # Reads accelerometer and run through processing pipeline
    def read(self):

        now = time.ticks_ms()

        # Read raw values
        raw_x, raw_y, raw_z = self.accel.acceleration()

        # Apply calibration(bias correction)
        if self.calibration is not None:
            cal_x, cal_y, cal_z = self.calibration.apply(raw_x, raw_y, raw_z)
        else:
            cal_x, cal_y, cal_z = raw_x, raw_y, raw_z

        
        # Gravity separation
        grav_result = self.grav_sep.update(cal_x, cal_y, cal_z)
        dyn_x, dyn_y, dyn_z = grav_result['dynamic']
        dyn_mag = grav_result['dynamic_magnitude']
        grav_x, grav_y, grav_z = grav_result['gravity']

        
        # World frame transform, use gravity estimate for orientation
        world_result = self.world_tf.process(cal_x, cal_y, cal_z, grav_x, grav_y, grav_z)
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
        self.stats_jerk.add_sample(jerk_mag)

        dyn_stats = self.stats_dyn.compute()    # None until window is full
        jerk_stats = self.stats_jerk.compute()  # None unitl window is full

        return{
            'roll': roll_deg,
            'pitch': pitch_deg,
            'dyn_mag': dyn_mag,
            'jerk_mag': jerk_mag,
            'accel_x': world_x,
            'accel_y': world_y, 
            'accel_z': world_z,
            'accel_std': dyn_stats['std_dev'] if dyn_stats else None,
            'accel_energy': dyn_stats['energy'] if dyn_stats else None,
            'accel_zero_cross': dyn_stats['zero_crossings'] if dyn_stats else None,
        }





    