"""Serving-side copies of the training notebook's feature and model code.

The notebook trains and evaluates; step 8 saves the chosen models as plain-JSON bundles plus a
parity fixture (200 real states with the notebook's probabilities). The API imports this package,
and tests/test_parity_fixture.py proves it reproduces the notebook's numbers.
"""

__version__ = "1.0.0"
