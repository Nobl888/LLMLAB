"""
KPI Comparator Configuration

Define how baseline vs candidate KPI outputs should be compared.
"""


class ComparatorConfig:
    """Configuration for KPI comparison rules."""
    
    # DEFAULT: Strict (for exact-match KPIs like counts)
    numeric_tolerance = 0
    tolerance_mode = "relative"  # "relative" or "absolute"
    
    @classmethod
    def for_count_metrics(cls):
        """
        Config for exact-match metrics (counts, inventory, IDs).
        No tolerance: 0% drift allowed.
        """
        config = cls()
        config.numeric_tolerance = 0.0  # Exact match required
        return config
    
    @classmethod
    def for_profit_metrics(cls):
        """
        Config for profit/revenue KPIs.
        Allow small rounding errors (1 cent per $1000).
        """
        config = cls()
        config.numeric_tolerance = 0.0001  # 0.01% drift
        return config
    
    @classmethod
    def for_aggregation_metrics(cls):
        """
        Config for COUNT/SUM/MEAN aggregations.
        Stricter: 0.5% drift.
        """
        config = cls()
        config.numeric_tolerance = 0.005
        return config
    
    @classmethod
    def for_percentage_metrics(cls):
        """
        Config for percentage/ratio KPIs.
        Allow 1 percentage point absolute drift (not relative).
        
        For 0-1 scale (ratios): 0.01 absolute tolerance
        For 0-100 scale (percentages): 1.0 absolute tolerance
        """
        config = cls()
        config.numeric_tolerance = 1.0  # 1 percentage point
        config.tolerance_mode = "absolute"
        return config
    
    def to_dict(self) -> dict:
        """Export config as dict for API responses."""
        return {
            'numeric_tolerance': self.numeric_tolerance,
            'tolerance_mode': self.tolerance_mode
        }
