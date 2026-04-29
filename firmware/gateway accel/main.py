from network import LoRa, WLAN
import socket
import struct
import time
from time import sleep


# ---- Packet format constants (kept in sync with the senders) ----
# These exist for documentation and for the size-based packet-type print
# below.  The forward path itself does NOT decode packets - it just
# relays raw bytes - so a format mismatch would not cause data loss,
# only stale console messages.
#
# Sources of truth:
#   firmware/gps-reciever/lib/LoRaTx.py   (Device A - sends accel only now)
#   firmware/gps-spoofer/lib/LoRaTx.py    (Device B - sends spoofed GPS)
#   ml/data/reciever.py                    (PC - unpacks both)
PACKET_GPS = 0
PACKET_ACCEL = 1

GPS_FORMAT = 'BBfffffifiIf'        # 44 B
ACCEL_FORMAT = 'BfffffffffffIf'    # 56 B (added utc_date+utc_time tail)
GPS_SIZE = struct.calcsize(GPS_FORMAT)
ACCEL_SIZE = struct.calcsize(ACCEL_FORMAT)


# Connect to the GPS Pygate as a WiFi STA.  The GPS Pygate runs the AP
# at SSID 'PygateLora' and the PC connects to the same AP - giving us
# a 3-device LAN where this Pygate forwards UDP straight to the PC.
wlan = WLAN(mode=WLAN.STA)
wlan.connect('PygateLora', auth=(WLAN.WPA2, 'pygatepw123'))
while not wlan.isconnected():
    sleep(0.5)
print("Connected IP:", wlan.ifconfig())

# ---- LoRa receiver ----
# This Pygate listens on the accel frequency (868.3 MHz).  Only Device A
# transmits here - the spoofer never sends accel - so packets received
# here are uncorrupted-by-collision and should arrive at ~1 Hz once the
# legit Pytrack is running with the densified main loop (6 sends/loop).
lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868)
lora.frequency(868300000)
lora.bandwidth(LoRa.BW_125KHZ)
lora.sf(10)

# Raw LoRa socket.  Pycom's LoRa socket is NON-BLOCKING by default and
# raises OSError(errno=5, EIO) when no packet is available.  The main
# loop swallows that specific error silently and prints anything else.
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

# UDP forwarding socket
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Client IP and Port (PC's IP on the Pygate AP DHCP range, accel UDP port)
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
        # errno 5 (EIO) is normal "no LoRa packet to read".  Sleep a
        # bit so we don't busy-loop the radio.
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
