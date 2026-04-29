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
ACCEL_FORMAT = 'BfffffffffffIf'    # 56 B
GPS_SIZE = struct.calcsize(GPS_FORMAT)
ACCEL_SIZE = struct.calcsize(ACCEL_FORMAT)


# ---- WiFi AP ----
# This Pygate hosts the local AP that the accel Pygate and the PC both
# join.  We sleep briefly after starting the AP so the IP query below
# returns the actual address instead of all-zeros.
wlan = WLAN(mode=WLAN.AP, ssid='PygateLora', auth=(WLAN.WPA2, 'pygatepw123'))
print("WiFi AP started: SSID=PygateLora, Password=pygatepw123")
sleep(2)
print("Pygate IP:", wlan.ifconfig())

# ---- LoRa receiver ----
# This Pygate listens on the GPS frequency (868.1 MHz).  After the
# firmware change that disabled Device A's GPS LoRa send, this gateway
# receives ONLY spoofed GPS packets from Device B - that is the entire
# point of the demo (a replay attacker as sole occupant of the GPS
# channel).  If you stop seeing forwarded packets here, the spoofer is
# off, out of range, or both - it is NOT a gateway problem.
lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868)
lora.frequency(868100000)
lora.bandwidth(LoRa.BW_125KHZ)
lora.sf(10)

# Raw LoRa socket.  Pycom's LoRa socket is NON-BLOCKING by default and
# raises OSError(errno=5, EIO) when no packet is available.  The main
# loop swallows that specific error silently and prints anything else.
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

# UDP forwarding socket
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Client IP and Port (PC's IP on the Pygate AP DHCP range)
client_IP = '192.168.4.10'
client_Port = 5000

print("Gateway GPS")
print("LoRa receiver configured:")
print("  Frequency: {} Hz".format(lora.frequency()))
print("  SF: {}".format(lora.sf()))
print("  Expected GPS size:   {} bytes".format(GPS_SIZE))
print("  Expected ACCEL size: {} bytes (not expected on this freq)".format(ACCEL_SIZE))
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
        # Other OSErrors (socket dead, hardware fault, etc.) deserve
        # a print so they don't get silenced like before.
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
    # Try to read RSSI/SNR for the most recent packet.  Useful as a
    # live link-health indicator during a bag-walk.
    try:
        stats = lora.stats()
        rssi = stats.rssi
        snr = stats.snr
    except Exception:
        rssi = '?'
        snr = '?'

    # Distinguish packet types by length so the gateway log matches
    # the PC receiver's view.  Anything else is logged as 'unknown'
    # so a sender format drift surfaces immediately.
    if n == GPS_SIZE:
        kind = "GPS"
    elif n == ACCEL_SIZE:
        kind = "ACCEL"
    else:
        kind = "UNKNOWN"

    try:
        udp_socket.sendto(data, (client_IP, client_Port))
        forwarded += 1
        print("[{}] {} {} B  rssi={} snr={}".format(
            forwarded, kind, n, rssi, snr))
    except Exception as e:
        print("UDP send error:", e)
