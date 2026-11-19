"""Static HTML panels of the optional report sections (schema v3 contract, SC3.3).

Importing this package registers each panel with ``panel_registry`` at its fixed position (SC4).
One module per feature, each owned by its feature branch; this file does not change when a
feature fills its panel in.
"""

from factordesk.report.panels import fragility as fragility
from factordesk.report.panels import kalman as kalman
from factordesk.report.panels import lead_lag as lead_lag
from factordesk.report.panels import performance as performance
from factordesk.report.panels import residual_alpha as residual_alpha
from factordesk.report.panels import shrunk as shrunk
from factordesk.report.panels import world_beta as world_beta
