import pycom
import time
from time import sleep
from pycoproc import Pycoproc
from L76GNSS import L76GNSS
from GPSSensor import GPSSensor
from LoRaTx import LoRaTx

from machine import SD
import os


# Device B identity. Used as:
#   - the `Label` column in the record-mode CSV (1 = "this device's data,
#     intended for replay/spoof transmission"; legit Device A uses 0).
#   - the label byte sent in every replayed GPS LoRa packet, so the PC
#     receiver can mark each row 0 (legit) vs 1 (spoof) for ML training.
LABEL = 1


# Record-mode CSV header MUST be the exact GPS-only subset of Device A's
# header in firmware/gps-reciever/main.py, in the same order, with the same
# capitalisation and the same ", " separator style, so the two CSV streams
# can be concatenated/compared without column-name juggling.
RECORD_CSV_HEADER = (
    "Time, UTC Date, UTC Time, Label, Latitude, Longitude, Altitude,"
    " Speed, HDOP, Satelites, Course, Fix\n"
)


def is_valid_gps(gps_data):
    if gps_data['fix'] not in [1, 2]:
        return False
    if gps_data['hdop'] is None or gps_data['hdop'] > 10.0:
        return False
    if gps_data['sats'] < 3 or gps_data['sats'] > 24:
        return False
    if not (50.0 < gps_data['lat'] < 72.0):  # Norway bounds
        return False
    if not (4.0 < gps_data['lon'] < 32.0):   # Norway bounds
        return False
    return True


def build_record_line(gps_data, label):
    """
    Build one CSV row for record mode.

    Same comma-no-space data-row style as Device A's build_log_line(),
    so a row from this device parses with the same CSV reader code as
    a row from Device A (just with the accel columns absent).
    """
    return "{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
        time.time(),
        gps_data.get('utc_date', ''),
        gps_data['utc_time'],
        label,
        gps_data['lat'],
        gps_data['lon'],
        gps_data['alt'],
        gps_data['speed'],
        gps_data['hdop'],
        gps_data['sats'],
        gps_data['course'],
        gps_data['fix']
    )


def read_mode():
    """
    Read mode.txt from SD card.
    Format: 'record' or 'replay:filename.csv'
    """
    try:
        f = open('/sd/mode.txt', 'r')
        content = f.read().strip()
        f.close()

        if content == 'record':
            return 'record', None
        elif content.startswith('replay:'):
            filename = content.split(':', 1)[1].strip()
            return 'replay', filename
        else:
            print("Invalid mode.txt, defaulting to record")
            return 'record', None

    except Exception:
        print("No mode.txt found, defaulting to record")
        return 'record', None


def load_replay_route(filename):
    """
    Load a recorded GPS route from SD card into memory.

    Three header layouts are accepted so old route files still replay:
      1. NEW (Device-A-aligned, 12 cols):
         "Time, UTC Date, UTC Time, Label, Latitude, Longitude, Altitude,
          Speed, HDOP, Satelites, Course, Fix"
      2. MID (10 cols): "utc_date,utc_time,lat,lon,alt,speed,hdop,sats,course,fix"
      3. OLD (9 cols):  "utc_time,lat,lon,alt,speed,hdop,sats,course,fix"
    """
    route = []
    try:
        f = open('/sd/{}'.format(filename), 'r')
        lines = f.read().split('\n')
        f.close()

        if not lines:
            print("Empty route file")
            return []

        header = lines[0].strip().lower()
        # Header detection - look for distinguishing column names.
        # The new header has both "label" and "latitude"; the mid header
        # has "utc_date" but no "label"; the old has only "utc_time".
        if 'label' in header and 'latitude' in header:
            schema = 'new'   # Time, UTC Date, UTC Time, Label, Latitude, ...
        elif 'utc_date' in header:
            schema = 'mid'   # utc_date,utc_time,lat,...
        else:
            schema = 'old'   # utc_time,lat,...
        print("Route header schema: {}".format(schema))

        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            try:
                parts = [p.strip() for p in line.split(',')]
                if schema == 'new':
                    # Time(0), UTC Date(1), UTC Time(2), Label(3),
                    # Lat(4), Lon(5), Alt(6), Speed(7), HDOP(8),
                    # Sats(9), Course(10), Fix(11)
                    utc_date = parts[1]
                    utc_time = parts[2]
                    lat   = float(parts[4])
                    lon   = float(parts[5])
                    alt   = float(parts[6])
                    speed = float(parts[7])
                    hdop  = float(parts[8])
                    sats  = int(parts[9])
                    course = float(parts[10])
                    fix   = int(parts[11])
                elif schema == 'mid':
                    utc_date = parts[0]
                    utc_time = parts[1]
                    lat   = float(parts[2])
                    lon   = float(parts[3])
                    alt   = float(parts[4])
                    speed = float(parts[5])
                    hdop  = float(parts[6])
                    sats  = int(parts[7])
                    course = float(parts[8])
                    fix   = int(parts[9])
                else:  # old
                    utc_date = ''
                    utc_time = parts[0]
                    lat   = float(parts[1])
                    lon   = float(parts[2])
                    alt   = float(parts[3])
                    speed = float(parts[4])
                    hdop  = float(parts[5])
                    sats  = int(parts[6])
                    course = float(parts[7])
                    fix   = int(parts[8])

                route.append({
                    'utc_date': utc_date,
                    'utc_time': utc_time,
                    'lat': lat,
                    'lon': lon,
                    'alt': alt,
                    'speed': speed,
                    'hdop': hdop,
                    'sats': sats,
                    'course': course,
                    'fix': fix
                })
            except Exception as e:
                print("Skipping bad route line:", e)
                continue

        print("Loaded {} route points".format(len(route)))
        return route

    except Exception as e:
        print("Failed to load route:", e)
        return []


def wait_for_fix(gps_sensor):
    """
    Wait for GPS fix. GPSSensor.read() blocks for ~1 sec internally so no
    extra inter-poll sleep is needed.
    LED: blinks blue while waiting.
    """
    print("Waiting for GPS fix...")
    blink_state = False

    while True:
        gps_data = gps_sensor.read()

        if gps_data and gps_data['fix'] > 0 and gps_data['utc_date'] and gps_data['utc_time']:
            print("GPS fix acquired (sats={}, hdop={})".format(
                gps_data['sats'], gps_data['hdop']))
            pycom.rgbled(0x000080)  # Solid blue
            return gps_data

        blink_state = not blink_state
        pycom.rgbled(0x000080 if blink_state else 0x000000)


def run_record(gps_sensor, lora_tx):
    """
    Record mode - saves real GPS to a timestamped CSV on SD card.
    No LoRa transmission.

    The CSV header and row format match Device A's GPS-only columns
    EXACTLY, so the two devices' logs are directly comparable.

    Record-mode Label column = 0 (recording is legitimate GPS data; the
    LABEL=1 spoof identity only takes effect during replay transmission).

    LED:
        blink blue = waiting for GPS fix
        solid blue = recording good data
    """
    print("Mode: RECORD")

    # Wait for first GPS fix before naming the file.
    gps_data = wait_for_fix(gps_sensor)

    timestamp = "{}_{:.0f}".format(
        gps_data.get('utc_date', '000000'),
        float(gps_data['utc_time'])
    )
    route_file = "/sd/route_{}.csv".format(timestamp)
    print("Route file: " + route_file)

    with open(route_file, 'w') as f:
        f.write(RECORD_CSV_HEADER)

    pycom.rgbled(0x000080)
    print("Recording started. Ctrl+C to stop")

    count = 0
    last_recorded_utc = None

    while True:
        gps_data = gps_sensor.read()

        # Skip if the parser didn't produce a new fix this read cycle.
        if not gps_data.get('new_fix', False):
            sleep(1)
            continue

        # Skip duplicates - only record when UTC time advances.
        if gps_data['utc_time'] == last_recorded_utc:
            sleep(1)
            continue

        if gps_data['fix'] > 0 and is_valid_gps(gps_data):
            pycom.rgbled(0x000080)
            try:
                with open(route_file, 'a') as f:
                    # Record-mode Label = 0 (legit-quality recording).
                    f.write(build_record_line(gps_data, 0))
                last_recorded_utc = gps_data['utc_time']
                count += 1
                print("Recorded point {}: {:.6f}, {:.6f}".format(
                    count, gps_data['lat'], gps_data['lon']))
            except Exception as e:
                print("Record write error:", e)
        else:
            if gps_data is None or gps_data['fix'] < 1:
                print("No GPS fix")
                pycom.rgbled(0x000080)
                sleep(0.5)
                pycom.rgbled(0x000000)
                sleep(0.5)
            else:
                print("GPS data filtered (HDOP={}, sats={})".format(
                    gps_data.get('hdop', '?'), gps_data.get('sats', '?')))

        sleep(1)


def run_replay(gps_sensor, lora_tx, filename):
    """
    Replay mode - loops through the recorded route and sends GPS-only
    LoRa packets with label=LABEL (=1, "spoofed").
    No accelerometer packets sent.

    LED:
        solid red = actively replaying/spoofing
        blink red = send failure
    """
    print("Mode: REPLAY")

    route = load_replay_route(filename)
    if not route:
        print("No route loaded. Check filename in mode.txt.")
        return

    print("Replaying {} points on loop. Ctrl+C to stop".format(len(route)))

    pycom.rgbled(0x800000)

    packet_count = 0
    idx = 0
    direction = 1

    while True:
        gps_data = route[idx]
        idx += direction

        # Bounce at boundaries so we never go off-array.
        if idx >= len(route):
            idx = len(route) - 2 if len(route) > 1 else 0
            direction = -1
            print("Route reversing...")
        elif idx < 0:
            idx = 1 if len(route) > 1 else 0
            direction = 1
            print("Route reversing...")

        success = lora_tx.send_gps(gps_data, LABEL)

        if success:
            packet_count += 1
            pycom.rgbled(0x800000)
            print("Replayed point {}/{} - {:.6f}, {:.6f}".format(
                idx, len(route), gps_data['lat'], gps_data['lon']))
        else:
            print("Send failed")
            pycom.rgbled(0x000000)
            sleep(0.1)
            pycom.rgbled(0x800000)

        if packet_count > 0 and packet_count % 10 == 0:
            stats = lora_tx.get_stats()
            print("Stats:", stats)

        sleep(2.5)


def main():
    # Init Pytrack
    py = Pycoproc(Pycoproc.PYTRACK)
    l76 = L76GNSS(py, timeout=60)
    gps_sensor = GPSSensor(l76)

    # Init LoRa
    lora_tx = LoRaTx(tx_power=14, spreading_factor=10)

    # Init SD card. 'already mounted' after a soft reset raises here -
    # ignore so we can keep running; any real SD failure surfaces on first I/O.
    sd = SD()
    try:
        os.mount(sd, '/sd')
    except OSError as e:
        print("SD mount note:", e)

    pycom.heartbeat(False)
    pycom.rgbled(0x000080)  # Blue = booting

    print("Device B starting...")

    mode, filename = read_mode()
    print("Mode: " + mode)

    try:
        if mode == 'record':
            run_record(gps_sensor, lora_tx)
        elif mode == 'replay':
            run_replay(gps_sensor, lora_tx, filename)

    except KeyboardInterrupt:
        print("\nStopping...")
        stats = lora_tx.get_stats()
        print("Final stats:", stats)
        pycom.rgbled(0x000000)

    except Exception as e:
        print("Error:", e)
        pycom.rgbled(0xFF0000)


if __name__ == '__main__':
    main()
