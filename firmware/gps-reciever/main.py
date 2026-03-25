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
LABEL = 0

def is_valid_gps(gps_data):
    if gps_data['fix'] not in [1,2]:
        return False
    if gps_data['hdop'] > 10.0:
        return False
    if gps_data['sats'] < 3 or gps_data['sats'] > 32:
        return False
    if (not 50.0 < gps_data['lat'] < 72.0): # Norway bounds
        return False
    if not (4.0 < gps_data['lon'] < 32.0): # Norway bounds
        return False
    return True


def main():
    
    # Initialize hardware
    py = Pycoproc(Pycoproc.PYTRACK)
    l76 = L76GNSS(py, timeout=30)
    lis = LIS2HH12(py)
    
    gps_sensor = GPSSensor(l76)
    accel_sensor = AccelSensor(lis)
    
    lora_tx = LoRaTx(tx_power=14, spreading_factor=10)

    # -------- SD CARD SETUP --------
    sd = SD()
    os.mount(sd, '/sd')

    log_file = None
    while log_file is None:
        gps_data = gps_sensor.read()
        if (gps_data and gps_data['fix'] in [1,2] and gps_data['utc_date'] and gps_data['utc_time']):
            timestamp = "{}_{:.0f}".format(gps_data['utc_date'], float(gps_data['utc_time']))
            log_file = "/sd/gps_log_A_{}.csv".format(timestamp)
            print("Log file: " + log_file)
        else:
            print("Waiting for GPS fix to create log file...")
            sleep(1)


    # Write CSV header
    with open(log_file, "w") as f:
        f.write("time,utc_time,device_id,label,lat,lon,alt,speed,hdop,sats,course,fix,accel_x,accel_y,accel_z,roll,pitch,magnitude,previous_mag,jerk\n")
    # --------------------------------
    
    # Led setup
    pycom.heartbeat(False)
    pycom.rgbled(0x000080)    # Blue Led
    
    print("System Startup - Device A")

    gps_count = 0
    accel_count = 0

    while True:
        try: 
            print("\nReading Sensors...")
            gps_data = gps_sensor.read()
            accel_data = accel_sensor.read()

            if gps_data is None:
                print("No GPS data yet...")
                sleep(1)
                continue
            
            print("GPS raw:", gps_data)

            if gps_data['fix'] > 0:
                if not is_valid_gps(gps_data):
                    print("Invalid GPS reading, skipping")
                    continue

                # Send GPS packet
                gps_ok = lora_tx.send_gps(gps_data)
                if gps_ok:
                    gps_count += 1
                    print("GPS sent ({})".format(gps_count))
                else:
                    print("GPS send failed")

                # Send acelerometer packet
                accel_ok = lora_tx.send_accel(accel_data)
                if accel_ok:
                    accel_count += 1
                    print("Accel sent ({})".format(accel_count))
                else:
                    print("Accel send failed")
                
                # Led Feedback
                if gps_ok and accel_ok:
                    pycom.rgbled(0x000080)  # Solid blue = sending
                else:
                    pycom.rgbled(0x800000)  # Red = Send failure
                    sleep(0.1)
                    pycom.rgbled(0x000080)

                print("GPS: {:.6f},{:.6f}".format(gps_data['lat'], gps_data['lon']))
                print("Sats: {} Fix:{}".format(
                    gps_data['sats'], gps_data['fix']))
                print("Accel magnitude: {:.2f}".format(
                    accel_data['magnitude']))
                
    
            # -------- SAVE TO SD card --------
                try:
                    with open(log_file, "a") as f:
                       line = "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
                            time.time(),
                            gps_data['utc_time'],
                            DEVICE_ID,
                            LABEL,                  #Label 0 = legitimate
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
                print("Sats:", gps_data['sats'])

                # Blink blue while waiting for fix
                pycom.rgbled(0x000080)
                sleep(0.5)
                pycom.rgbled(0x000000)
                sleep(0.5)

            # Print stats every 10 GPS packets    
            if gps_count > 0 and gps_count % 10 == 0:
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
