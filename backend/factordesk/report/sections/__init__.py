"""Optional report sections of the schema v3 contract (``docs/specs/schema-v3-contract.md``).

One module per feature, each defining exactly one section model and one ``SectionSpec``:

* ``fragility.py``: ``FragilitySection`` (``docs/specs/fragility-score.md``)
* ``lead_lag.py``: ``LeadLagSection`` (``docs/specs/lead-lag-betas.md``)
* ``kalman.py``: ``KalmanBetaSeries`` (``docs/specs/kalman-betas.md``)
* ``shrunk.py``: ``ShrunkBetas`` (``docs/specs/shrunk-betas.md``)
* ``residual_alpha.py``: ``ResidualAnalysis`` (``docs/methodology-residual-analysis.md``)

Each module is owned by its feature branch; ``schema.py`` imports each one with one statement.
"""
