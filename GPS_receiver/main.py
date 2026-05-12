#
# main.py
# Device A (legitimate Pytrack) entry point. Brings up the hardware,
# calibrates the accelerometer, mounts the SD card, waits for a GPS
# fix to name the log files, then loops:
#
#   accel bursts (half budget)  ->  GPS read  ->  accel bursts (other half)
#       LoRa accel sends                              LoRa accel sends
#                                                       SD log row
#
# The GPS LoRa send is intentionally DISABLED here - Device A's GPS
# now lives exclusively in the SD log. See main loop comments for why.
#

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


# Label byte on GPS LoRa packets if/when re-enabled. 0 = legit data.
LABEL = 0

# Each burst samples for ACCEL_BURST_MS (~20 samples @ 100 Hz). Short
# enough to fit more burst+send cycles per main-loop iteration so the
# accel LoRa stream arrives at the PC ~1 Hz instead of ~0.14 Hz.
ACCEL_BURST_MS = 200

# Number of accel burst+LoRa-send cycles per main-loop iteration. At
# SF=10 each LoRa send blocks for ~540 ms airtime + 200 ms burst, so
# each cycle costs ~740 ms wall-clock. 6 cycles = ~4.4 s of accel work
# per loop, near the SF=10 airtime ceiling. Half are emitted before the
# GPS read and half after, so accel coverage spans the whole loop
# window rather than clumping after GPS.
ACCEL_SENDS_PER_LOOP = 6


def is_valid_gps(gps_data):
    # Same bounds as the spoofer's is_valid_gps and the parser's
    # internal sanity checks.
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


def run_accel_bursts(accel_pipeline, lora_tx, sd_logger, n_bursts,
                     burst_ms, accel_count, gps_data_for_utc=None):
    # Run `n_bursts` short accel bursts back-to-back, each transmitting
    # its own LoRa packet on the accel frequency. The raw-accel SD file
    # is appended to during every burst so the 100 Hz raw record is
    # unbroken. Returns (last_features, updated_accel_count).
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
    # ---- Hardware ----
    py = Pycoproc(Pycoproc.PYTRACK)
    l76 = L76GNSS(py, timeout=30)
    lis = LIS2HH12(py)

    gps = GpsParser(l76)

    # ---- Calibrate accelerometer at startup ----
    # Device must sit STILL for ~2 sec (orange LED). Level is NOT
    # required - calibration is orientation-invariant.
    pycom.heartbeat(False)
    pycom.rgbled(0x808000)
    cal = AccelCalibration()
    cal.calibrate(lis)
    pycom.rgbled(0x000000)

    accel_pipeline = AccelPipeline(lis, calibration=cal)
    lora_tx = LoRaTx(tx_power=14, spreading_factor=10)

    # ---- SD card ----
    SdLogger.mount()
    accel_count = 0
    sd_logger = None

    # Most-recent GPS dict the device has parsed. Used to stamp accel
    # packets with A's UTC. Stays None until the first GPS fix; accel
    # packets sent before that have UTC=0 and the PC pairs by wall-clock.
    last_gps = None

    # ---- WARMUP: wait for first GPS fix so we can name the SD log file ----
    while sd_logger is None:
        gps_data = gps.read()
        if gps_data and gps_data.get('utc_time') and gps_data.get('utc_date'):
            last_gps = gps_data

        accel_data = accel_pipeline.read_burst(duration_ms=ACCEL_BURST_MS)
        if lora_tx.send_accel(accel_data, gps_data_for_utc=last_gps):
            accel_count += 1
            print("Accel sent ({})".format(accel_count))

        if (gps_data and gps_data['fix'] in [1, 2]
                and gps_data['utc_date'] and gps_data['utc_time']):
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

    # Split the burst budget half before / half after the GPS read so
    # the accel stream covers the whole loop wall-clock window evenly.
    n_before = ACCEL_SENDS_PER_LOOP // 2
    n_after = ACCEL_SENDS_PER_LOOP - n_before

    while True:
        try:
            print("\nReading Sensors...")

            # --- Half of the accel bursts BEFORE the GPS read ---
            accel_data, accel_count = run_accel_bursts(
                accel_pipeline, lora_tx, sd_logger,
                n_before, ACCEL_BURST_MS, accel_count,
                gps_data_for_utc=last_gps,
            )

            # --- GPS read (typically ~1-2 s, capped at 5 s) ---
            gps_data = gps.read()
            if gps_data and gps_data.get('utc_time') and gps_data.get('utc_date'):
                last_gps = gps_data

            # --- Other half of the accel bursts AFTER the GPS read ---
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

                # Dedup: skip if parser didn't see a fresh fix this read
                # cycle, or if this UTC time has already been logged.
                if (not gps_data.get('new_fix', False)
                        or gps_data['utc_time'] == last_logged_utc):
                    pycom.rgbled(0x000080)
                    continue

                last_logged_utc = gps_data['utc_time']

                # GPS LoRa send is DISABLED. Device A's GPS now lives
                # exclusively in the SD log; the PC log is fed only by
                # the spoofer's GPS + A's accel stream. Legit + spoof
                # are merged offline using the Accel UTC anchor.
                #
                # Why: A and B both transmit GPS on 868.1 MHz. Both
                # transmitting at the same time means the LoRa packets
                # collide and one is destroyed - caused ~47% legit
                # packet loss in earlier walks. Removing A's GPS LoRa
                # leaves 868.1 to the spoofer, which is what the demo
                # is meant to show anyway.
                #
                # To re-enable: uncomment the lora_tx.send_gps block
                # and delete the gps_ok=True / gps_count+=1 lines.
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

                # -------- SAVE TO SD card --------
                sd_logger.write_log_row(gps_data, accel_data, LABEL)
                print("Logged to SD")

            else:
                print("Waiting for GPS fix...")
                print("Sats:", gps_data['sats'])
                pycom.rgbled(0x000080)
                sleep(0.5)
                pycom.rgbled(0x000000)
                sleep(0.5)

            # Print stats every 10 GPS rows logged
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
