# KPI Analytics Domain Kit
# Validate customer KPI implementations against deterministic baselines
# with tolerance-based comparison

from .runner import KPIRunner
from .normalizer import KPINormalizer
from .comparator_config import ComparatorConfig
from .error_taxonomy import KPIErrorTaxonomy

__all__ = ['KPIRunner', 'KPINormalizer', 'ComparatorConfig', 'KPIErrorTaxonomy']
__version__ = '1.0.0'
