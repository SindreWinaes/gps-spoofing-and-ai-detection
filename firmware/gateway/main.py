from network import LoRa, WLAN
import socket
import struct
from time import sleep


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

while True:
    try: 
        data = s.recv
        if data:
            udp_socket.sendto(data, (client_IP, client_Port))
            print("Foorwarded {} bytes".format(len(data)))
    
    except:
        pass