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
    if gps_data['hdop'] > 5.0:
        return False
    if gps_data['sats'] < 4 or gps_data['sats'] > 32:
        return False
    if (not 50.0 < gps_data['lat'] < 72.0): # Norway bounds
        return False
    if not (4.0 < gps_data['lon'] < 32.0): # Norway bounds
        return False
    return True

# Read mode, returs 'record' or 'replay'
def read_mode():
    try:
        f = open('/sd/mode.txt', 'r')
        content = f.read().strip()
        f.close()
        
        if content == 'record':
            return 'record', None
        elif content.startswith('replay'):
            filename = content.split(':', 1)[1].strip()
            return 'replay', filename
        else:
            print("Invalid mode.txt, defaulting to record")        
            return 'record', None
        
    except Exception:
        print("No mode.txt found, defaulting to record")
        return 'record', None


    
def load_replay_route(filename):
    # Load the recorded GPS route from /sd/route.csv into memory

    route = []
    try:
        f = open('/sd/{}'.format(filename), 'r')
        lines = f.read().split('\n')
        f.close()

        # Skip header
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
                    'lat' : lat,
                    'lon' : lon,
                    'alt' : alt,
                    'speed' : speed,
                    'hdop' : hdop,
                    'sats' : sats,
                    'course' : course,
                    'fix' : fix
                })
            except Exception as e:
                print("Skipping bad route line:", e)
                continue

        print("Loaded {} route points".format(len(route)))
        return route
    
    except Exception as e:
        print("Failed to load route:", e)
        return[]
    
def run_record(gps_sensor, lora_tx):
    """
    Record mode, saves real GPS to /sd/route.csv.
    No LoRa transmission. LED = green while recording. 
    """
    print("Mode: RECORD")
    
    # Wait for fix before creating file
    gps_data = None
    while gps_data is None:
        gps_data = gps_sensor.read()
        if gps_data and gps_data['fix'] > 0 and gps_data['utc_date'] and gps_data['utc_time']:
            pycom.rgbled(0x000080)
            print("GPS Fix aquierd")
            break
        print("Waiting for GPS fix...")
        gps_data = None
        pycom.rgbled(0x000080)
        sleep(0.5)
        pycom.rgbled(0x000000)
        sleep(0.5)
        
    # Create timestamped file
    timestamp = "{}_{:.0f}".format(gps_data['utc_date'], float(gps_data['utc_time']))
    route_file = "/sd/route_{}.csv".format(timestamp)
    print("Route file: " + route_file)

    with open(route_file, 'w') as f:
        f.write("utc_time,lat,lon,alt,speed,hdop,sats,course,fix\n")
        
    pycom.rgbled(0x008000)      # Green = recording    
        
    
    count = 0
    while True:
        gps_data = gps_sensor.read()

        if gps_data and gps_data['fix'] > 0 and is_valid_gps(gps_data):
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
                count += 1
                
                print("Recorded point {}: {:.6f}, {:.6f}".format(count, gps_data['lat'], gps_data['lon']))
            except Exception as e:
                print("Record write error:", e)
        else:
            print("waiting for GPS fix...")
            pycom.rgbled(0x000080)
            sleep(0.5)
            pycom.rgbled(0x000000)
            sleep(0.5)
            continue
        sleep(1)

def run_replay(gps_sensor, lora_tx, filename):
    """ 
    Replay mode, loop through recorded route and send GPS-only packets.
    No accelerometer packets sent. LED = red while replaying
    """

    print("MODE: REPLAY")

    route = load_replay_route(filename)
    if not route:
        print("No route loaded, switch record mode first.")
        return
    
    print("Replayiong {} points on loop. Ctrl+C to stop".format(len(route)))
    pycom.rgbled(0x800000)      # RED = Replay spoofing


    packet_count = 0
    idx = 0
    direction = 1

    while True:
        # Loop route continuesly

        gps_data = route[idx]       # Read current point
        idx += direction            # Then advance
        
        # Check boundries and flip if needed. 
        if idx >= len(route):
            idx = len(route) - 2
            direction = -1
            print("Route reversing...")
        elif idx < 0:
            idx = 1
            direction = 1
            print("Route reversing")
        
        # Send GPS packet over LoRa, no accel
        success = lora_tx.send_gps(gps_data, LABEL)

        if success:
            packet_count += 1
            print("Replayed point  {}/{} - {:.6f}, {:.6f}".format(idx, len(route), gps_data['lat'], gps_data['lon']))

        else:
            print("Send Failed")
        
        if packet_count > 0 and packet_count % 10 == 0:
            stats = lora_tx.get_stats()
            print("Stats", stats)

        sleep(1)


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

    # LED setup
    pycom.heartbeat(False)
    pycom.rgbled(0x000080)

    print("Device B starting...")

    # Read mode from SD card
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
        print("Final stats: ", stats)

    except Exception as e:
        print("Error: ", e)
        pycom.rgbled(0xFF0000)


if __name__ == '__main__':
    main()