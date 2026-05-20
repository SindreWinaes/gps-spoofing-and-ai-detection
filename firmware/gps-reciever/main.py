import os
import pycom
from time import sleep
from machine import SD

from Common_library.Pycoproc import Pycoproc
from Common_library.L76GNSS import L76GNSS
from Common_library.LIS2HH12 import LIS2HH12
from Common_library.GpsParser import GpsParser
from Common_library.LoRaTx import LoRaTx

from GPS_receiver.AccelCalibration import AccelCalibration
from GPS_receiver.AccelPipeline import AccelPipeline
from GPS_receiver.SdLogger import SdLogger


# 0 = legit data
LABEL = 0
ACCEL_BURST_MS = 200
ACCEL_SENDS_PER_LOOP = 6


def is_valid_gps(gps_data):
    if gps_data['fix'] not in [1, 2]:
        return False
    if gps_data['hdop'] is None or gps_data['hdop'] > 10.0:
        return False
    if gps_data['sats'] < 3 or gps_data['sats'] > 24:
        return False
    if not (50.0 < gps_data['lat'] < 72.0):
        return False
    if not (4.0 < gps_data['lon'] < 32.0):
        return False
    return True


def is_valid_date(utc_date):
    if not utc_date or len(utc_date) != 6:
        return False
    if utc_date == '050180':
        return False
    try:
        day = int(utc_date[0:2])
        month = int(utc_date[2:4])
        year = int(utc_date[4:6])
    except ValueError:
        return False
    if not (1 <= day <= 31):
        return False
    if not (1 <= month <= 12):
        return False
    if year < 25:
        return False
    return True


def run_accel_bursts(accel_pipeline, lora_tx, sd_logger, n_bursts,
                     burst_ms, accel_count, gps_data_for_utc=None):
    raw_f = None
    try:
        raw_f = open(sd_logger.raw_accel_path, "a")
    except Exception as e:
        print("Raw accel SD open failed:", e)
        raw_f = None

    last_features = None
    try:
        for _ in range(n_bursts):
            last_features = accel_pipeline.read_burst(
                duration_ms=burst_ms,
                raw_file=raw_f,
            )
            if lora_tx.send_accel(last_features, gps_data_for_utc=gps_data_for_utc):
                accel_count += 1
    finally:
        if raw_f is not None:
            try:
                raw_f.close()
            except Exception:
                pass

    return last_features, accel_count


def main():
    py = Pycoproc(Pycoproc.PYTRACK)
    l76 = L76GNSS(py, timeout=30)
    lis = LIS2HH12(py)

    gps = GpsParser(l76)

    # device must sit still for ~2 s (orange LED)
    pycom.heartbeat(False)
    pycom.rgbled(0x808000)
    cal = AccelCalibration()
    cal.calibrate(lis)
    pycom.rgbled(0x000000)

    accel_pipeline = AccelPipeline(lis, calibration=cal)
    lora_tx = LoRaTx(tx_power=14, spreading_factor=10)

    SdLogger.mount()
    accel_count = 0
    sd_logger = None
    last_gps = None

    # wait for first GPS fix to name the SD log file
    while sd_logger is None:
        gps_data = gps.read()
        if (gps_data and gps_data.get('utc_time')
                and is_valid_date(gps_data.get('utc_date'))):
            last_gps = gps_data

        accel_data = accel_pipeline.read_burst(duration_ms=ACCEL_BURST_MS)
        if lora_tx.send_accel(accel_data, gps_data_for_utc=last_gps):
            accel_count += 1
            print("Accel sent ({})".format(accel_count))

        if (gps_data and gps_data['fix'] in [1, 2]
                and gps_data['utc_time']
                and is_valid_date(gps_data['utc_date'])):
            timestamp = "{}_{:.0f}".format(
                gps_data['utc_date'], float(gps_data['utc_time']))
            sd_logger = SdLogger(timestamp)
            print("Log file:       " + sd_logger.log_path)
            print("Raw accel file: " + sd_logger.raw_accel_path)
        else:
            print("Waiting for GPS fix to create log file...")
            sleep(1)
            pycom.rgbled(0x000080)
            sleep(0.5)
            pycom.rgbled(0x000000)
            sleep(0.5)

    pycom.rgbled(0x000080)
    print("System Startup - Device A")

    gps_count = 0
    last_logged_utc = None

    n_before = ACCEL_SENDS_PER_LOOP // 2
    n_after = ACCEL_SENDS_PER_LOOP - n_before

    while True:
        try:
            print("\nReading Sensors...")

            accel_data, accel_count = run_accel_bursts(
                accel_pipeline, lora_tx, sd_logger,
                n_before, ACCEL_BURST_MS, accel_count,
                gps_data_for_utc=last_gps,
            )

            gps_data = gps.read()
            if (gps_data and gps_data.get('utc_time')
                    and is_valid_date(gps_data.get('utc_date'))):
                last_gps = gps_data

            accel_data, accel_count = run_accel_bursts(
                accel_pipeline, lora_tx, sd_logger,
                n_after, ACCEL_BURST_MS, accel_count,
                gps_data_for_utc=last_gps,
            )

            print("Accel cycles this loop: {} (cumulative {})".format(
                ACCEL_SENDS_PER_LOOP, accel_count))

            if gps_data is None:
                print("No GPS data yet...")
                sleep(1)
                continue

            print("GPS raw:", gps_data)

            if gps_data['fix'] > 0:
                if not is_valid_gps(gps_data):
                    print("Invalid GPS reading, skipping")
                    continue

                # skip stale fix or already-logged UTC
                if (not gps_data.get('new_fix', False)
                        or gps_data['utc_time'] == last_logged_utc):
                    pycom.rgbled(0x000080)
                    continue

                last_logged_utc = gps_data['utc_time']

                # GPS LoRa send disabled; GPS captured to SD only
                # gps_ok = lora_tx.send_gps(gps_data, LABEL)
                gps_ok = True
                gps_count += 1
                print("GPS captured to SD ({}, no LoRa)".format(gps_count))

                pycom.rgbled(0x000080)

                print("GPS: {:.6f},{:.6f}".format(
                    gps_data['lat'], gps_data['lon']))
                print("Sats: {} Fix:{}".format(
                    gps_data['sats'], gps_data['fix']))

                if accel_data is not None:
                    print("Dyn accel: {:.6f} Jerk: {:.6f}".format(
                        accel_data['dyn_mag'], accel_data['jerk_mag']))
                    if accel_data.get('accel_std') is not None:
                        print("Std dev: {:.6f} Energy {:.6f}".format(
                            accel_data['accel_std'],
                            accel_data['accel_energy']))

                sd_logger.write_log_row(gps_data, accel_data, LABEL)
                print("Logged to SD")

            else:
                print("Waiting for GPS fix...")
                print("Sats:", gps_data['sats'])
                pycom.rgbled(0x000080)
                sleep(0.5)
                pycom.rgbled(0x000000)
                sleep(0.5)

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
