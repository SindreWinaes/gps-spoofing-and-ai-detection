#
# ExplainerClassification.py
# Thin wrapper around UBiQTree's ExplainerClassification. The EA model
# lists this as one of our classes to document the dependency; all the
# uncertainty-quantification logic comes from the UBiQTree library.
#
# UBiQTree adds uncertainty bounds to SHAP-style explanations by
# Dirichlet-resampling trees in a random-forest ensemble. The result is
# not just a single SHAP value per feature, but a distribution -
# mean, std, CIs and entropy. We use it as a second ranking signal next
# to plain SHAP so the final feature selection is more robust.
#
# Usage stays identical to UBiQTree:
#     from Pc_backend.Ml_pipeline.ExplainerClassification import ExplainerClassification
#     ec = ExplainerClassification(rf_model, X_train, y_train, beta=5.0, random_state=42)
#     result = ec.explain(x_row, n_samples=500, alpha=1.0, class_idx=1)
#
# Repo: https://github.com/dubeyakshat07/UBiQTree
#

from UBiQTree.classification import ExplainerClassification as _UbiQExplainerClassification


class ExplainerClassification(_UbiQExplainerClassification):
    """Re-export of UBiQTree.classification.ExplainerClassification so the
    EA model has a concrete class to point at. No behaviour changes -
    __init__, explain(), and the plot_uncertainty_* methods come straight
    from UBiQTree.
    """
    pass
