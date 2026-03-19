from machine import rng
import math


class GPSSpoofer:

    def __init__(self, delay_samples=5, noise_std=0.00002):

        # hvor mange gamle GPS-samples som lagres
        self.delay_samples = delay_samples

        # standardavvik for gaussian noise
        self.noise_std = noise_std

        # buffer for gamle koordinater
        self.buffer = []


    def uniform(self):
        """
        Lager et tilfeldig tall mellom 0 og 1
        ved hjelp av ESP32 hardware RNG
        """

        r = rng()

        # unngå log(0)
        if r == 0:
            r = 1

        return r / 0xFFFFFFFF


    def gaussian_noise(self):
        """
        Lager gaussisk støy ved hjelp av
        Box-Muller transform
        """

        u1 = self.uniform()
        u2 = self.uniform()

        z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)

        return z * self.noise_std


    def add_real_position(self, lat, lon, alt):
        """
        Legger ny ekte GPS-posisjon i buffer.
        Returnerer spoofed posisjon når buffer er full.
        """

        # lagre ny GPS
        self.buffer.append((lat, lon, alt))

        # hvis ikke nok samples enda
        if len(self.buffer) <= self.delay_samples:
            return None

        # hent eldste posisjon (delay spoofing)
        lat, lon, alt = self.buffer.pop(0)

        # legg til gaussian noise
        lat += self.gaussian_noise()
        lon += self.gaussian_noise()
        alt += self.gaussian_noise()

        return lat, lon, alt