"""
Baseline KPI: Total Profit

Ground truth implementation that correctly sums all profit values.
"""

import pandas as pd


def compute_kpi(df: pd.DataFrame):
    """
    Compute baseline KPI: total profit across all orders.
    
    Args:
        df: DataFrame with required columns: Country, order_year, Profit
    
    Returns:
        float: Sum of Profit column
    """
    return float(df['Profit'].sum())
