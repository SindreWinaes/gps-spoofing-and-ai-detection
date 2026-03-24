import socket
import struct
from datetime import datetime
import csv
import os

UDP_IP = "0.0.0.0"
UDP_PORT = 5000

# Packet type identifiers
PACKET_GPS = 0
PACKET_ACCEL = 1

GPS_FORMAT = 'Bfffffifi'
ACCEL_FORMAT = 'Bffffffff'

GPS_SIZE = struct.calcsize(GPS_FORMAT)
ACCEL_SIZE = struct.calcsize(ACCEL_FORMAT)

# Output directory
DATA_DIR = "ml/data/raw"
os.makedirs(DATA_DIR, exist_ok=True)  # Create directory if it doesn't exist

timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
gps_filename = os.path.join(DATA_DIR, f"gps_{timestamp_str}.csv")
accel_filename=  os.path.join(DATA_DIR, f"accel_{timestamp_str}.csv")


gps_headers = [
    'timestamp', 'packet_num', 
    'lat', 'lon', 'alt', 'speed','hdop', 'sats', 'course', 'fix'
    ]

accel_headers = [
    'timestamp', 'packet_num', 'accel_x', 'accel_y', 'accel_z', 'roll', 'pitch', 'magnitude', 'previous_mag', 'jerk'
]

# Create csv file with header 
# 

with open(gps_filename, 'w', newline='') as f:
    csv.writer(f).writerow(gps_headers)


with open(accel_filename, 'w', newline='') as f:
    csv.writer(f).writerow(accel_headers)

print(f"GPS data - {gps_filename}")
print(f"Accel data - {accel_filename}")

# Creates UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))


print(f"Listening for packets on {UDP_IP}:{UDP_PORT}")
print(f"Press Ctrl+C to stop\n")

total_packets = 0
gps_count = 0
accel_count = 0
unkown_count = 0


try:
    while True:
        # Recive packet
        data, addr = sock.recvfrom(256)

        if not data:
            continue

        total_packets += 1
        timestamp = datetime.now().isoformat()
        packet_type = data[0]

        if packet_type == PACKET_GPS and len(data) >= GPS_SIZE:
            gps_count += 1
            fields = struct.unpack(GPS_FORMAT, data[:GPS_SIZE])
            _, lat, lon, alt, speed, hdop, sats, course, fix = fields

            print(f"GPS #{gps_count:4d} | {lat:.6f}, {lon:.6f} | "
                  f"alt:{alt:.1f} spd:{speed:.2f} hdop_{hdop:.2f}"
                  f"sats:{sats} fix:{fix}")
            
            with open(gps_filename, 'a', newline='') as f:
                csv.writer(f).writerow([
                    timestamp, gps_count, lat, lon, alt, speed, hdop, sats, course, fix
                ])

        elif packet_type == PACKET_ACCEL and len(data) >= ACCEL_SIZE:
            accel_count += 1
            fields = struct.unpack(ACCEL_FORMAT, data[:ACCEL_SIZE])
            _, x, y, z, roll, pitch, mag, prev_mag, jerk = fields

            print(f"Acel #{accel_count:4d} | x:{x:.3f} y:{y:.3f} z:{z:.3f} | "
                  f"mag:{mag:.3f} jerk:{jerk:.4f}")
            
            with open(accel_filename, 'a', newline='') as f:
                csv.writer(f).writerow([
                    timestamp, accel_count, x, y, z, roll, pitch, mag, prev_mag, jerk
            ])
        
        else:
            unkown_count += 1
            print(f"UNKOWN #{unkown_count} | len:{len(data)}")

        if total_packets % 20 == 0:
            print(f"--- Totals: {gps_count} GPS, {accel_count} ACCEl, "
                  f"{unkown_count} unkown ---")

except KeyboardInterrupt:
    print(f"\nStopped")
    print(f"Total: {total_packets} packets, {gps_count} GPS, "
          f"{accel_count} ACCEL, {unkown_count} unkown")
finally:
    sock.close()
    
    