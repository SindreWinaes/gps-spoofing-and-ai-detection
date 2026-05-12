#
# LGBMClassifier.py
# Thin wrapper around lightgbm's sklearn-style LGBMClassifier. Present in
# the EA model to document the dependency; all training and prediction
# logic comes from lightgbm itself.
#
# Usage stays identical to lightgbm:
#     from Pc_backend.Ml_pipeline.LGBMClassifier import LGBMClassifier
#     model = LGBMClassifier(objective='binary', num_leaves=31, ...)
#     model.fit(X_tr, y_tr)
#     y_pred = model.predict(X_val)
#

import lightgbm as _lgb


class LGBMClassifier(_lgb.LGBMClassifier):
    """Re-export of lightgbm.LGBMClassifier so the EA model has a concrete
    class to point at. fit(), predict() and predict_proba() come straight
    from lightgbm - no behaviour changes.
    """
    pass
