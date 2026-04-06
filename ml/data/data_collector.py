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
ACCEL_FORMAT = 'Bffffffffff'

GPS_SIZE = struct.calcsize(GPS_FORMAT)
ACCEL_SIZE = struct.calcsize(ACCEL_FORMAT)

# Output directory
DATA_DIR = "ml/data/raw"
os.makedirs(DATA_DIR, exist_ok=True)  # Create directory if it doesn't exist

timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
log_filename = os.path.join(DATA_DIR, f"gps_log_{timestamp_str}.csv")

CSV_HEADER = (
    "Time, UTC Time, Device ID, Label, Latitude, Longitude, Altitude, Speed, HDOP, Satelites, Course, Fix,"
    " Roll Degrees, Pitch Degrees, Dynamic Magnitude, Jerk, Acceleration X, Acceleration Y, Acceleration Z," 
    "Standard Deviation, Energy, Zero Crossings\n"
)


with open(log_filename, 'w', newline='') as f:
    f.write(CSV_HEADER)


# Creates UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"Listening for packets on {UDP_IP}:{UDP_PORT}")
print(f"Press Ctrl+C to stop\n")

total_packets = 0
gps_count = 0
accel_count = 0
unkown_count = 0
latest_accel = None

try:
    while True:
        # Recive packet
        data, addr = sock.recvfrom(256)

        if not data:
            continue


        
        total_packets += 1
        packet_type = data[0]

        if packet_type == PACKET_GPS and len(data) >= GPS_SIZE:
            gps_count += 1
            fields = struct.unpack(GPS_FORMAT, data[:GPS_SIZE])
            _, lat, lon, alt, speed, hdop, sats, course, fix = fields

            print(f"GPS #{gps_count:4d} | {lat:.6f}, {lon:.6f} | "
                  f"alt:{alt:.1f} spd:{speed:.2f} hdop_{hdop:.2f}"
                  f"sats:{sats} fix:{fix}")
            
            with open(log_filename, 'a', newline='') as f:
                row_time = datetime.now().isoformat()

                if latest_accel is not None:
                    a = latest_accel


                    csv.writer(f).writerow([
                        row_time, '', '', '',
                        lat, lon, alt, speed, hdop, sats, course, fix,
                        a['roll'], a['pitch'], a['dyn_mag'], a['jerk_mag'],
                        a['accel_x'], a['accel_y'], a['accel_z'],
                        a['accel_std'], a['accel_energy'], a['accel_zero_cross']
                    ])
                else:
                    # GPS arrived before any accel, write with empty accel collumns
                    csv.writer(f).writerow([
                        row_time, '', '', '',
                        lat, lon, alt, speed, hdop, sats, course, fix,
                        '', '', '', '', '', '', '', '', '', ''
                    ])

        

        elif packet_type == PACKET_ACCEL and len(data) >= ACCEL_SIZE:
            accel_count += 1
            fields = struct.unpack(ACCEL_FORMAT, data[:ACCEL_SIZE])
            _, roll, pitch, dyn_mag, jerk_mag, accel_x, accel_y, accel_z, accel_std, accel_energy, accel_zero_cross = fields

            latest_accel = {
                'roll': roll, 'pitch': pitch, 
                'dyn_mag': dyn_mag, 'jerk_mag': jerk_mag,
                'accel_x': accel_x, 'accel_y': accel_y, 'accel_z': accel_z,
                'accel_std': accel_std, 'accel_energy':accel_energy, 'accel_zero_cross': accel_zero_cross
            }


            print(f"Acel #{accel_count:4d} | roll:{roll:.6f} pitch:{pitch:.6f} | "
                    f"dyn:{dyn_mag:.6f} jerk:{jerk_mag:.6f}")
        
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
    
    