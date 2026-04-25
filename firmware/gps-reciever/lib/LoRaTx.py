from network import LoRa
import socket
import struct



class LoRaTx:

    PACKET_GPS = 0
    PACKET_ACCEL = 1

    FREQ_GPS = 868100000
    FREQ_ACCEL = 868300000

    # GPS_FORMAT tail: I = utc_date (DDMMYY as uint32), f = utc_time (HHMMSS.SSS as float)
    # Added so the PC receiver can log real GPS UTC for both legit and spoofed streams.
    GPS_FORMAT = 'BBfffffifiIf'

    # ACCEL_FORMAT tail: I = utc_date (DDMMYY as uint32), f = utc_time
    # (HHMMSS.SSS as float).  Mirrors GPS_FORMAT so accel packets carry
    # A's most-recent UTC at the moment the packet was transmitted.  This
    # lets the PC receiver align accel rows with GPS rows on a shared
    # UTC timeline, which is needed for offline merging of A's SD log
    # (legit GPS+accel) with the PC log (spoof GPS + paired accel).
    # When the device has no fix yet (warmup) or no UTC available, the
    # tail is zeros and the PC treats those packets as "no UTC, pair by
    # wall-clock arrival".
    ACCEL_FORMAT = 'BfffffffffffIf'

    def __init__(self, tx_power=14, spreading_factor=10):
        # Initialize Lora EU868
        self.lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868)

        # Sets Radio parameters
        self.lora.frequency(self.FREQ_GPS)
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
        """Convert a GPSSensor.read() dict into (utc_date_int, utc_time_float).

        Both default to 0 if the dict is None or the fields aren't yet
        populated. The PC receiver treats (0, 0.0) as "no UTC available
        for this packet" and falls back to wall-clock pairing.
        """
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
        # Pack and send accelerometer packet on the accel frequency, then
        # restore the GPS frequency so the next GPS send goes out on FREQ_GPS.
        #
        # gps_data_for_utc: optional dict from GPSSensor.read() carrying
        # the most-recent UTC the device has parsed. Embedding UTC here
        # lets the PC align accel rows with GPS rows on a shared timeline
        # for offline merging.
        try:
            self.lora.frequency(self.FREQ_ACCEL)

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
            result = self._send_packet(packed)
            self.lora.frequency(self.FREQ_GPS)
            return result

        except Exception as e:
            print("Accel pack error: {}".format(e))
            # Best-effort restore of GPS frequency on error path
            try:
                self.lora.frequency(self.FREQ_GPS)
            except Exception:
                pass
            return False

    def get_stats(self):
        return {
            'packets_sent': self.packets_sent,
            'send_failures': self.send_failures,
            'success_rate': self.packets_sent / (self.packets_sent + self.send_failures)
                        if (self.packets_sent + self.send_failures) > 0
                        else 0
        }
