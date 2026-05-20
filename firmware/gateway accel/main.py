from network import LoRa, WLAN
import socket
import struct
import time
from time import sleep


PACKET_GPS = 0
PACKET_ACCEL = 1

GPS_FORMAT = 'BBfffffifiIf'        # 44 B
ACCEL_FORMAT = 'BfffffffffffIf'    # 56 B
GPS_SIZE = struct.calcsize(GPS_FORMAT)
ACCEL_SIZE = struct.calcsize(ACCEL_FORMAT)


wlan = WLAN(mode=WLAN.STA)
wlan.connect('PygateLora', auth=(WLAN.WPA2, 'pygatepw123'))
while not wlan.isconnected():
    sleep(0.5)
print("Connected IP:", wlan.ifconfig())

# accel frequency 868.3 MHz
lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868)
lora.frequency(868300000)
lora.bandwidth(LoRa.BW_125KHZ)
lora.sf(10)

s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

client_IP = '192.168.4.10'
client_Port = 5001

print("Gateway Accelerometer")
print("LoRa receiver configured:")
print("  Frequency: {} Hz".format(lora.frequency()))
print("  SF: {}".format(lora.sf()))
print("  Expected ACCEL size: {} bytes".format(ACCEL_SIZE))
print("  Expected GPS size:   {} bytes (not expected on this freq)".format(GPS_SIZE))
print(" Forwarding to {}:{}".format(client_IP, client_Port))
print("Waiting for packets...")

forwarded = 0

while True:
    try:
        data = s.recv(256)
    except OSError as e:
        # errno 5 (EIO) = no LoRa packet available
        if getattr(e, 'errno', None) == 5:
            time.sleep_ms(20)
            continue
        print("LoRa recv error:", e)
        time.sleep_ms(200)
        continue
    except Exception as e:
        print("LoRa recv exception:", e)
        time.sleep_ms(200)
        continue

    if not data:
        time.sleep_ms(20)
        continue

    n = len(data)
    try:
        stats = lora.stats()
        rssi = stats.rssi
        snr = stats.snr
    except Exception:
        rssi = '?'
        snr = '?'

    if n == ACCEL_SIZE:
        kind = "ACCEL"
    elif n == GPS_SIZE:
        kind = "GPS"
    else:
        kind = "UNKNOWN"

    try:
        udp_socket.sendto(data, (client_IP, client_Port))
        forwarded += 1
        print("[{}] {} {} B  rssi={} snr={}".format(
            forwarded, kind, n, rssi, snr))
    except Exception as e:
        print("UDP send error:", e)
