"""
KPI Error Taxonomy

Classify KPI computation errors in business language (for customer communication).

All errors fall into 6 categories, each with:
- severity: 'critical' | 'high' | 'medium'
- pattern: What went wrong technically
- business_impact: What it means for the customer's KPI
"""


class KPIErrorTaxonomy:
    """Map error patterns to business-relevant categories."""
    
    CATEGORIES = {
        'aggregation_error': {
            'severity': 'critical',
            'pattern': 'SUM vs MEAN mismatch, COUNT issue in aggregation',
            'example': 'Using .sum() on string column instead of numeric',
            'business_impact': 'Incorrect totals or aggregates; report undercounted or overcounted'
        },
        'groupby_error': {
            'severity': 'critical',
            'pattern': 'Wrong column in groupby, missing groupby entirely, or groupby key mismatch',
            'example': 'Grouping by Customer_ID instead of Region; results split incorrectly',
            'business_impact': 'Segmentation is wrong; metrics are broken down by incorrect dimension'
        },
        'filter_error': {
            'severity': 'critical',
            'pattern': 'Filter applied at wrong stage (before vs after groupby), wrong operator (AND vs OR)',
            'example': 'Filtering after aggregation loses data; using >= instead of >',
            'business_impact': 'Subset of data is wrong; metrics exclude or include wrong rows'
        },
        'dtype_coercion_error': {
            'severity': 'high',
            'pattern': 'String-to-number conversion fails, NaN/null handling, type mismatch',
            'example': 'Trying to add string "$100" to number 50 without stripping currency',
            'business_impact': 'Output type is wrong; metric becomes string instead of number'
        },
        'computation_error': {
            'severity': 'high',
            'pattern': 'Division by zero, NaN propagation, math error',
            'example': 'Computing profit_margin = profit / revenue when revenue=0 for some rows',
            'business_impact': 'NaN/Inf values appear; metric cannot be aggregated or compared'
        },
        'numeric_drift': {
            'severity': 'medium',
            'pattern': 'Output numeric but differs from baseline beyond tolerance',
            'example': 'Candidate=1000.5, baseline=1000.0, drift=0.05% (within tolerance but noted)',
            'business_impact': 'Calculation is slightly different; check if rounding or logic changed'
        }
    }
    
    @classmethod
    def classify(cls, error_code: str) -> dict:
        """
        Retrieve category info for an error.
        
        Args:
            error_code: One of the 6 category keys
        
        Returns:
            Dict with severity, pattern, example, business_impact
        """
        if error_code in cls.CATEGORIES:
            return cls.CATEGORIES[error_code]
        else:
            return {
                'severity': 'unknown',
                'pattern': 'Unknown error category',
                'example': '',
                'business_impact': 'See logs for details'
            }
    
    @classmethod
    def all_categories(cls) -> list:
        """Return list of all error category names."""
        return list(cls.CATEGORIES.keys())
    
    @classmethod
    def severity_level(cls, error_code: str) -> str:
        """Get severity of an error category."""
        return cls.classify(error_code).get('severity', 'unknown')
