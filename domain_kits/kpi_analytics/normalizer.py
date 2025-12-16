"""
KPI Analytics Normalizer

Convert diverse KPI outputs to canonical form for tolerance-based comparison.

Supports:
- Scalar (int, float): Single number
- Dict: Key-value pairs (all numeric)
- DataFrame: Tabular data (numeric columns only)
- Series: 1D array

Comparison uses TOLERANCE, not exact equality.
See ComparatorConfig for tolerance rules.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any


class KPINormalizer:
    """Convert KPI output to normalized form ready for comparison."""
    
    def normalize(self, output: Any, output_type: str) -> Dict[str, Any]:
        """
        Convert KPI result to canonical comparison form.
        
        Args:
            output: Raw output from compute_kpi() (actual value)
            output_type: Type name as string (e.g., 'int', 'float', 'DataFrame')
        
        Returns:
            Normalized dict with keys:
            - type: 'scalar' | 'dict' | 'DataFrame' | 'Series'
            - value: Serializable representation
            - shape: {'rows': int, 'columns': int}
            - metadata: Extra info (keys, column names, etc.)
            - status: 'valid' | 'invalid'
            - error: (if status='invalid') Error message
        """
        
        try:
            # SCALAR: int, float
            if output_type in ('int', 'float', 'numpy.int64', 'numpy.float64'):
                return {
                    'type': 'scalar',
                    'value': float(output),
                    'shape': {'rows': 1, 'columns': 1},
                    'metadata': {'unit': 'numeric'},
                    'status': 'valid'
                }
            
            # DICT: key-value pairs (all values must be numeric)
            elif output_type == 'dict':
                numeric_values = {}
                for k, v in output.items():
                    if isinstance(v, (int, float, np.number)):
                        numeric_values[k] = float(v)
                    else:
                        return {
                            'type': 'dict',
                            'status': 'invalid',
                            'error': f'Non-numeric value for key "{k}": {type(v).__name__}'
                        }
                
                return {
                    'type': 'dict',
                    'value': numeric_values,
                    'shape': {'rows': 1, 'columns': len(numeric_values)},
                    'metadata': {'keys': list(numeric_values.keys())},
                    'status': 'valid'
                }
            
            # DATAFRAME: tabular data
            elif output_type == 'DataFrame':
                if len(output) == 0:
                    return {
                        'type': 'DataFrame',
                        'status': 'invalid',
                        'error': 'Empty DataFrame'
                    }
                
                # Extract numeric columns only
                numeric_cols = output.select_dtypes(include=[np.number]).columns.tolist()
                if not numeric_cols:
                    return {
                        'type': 'DataFrame',
                        'status': 'invalid',
                        'error': 'No numeric columns found'
                    }
                
                # Convert to dict of lists (serializable)
                normalized = {}
                for col in numeric_cols:
                    normalized[col] = output[col].astype(float).tolist()
                
                return {
                    'type': 'DataFrame',
                    'value': normalized,
                    'shape': {'rows': len(output), 'columns': len(numeric_cols)},
                    'metadata': {
                        'numeric_columns': numeric_cols,
                        'original_columns': list(output.columns)
                    },
                    'status': 'valid'
                }
            
            # SERIES: 1D array
            elif output_type == 'Series':
                numeric_values = output.astype(float).tolist()
                return {
                    'type': 'Series',
                    'value': numeric_values,
                    'shape': {'rows': len(output), 'columns': 1},
                    'metadata': {'name': str(output.name), 'index': output.index.tolist()},
                    'status': 'valid'
                }
            
            # UNKNOWN TYPE
            else:
                return {
                    'type': 'unknown',
                    'status': 'invalid',
                    'error': f'Unsupported output type: {output_type}'
                }
        
        except Exception as e:
            return {
                'type': output_type,
                'status': 'invalid',
                'error': f'Normalization failed: {str(e)}'
            }
    
    def compare_normalized(self, baseline: Dict, candidate: Dict, tolerances: Dict) -> Dict[str, Any]:
        """
        Compare normalized baseline vs candidate with TOLERANCE (not strict equality).
        
        Args:
            baseline: Normalized baseline output (from normalize())
            candidate: Normalized candidate output (from normalize())
            tolerances: Dict with comparison rules
                - numeric_tolerance: Max allowed relative drift (default 0.01 = 1%)
                - Example: {numeric_tolerance: 0.01}
        
        Returns:
            {
                'match': True | False,
                'reason': str,
                'drift_pct': float (if numeric),
                'details': {...}
            }
        """
        
        numeric_tol = tolerances.get('numeric_tolerance', 0.01)
        
        # Step 1: Both must have valid status
        if baseline.get('status') != 'valid' or candidate.get('status') != 'valid':
            return {
                'match': False,
                'reason': 'One or both outputs have invalid status'
            }
        
        # Step 2: Types must match
        if baseline.get('type') != candidate.get('type'):
            return {
                'match': False,
                'reason': f"Type mismatch: baseline={baseline.get('type')}, candidate={candidate.get('type')}"
            }
        
        output_type = baseline.get('type')
        tolerance_mode = tolerances.get('tolerance_mode', 'relative')
        
        # SCALAR COMPARISON
        if output_type == 'scalar':
            baseline_val = baseline['value']
            candidate_val = candidate['value']
            
            if tolerance_mode == 'absolute':
                # Absolute difference (for percentage metrics)
                # Check if percentage_scale is explicitly provided
                scale = tolerances.get('percentage_scale')
                max_val = max(abs(baseline_val), abs(candidate_val))
                
                if scale == "ratio_0_1":
                    # Explicitly ratio scale (0-1): 1 percentage point = 0.01
                    effective_tol = numeric_tol / 100.0
                elif scale == "percent_0_100":
                    # Explicitly percent scale (0-100): 1 percentage point = 1.0
                    effective_tol = numeric_tol
                else:
                    # Auto-detect scale: if values are 0-1.5 range, assume ratio (0-1)
                    # Otherwise assume percent (0-100)
                    if max_val <= 1.5:
                        # Ratio scale (0-1): tolerance is in percentage points, so divide by 100
                        # e.g., 1 percentage point = 0.01 in ratio scale
                        effective_tol = numeric_tol / 100.0
                    else:
                        # Percent scale (0-100): tolerance is in percentage points directly
                        effective_tol = numeric_tol
                
                diff_abs = abs(candidate_val - baseline_val)
                drift_pct = diff_abs  # In absolute mode, drift_pct is the absolute difference
                
                # Use small epsilon for floating-point comparison
                if diff_abs < effective_tol or abs(diff_abs - effective_tol) < 1e-9:
                    return {
                        'match': True,
                        'reason': f'Scalar within absolute tolerance (diff={diff_abs:.6f}, tol={effective_tol:.6f})',
                        'drift_pct': drift_pct * 100 if max_val <= 1.5 else drift_pct,
                        'drift_abs': diff_abs
                    }
                else:
                    return {
                        'match': False,
                        'reason': f'Scalar absolute drift {diff_abs:.6f} exceeds tolerance {effective_tol:.6f}',
                        'drift_pct': drift_pct * 100 if max_val <= 1.5 else drift_pct,
                        'drift_abs': diff_abs,
                        'baseline_value': baseline_val,
                        'candidate_value': candidate_val
                    }
            else:
                # Relative difference (original behavior)
                if baseline_val == 0:
                    diff = abs(candidate_val)
                else:
                    diff = abs(candidate_val - baseline_val) / abs(baseline_val)
                
                if diff <= numeric_tol:
                    return {
                        'match': True,
                        'reason': f'Scalar within tolerance (diff={diff:.6f}, tol={numeric_tol})',
                        'drift_pct': diff * 100
                    }
                else:
                    return {
                        'match': False,
                        'reason': f'Scalar drift {diff:.6f} exceeds tolerance {numeric_tol}',
                        'drift_pct': diff * 100,
                        'baseline_value': baseline_val,
                        'candidate_value': candidate_val
                    }
        
        # DICT COMPARISON
        elif output_type == 'dict':
            baseline_val = baseline['value']
            candidate_val = candidate['value']
            
            # Keys must match exactly
            if set(baseline_val.keys()) != set(candidate_val.keys()):
                return {
                    'match': False,
                    'reason': f'Key mismatch: baseline={set(baseline_val.keys())}, candidate={set(candidate_val.keys())}'
                }
            
            # Check numeric tolerance on each key
            max_drift = 0
            failed_keys = []
            scale = tolerances.get('percentage_scale')
            
            for key in baseline_val.keys():
                base = baseline_val[key]
                cand = candidate_val[key]
                max_val = max(abs(base), abs(cand))
                
                if tolerance_mode == 'absolute':
                    # Absolute mode for dicts (percentage metrics)
                    if scale == "ratio_0_1":
                        effective_tol = numeric_tol / 100.0
                    elif scale == "percent_0_100":
                        effective_tol = numeric_tol
                    else:
                        # Auto-detect
                        if max_val <= 1.5:
                            effective_tol = numeric_tol / 100.0
                        else:
                            effective_tol = numeric_tol
                    drift = abs(cand - base)
                else:
                    # Relative mode (original)
                    if base == 0:
                        drift = abs(cand)
                    else:
                        drift = abs(cand - base) / abs(base)
                    effective_tol = numeric_tol
                
                max_drift = max(max_drift, drift)
                
                if drift > effective_tol:
                    failed_keys.append((key, drift))
            
            if failed_keys:
                return {
                    'match': False,
                    'reason': f'Dict keys exceed tolerance: {failed_keys}',
                    'max_drift_pct': max_drift * 100 if tolerance_mode == 'relative' else max_drift
                }
            
            return {
                'match': True,
                'reason': f'Dict within tolerance (max_drift={max_drift:.6f})',
                'max_drift_pct': max_drift * 100 if tolerance_mode == 'relative' else max_drift
            }
        
        # DATAFRAME COMPARISON
        elif output_type == 'DataFrame':
            baseline_val = baseline['value']
            candidate_val = candidate['value']
            
            # Shape must match
            if baseline['shape'] != candidate['shape']:
                return {
                    'match': False,
                    'reason': f"Shape mismatch: baseline={baseline['shape']}, candidate={candidate['shape']}"
                }
            
            # Check numeric tolerance per column, per row
            max_drift = 0
            failed_cells = []
            for col in baseline_val.keys():
                base_col = np.array(baseline_val[col])
                cand_col = np.array(candidate_val[col])
                
                for i, (base, cand) in enumerate(zip(base_col, cand_col)):
                    if base == 0:
                        drift = abs(cand)
                    else:
                        drift = abs(cand - base) / abs(base)
                    
                    max_drift = max(max_drift, drift)
                    
                    if drift > numeric_tol:
                        failed_cells.append((col, i, drift))
            
            if failed_cells:
                return {
                    'match': False,
                    'reason': f'DataFrame cells exceed tolerance: {failed_cells[:3]}...',  # Show first 3
                    'max_drift_pct': max_drift * 100,
                    'failed_count': len(failed_cells)
                }
            
            return {
                'match': True,
                'reason': f'DataFrame within tolerance (max_drift={max_drift:.6f})',
                'max_drift_pct': max_drift * 100
            }
        
        # SERIES COMPARISON
        elif output_type == 'Series':
            baseline_val = np.array(baseline['value'])
            candidate_val = np.array(candidate['value'])
            
            if len(baseline_val) != len(candidate_val):
                return {
                    'match': False,
                    'reason': f'Length mismatch: baseline={len(baseline_val)}, candidate={len(candidate_val)}'
                }
            
            max_drift = 0
            failed_indices = []
            for i, (base, cand) in enumerate(zip(baseline_val, candidate_val)):
                if base == 0:
                    drift = abs(cand)
                else:
                    drift = abs(cand - base) / abs(base)
                
                max_drift = max(max_drift, drift)
                
                if drift > numeric_tol:
                    failed_indices.append((i, drift))
            
            if failed_indices:
                return {
                    'match': False,
                    'reason': f'Series indices exceed tolerance: {failed_indices[:3]}...',
                    'max_drift_pct': max_drift * 100,
                    'failed_count': len(failed_indices)
                }
            
            return {
                'match': True,
                'reason': f'Series within tolerance (max_drift={max_drift:.6f})',
                'max_drift_pct': max_drift * 100
            }
        
        # No comparison rule
        return {
            'match': False,
            'reason': f'No comparison rule for type: {output_type}'
        }
