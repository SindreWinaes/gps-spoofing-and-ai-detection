#
# ModelBundle.py
# A trained model + the scaler it was trained against + the feature
# list it expects, packaged as one unit so the runtime classifier
# doesn't have to load three files manually and risk pairing the wrong
# scaler with the wrong model.
#
# On disk, save()/load() use a directory layout matching the existing
# ml/models/ folder so old artifacts and new ones can be mixed:
#     <path>/model.txt         (LightGBM native format)
#     <path>/scaler.pkl        (pickled sklearn StandardScaler)
#     <path>/feature_list.json (model input columns, in order)
#     <path>/metadata.json     (track_name, timestamps, etc.)
#

import json
import os
import pickle
from dataclasses import dataclass, field

import lightgbm as lgb


@dataclass
class ModelBundle:
    model: object = None        # LGBMClassifier or lightgbm.Booster
    scaler: object = None       # StandardScaler
    feature_list: list = field(default_factory=list)
    track_name: str = ""

    def save(self, path):
        # `path` is a directory. Creates it if missing.
        os.makedirs(path, exist_ok=True)

        # LightGBM native format - portable across versions and
        # inspectable. Works for both sklearn-wrapped LGBMClassifier
        # (has .booster_) and a bare lightgbm.Booster.
        model_path = os.path.join(path, "model.txt")
        if hasattr(self.model, "booster_"):
            self.model.booster_.save_model(model_path)
        elif isinstance(self.model, lgb.Booster):
            self.model.save_model(model_path)
        else:
            raise ValueError(
                "ModelBundle.save: unsupported model type {}".format(type(self.model))
            )

        with open(os.path.join(path, "scaler.pkl"), "wb") as f:
            pickle.dump(self.scaler, f)

        with open(os.path.join(path, "feature_list.json"), "w") as f:
            json.dump(list(self.feature_list), f, indent=2)

        with open(os.path.join(path, "metadata.json"), "w") as f:
            json.dump({"track_name": self.track_name}, f, indent=2)

    @classmethod
    def load(cls, path):
        # Reads back the four files written by save(). The model comes
        # back as a lightgbm.Booster - that's the prediction-only form,
        # which is all the Evaluator needs.
        model = lgb.Booster(model_file=os.path.join(path, "model.txt"))

        with open(os.path.join(path, "scaler.pkl"), "rb") as f:
            scaler = pickle.load(f)

        with open(os.path.join(path, "feature_list.json")) as f:
            feature_list = json.load(f)

        meta_path = os.path.join(path, "metadata.json")
        track_name = ""
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                track_name = json.load(f).get("track_name", "")

        return cls(
            model=model,
            scaler=scaler,
            feature_list=feature_list,
            track_name=track_name,
        )
