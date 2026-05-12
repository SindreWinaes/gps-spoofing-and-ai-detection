#
# RandomForestClassifier.py
# Thin wrapper around sklearn's RandomForestClassifier. Present in the
# EA model to document the dependency, and because the UbiQTree explainer
# needs a tree-ensemble classifier with an `estimators_` attribute - RF
# is the natural choice for that.
#
# Usage stays identical to sklearn:
#     from Pc_backend.Ml_pipeline.RandomForestClassifier import RandomForestClassifier
#     rf = RandomForestClassifier(n_estimators=100, random_state=42)
#     rf.fit(X_tr, y_tr)
#     y_pred = rf.predict(X_val)
#

from sklearn.ensemble import RandomForestClassifier as _SklearnRandomForestClassifier


class RandomForestClassifier(_SklearnRandomForestClassifier):
    """Re-export of sklearn.ensemble.RandomForestClassifier so the EA model
    has a concrete class to point at. All fit / predict behaviour comes
    from sklearn unchanged.

    The `estimators_` list and `classes_` array shown in the EA diagram
    are produced by sklearn after fit() and used by UbiQTree's
    ExplainerClassification to compute per-tree weights.
    """
    pass
