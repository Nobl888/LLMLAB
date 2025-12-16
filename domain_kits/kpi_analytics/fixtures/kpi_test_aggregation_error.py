"""
Test KPI: Aggregation Error

Intentionally broken KPI that uses MEAN instead of SUM.
This tests error detection and classification.
"""

import pandas as pd


def compute_kpi(df: pd.DataFrame):
    """
    Compute KPI with aggregation error (MEAN instead of SUM).
    
    This is intentionally wrong to test:
    1. Mismatch detection (candidate != baseline)
    2. Error classification (aggregation_error)
    
    Args:
        df: DataFrame with required columns: Country, order_year, Profit
    
    Returns:
        float: Mean of Profit column (should be Sum)
    """
    return float(df['Profit'].mean())
