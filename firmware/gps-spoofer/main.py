import os
import pycom
from machine import SD

from Common_library.Pycoproc import Pycoproc
from Common_library.L76GNSS import L76GNSS
from Common_library.GpsParser import GpsParser
from Common_library.LoRaTx import LoRaTx

from GPS_spoofer.ModeReader import ModeReader
from GPS_spoofer.RouteRecorder import RouteRecorder
from GPS_spoofer.RouteReplayer import RouteReplayer


# 1 = spoof label byte
SPOOF_LABEL = 1


def _mount_sd():
    sd = SD()
    try:
        os.mount(sd, '/sd')
    except OSError as e:
        print("SD mount note:", e)


def main():
    py = Pycoproc(Pycoproc.PYTRACK)
    l76 = L76GNSS(py, timeout=60)
    gps = GpsParser(l76)
    lora_tx = LoRaTx(tx_power=14, spreading_factor=10)

    _mount_sd()

    pycom.heartbeat(False)
    pycom.rgbled(0x000080)
    print("Device B starting...")

    mode, filename = ModeReader().read_mode()
    print("Mode: " + mode)

    try:
        if mode == 'record':
            RouteRecorder(gps).run()

        elif mode == 'replay':
            replayer = RouteReplayer(lora_tx, label=SPOOF_LABEL)
            if replayer.load_route(filename):
                replayer.run()
            else:
                pycom.rgbled(0xFF0000)

        else:
            print("Unknown mode: {}".format(mode))
            pycom.rgbled(0xFF0000)

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
