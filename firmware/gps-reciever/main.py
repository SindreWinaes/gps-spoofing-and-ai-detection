import pycom
import time
from time import sleep
from pycoproc import Pycoproc
from L76GNSS import L76GNSS
from LIS2HH12 import LIS2HH12

from GPSSensor import GPSSensor
from AccelSensor import AccelSensor
from LoRaTx import LoRaTx

from machine import SD
import os


def main():
    
    py = Pycoproc(Pycoproc.PYTRACK)
    
    l76 = L76GNSS(py, timeout=30)
    lis = LIS2HH12(py)
    
    gps_sensor = GPSSensor(l76)
    accel_sensor = AccelSensor(lis)
    
    lora_tx = LoRaTx(tx_power=14, spreading_factor=10)

    # -------- SD CARD SETUP --------
    sd = SD()
    os.mount(sd, '/sd')

    log_file = "/sd/gps_log.csv"

    # Write CSV header
    with open(log_file, "w") as f:
        f.write("time,lat,lon,alt,sats,fix,accel\n")
    # --------------------------------
    
    pycom.heartbeat(False)
    pycom.rgbled(0x000080)    # Blue Led
    
    print("Starting Sensor Transmission")

    
    packet_count = 0
    while True:
        try:
            print("Reading GPS...")
            gps_data = gps_sensor.read()
            
            print("Reading accelerometer...")
            accel_data = accel_sensor.read()
            
            if gps_data['fix'] > 0:
                print("Sending packet {}...".format(packet_count))
                success = lora_tx.send(gps_data, accel_data)
                
                if success:
                    packet_count += 1
                    pycom.rgbled(0x008000) # Green - Success
                    sleep(0.1)
                    pycom.rgbled(0x000080)
                    sleep(0.1)
                else:
                    pycom.rgbled(0x800000)
                    sleep(0.1)
                    pycom.rgbled(0x000080)
                    
                print("GPS: {:.6f}, {:.6f}".format(gps_data['lat'], gps_data['lon']))
                print("Sats: {},  Fix: {}".format(gps_data['sats'], gps_data['fix']))
                print("Accel magnitude: {:.2f}".format(accel_data['magnitude'])) 

                # -------- SAVE TO CSV --------
                with open(log_file, "a") as f:
                    line = "{},{},{},{},{},{},{}\n".format(
                        time.time(),
                        gps_data['lat'],
                        gps_data['lon'],
                        gps_data.get('alt', 0),
                        gps_data['sats'],
                        gps_data['fix'],
                        accel_data['magnitude']
                    )
                    f.write(line)
                # -----------------------------

            else: 
                print("Waiting for GPS fix...")
                print("Accel: {:.2f}, {:.2f}, {:.2f}".format(
                    accel_data['accel_x'],
                    accel_data['accel_y'],
                    accel_data['accel_z']
                ))

                pycom.rgbled(0x808000)
                sleep(1)
                pycom.rgbled(0x000080)
                
            if packet_count > 0 and packet_count % 10 == 0:
                stats = lora_tx.get_stats()
                print("stats: {}".format(stats))
                
            sleep(1)
            
        except KeyboardInterrupt:
            print("\nStopping...")
            stats = lora_tx.get_stats()
            print("Final stats: {}".format(stats))
            break
        
        except Exception as e:
            print("Error in main loop: {}".format(e))
            pycom.rgbled(0xFF0000)
            sleep(5)
            pycom.rgbled(0x000080)
            
if __name__ == '__main__': 
    main()
