"""Entry point for live GPS spoof classification."""

from Pc_backend.Runtime.Receiver import Receiver


MODEL_BUNDLE = "ml/models/combined"

GPS_PORT = 5000
ACCEL_PORT = 5001


if __name__ == "__main__":
    receiver = Receiver(
        udp_port_gps=GPS_PORT,
        udp_port_accel=ACCEL_PORT,
        model_bundle_path=MODEL_BUNDLE,
    )
    receiver.run()
