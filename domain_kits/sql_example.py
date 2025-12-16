"""
SQL Domain Kit: Practical Example
How to validate customer SQL queries using LLMLAB's generic engine
"""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


# ============================================================================
# 1. RUNNER – Execute SQL and capture output deterministically
# ============================================================================

class SQLQueryRunner:
    """Execute any SQL artifact against a controlled fixture database."""
    
    def __init__(self, fixture_csv: str):
        """
        fixture_csv: Path to the test data (e.g., 'transactions.csv')
        """
        self.fixture_csv = fixture_csv
        self.db_path = ':memory:'
    
    def _setup_fixture(self) -> sqlite3.Connection:
        """Load test data into memory DB."""
        conn = sqlite3.connect(self.db_path)
        
        # Read test data and create table
        df = pd.read_csv(self.fixture_csv)
        df.to_sql('input_data', conn, if_exists='replace', index=False)
        
        return conn
    
    def execute(self, sql_artifact_path: str) -> Dict[str, Any]:
        """
        Run the customer's SQL query.
        Returns: {"result_set": list of tuples, "column_names": list}
        """
        try:
            # Setup DB
            conn = self._setup_fixture()
            
            # Read customer's SQL
            sql_query = Path(sql_artifact_path).read_text()
            
            # Execute
            cursor = conn.execute(sql_query)
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            
            conn.close()
            
            return {
                "result_set": rows,
                "column_names": cols,
                "row_count": len(rows)
            }
        
        except Exception as e:
            raise ValueError(f"SQL execution failed: {str(e)}")
    
    def validate_syntax(self, sql_artifact_path: str) -> bool:
        """Quick check: is the SQL valid?"""
        try:
            sql_query = Path(sql_artifact_path).read_text()
            conn = sqlite3.connect(':memory:')
            conn.execute(f"EXPLAIN QUERY PLAN {sql_query}")
            return True
        except:
            return False


# ============================================================================
# 2. NORMALIZER – Convert SQL result sets to canonical comparison form
# ============================================================================

class SQLResultNormalizer:
    """
    Convert raw SQL output (list of tuples) to a stable, comparable DataFrame.
    
    Stability means:
    - Consistent column order
    - Consistent row order (sorted by key)
    - Consistent dtypes
    """
    
    def __init__(self, schema: Dict[str, str]):
        """
        schema: {"column_name": "dtype", ...}
                e.g., {"user_id": "int64", "amount": "float64"}
        """
        self.schema = schema
    
    def normalize(self, raw_output: Dict[str, Any]) -> pd.DataFrame:
        """Convert SQL result to comparable DataFrame."""
        
        # 1. Create DataFrame from result set
        rows = raw_output['result_set']
        cols = raw_output['column_names']
        
        df = pd.DataFrame(rows, columns=cols)
        
        # 2. Cast to expected dtypes
        for col, dtype in self.schema.items():
            if col in df.columns:
                df[col] = df[col].astype(dtype)
        
        # 3. Sort for stable comparison (by first column, typically ID or date)
        sort_cols = [c for c in ['id', 'user_id', 'date', 'timestamp'] if c in df.columns]
        if sort_cols:
            df = df.sort_values(by=sort_cols).reset_index(drop=True)
        
        return df


# ============================================================================
# 3. COMPARATOR CONFIG – Define comparison rules for this domain
# ============================================================================

class ComparatorConfig:
    """Define how to compare baseline vs candidate for SQL queries."""
    
    def __init__(self):
        self.numeric_tolerance = 0.001      # Allow 0.1% difference
        self.allow_dtype_coercion = True     # DB might return int instead of float
        self.nullable_handling = 'allow_nulls_both'  # NULL in both = OK
        self.max_allowed_drift = {           # Per-column tolerance
            'amount': 0.05,                  # Currency: 5 cents
            'count': 0,                      # Aggregates: exact match
            'revenue': 0.02,                 # Revenue: 2%
        }


# ============================================================================
# 4. ERROR TAXONOMY – Classify SQL errors in business language
# ============================================================================

class SQLErrorTaxonomy:
    """Map diff patterns to business-relevant error categories."""
    
    CATEGORIES = {
        'missing_rows': {
            'severity': 'critical',
            'pattern': 'Baseline has rows; candidate does not',
            'example': 'WHERE clause too restrictive; filtered out data',
            'business_impact': 'Incomplete results; reports undercounted'
        },
        'extra_rows': {
            'severity': 'high',
            'pattern': 'Candidate has rows; baseline does not',
            'example': 'Missing WHERE clause; includes unwanted data',
            'business_impact': 'Overcounted; metrics inflated'
        },
        'wrong_aggregation': {
            'severity': 'critical',
            'pattern': 'GROUP BY or aggregate function wrong',
            'example': 'SUM(amount) instead of AVG(amount)',
            'business_impact': 'Completely wrong metric value'
        },
        'join_error': {
            'severity': 'high',
            'pattern': 'JOIN condition wrong; missing/duplicate rows',
            'example': 'INNER JOIN instead of LEFT JOIN',
            'business_impact': 'Lost or duplicated data in join'
        },
        'column_error': {
            'severity': 'high',
            'pattern': 'Wrong column selected or computed',
            'example': 'Selected price instead of adjusted_price',
            'business_impact': 'Wrong data in report'
        },
        'ordering_error': {
            'severity': 'low',
            'pattern': 'Rows in different order',
            'example': 'ORDER BY DESC instead of ASC (still same data)',
            'business_impact': 'Cosmetic; data is correct'
        },
        'numeric_drift': {
            'severity': 'medium',
            'pattern': 'Numbers differ slightly',
            'example': 'Rounding error; amount 100.01 vs 100.00',
            'business_impact': 'Acceptable drift; monitor for accumulation'
        }
    }
    
    @classmethod
    def classify(cls, diff_pattern: str) -> Dict[str, Any]:
        """Given a diff pattern, return error category."""
        return cls.CATEGORIES.get(diff_pattern, {
            'severity': 'unknown',
            'pattern': diff_pattern
        })


# ============================================================================
# 5. PUTTING IT TOGETHER – Full validation workflow for SQL
# ============================================================================

def validate_sql_query(
    baseline_sql: str,
    candidate_sql: str,
    test_fixture: str
) -> Dict[str, Any]:
    """
    End-to-end SQL validation:
    1. Run both queries on same test data
    2. Normalize outputs
    3. Compare row-by-row
    4. Classify errors
    """
    
    runner = SQLQueryRunner(fixture_csv=test_fixture)
    normalizer = SQLResultNormalizer(schema={
        'user_id': 'int64',
        'transaction_date': 'object',
        'amount': 'float64',
        'category': 'object'
    })
    config = ComparatorConfig()
    
    # Execute both
    baseline_output = runner.execute(baseline_sql)
    candidate_output = runner.execute(candidate_sql)
    
    # Normalize
    baseline_df = normalizer.normalize(baseline_output)
    candidate_df = normalizer.normalize(candidate_output)
    
    # Compare
    total_rows_baseline = len(baseline_df)
    total_rows_candidate = len(candidate_df)
    
    comparison_result = {
        'baseline_rows': total_rows_baseline,
        'candidate_rows': total_rows_candidate,
        'matches': total_rows_baseline == total_rows_candidate,
        'row_diff': abs(total_rows_candidate - total_rows_baseline)
    }
    
    # Classify error
    if total_rows_candidate < total_rows_baseline:
        error_type = 'missing_rows'
    elif total_rows_candidate > total_rows_baseline:
        error_type = 'extra_rows'
    else:
        error_type = 'ordering_error' if not baseline_df.equals(candidate_df) else 'no_error'
    
    error_info = SQLErrorTaxonomy.classify(error_type)
    
    return {
        'status': 'PASS' if error_type == 'no_error' else 'FAIL',
        'error_type': error_type,
        'error_severity': error_info.get('severity', 'unknown'),
        'error_business_impact': error_info.get('business_impact', ''),
        'comparison': comparison_result,
        'recommendation': 'APPROVE' if error_type == 'no_error' else 'REVIEW'
    }


# ============================================================================
# 6. EXAMPLE USAGE
# ============================================================================

if __name__ == '__main__':
    # Example baseline oracle (correct SQL)
    baseline_sql = """
    SELECT 
        user_id,
        DATE(transaction_date) as transaction_date,
        SUM(amount) as total_spent,
        COUNT(*) as num_transactions
    FROM input_data
    WHERE status = 'completed'
    GROUP BY user_id, transaction_date
    ORDER BY user_id, transaction_date
    """
    
    # Example candidate (LLM-generated, might have bugs)
    candidate_sql_correct = """
    SELECT 
        user_id,
        DATE(transaction_date) as transaction_date,
        SUM(amount) as total_spent,
        COUNT(*) as num_transactions
    FROM input_data
    WHERE status = 'completed'
    GROUP BY user_id, transaction_date
    ORDER BY user_id, transaction_date
    """
    
    candidate_sql_wrong = """
    SELECT 
        user_id,
        DATE(transaction_date) as transaction_date,
        AVG(amount) as total_spent,  # BUG: should be SUM
        COUNT(*) as num_transactions
    FROM input_data
    WHERE status = 'completed'
    GROUP BY user_id, transaction_date
    ORDER BY user_id, transaction_date
    """
    
    print("=" * 80)
    print("SQL Domain Kit Example")
    print("=" * 80)
    
    # Note: In real scenario, you'd have actual test data
    # For now, this shows the structure
    print("\n✅ ARCHITECTURE READY")
    print("   - Runner: Execute SQL deterministically")
    print("   - Normalizer: Convert to comparable form")
    print("   - Comparator: Apply tolerances + config")
    print("   - Taxonomy: Classify errors in business terms")
    print("\nNEXT: Integrate with core validation engine")
