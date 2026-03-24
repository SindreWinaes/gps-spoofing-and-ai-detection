from network import LoRa, WLAN
import socket
import struct
import ubinascii
from time import sleep
import time

PACKET_GPS = 0
PACKET_ACCEL = 1

GPS_FORMAT = 'Bfffffifi'

GPS_SIZE = struct.calcsize(GPS_FORMAT)

ACCEL_FORMAT = 'Bffffffff'
ACCEL_SIZE = struct.calcsize(ACCEL_FORMAT)

# Initialize WiFi AP
wlan = WLAN(mode=WLAN.AP, ssid='PygateLora', auth=(WLAN.WPA2, 'pygatepw123'))
print("WiFi AP started: SSID=PygateLora, Password=pygatepw123")
print("Pygate IP:", wlan.ifconfig())

# Initialize LoRa receiver
lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868)
lora.frequency(868100000)
lora.bandwidth(LoRa.BW_125KHZ)
lora.sf(10)

# Creates raw LoRa socket
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

# Creates UDP socket for forwarding
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Client IP and Port
client_IP = '192.168.4.2'
client_Port = 5000

print("LoRa receiver configured:")
print("  Frequency: {} Hz".format(lora.frequency()))
print("  Bandwidth: {}".format(lora.bandwidth()))
print("  SF: {}".format(lora.sf()))
print(" Forwarding to {}:{}".format(client_IP, client_Port))
print("Waiting for packets...")

packet_count = 0
gps_count = 0
accel_count = 0
unkown_count = 0



while True:
    # Try blocking receive with timeout
    
    s.settimeout(1.0)  # 1 second timeout
    try:
        data = s.recv(256)
        
        if data and len(data) > 0:
            packet_count += 1
            timestamp = time.time()

            # Read packet type from the first byte
            packet_type = data[0]

            if packet_type == PACKET_GPS and len(data) >= GPS_SIZE:
                gps_count += 1
                fields = struct.unpack(GPS_FORMAT, data[:GPS_SIZE])
                _, lat, lon, alt, speed, hdop, sats, course, fix = fields 

                print("GPS #{} | {:.6f}, {:.6f} | alt:{:.1f} | spd:{:.2f} | hdop:{:.2f} | sats{} | fix:{}".format(
                    gps_count, lat, lon, alt, speed, hdop, sats, fix)
                )

            elif packet_type == PACKET_ACCEL and len(data) >= ACCEL_SIZE:
                accel_count += 1
                fields = struct.unpack(ACCEL_FORMAT, data[:ACCEL_SIZE])
                _, x, y, z, roll, pitch, mag, prev_mag, jerk = fields
                
                print("ACCEL #{} | x:{:.3f}  y:{:.3f} z:{:.3f} | mag:{:.3f} | jerk:{:.4f}".format(
                    accel_count, x, y, z, mag, jerk
                ))

            else: 
                unkown_count += 1
                print("UNKNOWN packet #{} | len:{} | hex:{}".format(
                    unkown_count, len(data), ubinascii.hexlify(data)
                ))               

            # Forward to computer
            udp_socket.sendto(data, (client_IP, client_Port))

            if packet_count % 20 == 0:
                print("--- Totals: {} GPS, {} ACCEl, {} unknown ---".format(
                    gps_count, accel_count, unkown_count
                ))

    except:
        pass