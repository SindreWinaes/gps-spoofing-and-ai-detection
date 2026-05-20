"""
live_classify.py
Top-level entry point for live GPS spoof classification.
"""

from Pc_backend.Runtime.Receiver import Receiver


# Which trained model to use for online classification.
# Pick one of:
#   "ml/models/shap"     - 7 features, SHAP-ranked
#   "ml/models/ubiqtree" - 8 features, UbiQTree-ranked
#   "ml/models/combined" - 8 features, fused ranking (best on last holdout)
# Set to None to disable classification - acts as a plain logger.
MODEL_BUNDLE = "ml/models/combined"

# UDP ports the gateways forward to. Match what gateway firmware sends.
GPS_PORT = 5000
ACCEL_PORT = 5001


if __name__ == "__main__":
    receiver = Receiver(
        udp_port_gps=GPS_PORT,
        udp_port_accel=ACCEL_PORT,
        model_bundle_path=MODEL_BUNDLE,
    )
    receiver.run()
