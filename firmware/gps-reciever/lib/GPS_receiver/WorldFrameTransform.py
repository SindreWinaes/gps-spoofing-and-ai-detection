#
# WorldFrameTransform.py
# Raw accel readings live in the device frame and change with how the
# Pytrack is oriented. This rotates them so Z always points up and XY is
# horizontal - that way the rest of the pipeline doesn't care about
# device tilt.
#

import math


class WorldFrameTransform:

    def __init__(self):
        pass

    def compute_roll_pitch(self, cal_x, cal_y, cal_z):
        # Roll about X, pitch about Y, both in radians
        roll = math.atan2(cal_y, cal_z)
        pitch = math.atan2(-cal_x, math.sqrt(cal_y * cal_y + cal_z * cal_z))
        return (roll, pitch)

    def to_world_frame(self, ax, ay, az, roll_rad, pitch_rad):
        # Standard rotation matrix using precomputed trig values
        sr = math.sin(roll_rad)
        cr = math.cos(roll_rad)
        sp = math.sin(pitch_rad)
        cp = math.cos(pitch_rad)

        world_x = cp * ax + sp * sr * ay + sp * cr * az
        world_y = cr * ay - sr * az
        world_z = -sp * ax + cp * sr * ay + cp * cr * az

        return (world_x, world_y, world_z)

    def process(self, cal_x, cal_y, cal_z, grav_x=None, grav_y=None, grav_z=None):
        # If a gravity estimate is supplied, derive roll/pitch from it.
        # Otherwise fall back to the raw cal vector (assumes near-static).
        if grav_x is not None:
            roll, pitch = self.compute_roll_pitch(grav_x, grav_y, grav_z)
        else:
            roll, pitch = self.compute_roll_pitch(cal_x, cal_y, cal_z)

        wx, wy, wz = self.to_world_frame(cal_x, cal_y, cal_z, roll, pitch)

        return {
            'roll_deg': math.degrees(roll),
            'pitch_deg': math.degrees(pitch),
            'world_accel': (wx, wy, wz),
        }
