from network import LoRa
import socket 
import struct



class LoRaTx:
    
    PACKET_GPS = 0
    PACKET_ACCEL = 1

    GPS_FORMAT = 'Bfffffifi'
    ACCEL_FORMAT = 'Bffffffff'
    
    def __init__(self, tx_power=14, spreading_factor=10):
        # Initialize Lora EU68
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
        """Low level send - Handles blocking and unblocking and error handling"""
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
            print("LoRa send faiel: {}".format(e))
            return False
        
    def send_gps(self, gps_data):
        #Pack and send GPS packet
        try:
            packed = struct.pack(
                self.GPS_FORMAT,
                self.PACKET_GPS,
                gps_data['lat'],
                gps_data['lon'],
                gps_data['alt'],
                gps_data['speed'],
                gps_data['hdop'],
                gps_data['sats'],
                gps_data['course'],
                gps_data['fix']
            )
            return self._send_packet(packed)
        
        except Exception as e:
            print("GPS pack error: {}".format(e))
            return False

    def send_accel(self, accel_data):
        # Pack and send accelerometer packet
        try:
            packed = struct.pack(
                self.ACCEL_FORMAT,
                self.PACKET_ACCEL,
                accel_data['accel_x'],
                accel_data['accel_y'],
                accel_data['accel_z'],
                accel_data['roll'],
                accel_data['pitch'],
                accel_data['magnitude'],
                accel_data['previous_mag'],
                accel_data['jerk']
            )
            return self._send_packet(packed)
        
        except Exception as e:
            print("Accel Pack error: {}".format(e))
            return False

    def get_stats(self):
        return{
            'packets_sent': self.packets_sent,
            'send_failures': self.send_failures,
            'success_rate': self.packets_sent / (self.packets_sent + self.send_failures)
                        if (self.packets_sent + self.send_failures) > 0
                        else 0
        }