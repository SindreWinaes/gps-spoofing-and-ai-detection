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

    log_file = "/sd/gps_log_spoofer.csv"

    # Write CSV header
    with open(log_file, "w") as f:
        f.write("time,lat,lon,alt,sats,accel\n")

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

                    pycom.rgbled(0x008000)
                    sleep(0.1)
                    pycom.rgbled(0x000080)

                else:

                    pycom.rgbled(0x800000)
                    sleep(0.1)
                    pycom.rgbled(0x000080)

                print("Sats:", gps_data['sats'])
                print("Accel magnitude: {:.2f}".format(
                    accel_data['magnitude']
                ))

                # SAVE TO CSV
                with open(log_file, "a") as f:

                    line = "{},{},{},{},{},{}\n".format(
                        time.time(),
                        gps_data['lat'],
                        gps_data['lon'],
                        gps_data['alt'],
                        gps_data['sats'],
                        accel_data['magnitude']
                    )

                    f.write(line)

            else:

                print("Waiting for GPS fix...")
                print("Sats:", gps_data['sats'])

                pycom.rgbled(0x808000)
                sleep(1)
                pycom.rgbled(0x000080)

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