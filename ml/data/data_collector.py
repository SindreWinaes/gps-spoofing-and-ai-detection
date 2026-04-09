import socket
import struct
from datetime import datetime
import csv
import os
import select

UDP_IP = "0.0.0.0"


# Two sockets
sock_gps = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_gps.bind((UDP_IP,  5000))

sock_accel = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_accel.bind((UDP_IP, 5001))

print ("Listening: GPS on :5000, Accel on :5001")

# Packet type identifiers
PACKET_GPS = 0
PACKET_ACCEL = 1

GPS_FORMAT = 'BBfffffifi'
ACCEL_FORMAT = 'Bfffffffffff'

GPS_SIZE = struct.calcsize(GPS_FORMAT)
ACCEL_SIZE = struct.calcsize(ACCEL_FORMAT)

print(f"Expected GPS packet size: {GPS_SIZE} bytes")
print(f"Expected ACCEL packet size: {ACCEL_SIZE} bytes")

# Output directory
DATA_DIR = "ml/data/raw"
os.makedirs(DATA_DIR, exist_ok=True)

timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
log_filename = os.path.join(DATA_DIR, f"gps_log_{timestamp_str}.csv")

CSV_HEADER = (
    "Time, UTC Time, Label, Latitude, Longitude, Altitude, Speed, HDOP, Satelites, Course, Fix,"
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
                _, label, lat, lon, alt, speed, hdop, sats, course, fix = fields

                # UPDATED: sanity check for corrupt GPS packets
                if abs(lat) > 90 or abs(lon) > 180 or sats < 0 or sats > 32:
                    print(f"GPS #{gps_count:4d} | Corrupt packet, skipping")
                    continue

                print(f"GPS #{gps_count:4d} | {lat:.6f}, {lon:.6f} | "
                    f"alt:{alt:.1f} spd:{speed:.2f} hdop:{hdop:.2f} "
                    f"sats:{sats} fix:{fix} label:{label}")

                with open(log_filename, 'a', newline='') as f:
                    row_time = datetime.now().isoformat()

                    if latest_accel is not None:
                        a = latest_accel
                        csv.writer(f).writerow([
                            row_time, '', label,
                            lat, lon, alt, speed, hdop, sats, course, fix,
                            a['roll'], a['pitch'], a['dyn_mag'], a['jerk_mag'], a['jerk_std'],
                            a['accel_x'], a['accel_y'], a['accel_z'],
                            a['accel_std'], a['accel_energy'], a['accel_zero_cross']
                        ])
                    else:
                        # GPS arrived before any accel, write with empty accel columns
                        csv.writer(f).writerow([
                            row_time, '', label,
                            lat, lon, alt, speed, hdop, sats, course, fix,
                            '', '', '', '', '', '', '', '', '', '', ''
                        ])

            elif packet_type == PACKET_ACCEL:
                # UPDATED: print actual size to help debug format mismatches
                if len(data) < ACCEL_SIZE:
                    print(f"Accel packet too small: got {len(data)} bytes, expected {ACCEL_SIZE}")
                    unknown_count += 1
                    continue

                accel_count += 1
                fields = struct.unpack(ACCEL_FORMAT, data[:ACCEL_SIZE])
                _, roll, pitch, dyn_mag, jerk_mag, jerk_std, accel_x, accel_y, accel_z, accel_std, accel_energy, accel_zero_cross = fields

                latest_accel = {
                    'roll': roll, 'pitch': pitch,
                    'dyn_mag': dyn_mag, 'jerk_mag': jerk_mag, 'jerk_std': jerk_std,
                    'accel_x': accel_x, 'accel_y': accel_y, 'accel_z': accel_z,
                    'accel_std': accel_std, 'accel_energy': accel_energy, 'accel_zero_cross': accel_zero_cross
                }

                print(f"Accel #{accel_count:4d} | roll:{roll:.4f} pitch:{pitch:.4f} | "
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
    sock_accel.close