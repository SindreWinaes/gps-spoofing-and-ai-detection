#
# AccelPacket.py
# Decoded form of an accelerometer LoRa packet from Device A. The utc
# field is Device A's UTC at sample time - used as the anchor for
# offline timeline merging with A's SD log.
#
# Note: roll is float (the EA spec had it as int by mistake - that
# would round all tilt readings to whole degrees, which would destroy
# the orientation features).
#

from dataclasses import dataclass


@dataclass
class AccelPacket:
    roll: float = 0.0
    pitch: float = 0.0
    dyn_mag: float = 0.0
    jerk_mag: float = 0.0
    jerk_std: float = 0.0
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    accel_std: float = 0.0
    accel_energy: float = 0.0
    accel_zero_cross: float = 0.0
    # Device A's UTC at the moment this accel was sampled, as
    # 'DDMMYY_HHMMSS.SSS' or '' if A didn't have a fix yet.
    utc: str = ""
