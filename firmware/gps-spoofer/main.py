import pycom
import time
from time import sleep
from pycoproc import Pycoproc
from L76GNSS import L76GNSS
from GPSSensor import GPSSensor
from LoRaTx import LoRaTx

from machine import SD
import os

LABEL = 1

def is_valid_gps(gps_data):
    if gps_data['fix'] not in [1,2]:
        return False
    if gps_data['hdop'] > 10.0:
        return False
    if gps_data['sats'] < 3 or gps_data['sats'] > 24:
        return False
    if (not 50.0 < gps_data['lat'] < 72.0): # Norway bounds
        return False
    if not (4.0 < gps_data['lon'] < 32.0): # Norway bounds
        return False
    return True

def read_mode():
    # Read mode.txt from SD card
    # Format: 'record' or 'replay:filename.csv'
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
    # Load recorded GPS route from SD card into memory
    route = []
    try:
        f = open('/sd/{}'.format(filename), 'r')
        lines = f.read().split('\n')
        f.close()

        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            try:
                parts = line.split(',')
                utc_time = parts[0]
                lat = float(parts[1])
                lon = float(parts[2])
                alt = float(parts[3])
                speed = float(parts[4])
                hdop = float(parts[5])
                sats = int(parts[6])
                course = float(parts[7])
                fix = int(parts[8])
                route.append({
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
    Wait for GPS fix. Reads as fast as possible without extra sleeps.
    The GPSSensor.read() already takes ~1s internally (accumulates 500 bytes),
    so no additional delay needed between attempts.

    LED: blinks blue while waiting
    """
    print("Waiting for GPS fix...")
    blink_state = False

    while True:
        gps_data = gps_sensor.read()

        if gps_data and gps_data['fix'] > 0 and gps_data['utc_date'] and gps_data['utc_time']:
            print("GPS Fix acquired (sats={}, hdop={})".format(
                gps_data['sats'], gps_data['hdop']))
            pycom.rgbled(0x000080)  # Solid blue
            return gps_data

        # Blink blue LED - toggle each read cycle (~1s from internal read timing)
        blink_state = not blink_state
        pycom.rgbled(0x000080 if blink_state else 0x000000)


def run_record(gps_sensor, lora_tx):
    """
    Record mode - saves real GPS to timestamped CSV on SD card.
    No LoRa transmission.

    LED states:
        Blink blue   = waiting for GPS fix
        Solid blue   = recording good data
    """
    print("Mode: RECORD")

    # Wait for GPS fix before creating file
    gps_data = wait_for_fix(gps_sensor)

    # Create timestamped route file
    timestamp = "{}_{:.0f}".format(gps_data['utc_date'], float(gps_data['utc_time']))
    route_file = "/sd/route_{}.csv".format(timestamp)
    print("Route file: " + route_file)

    with open(route_file, 'w') as f:
        f.write("utc_time,lat,lon,alt,speed,hdop,sats,course,fix\n")

    pycom.rgbled(0x000080)  # Solid blue = recording active
    print("Recording started. Ctrl+C to stop")

    count = 0
    last_recorded_utc = None

    while True:
        gps_data = gps_sensor.read()

        # Skip if no new GPS fix from the parser
        if not gps_data.get('new_fix', False):
            sleep(1)
            continue

        # Skip if we already recorded this UTC timestamp
        if gps_data['utc_time'] == last_recorded_utc:
            sleep(1)
            continue

        if gps_data['fix'] > 0 and is_valid_gps(gps_data):
            pycom.rgbled(0x000080)  # Solid blue
            try:
                with open(route_file, 'a') as f:
                    line = "{},{},{},{},{},{},{},{},{}\n".format(
                        gps_data['utc_time'],
                        gps_data['lat'],
                        gps_data['lon'],
                        gps_data['alt'],
                        gps_data['speed'],
                        gps_data['hdop'],
                        gps_data['sats'],
                        gps_data['course'],
                        gps_data['fix']
                    )
                    f.write(line)
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
    Replay mode - loops through recorded route sending GPS-only packets.
    No accelerometer packets sent.

    LED states:
        Solid red  = actively replaying/spoofing
        Blink red  = send failure
    """
    print("MODE: REPLAY")

    route = load_replay_route(filename)
    if not route:
        print("No route loaded. Check filename in mode.txt.")
        return

    print("Replaying {} points on loop. Ctrl+C to stop".format(len(route)))

    pycom.rgbled(0x800000)  # Solid red = spoofing active

    packet_count = 0
    idx = 0
    direction = 1

    while True:
        gps_data = route[idx]
        idx += direction

        # Bounce at boundaries
        if idx >= len(route):
            idx = len(route) - 2
            direction = -1
            print("Route reversing...")
        elif idx < 0:
            idx = 1
            direction = 1
            print("Route reversing...")

        success = lora_tx.send_gps(gps_data, LABEL)

        if success:
            packet_count += 1
            pycom.rgbled(0x800000)  # Solid red = sending
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

    # Init SD card
    sd = SD()
    os.mount(sd, '/sd')

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
        pycom.rgbled(0x000000)  # Turn off LED on clean exit

    except Exception as e:
        print("Error:", e)
        pycom.rgbled(0xFF0000)  # Red = unhandled error


if __name__ == '__main__':
    main()