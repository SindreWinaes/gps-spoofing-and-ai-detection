from network import LoRa
import socket
import struct



class LoRaTx:

    PACKET_GPS = 0
    PACKET_ACCEL = 1

    # GPS_FORMAT tail: I = utc_date (DDMMYY as uint32), f = utc_time (HHMMSS.SSS as float)
    # MUST match firmware/gps-reciever/lib/LoRaTx.py and ml/data/reciever.py.
    # The PC receiver rejects packets shorter than struct.calcsize(GPS_FORMAT).
    GPS_FORMAT = 'BBfffffifiIf'

    # ACCEL_FORMAT mirrors the legit receiver's format with a UTC tail.
    # The spoofer never actually sends accel packets in normal operation
    # (it only replays GPS), but keeping this format string in sync with
    # firmware/gps-reciever/lib/LoRaTx.py prevents drift if anyone copies
    # this file or runs format-comparison tests.
    ACCEL_FORMAT = 'BfffffffffffIf'

    def __init__(self, tx_power=14, spreading_factor=10):
        # Initialize Lora EU868
        self.lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868)

        # Sets Radio parameters
        self.lora.frequency(868100000)
        self.lora.bandwidth(LoRa.BW_125KHZ)
        self.lora.sf(spreading_factor)
        self.lora.tx_power(tx_power)

        # Open socket after config
        self.s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
        self.s.setblocking(False)

        self.packets_sent = 0
        self.send_failures = 0

    def _send_packet(self, packed):
        """Low level send - handles blocking and error reporting."""
        try:
            self.s.setblocking(True)
            bytes_sent = self.s.send(packed)
            self.s.setblocking(False)

            if bytes_sent == len(packed):
                self.packets_sent += 1
                return True
            else:
                self.send_failures += 1
                print("Partial send: {}/{}".format(bytes_sent, len(packed)))
                return False

        except Exception as e:
            self.send_failures += 1
            print("LoRa send fail: {}".format(e))
            return False

    @staticmethod
    def _parse_utc(gps_data):
        """Convert a GPS dict's utc_date/utc_time strings to (int, float)."""
        utc_date_int = 0
        utc_time_float = 0.0
        if not gps_data:
            return utc_date_int, utc_time_float
        try:
            utc_date_raw = gps_data.get('utc_date', '') if hasattr(gps_data, 'get') else ''
        except Exception:
            utc_date_raw = ''
        try:
            utc_time_raw = gps_data.get('utc_time', '') if hasattr(gps_data, 'get') else ''
        except Exception:
            utc_time_raw = ''
        try:
            utc_date_int = int(utc_date_raw) if utc_date_raw else 0
        except (ValueError, TypeError):
            utc_date_int = 0
        try:
            utc_time_float = float(utc_time_raw) if utc_time_raw else 0.0
        except (ValueError, TypeError):
            utc_time_float = 0.0
        return utc_date_int, utc_time_float

    def send_gps(self, gps_data, label):
        # Pack and send GPS packet
        try:
            utc_date_int, utc_time_float = self._parse_utc(gps_data)

            packed = struct.pack(
                self.GPS_FORMAT,
                self.PACKET_GPS,
                label,
                gps_data['lat'],
                gps_data['lon'],
                gps_data['alt'],
                gps_data['speed'],
                gps_data['hdop'],
                gps_data['sats'],
                gps_data['course'],
                gps_data['fix'],
                utc_date_int,
                utc_time_float
            )
            return self._send_packet(packed)

        except Exception as e:
            print("GPS pack error: {}".format(e))
            return False

    def send_accel(self, accel_data, gps_data_for_utc=None):
        # Spoofer does not send accel packets in normal operation; this
        # method exists only so the spoofer's LoRaTx API stays
        # interchangeable with the legit Pytrack's LoRaTx (firmware
        # reuse, format-equivalence tests, etc.).
        try:
            def safe(val):
                return val if val is not None else 0.0

            utc_date_int, utc_time_float = self._parse_utc(gps_data_for_utc)

            packed = struct.pack(
                self.ACCEL_FORMAT,
                self.PACKET_ACCEL,
                accel_data['roll'],
                accel_data['pitch'],
                safe(accel_data['dyn_mag']),
                safe(accel_data['jerk_mag']),
                safe(accel_data['jerk_std']),
                safe(accel_data['accel_x']),
                safe(accel_data['accel_y']),
                safe(accel_data['accel_z']),
                safe(accel_data['accel_std']),
                safe(accel_data['accel_energy']),
                safe(accel_data['accel_zero_cross']),
                utc_date_int,
                utc_time_float,
            )
            return self._send_packet(packed)

        except Exception as e:
            print("Accel pack error: {}".format(e))
            return False

    def get_stats(self):
        return {
            'packets_sent': self.packets_sent,
            'send_failures': self.send_failures,
            'success_rate': self.packets_sent / (self.packets_sent + self.send_failures)
                        if (self.packets_sent + self.send_failures) > 0
                        else 0
        }
