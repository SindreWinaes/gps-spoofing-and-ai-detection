#
# ModeReader.py
# Reads /sd/mode.txt to decide whether Device B should record a fresh
# route or replay a previously recorded one. Keeping this tiny so the
# operator can swap modes without re-flashing the device - just edit
# mode.txt on the SD card.
#
# mode.txt content:
#   "record"                       -> record a new route
#   "replay:<filename.csv>"        -> replay the named route from /sd
# Anything else (missing file, malformed content) -> falls back to record.
#


# Default file location on the Pytrack SD card
DEFAULT_MODE_PATH = '/sd/mode.txt'


class ModeReader:

    def __init__(self, path=DEFAULT_MODE_PATH):
        self.path = path

    def read_mode(self):
        # Returns (mode, filename). filename is None when mode == 'record'.
        try:
            f = open(self.path, 'r')
            content = f.read().strip()
            f.close()

            if content == 'record':
                return ('record', None)
            elif content.startswith('replay:'):
                filename = content.split(':', 1)[1].strip()
                return ('replay', filename)
            else:
                print("Invalid mode.txt, defaulting to record")
                return ('record', None)

        except Exception:
            print("No mode.txt found, defaulting to record")
            return ('record', None)
