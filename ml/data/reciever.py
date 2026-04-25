import socket
import struct
from datetime import datetime
import csv
import os
import select
from time import time

UDP_IP = "0.0.0.0"


# Two sockets
sock_gps = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_gps.bind((UDP_IP,  5000))

sock_accel = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_accel.bind((UDP_IP, 5001))

print("Listening: GPS on :5000, Accel on :5001")

# Packet type identifiers
PACKET_GPS = 0
PACKET_ACCEL = 1

# GPS_FORMAT tail: I = utc_date (DDMMYY as uint32), f = utc_time (HHMMSS.SSS as float)
# Must match firmware/gps-reciever/lib/LoRaTx.py and firmware/gps-spoofer/lib/LoRaTx.py.
GPS_FORMAT = 'BBfffffifiIf'

# ACCEL_FORMAT tail: I = utc_date (DDMMYY as uint32), f = utc_time
# (HHMMSS.SSS as float) at the moment Device A transmitted this packet.
# Pairs accel rows with GPS rows on a shared UTC timeline for offline merging.
# Must match firmware/gps-reciever/lib/LoRaTx.py.
ACCEL_FORMAT = 'BfffffffffffIf'

GPS_SIZE = struct.calcsize(GPS_FORMAT)
ACCEL_SIZE = struct.calcsize(ACCEL_FORMAT)

print(f"Expected GPS packet size: {GPS_SIZE} bytes")
print(f"Expected ACCEL packet size: {ACCEL_SIZE} bytes")

# Output directory
DATA_DIR = "ml/data/raw"
os.makedirs(DATA_DIR, exist_ok=True)

timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
log_filename = os.path.join(DATA_DIR, f"gps_log_{timestamp_str}.csv")

# Accel UTC column: A's UTC at the moment the paired accel was sampled.
# This is the anchor used for offline timeline merging with A's SD log.
CSV_HEADER = (
    "Time, UTC Time, Label, Latitude, Longitude, Altitude, Speed, HDOP, Satelites, Course, Fix,"
    " Accel UTC,"
    " Roll Degrees, Pitch Degrees, Dynamic Magnitude, Jerk, Jerk Std, Acceleration X, Acceleration Y, Acceleration Z,"
    " Standard Deviation, Energy, Zero Crossings\n"
)

with open(log_filename, 'w', newline='') as f:
    f.write(CSV_HEADER)

print(f"Logging to: {log_filename}")
print(f"Press Ctrl+C to stop\n")

total_packets = 0
gps_count = 0
accel_count = 0
unknown_count = 0
latest_accel = None
latest_accel_time = 0


def format_utc(utc_date_int, utc_time_float):
    """Render packet UTC fields as 'DDMMYY_HHMMSS.SSS' or '' if absent."""
    if utc_date_int > 0 and utc_time_float > 0:
        return "{:06d}_{:013.6f}".format(int(utc_date_int), float(utc_time_float))
    return ''


try:
    while True:
        readable, _, _ = select.select([sock_gps, sock_accel], [], [], 1.0)

        for sock in readable:
            data, addr = sock.recvfrom(256)

            if not data:
                continue

            total_packets += 1
            packet_type = data[0]

            if packet_type == PACKET_GPS and len(data) >= GPS_SIZE:
                gps_count += 1
                fields = struct.unpack(GPS_FORMAT, data[:GPS_SIZE])
                (_, label, lat, lon, alt, speed, hdop, sats, course, fix,
                 utc_date_int, utc_time_float) = fields

                # Sanity check for corrupt GPS packets
                if abs(lat) > 90 or abs(lon) > 180 or sats < 0 or sats > 32:
                    print(f"GPS #{gps_count:4d} | Corrupt packet, skipping")
                    continue

                utc_gps = format_utc(utc_date_int, utc_time_float)

                print(f"GPS #{gps_count:4d} | {lat:.6f}, {lon:.6f} | "
                      f"alt:{alt:.1f} spd:{speed:.2f} hdop:{hdop:.2f} "
                      f"sats:{sats} fix:{fix} label:{label} utc:{utc_gps}")

                with open(log_filename, 'a', newline='') as f:
                    row_time = datetime.now().isoformat()
                    accel_age = time() - latest_accel_time

                    if latest_accel is not None and accel_age < 15.0:
                        a = latest_accel
                        csv.writer(f).writerow([
                            row_time, utc_gps, label,
                            lat, lon, alt, speed, hdop, sats, course, fix,
                            a.get('utc_a', ''),
                            a['roll'], a['pitch'], a['dyn_mag'], a['jerk_mag'], a['jerk_std'],
                            a['accel_x'], a['accel_y'], a['accel_z'],
                            a['accel_std'], a['accel_energy'], a['accel_zero_cross']
                        ])
                    else:
                        # GPS arrived before any accel (or accel went stale),
                        # write with empty accel columns including Accel UTC.
                        csv.writer(f).writerow([
                            row_time, utc_gps, label,
                            lat, lon, alt, speed, hdop, sats, course, fix,
                            '', '', '', '', '', '', '', '', '', '', '', ''
                        ])

            elif packet_type == PACKET_ACCEL:
                if len(data) < ACCEL_SIZE:
                    print(f"Accel packet too small: got {len(data)} bytes, expected {ACCEL_SIZE}")
                    unknown_count += 1
                    continue

                accel_count += 1
                fields = struct.unpack(ACCEL_FORMAT, data[:ACCEL_SIZE])
                (_, roll, pitch, dyn_mag, jerk_mag, jerk_std,
                 accel_x, accel_y, accel_z,
                 accel_std, accel_energy, accel_zero_cross,
                 utc_date_int, utc_time_float) = fields

                utc_a = format_utc(utc_date_int, utc_time_float)

                latest_accel = {
                    'roll': roll, 'pitch': pitch,
                    'dyn_mag': dyn_mag, 'jerk_mag': jerk_mag, 'jerk_std': jerk_std,
                    'accel_x': accel_x, 'accel_y': accel_y, 'accel_z': accel_z,
                    'accel_std': accel_std, 'accel_energy': accel_energy,
                    'accel_zero_cross': accel_zero_cross,
                    'utc_a': utc_a,
                }
                latest_accel_time = time()

                print(f"Accel #{accel_count:4d} | utc_a:{utc_a} | "
                      f"roll:{roll:.4f} pitch:{pitch:.4f} | "
                      f"dyn:{dyn_mag:.4f} jerk:{jerk_mag:.4f} jerk_std:{jerk_std:.4f}")

            else:
                unknown_count += 1
                print(f"UNKNOWN #{unknown_count} | type:{packet_type} len:{len(data)}")

            if total_packets % 20 == 0:
                print(f"--- Totals: {gps_count} GPS, {accel_count} ACCEL, "
                      f"{unknown_count} unknown ---")

except KeyboardInterrupt:
    print(f"\nStopped")
    print(f"Total: {total_packets} packets, {gps_count} GPS, "
          f"{accel_count} ACCEL, {unknown_count} unknown")
    print(f"Saved to: {log_filename}")
finally:
    sock_gps.close()
    sock_accel.close()
