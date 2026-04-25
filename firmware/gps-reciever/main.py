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
    "Time, UTC Date, UTC Time, Label, Latitude, Longitude, Altitude, Speed, HDOP, Satelites, Course, Fix,"
    " Roll Degrees, Pitch Degrees, Dynamic Magnitude, Jerk, Jerk Std, Acceleration X, Acceleration Y, Acceleration Z,"
    " Standard Deviation, Energy, Zero Crossings\n"
)

# Raw high-rate accelerometer log (written during every burst read).
# One row per sample at ~100 Hz. Lets us recompute any feature offline with
# different window sizes / filters / ML models.
RAW_ACCEL_HEADER = (
    "ts_ms,sample_idx,raw_x,raw_y,raw_z,cal_x,cal_y,cal_z,"
    "world_x,world_y,world_z,dyn_mag,roll_deg,pitch_deg\n"
)

# --- Accel densification ---
# Each burst samples for ACCEL_BURST_MS (~20 samples at 100 Hz).  This is
# shorter than before (was 1000 ms) so we can fit more burst+send cycles
# per main loop and the LoRa accel stream arrives at the PC ~1 Hz instead
# of ~0.14 Hz.  The 50-sample rolling window stats remain valid because
# the WindowStats circular buffer carries samples across bursts.
ACCEL_BURST_MS = 200

# Number of accel burst+LoRa-send cycles per main-loop iteration.
# At SF=10, each LoRa send blocks for ~540 ms of airtime, plus the
# 200 ms burst, so each cycle costs ~740 ms wall-clock.  6 cycles =
# ~4.4 s of accel work per loop, which is roughly the airtime ceiling
# at SF=10 - going higher gives diminishing returns.
# Half are emitted BEFORE the GPS read and half AFTER, so accel
# coverage spans the whole loop window rather than clumping after GPS.
ACCEL_SENDS_PER_LOOP = 6


def is_valid_gps(gps_data):
    # Same bounds as the spoofer's is_valid_gps and GPSSensor sanity checks:
    # 3..24 sats covers GPS+GLONASS realistic max, HDOP <10 excludes garbage fixes.
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


def build_log_line(gps_data, accel_data, label):

    def safe(val):
        if val is None:
            return ''
        return '{:.6f}'.format(val)

    def safe_gps(val):
        if val is None:
            return ''
        return str(val)

    return "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
        time.time(),
        gps_data.get('utc_date', '') or '',
        gps_data.get('utc_time', '') or '',
        label,
        safe_gps(gps_data.get('lat')),
        safe_gps(gps_data.get('lon')),
        safe_gps(gps_data.get('alt')),
        safe_gps(gps_data.get('speed')),
        safe_gps(gps_data.get('hdop')),
        gps_data.get('sats', 0),
        safe_gps(gps_data.get('course')),
        gps_data.get('fix', 0),
        safe(accel_data.get('roll')),
        safe(accel_data.get('pitch')),
        safe(accel_data.get('dyn_mag')),
        safe(accel_data.get('jerk_mag')),
        safe(accel_data.get('jerk_std')),
        safe(accel_data.get('accel_x')),
        safe(accel_data.get('accel_y')),
        safe(accel_data.get('accel_z')),
        safe(accel_data.get('accel_std')),
        safe(accel_data.get('accel_energy')),
        safe(accel_data.get('accel_zero_cross')),
    )


def run_accel_bursts(accel_sensor, lora_tx, raw_accel_file, n_bursts,
                     burst_ms, accel_count, gps_data_for_utc=None):
    """Run `n_bursts` short accel bursts back-to-back, each transmitting
    its own LoRa packet on the accel frequency.

    Each call opens the raw-accel SD file once and appends every sample
    inside the bursts to it (so the 100 Hz raw record is unbroken).

    `gps_data_for_utc` is the most recent GPS dict the main loop has
    seen, used to stamp each accel packet with A's UTC for offline
    timeline alignment with spoof GPS at the PC.

    Returns:
        (last_features_dict, updated_accel_count)
    """
    raw_f = None
    try:
        raw_f = open(raw_accel_file, "a")
    except Exception as e:
        print("Raw accel SD open failed:", e)
        raw_f = None

    last_features = None
    try:
        for _ in range(n_bursts):
            last_features = accel_sensor.read_burst(
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

    # Initialize hardware
    py = Pycoproc(Pycoproc.PYTRACK)
    l76 = L76GNSS(py, timeout=30)
    lis = LIS2HH12(py)

    gps_sensor = GPSSensor(l76)

    # Calibrate accelerometer at startup. Device must sit STILL for ~2 sec
    # (orange LED). Level is NOT required - calibration is orientation-invariant.
    pycom.heartbeat(False)
    pycom.rgbled(0x808000)
    cal = AccelCalibration()
    cal.calibration(lis)
    pycom.rgbled(0x000000)
    accel_sensor = AccelSensor(lis, calibration=cal)

    lora_tx = LoRaTx(tx_power=14, spreading_factor=10)

    # -------- SD CARD SETUP --------
    sd = SD()
    try:
        os.mount(sd, '/sd')
    except OSError as e:
        # 'already mounted' after a soft reset raises here. Ignore so we
        # can keep running; any real SD failure will show up on first write.
        print("SD mount note:", e)

    log_file = None
    raw_accel_file = None
    accel_count = 0

    # Most-recent GPS dict the device has parsed.  Used to stamp accel
    # packets with A's UTC.  Stays None until the first GPS fix; accel
    # packets sent before that have UTC=0 and the PC handles that as
    # "no UTC, pair by wall-clock arrival".
    last_gps = None

    # ---- WARMUP: wait for first GPS fix so we can name the SD log file ----
    while log_file is None:
        gps_data = gps_sensor.read()
        if gps_data and gps_data.get('utc_time') and gps_data.get('utc_date'):
            last_gps = gps_data

        accel_data = accel_sensor.read_burst(duration_ms=ACCEL_BURST_MS)
        if lora_tx.send_accel(accel_data, gps_data_for_utc=last_gps):
            accel_count += 1
            print("Accel sent ({})".format(accel_count))

        if (gps_data and gps_data['fix'] in [1, 2]
                and gps_data['utc_date'] and gps_data['utc_time']):
            timestamp = "{}_{:.0f}".format(
                gps_data['utc_date'], float(gps_data['utc_time']))
            log_file = "/sd/gps_log_A_{}.csv".format(timestamp)
            raw_accel_file = "/sd/accel_raw_A_{}.csv".format(timestamp)
            print("Log file: " + log_file)
            print("Raw accel file: " + raw_accel_file)
        else:
            print("Waiting for GPS fix to create log file...")
            sleep(1)
            pycom.rgbled(0x000080)
            sleep(0.5)
            pycom.rgbled(0x000000)
            sleep(0.5)

    # Write CSV headers
    with open(log_file, "w") as f:
        f.write(CSV_HEADER)
    with open(raw_accel_file, "w") as f:
        f.write(RAW_ACCEL_HEADER)
    # --------------------------------

    pycom.rgbled(0x000080)
    print("System Startup - Device A")

    gps_count = 0
    last_logged_utc = None

    # Split the burst budget half before / half after the GPS read so the
    # accel stream covers the whole loop wall-clock window evenly.
    n_before = ACCEL_SENDS_PER_LOOP // 2
    n_after = ACCEL_SENDS_PER_LOOP - n_before

    while True:
        try:
            print("\nReading Sensors...")

            # --- Half of the accel bursts BEFORE the GPS read ---
            accel_data, accel_count = run_accel_bursts(
                accel_sensor, lora_tx, raw_accel_file,
                n_before, ACCEL_BURST_MS, accel_count,
                gps_data_for_utc=last_gps,
            )

            # --- GPS read (typically ~1-2 s, capped at 5 s) ---
            gps_data = gps_sensor.read()
            if gps_data and gps_data.get('utc_time') and gps_data.get('utc_date'):
                last_gps = gps_data

            # --- Other half of the accel bursts AFTER the GPS read ---
            accel_data, accel_count = run_accel_bursts(
                accel_sensor, lora_tx, raw_accel_file,
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

                # Dedup: skip if the parser didn't see a fresh fix this read
                # cycle, or if this UTC time has already been logged.
                if (not gps_data.get('new_fix', False)
                        or gps_data['utc_time'] == last_logged_utc):
                    pycom.rgbled(0x000080)
                    continue

                last_logged_utc = gps_data['utc_time']

                # GPS LoRa send is DISABLED.  Device A's GPS now lives
                # exclusively in the SD log (gps_log_A_*.csv); the PC
                # log is fed only by the spoofer's GPS stream + A's
                # accel stream, and the legit + spoof datasets are
                # merged offline using the Accel UTC anchor.
                #
                # Why: A and B both transmit GPS on 868.1 MHz.  When
                # both transmit at the same time the LoRa packets
                # collide and one (usually A's) is destroyed, which
                # caused ~47 % legit-GPS packet loss in the previous
                # walks.  Removing A's GPS LoRa send leaves 868.1 MHz
                # exclusively to the spoofer, which is what the demo
                # is meant to show anyway.
                #
                # To re-enable: uncomment the four send_gps lines below
                # and delete the gps_ok=True / gps_count+=1 lines.
                # gps_ok = lora_tx.send_gps(gps_data, LABEL)
                # if gps_ok:
                #     gps_count += 1
                #     print("GPS sent ({})".format(gps_count))
                # else:
                #     print("GPS send failed")
                gps_ok = True
                gps_count += 1
                print("GPS captured to SD ({}, no LoRa)".format(gps_count))

                # LED feedback - blue means "row captured to SD".  Red
                # would only ever show on a future failure path; with
                # GPS LoRa disabled gps_ok is always True here.
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
