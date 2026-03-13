from network import LoRa
import socket 
import struct
from AccelSensor import AccelSensor
from GPSSensor import GPSSensor


class LoRaTx:
    
    
    def __init__(self, tx_power=14, spreading_factor=10):
        # Initialize Lora EU68
        self.lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868)

        self.lora.frequency(868100000)
        self.lora.bandwidth(LoRa.BW_125KHZ)
        self.lora.sf(spreading_factor)
        self.lora.tx_power(tx_power)

        self.s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
        self.s.setblocking(False)
        
        self.frequency = 868100000
        self.bandwidth = LoRa.BW_125KHZ
        self.spreadfactor = spreading_factor
        self.txPwr = tx_power
        
        self.packets_sent = 0
        self.send_failures = 0
        
    def _pack_data(self, gps_data, accel_data):
            data = struct.pack('fffffififfffffff', 
                               gps_data['lat'], 
                               gps_data['lon'],
                               gps_data['alt'],
                               gps_data['speed'],
                               gps_data['hdop'], 
                               gps_data['sats'], 
                               gps_data['course'], 
                               gps_data['fix'],
                               
                               
                               accel_data['accel_x'],
                               accel_data['accel_y'],
                               accel_data['accel_z'],
                               accel_data['roll'],
                               accel_data['pitch'],
                               accel_data['magnitude'],
                               accel_data['previous_mag'],
                               accel_data['jerk'])
            return data
    
    def send(self, gps_data, accel_data):
        try: 
            packed = self._pack_data(gps_data, accel_data)
            
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
            print("LoRa send failed: {}".format(e))
            return False
        
    def get_stats(self):
        return{
            'packets_sent': self.packets_sent,
            'send_failures': self.send_failures,
            'success_rate': self.packets_sent / (self.packets_sent + self.send_failures)
                        if (self.packets_sent + self.send_failures) > 0
                        else 0
        }