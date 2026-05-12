#
# GpsPacket.py
# Decoded form of a GPS LoRa packet that arrived at the gateway and was
# forwarded to the PC over UDP. Plain data holder produced by
# PacketDecoder. The label byte is 0 for legit (Device A) or 1 for
# spoofed (Device B), exactly as the firmware sets it.
#

from dataclasses import dataclass


@dataclass
class GpsPacket:
    label: int = 0
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    speed: float = 0.0
    hdop: float = 0.0
    num_sats: int = 0
    course: float = 0.0
    fix: int = 0
    # 'DDMMYY_HHMMSS.SSS' rendered by PacketDecoder._format_utc, or ''
    # when the firmware didn't have a fix yet at packet-send time.
    utc: str = ""
