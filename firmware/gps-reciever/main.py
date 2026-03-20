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

DEVICE_ID = 'A'


def is_valid_gps(gps_data):
    if gps_data['fix'] not in [1,2]:
        return False
    if gps_data['hdop'] > 5.0:
        return False
    if gps_data['sats'] < 4 or gps_data['sats'] > 32:
        return False
    if (not 50.0 < gps_data['lat'] < 72.0): # Norway bounds
        return False
    if not (4.0 < gps_data['lon'] < 32.0): # Norway bounds
        return False
    return True


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
        f.write("time,device_id,label,lat,lon,alt,speed,hdop,sats,course,fix,accel_x,accel_y,accel_z,roll,pitch,magnitude,previous_mag,jerk\n")
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
                if not is_valid_gps(gps_data):
                    print("Invalid GPS reading, skipping")
                    continue

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
            try:
                with open(log_file, "a") as f:
                    line = "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
                        time.time(),
                        DEVICE_ID,
                        0,                  #Label 0 = legitimate
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
                        accel_data['jerk']
                    )
                    f.write(line)
                print("Logged to SD")
            except Exception as e:
                print("SD write error:", e)    
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
