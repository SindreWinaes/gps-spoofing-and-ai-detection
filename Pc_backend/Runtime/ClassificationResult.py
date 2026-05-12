#
# ClassificationResult.py
# What OnlineClassifier.classify() hands back: the predicted class
# (0 = legit, 1 = spoof), the model's confidence (probability for the
# predicted class), the exact features it used, and a wall-clock
# timestamp.
#

from dataclasses import dataclass, field


@dataclass
class ClassificationResult:
    prediction: int = -1
    confidence: float = 0.0
    features_used: dict = field(default_factory=dict)
    timestamp: str = ""
