
'''
Raw accelerometer readings are in the device frame,
they change depending on how the Pytrack is oriented.

This module changes that so Z always points up, and X and Y is horisontal.
This makes the pytracks orientation irrelevant for acclerometer readings. 
'''


import math

class WorldFrameTransform:


    def __init__(self):
        pass

    def compute_roll_pitch(self, cal_x, cal_y, cal_z):


        roll = math.atan2(cal_y, cal_z)

        pitch = math.atan2(-cal_x, math.sqrt(cal_y * cal_y + cal_z * cal_z))

        return(roll, pitch)
    
    def to_world_frame(self, ax, ay, az, roll_rad, pitch_rad):

        # Precompute trig values

        sr = math.sin(roll_rad)
        cr = math.cos(roll_rad)
        sp = math.sin(pitch_rad)
        cp = math.cos(pitch_rad)

        # Apply rotation matrix
        world_x = cp * ax + sp * sr * ay + sp * cr * az
        world_y = cr * ay - sr * az
        world_z = -sp * ax + cp * sr * ay + cp * cr * az

        return(world_x, world_y, world_z)
    

    def process(self, cal_x, cal_y, cal_z, grav_x=None, grav_y=None, grav_z=None):

        if grav_x is not None:
            roll, pitch = self.compute_roll_pitch(grav_x, grav_y, grav_z)
        else:
            roll, pitch = self.compute_roll_pitch(cal_x, cal_y, cal_z)


        wx, wy, wz = self.to_world_frame(cal_x, cal_y, cal_z, roll, pitch)

        return{
            'roll_deg': math.degrees(roll),
            'pitch_deg': math.degrees(pitch),
            'world_accel': (wx, wy, wz),
        }