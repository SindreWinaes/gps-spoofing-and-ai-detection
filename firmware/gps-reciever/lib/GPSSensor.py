import time
from time import sleep

class GPSSensor:
    
    def __init__(self, gps):
        
        # Store reference to the L76GNSS object
        self.gps = gps
        
        # GPS position in decimal degrees
        
        self.lat = None     # Positive/Negative = North/South
        self.lon = None     # Positive/Negative = East/West
        
        # Altitude - meter above sea level
        self.alt = None
        
        # GPS reported speed, compares postiions over time, not from actual velocity. Can have noise and show phantom mmovement.
        self.speed = None
        
        # Horizontal Dilution of Precission - Measure of GPS accuracy based on satelite geometry
        # Lower value = Better Accuracy
        self.hdop = None
        
        # Number of Satelites
        self.num_sats = 0
        # Course while moving        
        self.course = None
        
        # Quality indicator, should be >= 1
        self.fix_quality = 0

        self.utc_time = None
        self.utc_date = None
        
        
    def read(self):
        # byte string to store raw nmea (National Marine Electronics Association) data
        raw_data = b''
        
        start = time.time()
        
        # Read for up to 5 seconds
        while time.time() - start < 5:
            chunk = self.gps._read()                                # _read() method from L76GNSS
            raw_data += chunk.lstrip(b'\n\n').rstrip(b'\n\n')       # Reads the data in small chunks
            
            
            # At 500 bytes we likely have one complete sentence
            if len (raw_data) > 500:
                
                # Decode raw bytes to ASCII string, ignoring invalid any invalid bytes
                # Then parses all the data (NMEA sentences) recieved
                self._parse_raw_data(raw_data.decode('ascii', 'ignore'))
                break
            sleep(0.1)
            
    
        # Return all parsed fields as a dictionay    
        return{
          'lat' : self.lat,
          'lon' : self.lon,
          'alt' : self.alt,
          'speed' : self.speed,
          'hdop' : self.hdop,
          'sats': self.num_sats,
          'course' : self.course,
          'fix' : self.fix_quality,
          'utc_time' : self.utc_time,
          'utc_date' : self.utc_date
          
        }
        
        
    def _parse_raw_data(self, data):
        for line in data.replace('\r', '').split('\n'):
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
        
        '''
        GGA sentences has a defined format with specific fields at specific positions. 
        
        $ Field positions (0-indexed after splitting by comma):
            [0] = Sentence ID ($GPGGA or $GNGGA)
            [1] = UTC time (HHMMSS.SSS)
            [2] = Latitude in DDMM.MMMM format
            [3] = N or S (North/South hemisphere)
            [4] = Longitude in DDDMM.MMMM format
            [5] = E or W (East/West hemisphere)
            [6] = Fix quality (0=none, 1=GPS, 2=DGPS)
            [7] = Number of satellites in use
            [8] = HDOP (Horizontal Dilution of Precision)
            [9] = Altitude above mean sea level in meters
            [10] = M (meters unit indicator)
        '''
        
        # Splits the sentence into fields separated by comma
        p = line.split(',')
        
        # Fileds 2-5: Latitude anf longtitude
        if len(p) >= 15:

            if p[1]:            
                self.utc_time = p[1]    # Format: HHMMSS.SSS        

            if p[2] and p[4]:
                self.lat = self._conv(p[2], p[3])
                self.lon = self._conv(p[4], p[5])
                
            # field 6: Fix quality    
            if p[6]:
                self.fix_quality = int(p[6])
                
            # field 7: Number of satelites used to calculate its positions
            if p[7]:
                self.num_sats = int(p[7])
            
            # fieled 8: Horizontal Dilutioon of Precission
            # Measures how the satelites geometry affects postition
            if p[8]:
                self.hdop = float(p[8])
                
            # Field 9: Altitude above sea level
            if p[9]:
                self.alt = float(p[9])
                
                
    def _parse_rmc(self, line):
        
        '''
        Parse RMC - Recomended Minimum Navigation data
        
        Key fields:
        [0] = Sentence ID ($GPRMC or $GNRMC)
        [1] = UTC time
        [2] = Status: A=active/valid, V=void/invalid
        [3-6] = Lat/lon (we already get this from GGA)
        [7] = Speed over ground in KNOTS (nautical miles per hour)
        [8] = Course over ground in degrees (0-360)
        [9] = Date (DDMMYY)
            
        '''
        
        p = line.split(',')
        
        
        if len(p) >= 8:
            # Field 7: Speed over ground in knots
            if p[7]:
                # Convert knots to km/h 
                self.speed = float(p[7]) * 1.852
                
            # Field 8: Course over ground    
            if p[8]:
                self.course = float(p[8])

            if p[9]:
                self.utc_date = p[9]    # Format: DDMMYY
        
                
                
    def _parse_vtg(self, line):
        
        '''
        Parse a VTG sentence - Velocity and track (course) info
        
       Key fields:
        [0] = Sentence ID ($GPVTG)
        [1] = Course over ground (true north) in degrees
        [2] = T (true)
        [3] = Course over ground (magnetic) in degrees
        [4] = M (magnetic)
        [5] = Speed in knots
        [6] = N (knots)
        [7] = Speed in km/h  <-- this is what we want
        [8] = K (km/h)
            
        '''        
        
        p = line.split(',')
        
        if len(p) >= 8:
            
            
            # Field 7: Speed over ground in km/h (no conversion needed)
            if p[7]:
                self.speed = float(p[7])
                
        
                
    def _conv(self, val, direction):
        '''
        Converts NMEA coordinates format to decimal degrees. 
        '''
        
        deg = float(val) // 100
        
        mins = (float(val) % 100) / 60
        
        r = deg + mins
        
        if direction in ['S', 'W']:
            r *= -1
            
        return r
    
    
            