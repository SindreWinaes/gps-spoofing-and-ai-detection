#
# GpsParser.py
# Wraps the L76GNSS driver and parses NMEA into a typed GPS fix dict.
#

import time
from time import sleep


class GpsParser:

    def __init__(self, gps):
        # gps is an L76GNSS driver instance from the Pycom library
        self.gps = gps

        # Position in decimal degrees
        self.lat = None
        self.lon = None
        self.alt = None

        # GPS-derived speed in km/h (computed from position deltas, can be noisy)
        self.speed = None

        # HDOP: lower = better fix accuracy
        self.hdop = None

        # Fix metadata
        self.num_sats = 0
        self.course = None
        self.fix_quality = 0

        self.utc_time = None
        self.utc_date = None

        # Set True when read() picks up a fix with a UTC time we haven't seen
        self._got_new_fix = False

    def read(self):
        # Read NMEA for up to 5 seconds, parse what we get, return a fix dict
        raw_data = b''
        self._got_new_fix = False

        start = time.time()

        while time.time() - start < 5:
            chunk = self.gps._read()
            raw_data += chunk.lstrip(b'\n\n').rstrip(b'\n\n')

            # ~500 bytes is usually one full NMEA sentence
            if len(raw_data) > 500:
                try:
                    decoded = raw_data.decode('ascii', 'ignore')
                    self._parse_raw_data(decoded)
                except Exception:
                    pass
                break

            sleep(0.1)

        return {
            'lat': self.lat,
            'lon': self.lon,
            'alt': self.alt,
            'speed': self.speed,
            'hdop': self.hdop,
            'sats': self.num_sats,
            'course': self.course,
            'fix': self.fix_quality,
            'utc_time': self.utc_time,
            'utc_date': self.utc_date,
            'new_fix': self._got_new_fix,
        }

    def _parse_raw_data(self, data):
        for line in data.replace('\r', '').split('\n'):
            # Only parse complete sentences starting with $
            if not line.startswith('$'):
                continue

            # Drop checksum so the last field doesn't get junk appended
            if '*' in line:
                line = line[:line.index('*')]

            try:
                if 'GGA' in line:
                    self._parse_gga(line)
                elif 'RMC' in line:
                    self._parse_rmc(line)
                elif 'VTG' in line:
                    self._parse_vtg(line)
            except:
                pass

    def _parse_gga(self, line):
        # GGA gives position, fix quality, sat count, HDOP, altitude
        p = line.split(',')

        if len(p) >= 15:
            if p[1] and len(p[1]) >= 9:
                # New fix only when UTC time advances
                old_time = self.utc_time
                self.utc_time = p[1]   # HHMMSS.SSS
                if self.utc_time != old_time:
                    self._got_new_fix = True

            if p[2] and p[4]:
                self.lat = self._conv(p[2], p[3])
                self.lon = self._conv(p[4], p[5])

            if p[6]:
                self.fix_quality = int(p[6])

            if p[7]:
                sats = int(p[7])
                # No GNSS constellation shows more than ~24 sats at once
                if 0 <= sats <= 24:
                    self.num_sats = sats

            if p[8]:
                hdop = float(p[8])
                # Valid HDOP is roughly 0.5 to 50
                if 0.0 < hdop < 50.0:
                    self.hdop = hdop

            if p[9]:
                self.alt = float(p[9])

    def _parse_rmc(self, line):
        # RMC gives speed (knots), course, and UTC date
        p = line.split(',')

        if len(p) >= 10:
            if p[7]:
                speed = float(p[7]) * 1.852   # knots -> km/h
                if 0.0 <= speed < 500.0:
                    self.speed = speed

            if p[8]:
                course = float(p[8])
                if 0.0 <= course <= 360.0:
                    self.course = course

            if p[9] and len(p[9]) >= 6:
                self.utc_date = p[9]   # DDMMYY

    def _parse_vtg(self, line):
        # VTG gives speed in km/h directly (preferred over RMC's knots)
        p = line.split(',')

        if len(p) >= 8:
            if p[7]:
                speed = float(p[7])
                if 0.0 <= speed < 500.0:
                    self.speed = speed

    def _conv(self, val, direction):
        # NMEA DDMM.MMMM -> decimal degrees
        deg = float(val) // 100
        mins = (float(val) % 100) / 60
        r = deg + mins
        if direction in ['S', 'W']:
            r *= -1
        return r
