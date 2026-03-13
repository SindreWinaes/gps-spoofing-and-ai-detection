from network import LoRa, WLAN
import socket
import ubinascii
from time import sleep

# Initialize WiFi AP
wlan = WLAN(mode=WLAN.AP, ssid='PygateLora', auth=(WLAN.WPA2, 'pygatepw123'))
print("WiFi AP started: SSID=PygateLora, Password=pygatepw123")
print("Pygate IP:", wlan.ifconfig())

# Initialize LoRa receiver
lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868)
lora.frequency(868100000)
lora.bandwidth(LoRa.BW_125KHZ)
lora.sf(10)

# Create raw LoRa socket
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

print("LoRa receiver configured:")
print("  Frequency: {} Hz".format(lora.frequency()))
print("  Bandwidth: {}".format(lora.bandwidth()))
print("  SF: {}".format(lora.sf()))
print("Waiting for packets...")

packet_count = 0

while True:
    # Try blocking receive with timeout
    s.settimeout(1.0)  # 1 second timeout
    try:
        data = s.recv(256)
        if data:
            packet_count += 1
            print("Packet {} received! Length: {} bytes".format(packet_count, len(data)))
            print("Raw hex:", ubinascii.hexlify(data))
    except:
        pass  # Timeout, keep waiting