from network import LoRa, WLAN
import socket
import struct
from time import sleep


PACKET_GPS = 0
PACKET_ACCEL = 1

GPS_FORMAT = 'BBfffffifi'

GPS_SIZE = struct.calcsize(GPS_FORMAT)

ACCEL_FORMAT = 'Bffffffffff'
ACCEL_SIZE = struct.calcsize(ACCEL_FORMAT)

# Connect to GPS Gateway as a client
wlan = WLAN(mode=WLAN.STA)
wlan.connect('PygateLora', auth=(WLAN.WPA2, 'pygatepw123'))
while not wlan.isconnected():
    sleep(0.5)
print("Connected IP:", wlan.ifconfig())

# Initialize LoRa receiver
lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868)
lora.frequency(868300000)
lora.bandwidth(LoRa.BW_125KHZ)
lora.sf(10)

# Creates raw LoRa socket
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

# Creates UDP socket for forwarding
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Client IP and Port
client_IP = '192.168.4.10'
client_Port = 5001

print("Gateway Accelerometer")
print("LoRa receiver configured:")
print("  Frequency: {} Hz".format(lora.frequency()))
print("  Bandwidth: {}".format(lora.bandwidth()))
print("  SF: {}".format(lora.sf()))
print(" Forwarding to {}:{}".format(client_IP, client_Port))
print("Waiting for packets...")

while True:
    try: 
        data = s.recv(256)
        if data:
            udp_socket.sendto(data, (client_IP, client_Port))
            print("Foorwarded {} bytes".format(len(data)))
    
    except:
        pass