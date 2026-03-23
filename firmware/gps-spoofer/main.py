import pycom
import time
from time import sleep
from pycoproc import Pycoproc
from L76GNSS import L76GNSS
from LIS2HH12 import LIS2HH12

from GPSSensor import GPSSensor
from AccelSensor import AccelSensor
from LoRaTx import LoRaTx
from spoof import GPSSpoofer

from machine import SD
import os

DEVICE_ID = 'B'

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

    # Init Pytrack
    py = Pycoproc(Pycoproc.PYTRACK)

    # Init sensors
    l76 = L76GNSS(py, timeout=60)
    lis = LIS2HH12(py)

    gps_sensor = GPSSensor(l76)
    accel_sensor = AccelSensor(lis)

    # Init LoRa
    lora_tx = LoRaTx(tx_power=14, spreading_factor=10)

    # Init SD card
    sd = SD()
    os.mount(sd, '/sd')

    log_file = None

    while log_file is None:
        gps_data = gps_sensor.read()
        if gps_data and gps_data['fix'] in [1, 2] and gps_data['utc_date'] and gps_data['utc_time']:
            date = gps_data['utc_date']     # DDMMYY
            t =  gps_data['utc_time']       # HHMMSS.SSS
            timestamp = "{}_{:.0f}".format(date, float(t))
            log_file = "/sd/gps_log_spoofer_{}.csv".format(timestamp)
            print("Log file: " + log_file)
        else:
            print("Waiting for GPS fix to create log file...")
            sleep(1)

    # Write CSV header
    with open(log_file, "w") as f:
        f.write("time,device_id,label,lat,lon,alt,speed,hdop,sats,course,fix,accel_x,accel_y,accel_z,roll,pitch,magnitude,previous_mag,jerk\n")

    # Init spoofer
    spoofer = GPSSpoofer(
        delay_samples=5,
        noise_std=0.00002
    )

    # LED setup
    pycom.heartbeat(False)
    pycom.rgbled(0x000080)

    print("System started")

    packet_count = 0

    while True:
        try:

            print("\nReading sensors...")

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

                print("Real GPS: {:.6f}, {:.6f}".format(
                    gps_data['lat'], gps_data['lon']
                ))

                spoof = spoofer.add_real_position(
                    gps_data['lat'],
                    gps_data['lon'],
                    gps_data['alt']
                )

                if spoof is None:
                    print("Buffering GPS for delay spoofing...")
                    sleep(1)
                    continue

                lat, lon, alt = spoof

                gps_data['lat'] = lat
                gps_data['lon'] = lon
                gps_data['alt'] = alt

                print("Spoofed GPS: {:.6f}, {:.6f}".format(lat, lon))

                success = lora_tx.send(gps_data, accel_data)

                if success:

                    packet_count += 1
                    pycom.rgbled(0x000080) # Solid blue = reciving gps and sending

                    # SAVE TO CSV
                    try:        
                        with open(log_file, "a") as f:

                            line = "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
                                time.time(),
                                DEVICE_ID,
                                1,                  #Label 1 = spoofed
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

                else:
                    pycom.rgbled(0x800000)
                    sleep(0.1)
                    pycom.rgbled(0x000080)

                
                print("Sats:", gps_data['sats'])
                print("Accel magnitude: {:.2f}".format(
                       accel_data['magnitude']
                   ))

            else:

                print("Waiting for GPS fix...")
                print("Sats:", gps_data['sats'])

                # Blinks blue while waiting for fix. 
                pycom.rgbled(0x000080)
                sleep(0.5)
                pycom.rgbled(0x000000)
                sleep(0.5)

            sleep(1)

        except KeyboardInterrupt:

            print("\nStopping system...")
            stats = lora_tx.get_stats()
            print("Final stats:", stats)
            break

        except Exception as e:

            print("Error:", e)

            pycom.rgbled(0xFF0000)
            sleep(5)
            pycom.rgbled(0x000080)


if __name__ == '__main__':
    main()