import pycom
import time
from time import sleep
from pycoproc import Pycoproc
from L76GNSS import L76GNSS
from LIS2HH12 import LIS2HH12
from calibration import AccelCalibration
from GPSSensor import GPSSensor
from AccelSensor import AccelSensor
from LoRaTx import LoRaTx

from machine import SD
import os

LABEL = 0

CSV_HEADER = (
    "Time, UTC Time, Label, Latitude, Longitude, Altitude, Speed, HDOP, Satelites, Course, Fix,"
    " Roll Degrees, Pitch Degrees, Dynamic Magnitude, Jerk, Acceleration X, Acceleration Y, Acceleration Z," 
    "Standard Deviation, Energy, Zero Crossings\n"
)

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

# Maps to CSV collum
def build_log_line(gps_data, accel_data, label):
    
    def safe(val):
        if val is None:
            return ''
        return '{:.6f}'.format(val)
    
    return "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
        time.time(),
        gps_data['utc_time'],
        LABEL,                  #Label 0 = legitimate
        gps_data['lat'], 
        gps_data['lon'],
        gps_data['alt'],
        gps_data['speed'],                    
        gps_data['hdop'],                     
        gps_data['sats'],                     
        gps_data['course'],                     
        gps_data['fix'],
        accel_data['roll'],
        accel_data['pitch'],
        safe(accel_data['dyn_mag']), 
        safe(accel_data['jerk_mag']),
        safe(accel_data['accel_x']),                    
        safe(accel_data['accel_y']),                   
        safe(accel_data['accel_z']),
        safe(accel_data['accel_std']),                    
        safe(accel_data['accel_energy']),                   
        safe(accel_data['accel_zero_cross']),                                                                    
    )


def main():
    
    # Initialize hardware
    py = Pycoproc(Pycoproc.PYTRACK)
    l76 = L76GNSS(py, timeout=30)
    lis = LIS2HH12(py)
    
    gps_sensor = GPSSensor(l76)
    
    # Calibrate Accelerometer at startup, device must sit still and bbe level.
    pycom.heartbeat(False)
    pycom.rgbled(0x808000) # Yellow = calibrating
    cal = AccelCalibration()
    cal.calibration(lis, num_samples=50)
    pycom.rgbled(0x000000)
    accel_sensor = AccelSensor(lis, calibration=cal)
    

    

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
            pycom.rgbled(0x000080)
            sleep(0.5)
            pycom.rgbled(0x000000)
            sleep(0.5)
        


    # Write CSV header
    with open(log_file, "w") as f:
        f.write(CSV_HEADER)
    # --------------------------------
    
   
    pycom.rgbled(0x000080)
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
                gps_ok = lora_tx.send_gps(gps_data, LABEL)
                if gps_ok:
                    gps_count += 1
                    print("GPS sent ({})".format(gps_count))
                else:
                    print("GPS send failed")

                # Send acelerometer packet
                accel_ok = lora_tx.send_accel(accel_data, LABEL)
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
                
                print("Dyn accel: {:.6f} Jerk: {:.6f}".format(
                    accel_data['dyn_mag'], accel_data['jerk_mag']))
                if accel_data['accel_std'] is not None:
                    print("Std dev: {:.6f} Energy {:.6f}".format(
                        accel_data['accel_std'], accel_data['accel_energy']))
                
    
            # -------- SAVE TO SD card --------
                try:
                    with open(log_file, "a") as f:
                       line = build_log_line(gps_data, accel_data, LABEL)
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
