#
# StandardScaler.py
# Thin wrapper around sklearn's StandardScaler. The EA model lists this
# as one of our classes to document the dependency; the actual fit /
# transform / fit_transform behaviour comes straight from sklearn.
#
# Usage stays identical to sklearn:
#     from Pc_backend.Ml_pipeline.StandardScaler import StandardScaler
#     scaler = StandardScaler()
#     X_scaled = scaler.fit_transform(X)
#

from sklearn.preprocessing import StandardScaler as _SklearnStandardScaler


class StandardScaler(_SklearnStandardScaler):
    """Re-export of sklearn.preprocessing.StandardScaler so the EA model has
    a concrete class to point at. No behaviour changes - fit(), transform()
    and fit_transform() come straight from sklearn.
    """
    pass
