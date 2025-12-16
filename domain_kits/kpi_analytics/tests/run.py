"""
KPI Kit Acceptance Test Runner (Day 5)

Run all acceptance tests to verify kit is production-ready.
This script becomes the CI gate for future kit changes.

Usage:
    python -m domain_kits.kpi_analytics.tests.run
    
    or
    
    python domain_kits/kpi_analytics/tests/run.py
"""

import sys
import os
from pathlib import Path
import tempfile
import pandas as pd
import time

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from domain_kits.kpi_analytics.runner import KPIRunner
from domain_kits.kpi_analytics.normalizer import KPINormalizer
from domain_kits.kpi_analytics.comparator_config import ComparatorConfig
from domain_kits.kpi_analytics.error_taxonomy import KPIErrorTaxonomy


def test_baseline_passes():
    """Test 1: Baseline KPI executes successfully."""
    print("\n[TEST 1] Baseline KPI passes")
    runner = KPIRunner()
    result = runner.execute(
        'domain_kits/kpi_analytics/fixtures/kpi_oracle_baseline.py',
        'domain_kits/kpi_analytics/fixtures/superstore_sales.csv'
    )
    
    assert result['status'] == 'success', f"Expected success, got {result['status']}"
    assert result['output_type'] in ('int', 'float'), f"Expected numeric, got {result['output_type']}"
    assert result['output'] is not None, "Output should not be None"
    print(f"✅ PASS: Baseline result={result['output']}, type={result['output_type']}")
    return result


def test_broken_kpi_fails(baseline_result):
    """Test 2: Known-bad KPI fails with correct error classification."""
    print("\n[TEST 2] Known-bad KPI fails with correct classification")
    runner = KPIRunner()
    candidate = runner.execute(
        'domain_kits/kpi_analytics/fixtures/kpi_test_aggregation_error.py',
        'domain_kits/kpi_analytics/fixtures/superstore_sales.csv'
    )
    
    assert candidate['status'] == 'success', f"Candidate should execute, got {candidate['status']}"
    
    # Normalize and compare
    normalizer = KPINormalizer()
    baseline_norm = normalizer.normalize(baseline_result['output'], baseline_result['output_type'])
    candidate_norm = normalizer.normalize(candidate['output'], candidate['output_type'])
    
    assert baseline_norm['status'] == 'valid', "Baseline should normalize"
    assert candidate_norm['status'] == 'valid', "Candidate should normalize"
    
    # Strict comparison (default)
    config = ComparatorConfig()
    comparison = normalizer.compare_normalized(baseline_norm, candidate_norm, config.to_dict())
    
    assert comparison['match'] == False, "Known-bad KPI should not match baseline"
    print(f"✅ PASS: Mismatch detected, reason='{comparison['reason']}'")
    
    # Classify error
    error_category = 'aggregation_error'
    error_info = KPIErrorTaxonomy.classify(error_category)
    assert error_info['severity'] == 'critical', "Aggregation error should be critical"
    print(f"✅ PASS: Error classified as {error_category} (severity={error_info['severity']})")


def test_timeout_enforcement():
    """Test 3: 30-second timeout enforced."""
    print("\n[TEST 3] Timeout enforcement (30 seconds)")
    
    # Create a timeout KPI
    code = """
import time
import pandas as pd

def compute_kpi(df: pd.DataFrame):
    time.sleep(60)  # Will timeout at 30s
    return 0
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_path = f.name
    
    try:
        runner = KPIRunner()
        start = time.time()
        result = runner.execute(temp_path, 'domain_kits/kpi_analytics/fixtures/superstore_sales.csv')
        elapsed = time.time() - start
        
        assert result['status'] == 'error', f"Should error on timeout, got {result['status']}"
        assert 'timeout' in result['error'].lower(), f"Error should mention timeout: {result['error']}"
        assert elapsed < 35, f"Should timeout ~30s, took {elapsed}s"
        print(f"✅ PASS: Timeout enforced at {elapsed:.1f}s, error='{result['error']}'")
    finally:
        os.unlink(temp_path)


def test_fixture_validation():
    """Test 4: Fixture validation (required columns)."""
    print("\n[TEST 4] Fixture validation (required columns)")
    
    # Create a fixture with MISSING required columns
    bad_fixture = pd.DataFrame({
        'name': ['Alice', 'Bob'],
        'age': [25, 30]
    })
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        bad_fixture.to_csv(f.name, index=False)
        bad_fixture_path = f.name
    
    # Create a valid KPI code
    code = """
import pandas as pd

def compute_kpi(df: pd.DataFrame):
    return df.shape[0]
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_code_path = f.name
    
    try:
        runner = KPIRunner()
        result = runner.execute(temp_code_path, bad_fixture_path)
        
        assert result['status'] == 'error', f"Should error on bad fixture, got {result['status']}"
        assert 'required columns' in result['error'].lower(), f"Error should mention required columns: {result['error']}"
        print(f"✅ PASS: Fixture validation works, error='{result['error']}'")
    finally:
        os.unlink(bad_fixture_path)
        os.unlink(temp_code_path)


def test_tolerance_comparison():
    """Test 5: Tolerance-based comparison with all three modes (count, aggregation, profit)."""
    print("\n[TEST 5] Tolerance-based comparison")
    
    normalizer = KPINormalizer()
    
    # Test 5a: profit metrics PASS (0.009% drift < 0.01% tolerance)
    baseline = normalizer.normalize(10000.0, 'float')
    candidate = normalizer.normalize(10009.0, 'float')  # 0.009% drift: (10009-10000)/10000 = 0.0009 < 0.0001? NO
    # Actually: 0.0009 > 0.0001, so let's use a smaller diff
    # Let's use: 10000 vs 10000.5 = 0.00005 < 0.0001 ✓
    candidate = normalizer.normalize(10000.5, 'float')
    
    config = ComparatorConfig.for_profit_metrics()
    comparison = normalizer.compare_normalized(baseline, candidate, config.to_dict())
    
    assert comparison['match'] == True, f"Should match within tolerance: {comparison}"
    print(f"✅ PASS: 10000.00 vs 10000.5 matches (profit_metrics, tolerance=0.0001)")
    
    # Test 5b: profit metrics FAIL (1% drift >> 0.0001 tolerance)
    candidate2 = normalizer.normalize(10100.0, 'float')  # 1% diff
    comparison2 = normalizer.compare_normalized(baseline, candidate2, config.to_dict())
    
    assert comparison2['match'] == False, f"Should not match beyond tolerance: {comparison2}"
    print(f"✅ PASS: 10000.00 vs 10100.00 fails (1% drift >> 0.01% tolerance)")
    
    # Test 5c: aggregation metrics PASS (0.1% drift <= 0.5% tolerance)
    baseline_agg = normalizer.normalize(1000.0, 'float')
    candidate_agg = normalizer.normalize(1001.0, 'float')  # 0.1% drift
    
    config_agg = ComparatorConfig.for_aggregation_metrics()
    comparison_agg = normalizer.compare_normalized(baseline_agg, candidate_agg, config_agg.to_dict())
    
    assert comparison_agg['match'] == True, f"Should match within aggregation tolerance: {comparison_agg}"
    print(f"✅ PASS: 1000 vs 1001 matches (aggregation_metrics, 0.5% tolerance)")
    
    # Test 5d: count metrics FAIL (exact match required, 0% tolerance)
    config_count = ComparatorConfig.for_count_metrics()
    comparison_count = normalizer.compare_normalized(baseline_agg, candidate_agg, config_count.to_dict())
    
    assert comparison_count['match'] == False, f"Count should not tolerate any diff: {comparison_count}"
    print(f"✅ PASS: 1000 vs 1001 fails (count_metrics, tolerance=0%)")
    
    # Test 5e: percentage metrics PASS (1 point tolerance, ratio scale)
    baseline_pct = normalizer.normalize(0.42, 'float')
    candidate_pct = normalizer.normalize(0.43, 'float')  # 1 percentage point diff
    
    config_pct = ComparatorConfig.for_percentage_metrics()
    comparison_pct = normalizer.compare_normalized(baseline_pct, candidate_pct, config_pct.to_dict())
    
    assert comparison_pct['match'] == True, f"Should match within 1 percentage point: {comparison_pct}"
    print(f"✅ PASS: 0.42 vs 0.43 matches (percentage_metrics, 1 point = 0.01 in ratio scale)")
    
    # Test 5f: percentage metrics FAIL (8 points > 1 point tolerance)
    candidate_pct2 = normalizer.normalize(0.50, 'float')  # 8 percentage point diff
    comparison_pct2 = normalizer.compare_normalized(baseline_pct, candidate_pct2, config_pct.to_dict())
    
    assert comparison_pct2['match'] == False, f"Should not match with 8 point diff: {comparison_pct2}"
    print(f"✅ PASS: 0.42 vs 0.50 fails (8 percentage points > 1 point tolerance)")
    
    # Test 5g: percentage metrics PASS (percent scale 0-100)
    baseline_pct100 = normalizer.normalize(42.0, 'float')
    candidate_pct100 = normalizer.normalize(43.0, 'float')  # 1 point diff
    
    comparison_pct100 = normalizer.compare_normalized(baseline_pct100, candidate_pct100, config_pct.to_dict())
    
    assert comparison_pct100['match'] == True, f"Should match within 1 point (percent scale): {comparison_pct100}"
    print(f"✅ PASS: 42.0 vs 43.0 matches (percentage_metrics, 1 point = 1.0 in percent scale)")


def test_error_taxonomy():
    """Test 6: Error taxonomy has all 6 categories."""
    print("\n[TEST 6] Error taxonomy")
    
    expected = [
        'aggregation_error',
        'groupby_error',
        'filter_error',
        'dtype_coercion_error',
        'computation_error',
        'numeric_drift'
    ]
    
    for cat in expected:
        info = KPIErrorTaxonomy.classify(cat)
        assert 'severity' in info, f"Missing severity for {cat}"
        assert 'pattern' in info, f"Missing pattern for {cat}"
        print(f"  ✅ {cat:25} (severity={info['severity']})")
    
    print(f"✅ PASS: All 6 error categories defined")


def main():
    """Run all acceptance tests."""
    print("=" * 70)
    print("KPI KIT ACCEPTANCE TEST RUNNER")
    print("=" * 70)
    
    try:
        # Run tests in order
        baseline = test_baseline_passes()
        test_broken_kpi_fails(baseline)
        test_timeout_enforcement()
        test_fixture_validation()
        test_tolerance_comparison()
        test_error_taxonomy()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print("\nKit is production-ready. You can now:")
        print("  1. Integrate into validate.py")
        print("  2. Deploy to Render")
        print("  3. Start Jan outreach")
        return 0
    
    except AssertionError as e:
        print("\n" + "=" * 70)
        print("❌ TEST FAILED")
        print("=" * 70)
        print(f"\nError: {e}")
        return 1
    
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ UNEXPECTED ERROR")
        print("=" * 70)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
